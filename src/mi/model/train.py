"""One-command pipeline: audit-checked data -> features/labels -> rule baselines -> fitted models ->
validation selection -> calibration on a disjoint window -> ONE locked out-of-time test -> model card,
artifacts and the scoring table used by the Customer/Product Intelligence agent.

Usage: python -m mi.model.train            (deterministic; seed fixed)
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from mi.config import config_hash, load_config
from mi.ingest.load import load, manifest
from mi.model.features import CAMPAIGN_FEATURES, FEATURES, POPULARITY_FEATURES, build_panel, prepare
from mi.paths import PROCESSED, REPORTS

SEED = 20261114


def design(df: pd.DataFrame, cats: list[str], feats: list[str]) -> np.ndarray:
    X = df[feats].to_numpy(dtype=float)
    onehot = np.stack([(df.product_category == c).to_numpy(dtype=float) for c in cats], axis=1)
    return np.hstack([X, onehot])


def rule_popularity(df):  # A: category-wide prior-4-week penetration (same for every household)
    return df.cat_pop_4w.to_numpy(dtype=float)


def rule_repeat(df):  # B: weeks with a category purchase in last 12 weeks, ties broken by recency
    return (df.cat_weeks_active_12w + (1 - df.cat_weeks_since_last / 12) * 0.5).to_numpy(dtype=float)


def make_models():
    log1p = FunctionTransformer(lambda X: np.sign(X) * np.log1p(np.abs(X)))
    return {
        "logreg_l2": make_pipeline(log1p, StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)),
        "hgb_small": HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=15,
                                                    min_samples_leaf=80, l2_regularization=1.0, random_state=SEED),
        "hgb_deeper": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                                     min_samples_leaf=40, l2_regularization=1.0, random_state=SEED),
    }


def recall_at_k(df: pd.DataFrame, score: np.ndarray, k: int = 3) -> float:
    d = df[["household_id", "y"]].copy()
    d["s"] = score
    d["rank"] = d.groupby("household_id").s.rank(ascending=False, method="first")
    g = d.groupby("household_id").agg(pos=("y", "sum"), hit=("y", lambda s: 0))
    hits = d[d["rank"] <= k].groupby("household_id").y.sum()
    g["hit"] = hits.reindex(g.index).fillna(0)
    g = g[g.pos > 0]
    return float((g.hit / g.pos).mean())


def precision_top(y, s, frac=0.10):
    n = max(1, int(len(s) * frac))
    idx = np.argsort(-s, kind="stable")[:n]
    return float(np.mean(np.asarray(y)[idx]))


def metrics(df, y, s, prob=None) -> dict:
    out = {"n": int(len(y)), "prevalence": float(np.mean(y)), "AP": float(average_precision_score(y, s)),
           "ROC_AUC": float(roc_auc_score(y, s)), "precision_top10pct": precision_top(y, s),
           "recall_at_3": recall_at_k(df, s, 3)}
    if prob is not None:
        p = np.clip(prob, 1e-6, 1 - 1e-6)
        out["Brier"] = float(brier_score_loss(y, p))
        out["log_loss"] = float(log_loss(y, p))
    return out


def calibration_table(y, p, bins=10) -> list[dict]:
    q = pd.qcut(pd.Series(p).rank(method="first"), bins, labels=False)
    t = pd.DataFrame({"y": y, "p": p, "bin": q}).groupby("bin").agg(mean_pred=("p", "mean"), observed=("y", "mean"), n=("y", "size"))
    return [{k: (float(v) if k != "n" else int(v)) for k, v in r.items()} for r in t.reset_index(drop=True).to_dict("records")]


def bootstrap_by_household(df, y, s_a, p_a, s_b, p_b, n_boot=200, seed=SEED) -> dict:
    """Cluster bootstrap over households: CI for AP and Brier differences (A minus B)."""
    rng = np.random.default_rng(seed)
    hh = df.household_id.to_numpy()
    uniq, inv = np.unique(hh, return_inverse=True)
    rows_by_hh = pd.Series(np.arange(len(hh))).groupby(inv).apply(np.array).to_list()
    d_ap, d_br = [], []
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([rows_by_hh[i] for i in pick])
        yy = y[idx]
        if yy.min() == yy.max():
            continue
        d_ap.append(average_precision_score(yy, s_a[idx]) - average_precision_score(yy, s_b[idx]))
        d_br.append(np.mean((p_a[idx] - yy) ** 2) - np.mean((p_b[idx] - yy) ** 2))
    q = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    return {"n_boot": len(d_ap), "AP_diff_mean": float(np.mean(d_ap)), "AP_diff_95ci": q(d_ap),
            "Brier_diff_mean": float(np.mean(d_br)), "Brier_diff_95ci": q(d_br)}


def robust_gap(model, cal, cats, yca) -> dict:
    return {"model": float(average_precision_score(yca, model.predict_proba(design(cal, cats, FEATURES))[:, 1])),
            "rule": float(average_precision_score(yca, rule_repeat(cal)))}


def make_run_id(cfg_hash: str, model_name: str, seed: int, data_commit, features: list[str]) -> str:
    """Run identity must change whenever the model's inputs change (config, model, seed, data, feature list)."""
    return "run-" + hashlib.sha256(json.dumps([cfg_hash, model_name, seed, data_commit, list(features)]).encode()).hexdigest()[:10]


def file_hash(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def run(cfg=None, write=True) -> dict:
    t0 = time.time()
    cfg = cfg or load_config()
    cats, T = cfg["categories"], cfg["temporal"]
    tx, products = load("transactions"), load("products")
    red, camp, cdesc = load("coupon_redemptions"), load("campaigns"), load("campaign_descriptions")
    prep = prepare(tx, products, cats)
    cut_all = T["train_cutoffs"] + [T["validation_cutoff"], T["calibration_cutoff"], T["test_cutoff"]]
    panel = build_panel(prep, cut_all, cfg, red, camp, cdesc)
    split = np.select([panel.cutoff.isin(T["train_cutoffs"]), panel.cutoff == T["validation_cutoff"],
                       panel.cutoff == T["calibration_cutoff"], panel.cutoff == T["test_cutoff"]],
                      ["train", "validation", "calibration", "test"], default="unused")
    panel["split"] = split
    parts = {k: panel[panel.split == k].reset_index(drop=True) for k in ["train", "validation", "calibration", "test"]}
    split_counts = {k: {"rows": int(len(v)), "households": int(v.household_id.nunique()),
                        "positives": int(v.y.sum()), "prevalence": float(v.y.mean()),
                        "cutoffs": sorted(map(int, v.cutoff.unique()))} for k, v in parts.items()}

    # --- validation selection among fitted candidates (and rules, for reference)
    Xtr, ytr = design(parts["train"], cats, FEATURES), parts["train"].y.to_numpy()
    Xva, yva = design(parts["validation"], cats, FEATURES), parts["validation"].y.to_numpy()
    models, val = {}, {}
    for name, m in make_models().items():
        m.fit(Xtr, ytr)
        models[name] = m
        val[name] = float(average_precision_score(yva, m.predict_proba(Xva)[:, 1]))
    val["rule_repeat"] = float(average_precision_score(yva, rule_repeat(parts["validation"])))
    val["rule_popularity"] = float(average_precision_score(yva, rule_popularity(parts["validation"])))
    best = max([k for k in models], key=lambda k: val[k])
    model = models[best]

    # --- calibration on disjoint window (isotonic), for model and for the repeat rule (fair Brier comparison)
    cal = parts["calibration"]
    Xca, yca = design(cal, cats, FEATURES), cal.y.to_numpy()
    iso_m = IsotonicRegression(out_of_bounds="clip").fit(model.predict_proba(Xca)[:, 1], yca)
    iso_r = IsotonicRegression(out_of_bounds="clip").fit(rule_repeat(cal), yca)
    iso_p = IsotonicRegression(out_of_bounds="clip").fit(rule_popularity(cal), yca)

    # --- locked test, evaluated once
    te = parts["test"]
    Xte, yte = design(te, cats, FEATURES), te.y.to_numpy()
    s_model = model.predict_proba(Xte)[:, 1]
    p_model = iso_m.predict(s_model)
    s_rep, s_pop = rule_repeat(te), rule_popularity(te)
    p_rep, p_pop = iso_r.predict(s_rep), iso_p.predict(s_pop)
    test = {"model_" + best: metrics(te, yte, s_model, p_model),
            "model_uncalibrated_brier": float(brier_score_loss(yte, s_model)),
            "rule_repeat": metrics(te, yte, s_rep, p_rep),
            "rule_popularity": metrics(te, yte, s_pop, p_pop)}
    boot = bootstrap_by_household(te, yte, s_model, p_model, s_rep, p_rep)
    winner = "model" if boot["AP_diff_95ci"][0] > 0 else "rule_repeat"

    # --- per-category and per-segment errors (test)
    te = te.assign(p_model=p_model, p_rule=p_rep)
    by_cat = []
    for c, g in te.groupby("product_category"):
        by_cat.append({"category": c, "n": int(len(g)), "prevalence": float(g.y.mean()),
                       "AP_model": float(average_precision_score(g.y, g.p_model + 1e-9 * s_model[g.index])),
                       "AP_rule": float(average_precision_score(g.y, s_rep[g.index])),
                       "AP_popularity_baseline": float(g.y.mean())})
    by_seg = []
    for sg, g in te.groupby("segment"):
        by_seg.append({"segment": sg, "n": int(len(g)), "prevalence": float(g.y.mean()),
                       "mean_pred_model": float(g.p_model.mean()), "mean_pred_rule": float(g.p_rule.mean()),
                       "Brier_model": float(np.mean((g.p_model - g.y) ** 2)),
                       "Brier_rule": float(np.mean((g.p_rule - g.y) ** 2)),
                       "AP_model": float(average_precision_score(g.y, s_model[g.index])) if g.y.nunique() > 1 else None,
                       "AP_rule": float(average_precision_score(g.y, s_rep[g.index])) if g.y.nunique() > 1 else None})
    # documented failure: where does the model do worst relative to the rule?
    worst_cat = min(by_cat, key=lambda r: r["AP_model"] - r["AP_rule"])
    fn = te[(te.y == 1) & (te.p_model < 0.05)]
    failure = {
        "weakest_category_vs_rule": worst_cat,
        "missed_buyers_pred_below_5pct": {"n": int(len(fn)), "share_of_positives": float(len(fn) / max(1, te.y.sum())),
                                          "segment_mix": {k: int(v) for k, v in fn.segment.value_counts().items()}},
        "interpretation": "Households with no category purchase in 12 weeks who then buy are near-unpredictable "
                          "from behaviour alone; the model gives them low scores. This is the cold-start limit."}

    # --- ablation and robustness (validation-selected config refit without feature groups)
    abl = {}
    for label, drop in [("no_campaign_coupon_features", CAMPAIGN_FEATURES), ("no_popularity_features", POPULARITY_FEATURES)]:
        feats = [f for f in FEATURES if f not in drop]
        m2 = make_models()[best]
        m2.fit(design(parts["train"], cats, feats), ytr)
        abl[label] = float(average_precision_score(yte, m2.predict_proba(design(te, cats, feats))[:, 1]))
    robust = {"backtest_cutoff_45_AP_model": float(average_precision_score(yca, model.predict_proba(Xca)[:, 1])),
              "backtest_cutoff_45_AP_rule": float(average_precision_score(yca, rule_repeat(cal)))}

    # --- historical economics inputs (OBSERVED): mean 4-week category spend among buyers, test window
    spend = te[te.y == 1].groupby("product_category").label_spend.mean().round(4).to_dict()
    # per category x segment: purchase rate and SD of 4-week category spend incl. non-buyers (for pilot sizing)
    seg_stats = {f"{c}|{s}": {"n": int(len(g)), "purchase_rate": round(float(g.y.mean()), 4),
                              "spend_mean": round(float(g.label_spend.mean()), 4), "spend_sd": round(float(g.label_spend.std(ddof=1)), 4)}
                 for (c, s), g in te.groupby(["product_category", "segment"])}
    # paired model-vs-rule AP gap on every non-training window (temporal stability, not just household sampling)
    window_gaps = {"validation_41": {"model": val[best], "rule": val["rule_repeat"]},
                   "calibration_45": robust_gap(model, cal, cats, yca),
                   "test_49": {"model": test["model_" + best]["AP"], "rule": test["rule_repeat"]["AP"]}}
    tx_c = tx.merge(products[["product_id", "product_category"]], on="product_id")
    coup = tx_c[(tx_c.coupon_disc > 0) & tx_c.product_category.isin(cats)].groupby("product_category").coupon_disc.mean().round(4).to_dict()

    # --- forward scoring at the final cutoff (MODEL ESTIMATE for the next, unobserved 4 weeks)
    sc = build_panel(prep, [T["scoring_cutoff"]], cfg, red, camp, cdesc, with_label=False)
    s_sc = model.predict_proba(design(sc, cats, FEATURES))[:, 1]
    sc["p_model"] = iso_m.predict(s_sc)
    sc["p_rule"] = iso_r.predict(rule_repeat(sc))
    sc["p_used"] = sc.p_model if winner == "model" else sc.p_rule

    run_id = make_run_id(config_hash(cfg), best, SEED, manifest().get("commit"), FEATURES)
    report = {
        "run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "OBSERVED (historical backtest) — predicts observed purchase under historical conditions, NOT response to a coupon",
        "seed": SEED, "config_hash": config_hash(cfg), "data_manifest_commit": manifest().get("commit"),
        "target": f"household buys category in the next {T['horizon_weeks']} weeks (any basket)",
        "unit": "(cutoff_week, household_id, product_category)", "features": FEATURES,
        "split_counts": split_counts, "validation_AP": val, "selected_model": best,
        "calibration": "isotonic regression fit on calibration window only", "test": test,
        "bootstrap_model_minus_rule_repeat": boot, "decision_score_used": winner,
        "calibration_deciles_model": calibration_table(yte, p_model),
        "by_category": by_cat, "by_segment": by_seg, "failure_case": failure,
        "ablation_test_AP": abl, "robustness": robust,
        "economics_inputs_observed": {"mean_4w_category_spend_among_buyers_test": spend,
                                      "mean_coupon_disc_per_couponed_line": coup,
                                      "test_window_category_segment_stats": seg_stats},
        "window_gaps_model_vs_rule": window_gaps,
        "seconds": round(time.time() - t0, 1),
    }
    if write:
        PROCESSED.mkdir(exist_ok=True, parents=True)
        cols = ["household_id", "product_category", "segment", "p_model", "p_rule", "p_used",
                "cat_weeks_active_12w", "cat_spend_12w", "hh_baskets_12w"]
        sc[cols].to_parquet(PROCESSED / "scores_latest.parquet", index=False)
        # raw locked-test predictions so every reported test metric can be re-derived independently (gitignored)
        te[["household_id", "product_category", "segment", "y", "label_spend"]].assign(
            s_model=s_model, p_model=p_model, s_rule=s_rep, p_rule=p_rep, s_popularity=s_pop, p_popularity=p_pop
        ).to_parquet(PROCESSED / "test_predictions.parquet", index=False)
        with open(PROCESSED / "model.pkl", "wb") as f:
            pickle.dump({"model": model, "iso_model": iso_m, "iso_rule": iso_r, "features": FEATURES,
                         "categories": cats, "run_id": run_id}, f)
        report["artifacts"] = {"scores": "data/processed/scores_latest.parquet",
                               "scores_sha16": file_hash(PROCESSED / "scores_latest.parquet"),
                               "model": "data/processed/model.pkl", "model_sha16": file_hash(PROCESSED / "model.pkl")}
        (REPORTS / "model_report.json").write_text(json.dumps(report, indent=2))
        (REPORTS / "model_card.md").write_text(model_card(report), encoding="utf-8")
    return report


def model_card(r: dict) -> str:
    sel = "model_" + r["selected_model"]
    T = r["test"]
    L = [f"# Model card — {r['run_id']}", "", f"**Status:** {r['status']}", "",
         "**Intended use:** rank existing households by the probability of buying a category in the next 4 weeks under "
         "historical conditions (audience sizing, demand context, test stratification). **Not** coupon uplift, persuadability or a demand forecast.",
         f"- Features ({len(r['features'])}): {', '.join(r['features'])}",
         "- Long-history features adopted 2026-11-14 under the pre-registered protocol `data/eval/model_eval_protocol_v1.json`; "
         "full evaluation (rolling origin, calibration drift, contact sizes, subgroups with CIs) in `reports/model_evaluation.md`.",
         "- `history_weeks_available` is a time index (weeks of data before the lookback); trees treat later cutoffs as the training maximum.",
         f"- Target: {r['target']}", f"- Unit: {r['unit']}", f"- Seed {r['seed']}, config hash `{r['config_hash']}`, data commit `{str(r['data_manifest_commit'])[:12]}`",
         f"- Selected on validation AP: **{r['selected_model']}** ({json.dumps({k: round(v, 4) for k, v in r['validation_AP'].items()})})",
         f"- Calibration: {r['calibration']}", "", "## Split", "", "| split | cutoffs | rows | households | positives | prevalence |", "|---|---|---:|---:|---:|---:|"]
    for k, v in r["split_counts"].items():
        L.append(f"| {k} | {v['cutoffs']} | {v['rows']:,} | {v['households']:,} | {v['positives']:,} | {v['prevalence']:.3f} |")
    L += ["", "## Out-of-time evaluation window (cutoff 49 → weeks 50–53; inspected in earlier passes, so this is REPEATED evaluation)", "",
          "| scorer | AP | ROC AUC | Brier (calibrated) | precision top 10% | Recall@3 per household |", "|---|---:|---:|---:|---:|---:|"]
    for k in [sel, "rule_repeat", "rule_popularity"]:
        m = T[k]
        L.append(f"| {k} | {m['AP']:.4f} | {m['ROC_AUC']:.4f} | {m.get('Brier', float('nan')):.4f} | {m['precision_top10pct']:.4f} | {m['recall_at_3']:.4f} |")
    b = r["bootstrap_model_minus_rule_repeat"]
    L += ["", f"Prevalence {T[sel]['prevalence']:.4f}. Household-cluster bootstrap ({b['n_boot']} draws), model − repeat rule: "
          f"AP {b['AP_diff_mean']:+.4f} (95% CI {b['AP_diff_95ci'][0]:+.4f} to {b['AP_diff_95ci'][1]:+.4f}); "
          f"Brier {b['Brier_diff_mean']:+.5f} (95% CI {b['Brier_diff_95ci'][0]:+.5f} to {b['Brier_diff_95ci'][1]:+.5f}).",
          f"**Score used by the decision tools:** `{r['decision_score_used']}` (model is used only if the AP gain CI excludes 0).", "",
          "## By category (test)", "", "| category | prevalence | AP model | AP repeat rule |", "|---|---:|---:|---:|"]
    for c in r["by_category"]:
        L.append(f"| {c['category']} | {c['prevalence']:.3f} | {c['AP_model']:.3f} | {c['AP_rule']:.3f} |")
    L += ["", "## By segment (test)", "", "| segment | n | prevalence | mean pred model | Brier model | Brier rule |", "|---|---:|---:|---:|---:|---:|"]
    for s in r["by_segment"]:
        L.append(f"| {s['segment']} | {s['n']:,} | {s['prevalence']:.3f} | {s['mean_pred_model']:.3f} | {s['Brier_model']:.4f} | {s['Brier_rule']:.4f} |")
    f = r["failure_case"]
    L += ["", "## Documented failure", "", f"- Weakest category vs rule: {f['weakest_category_vs_rule']['category']} "
          f"(AP model {f['weakest_category_vs_rule']['AP_model']:.3f} vs rule {f['weakest_category_vs_rule']['AP_rule']:.3f})",
          f"- Buyers given < 5% probability: {f['missed_buyers_pred_below_5pct']['n']:,} "
          f"({f['missed_buyers_pred_below_5pct']['share_of_positives']:.1%} of positives); mix {f['missed_buyers_pred_below_5pct']['segment_mix']}",
          f"- {f['interpretation']}", "", "## Ablation (test AP, same config refit)", ""]
    L += [f"- {k}: {v:.4f}" for k, v in r["ablation_test_AP"].items()]
    L += [f"- {k}: {v:.4f}" for k, v in r["robustness"].items()]
    L += ["", "## Limits", "", "- Historical propensity ≠ incremental effect of a coupon. Campaign exposure was not randomized.",
          "- Test window is the holiday period (weeks 50–53); seasonality may differ from other months.",
          "- One anonymous retailer's 2,469-household panel; no margin, stock, consent or cost data.",
          "- Demographics (801 households) deliberately excluded: incomplete and not needed for behavioural targeting."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    r = run()
    print(json.dumps({k: r[k] for k in ["run_id", "selected_model", "validation_AP", "decision_score_used", "seconds"]}, indent=1))
    sel = "model_" + r["selected_model"]
    for k in [sel, "rule_repeat", "rule_popularity"]:
        print(k, {m: round(v, 4) for m, v in r["test"][k].items() if isinstance(v, float)})
    print("bootstrap", r["bootstrap_model_minus_rule_repeat"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
