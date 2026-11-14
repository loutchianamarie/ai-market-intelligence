"""Commercial diagnostic of the category-purchase model + pre-registered promotion-context ablation (protocol v2).

Reproduces the production model, adds two promotion-context features computed from weeks <= cutoff only, applies
the pre-registered adoption rule mechanically, and translates ranking quality into commercial reach: future
category purchases found per fixed number of contacts versus the recency rule (with household-cluster bootstrap
CIs) and unique households contacted. Buyers identified are NOT buyers persuaded; no score is coupon uplift.

Usage: python -m mi.model.diagnostic -> reports/model_diagnostic.json, reports/model_diagnostic.md
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score

from mi.config import load_config
from mi.ingest.load import load
from mi.ingest.promotions import join_transactions, load_promotions
from mi.model.features import FEATURES, build_panel, prepare
from mi.model.train import SEED, design, rule_popularity, rule_repeat
from mi.paths import REPORTS, ROOT

PROTOCOL = ROOT / "data" / "eval" / "model_eval_protocol_v2.json"
PROMO = ["hh_cat_promo_share_12w", "cat_promo_index_4w"]
NO_RECENT = {"LOW_ACTIVITY", "ACTIVE_NONBUYER"}
FEATURE_PROVENANCE = {
    **{f: {"source": "transactions (+products for category)", "window": "12-week lookback <= cutoff"} for f in FEATURES},
    "cat_weeks_active_prior14": {"source": "transactions", "window": "14 weeks before the lookback"},
    "cat_bought_before_lookback": {"source": "transactions", "window": "any week before the lookback"},
    "history_weeks_available": {"source": "calendar", "window": "weeks of data before the lookback (time index)"},
    "hh_coupon_disc_12w": {"source": "transactions.coupon_disc", "window": "12-week lookback"},
    "hh_redemptions_12w": {"source": "coupon_redemptions", "window": "redemption date <= cutoff date"},
    "hh_campaigns_started": {"source": "campaigns + campaign_descriptions", "window": "campaign start <= cutoff date (no coupon-pool reconstruction)"},
    "hh_cat_promo_share_12w": {"source": "transactions x promotions (covered stores)", "window": "12-week lookback <= cutoff"},
    "cat_promo_index_4w": {"source": "promotions", "window": "weeks cutoff-3..cutoff vs weeks 1..cutoff"},
}


def promo_features(cutoffs, cats) -> pd.DataFrame:
    promo = load_promotions()
    tx, pr = load("transactions"), load("products")
    prod_cat = pr[pr.product_category.isin(cats)][["product_id", "product_category"]]
    t = tx[tx.product_id.isin(set(prod_cat.product_id))][["household_id", "product_id", "store_id", "week", "sales_value"]]
    j = join_transactions(t, promo)
    j = j.merge(prod_cat.assign(product_id=pd.to_numeric(prod_cat.product_id)), on="product_id", how="left")
    cov = j[j.promo_store_covered]
    cov = cov.assign(promoted=(cov.on_display.fillna(False) | cov.in_mailer.fillna(False)).astype(bool))
    hw = cov.groupby(["household_id", "product_category", "week"]).promoted.max().reset_index()
    pc = promo[promo.product_id.isin(set(pd.to_numeric(prod_cat.product_id)))].merge(
        prod_cat.assign(product_id=pd.to_numeric(prod_cat.product_id)), on="product_id")
    cw = pc.groupby(["product_category", "week"]).size().rename("rows").reset_index()
    out = []
    for c in cutoffs:
        w = hw[(hw.week > c - 12) & (hw.week <= c)]
        share = w.groupby(["household_id", "product_category"]).promoted.mean().rename("hh_cat_promo_share_12w").reset_index()
        cwc = cw[cw.week <= c]
        idx = (cwc[cwc.week > c - 4].groupby("product_category").rows.mean() / cwc.groupby("product_category").rows.mean()).rename("cat_promo_index_4w")
        share["cutoff"] = c
        out.append(share.merge(idx.reset_index(), on="product_category", how="left"))
    feats = pd.concat(out, ignore_index=True)
    return feats, cw


def _fit(X, y):
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=15, min_samples_leaf=80,
                                          l2_regularization=1.0, random_state=SEED).fit(X, y)


def reach(df, s_model, s_rule, ks, n_boot=300, seed=SEED) -> list[dict]:
    rng = np.random.default_rng(seed)
    hh = df.household_id.to_numpy()
    uniq, inv = np.unique(hh, return_inverse=True)
    rows_by = pd.Series(np.arange(len(hh))).groupby(inv).apply(np.array).to_list()
    y = df.y.to_numpy()
    def tp(idx, s, k):
        o = idx[np.argsort(-s[idx], kind="stable")[:k]]
        return y[o].sum(), len(np.unique(hh[o]))
    full = np.arange(len(df))
    out = []
    for k in ks:
        tm, um = tp(full, s_model, k)
        tr, ur = tp(full, s_rule, k)
        gains = []
        for _ in range(n_boot):
            idx = np.concatenate([rows_by[i] for i in rng.integers(0, len(uniq), len(uniq))])
            kk = int(round(k * len(idx) / len(df)))
            gains.append(tp(idx, s_model, kk)[0] - tp(idx, s_rule, kk)[0])
        out.append({"contacts": k, "purchases_found_model": int(tm), "purchases_found_rule": int(tr),
                    "gain_over_rule": int(tm - tr), "gain_95ci": [float(np.percentile(gains, 2.5)), float(np.percentile(gains, 97.5))],
                    "precision_model": round(tm / k, 4), "precision_rule": round(tr / k, 4),
                    "unique_households_model": int(um), "unique_households_rule": int(ur)})
    return out


def run(write=True) -> dict:
    t0 = time.time()
    proto = json.loads(PROTOCOL.read_text())
    cfg = load_config()
    cats, T = cfg["categories"], cfg["temporal"]
    cut = T["train_cutoffs"] + [T["validation_cutoff"], T["calibration_cutoff"], T["test_cutoff"]]
    prep = prepare(load("transactions"), load("products"), cats)
    panel = build_panel(prep, cut, cfg, load("coupon_redemptions"), load("campaigns"), load("campaign_descriptions"))
    pf, cw = promo_features(cut, cats)
    pf["household_id"] = pf.household_id.astype(str)
    panel = panel.merge(pf, on=["cutoff", "household_id", "product_category"], how="left")
    panel["hh_cat_promo_share_12w"] = panel.hh_cat_promo_share_12w.fillna(0.0)
    by = {c: panel[panel.cutoff == c].reset_index(drop=True) for c in cut}
    tr = pd.concat([by[c] for c in T["train_cutoffs"]], ignore_index=True)
    va, te = by[T["validation_cutoff"]], by[T["test_cutoff"]]
    feats = {"production": FEATURES, "production_plus_promo": FEATURES + PROMO}
    models = {n: _fit(design(tr, cats, f), tr.y.to_numpy()) for n, f in feats.items()}
    sc = lambda n, d: models[n].predict_proba(design(d, cats, feats[n]))[:, 1]  # noqa: E731
    # reproduction check of the reported production AP on window 49
    ap49_prod = float(average_precision_score(te.y, sc("production", te)))
    rep = json.loads((REPORTS / "model_report.json").read_text())
    reported = rep["test"]["model_" + rep["selected_model"]]["AP"]
    # adoption rule
    nr = va.segment.isin(NO_RECENT).to_numpy()
    sel = {n: {"AP_41": float(average_precision_score(va.y, sc(n, va))),
               "AP_41_no_recent": float(average_precision_score(va.y[nr], sc(n, va)[nr]))} for n in feats}
    pool = T["train_cutoffs"] + [T["validation_cutoff"]]
    trd = pd.concat([by[c] for c in pool if c + T["horizon_weeks"] <= T["calibration_cutoff"]], ignore_index=True)
    roll45 = {n: float(average_precision_score(by[45].y, _fit(design(trd, cats, f), trd.y.to_numpy()).predict_proba(design(by[45], cats, f))[:, 1]))
              for n, f in feats.items()}
    g41 = sel["production_plus_promo"]["AP_41"] - sel["production"]["AP_41"]
    g45 = roll45["production_plus_promo"] - roll45["production"]
    gnr = sel["production_plus_promo"]["AP_41_no_recent"] - sel["production"]["AP_41_no_recent"]
    adopt = g41 >= 0.005 and g45 >= 0.005 and gnr >= 0
    chosen = "production_plus_promo" if adopt else "production"
    # commercial diagnostic on 49 (repeated evaluation)
    s_m, s_r, s_p = sc(chosen, te), rule_repeat(te), rule_popularity(te)
    capacity = reach(te, s_m, s_r, proto["commercial_metrics"]["capacities_rows"])
    per_cat = []
    for c, g in te.groupby("product_category"):
        idx = g.index.to_numpy()
        top_m = idx[np.argsort(-s_m[idx], kind="stable")[:100]]
        top_r = idx[np.argsort(-s_r[idx], kind="stable")[:100]]
        per_cat.append({"category": c, "eligible": int(len(g)), "buyers": int(g.y.sum()),
                        "found_in_100_model": int(te.y.to_numpy()[top_m].sum()), "found_in_100_rule": int(te.y.to_numpy()[top_r].sum())})
    groups = {"new_to_category": ((te.cat_bought_before_lookback == 0) & (te.cat_weeks_active_12w == 0)).to_numpy(),
              "lapsing": (te.segment == "LAPSING").to_numpy(), "active": te.segment.isin({"REGULAR", "RECENT_LIGHT"}).to_numpy(),
              "no_recent_history": te.segment.isin(NO_RECENT).to_numpy()}
    from mi.model.train import bootstrap_by_household
    subs = []
    for name, m in groups.items():
        d = te[m].reset_index(drop=True)
        pos = int(d.y.sum())
        row = {"group": name, "rows": int(m.sum()), "households": int(d.household_id.nunique()), "buyers": pos,
               "prevalence": round(float(d.y.mean()), 4) if len(d) else None}
        if 0 < pos < len(d):
            row.update({"AP_model": round(float(average_precision_score(d.y, s_m[m])), 4), "AP_rule": round(float(average_precision_score(d.y, s_r[m])), 4)})
            if pos >= 100:
                b = bootstrap_by_household(d, d.y.to_numpy(), s_m[m], s_m[m], s_r[m], s_r[m], n_boot=200)
                row["AP_diff_95ci"] = [round(x, 4) for x in b["AP_diff_95ci"]]
        subs.append(row)
    month = {str(c): {"AP_model": round(float(average_precision_score(by[c].y, sc(chosen, by[c]))), 4),
                      "AP_rule": round(float(average_precision_score(by[c].y, rule_repeat(by[c]))), 4),
                      "prevalence": round(float(by[c].y.mean()), 4)} for c in (41, 45, 49)}
    res = {"protocol": str(PROTOCOL.relative_to(ROOT)), "protocol_status": proto["status"],
           "reproduction": {"production_AP_49_recomputed": round(ap49_prod, 6), "production_AP_49_reported": round(reported, 6),
                            "exact": abs(ap49_prod - reported) < 1e-9},
           "ablation": {"selection_41": sel, "rolling_45": roll45, "gain_41": round(g41, 4), "gain_rolling_45": round(g45, 4),
                        "gain_no_recent_41": round(gnr, 4), "adopted": adopt, "chosen_model": chosen,
                        "rule": proto["adoption_rule"]},
           "feature_provenance": {f: FEATURE_PROVENANCE.get(f, {"source": "transactions", "window": "<= cutoff"}) for f in feats[chosen] + (PROMO if not adopt else [])},
           "excluded_by_design": proto["excluded_by_design"],
           "commercial_reach_49": {"note": "window 49 is REPEATED evaluation; purchases found are buyers identified, not persuaded",
                                   "by_capacity": capacity, "per_category_at_100": per_cat},
           "subgroups_49": subs, "by_month": month, "label_horizon_weeks": T["horizon_weeks"],
           "interpretation": proto["interpretation_rule"], "seconds": round(time.time() - t0, 1)}
    if write:
        (REPORTS / "model_diagnostic.json").write_text(json.dumps(res, indent=2))
        (REPORTS / "model_diagnostic.md").write_text(to_md(res), encoding="utf-8")
    return res


def to_md(r) -> str:
    a = r["ablation"]
    L = ["# Model commercial diagnostic (protocol v2)", "",
         f"Reproduction of production AP on window 49: recomputed {r['reproduction']['production_AP_49_recomputed']:.6f} vs reported "
         f"{r['reproduction']['production_AP_49_reported']:.6f} → exact: **{r['reproduction']['exact']}**.", "",
         "## Promotion-context ablation (pre-registered rule)", "",
         f"Gain @41 {a['gain_41']:+.4f}; rolling @45 {a['gain_rolling_45']:+.4f}; no-recent-history @41 {a['gain_no_recent_41']:+.4f} → "
         f"**adopted: {a['adopted']}** (model used below: `{a['chosen_model']}`).", "",
         "## Commercial reach at fixed contact capacity (window 49, repeated evaluation)", "",
         "| contacts (household × category rows) | purchases found: model | rule | gain (95% CI) | precision model / rule | unique households model / rule |",
         "|---:|---:|---:|---|---|---|"]
    for c in r["commercial_reach_49"]["by_capacity"]:
        L.append(f"| {c['contacts']:,} | {c['purchases_found_model']:,} | {c['purchases_found_rule']:,} | {c['gain_over_rule']:+d} "
                 f"({c['gain_95ci'][0]:+.0f} to {c['gain_95ci'][1]:+.0f}) | {c['precision_model']:.3f} / {c['precision_rule']:.3f} | "
                 f"{c['unique_households_model']:,} / {c['unique_households_rule']:,} |")
    L += ["", "Per category, top 100 contacts: " + "; ".join(f"{x['category']} {x['found_in_100_model']} vs {x['found_in_100_rule']}"
                                                         for x in r["commercial_reach_49"]["per_category_at_100"]), "",
          "## Subgroups (window 49)", "", "| group | rows | households | buyers | prevalence | AP model | AP rule | AP diff 95% CI |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for s in r["subgroups_49"]:
        L.append(f"| {s['group']} | {s['rows']:,} | {s['households']:,} | {s['buyers']:,} | {s['prevalence']} | {s.get('AP_model', '-')} | {s.get('AP_rule', '-')} | {s.get('AP_diff_95ci', 'n/a')} |")
    L += ["", "## By month", "", "| cutoff | AP model | AP rule | prevalence |", "|---|---:|---:|---:|"]
    L += [f"| {k} | {v['AP_model']} | {v['AP_rule']} | {v['prevalence']} |" for k, v in r["by_month"].items()]
    L += ["", f"*{r['interpretation']}*", "", "Windows 41/45 were used for selection/calibration in earlier passes; 49 is repeated evaluation."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    r = run()
    print(json.dumps({k: r[k] for k in ("reproduction", "ablation")}, indent=1))
    for c in r["commercial_reach_49"]["by_capacity"]:
        print(c)
    print(r["seconds"], "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
