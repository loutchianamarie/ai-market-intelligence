"""Extended, pre-registered evaluation of the category-purchase model (protocol: data/eval/model_eval_protocol_v1.json).

Chronological only: train on cutoffs 13-37, select on 41, calibrate (isotonic) on 45, report on 49 as REPEATED
evaluation (49 was inspected in earlier passes). A rolling-origin check refits every candidate on all cutoffs whose
labels end before each target window. Subgroup uncertainty uses a household-cluster bootstrap and is reported
only for slices with >= 100 positives. The adoption rule is applied mechanically; if no candidate passes, the
production model is kept and the negative result is reported. Purchase probability is NOT coupon uplift.

Usage: python -m mi.model.evaluate   -> reports/model_evaluation.json, reports/model_evaluation.md
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from mi.config import load_config
from mi.ingest.load import load
from mi.model.features import FEATURES_V1, LONG_HISTORY, build_panel, prepare
from mi.model.train import SEED, bootstrap_by_household, design, make_models, rule_popularity, rule_repeat
from mi.paths import REPORTS, ROOT

PROTOCOL = ROOT / "data" / "eval" / "model_eval_protocol_v1.json"
LONG = LONG_HISTORY
FEATURES = FEATURES_V1          # protocol v1 compares against the ORIGINAL feature set
NO_RECENT = {"LOW_ACTIVITY", "ACTIVE_NONBUYER"}
MIN_POS_FOR_CI = 100


def add_long_history(panel: pd.DataFrame, hcw: pd.DataFrame, lookback: int = 12) -> pd.DataFrame:
    """Longer-history features from weeks <= cutoff - lookback only (no information after the cutoff)."""
    parts = []
    for c in sorted(panel.cutoff.unique()):
        lo_lb = c - lookback + 1                     # first week of the 12-week lookback
        prior = hcw[(hcw.week < lo_lb) & (hcw.week >= lo_lb - 14)]
        before = hcw[hcw.week < lo_lb]
        a = prior.groupby(["household_id", "product_category"]).week.nunique().rename("cat_weeks_active_prior14")
        b = before.groupby(["household_id", "product_category"]).size().gt(0).astype(float).rename("cat_bought_before_lookback")
        f = pd.concat([a, b], axis=1).reset_index()
        f["cutoff"] = c
        parts.append(f)
    feats = pd.concat(parts, ignore_index=True)
    out = panel.merge(feats, on=["cutoff", "household_id", "product_category"], how="left")
    out[["cat_weeks_active_prior14", "cat_bought_before_lookback"]] = out[["cat_weeks_active_prior14", "cat_bought_before_lookback"]].fillna(0.0)
    out["history_weeks_available"] = (out.cutoff - lookback).clip(lower=0).astype(float)
    return out


def ece(y, p, bins=10) -> float:
    q = pd.qcut(pd.Series(p).rank(method="first"), bins, labels=False)
    d = pd.DataFrame({"y": y, "p": p, "b": q}).groupby("b").agg(o=("y", "mean"), m=("p", "mean"), n=("y", "size"))
    return float((d.n * (d.o - d.m).abs()).sum() / d.n.sum())


def prec_recall_top(y, s, frac) -> dict:
    n = max(1, int(round(len(s) * frac)))
    idx = np.argsort(-s, kind="stable")[:n]
    tp = float(np.asarray(y)[idx].sum())
    return {"contacts": n, "precision": tp / n, "recall": tp / max(1.0, float(np.sum(y)))}


def per_category_at_k(df, s, k=250) -> list[dict]:
    rows = []
    for c, g in df.assign(_s=s).groupby("product_category"):
        top = g.nlargest(k, "_s")
        rows.append({"category": c, "k": int(min(k, len(g))), "precision_at_k": float(top.y.mean()),
                     "recall_at_k": float(top.y.sum() / max(1, g.y.sum())), "prevalence": float(g.y.mean())})
    return rows


def _fit(name, X, y):
    if name in ("hgb_small", "hgb_small_longhist"):
        return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=15, min_samples_leaf=80,
                                              l2_regularization=1.0, random_state=SEED).fit(X, y)
    return make_models()[name].fit(X, y)


def _feats(name):
    return FEATURES + LONG if name == "hgb_small_longhist" else FEATURES


def run(write=True) -> dict:
    t0 = time.time()
    proto = json.loads(PROTOCOL.read_text())
    cfg = load_config()
    cats, T = cfg["categories"], cfg["temporal"]
    prep = prepare(load("transactions"), load("products"), cats)
    red, camp, cd = load("coupon_redemptions"), load("campaigns"), load("campaign_descriptions")
    cut = T["train_cutoffs"] + [T["validation_cutoff"], T["calibration_cutoff"], T["test_cutoff"]]
    panel = build_panel(prep, cut, cfg, red, camp, cd)   # includes LONG_HISTORY columns (same definition as add_long_history)
    by = {c: panel[panel.cutoff == c].reset_index(drop=True) for c in cut}
    tr = pd.concat([by[c] for c in T["train_cutoffs"]], ignore_index=True)
    va, ca, te = by[T["validation_cutoff"]], by[T["calibration_cutoff"]], by[T["test_cutoff"]]
    fitted = ["logreg_l2", "hgb_small", "hgb_small_longhist"]

    models = {n: _fit(n, design(tr, cats, _feats(n)), tr.y.to_numpy()) for n in fitted}
    score = lambda n, df: (models[n].predict_proba(design(df, cats, _feats(n)))[:, 1] if n in models  # noqa: E731
                           else (rule_repeat(df) if n == "rule_repeat" else rule_popularity(df)))
    names = ["rule_popularity", "rule_repeat"] + fitted

    # 1) selection window 41 (overall + no-recent-history subgroup)
    nr_va = va.segment.isin(NO_RECENT).to_numpy()
    sel = {n: {"AP": float(average_precision_score(va.y, score(n, va))),
               "AP_no_recent_history": float(average_precision_score(va.y[nr_va], score(n, va)[nr_va]))} for n in names}

    # 2) rolling origin: refit on all cutoffs whose label window ends before the target cutoff
    rolling = {}
    pool = T["train_cutoffs"] + [T["validation_cutoff"], T["calibration_cutoff"]]
    for tgt in (T["validation_cutoff"], T["calibration_cutoff"], T["test_cutoff"]):
        trc = [c for c in pool if c + T["horizon_weeks"] <= tgt]
        trd = pd.concat([by[c] for c in trc], ignore_index=True)
        d = by[tgt]
        row = {"train_cutoffs": trc, "prevalence": float(d.y.mean()), "n": int(len(d))}
        for n in names:
            if n in fitted:
                m = _fit(n, design(trd, cats, _feats(n)), trd.y.to_numpy())
                s = m.predict_proba(design(d, cats, _feats(n)))[:, 1]
            else:
                s = score(n, d)
            row[n] = float(average_precision_score(d.y, s))
        rolling[str(tgt)] = row

    # 3) mechanical adoption rule
    prod = "hgb_small"
    adopted, rule_log = prod, []
    for n in ("logreg_l2", "hgb_small_longhist"):
        g41 = sel[n]["AP"] - sel[prod]["AP"]
        g45 = rolling[str(T["calibration_cutoff"])][n] - rolling[str(T["calibration_cutoff"])][prod]
        nr = sel[n]["AP_no_recent_history"] - sel[prod]["AP_no_recent_history"]
        passed = g41 >= 0.005 and g45 >= 0.005 and nr >= 0
        rule_log.append({"candidate": n, "AP_gain_41": round(g41, 4), "AP_gain_rolling_45": round(g45, 4),
                         "AP_change_no_recent_41": round(nr, 4), "passes": passed})
        if passed and (adopted == prod or g41 > sel[adopted]["AP"] - sel[prod]["AP"]):
            adopted = n

    # 4) calibration on 45, evaluated on the later window 49; plus 41 -> 45/49 drift check
    def calib(n, fit_df, eval_df):
        iso = IsotonicRegression(out_of_bounds="clip").fit(score(n, fit_df), fit_df.y)
        p = iso.predict(score(n, eval_df))
        return p, {"Brier": float(brier_score_loss(eval_df.y, p)), "ECE": ece(eval_df.y.to_numpy(), p)}
    calib_tbl = {}
    for n in names:
        _, m49 = calib(n, ca, te)
        _, d45 = calib(n, va, ca)
        _, d49 = calib(n, va, te)
        calib_tbl[n] = {"fit45_eval49": m49, "fit41_eval45": d45, "fit41_eval49": d49}

    # 5) repeated evaluation on 49: overall, contact sizes, per category, subgroups with bootstrap CIs
    y49 = te.y.to_numpy()
    s_m, s_r = score(adopted, te), score("rule_repeat", te)
    p_m, _ = calib(adopted, ca, te)
    p_r, _ = calib("rule_repeat", ca, te)
    overall = {n: {"AP": float(average_precision_score(y49, score(n, te))), "ROC_AUC": float(roc_auc_score(y49, score(n, te))),
                   **{f"top{int(f * 100)}pct": prec_recall_top(y49, score(n, te), f) for f in (0.05, 0.10, 0.20)}} for n in names}
    slices = {"all": np.ones(len(te), bool)}
    for c in cats:
        slices[f"category={c}"] = (te.product_category == c).to_numpy()
    for sg in sorted(te.segment.unique()):
        slices[f"segment={sg}"] = (te.segment == sg).to_numpy()
    slices["no_recent_history"] = te.segment.isin(NO_RECENT).to_numpy()
    sub = []
    for name, m in slices.items():
        d = te[m].reset_index(drop=True)
        pos = int(d.y.sum())
        row = {"slice": name, "n": int(m.sum()), "positives": pos, "prevalence": float(d.y.mean()) if len(d) else None}
        if pos and pos < len(d):
            row.update({"AP_model": float(average_precision_score(d.y, s_m[m])), "AP_rule": float(average_precision_score(d.y, s_r[m])),
                        "Brier_model": float(np.mean((p_m[m] - d.y) ** 2)), "Brier_rule": float(np.mean((p_r[m] - d.y) ** 2))})
            if pos >= MIN_POS_FOR_CI:
                b = bootstrap_by_household(d, d.y.to_numpy(), s_m[m], p_m[m], s_r[m], p_r[m], n_boot=200)
                row["AP_diff_95ci"] = [round(x, 4) for x in b["AP_diff_95ci"]]
            else:
                row["AP_diff_95ci"] = "not reported (< 100 positives)"
        sub.append(row)
    windows = {str(c): {"month": {41: "Oct 2017", 45: "Nov 2017", 49: "Dec 2017"}[c], "prevalence": float(by[c].y.mean()),
                        "AP_model": float(average_precision_score(by[c].y, score(adopted, by[c]))),
                        "AP_rule": float(average_precision_score(by[c].y, score("rule_repeat", by[c])))}
               for c in (41, 45, 49)}
    res = {"protocol": str(PROTOCOL.relative_to(ROOT)), "protocol_status": proto["status"],
           "production_model": prod, "adopted_model": adopted, "adoption_rule": proto["adoption_rule"], "adoption_log": rule_log,
           "selection_window_41": sel, "rolling_origin_AP": rolling, "calibration": calib_tbl,
           "repeated_evaluation_49": {"note": proto["splits"]["note_49"], "overall": overall,
                                      "per_category_at_250": per_category_at_k(te, s_m, 250),
                                      "subgroups_model_vs_rule": sub},
           "by_window": windows, "seed": SEED, "seconds": round(time.time() - t0, 1),
           "intended_use": proto["intended_use"]}
    if write:
        (REPORTS / "model_evaluation.json").write_text(json.dumps(res, indent=2))
        (REPORTS / "model_evaluation.md").write_text(to_md(res), encoding="utf-8")
    return res


def to_md(r: dict) -> str:
    f = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)  # noqa: E731
    L = ["# Model evaluation (pre-registered protocol v1)", "",
         f"Protocol: `{r['protocol']}`. Production: `{r['production_model']}`. **Adopted after the rule: `{r['adopted_model']}`.**",
         "Window 49 (Dec 2017) was inspected in earlier passes, so its numbers are *repeated evaluation*, not an untouched test.",
         "Purchase probability under historical conditions is **not** coupon uplift.", "",
         "## Adoption rule", "", r["adoption_rule"], "", "| candidate | AP gain @41 | AP gain rolling @45 | no-recent-history AP change @41 | passes |",
         "|---|---:|---:|---:|---|"]
    L += [f"| {x['candidate']} | {x['AP_gain_41']:+.4f} | {x['AP_gain_rolling_45']:+.4f} | {x['AP_change_no_recent_41']:+.4f} | {x['passes']} |" for x in r["adoption_log"]]
    L += ["", "## Rolling-origin AP (refit on all earlier label windows)", "", "| target | prevalence | " + " | ".join(k for k in r["rolling_origin_AP"]["41"] if k not in ("train_cutoffs", "prevalence", "n")) + " |",
          "|---|---:|" + "---:|" * (len(r["rolling_origin_AP"]["41"]) - 3)]
    for t, row in r["rolling_origin_AP"].items():
        L.append(f"| {t} | {row['prevalence']:.3f} | " + " | ".join(f(v) for k, v in row.items() if k not in ("train_cutoffs", "prevalence", "n")) + " |")
    L += ["", "## Calibration (isotonic fit on 45, evaluated on 49; drift: fit on 41)", "", "| scorer | Brier 45→49 | ECE 45→49 | ECE 41→45 | ECE 41→49 |", "|---|---:|---:|---:|---:|"]
    for n, c in r["calibration"].items():
        L.append(f"| {n} | {c['fit45_eval49']['Brier']:.4f} | {c['fit45_eval49']['ECE']:.4f} | {c['fit41_eval45']['ECE']:.4f} | {c['fit41_eval49']['ECE']:.4f} |")
    ov = r["repeated_evaluation_49"]["overall"]
    L += ["", "## Contact-size precision / recall on 49 (18,480 household-category rows)", "", "| scorer | AP | top 5% P / R | top 10% P / R | top 20% P / R |", "|---|---:|---:|---:|---:|"]
    for n, o in ov.items():
        L.append(f"| {n} | {o['AP']:.3f} | " + " | ".join(f"{o[k]['precision']:.3f} / {o[k]['recall']:.3f}" for k in ("top5pct", "top10pct", "top20pct")) + " |")
    L += ["", "## Subgroups on 49 (adopted model vs repeat rule; CI only with >= 100 positives)", "", "| slice | n | positives | prevalence | AP model | AP rule | AP diff 95% CI | Brier model | Brier rule |", "|---|---:|---:|---:|---:|---:|---|---:|---:|"]
    for s in r["repeated_evaluation_49"]["subgroups_model_vs_rule"]:
        L.append(f"| {s['slice']} | {s['n']} | {s['positives']} | {f(s['prevalence'])} | {f(s.get('AP_model', '-'))} | {f(s.get('AP_rule', '-'))} | {s.get('AP_diff_95ci', '-')} | {f(s.get('Brier_model', '-'))} | {f(s.get('Brier_rule', '-'))} |")
    L += ["", "## By window (month)", "", "| cutoff | month | prevalence | AP model | AP rule |", "|---|---|---:|---:|---:|"]
    L += [f"| {k} | {w['month']} | {w['prevalence']:.3f} | {w['AP_model']:.3f} | {w['AP_rule']:.3f} |" for k, w in r["by_window"].items()]
    L += ["", "Window 41 also chose the production model; 45 calibrated it. AP on 41/45 is therefore not independent of model choice."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    r = run()
    print(f"adopted: {r['adopted_model']} (production {r['production_model']}); {r['seconds']}s")
    for x in r["adoption_log"]:
        print(" ", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
