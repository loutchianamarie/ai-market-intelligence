"""Robustness check of a category's buyer-base trend (used for the Yogurt -5% signal).

Checks: equal-length windows (week 1 is a single day), panel attrition (are lost buyers still shopping?),
buyer composition (retained / lost / new), 4-week buyer counts across the year versus other categories,
store coverage, and promotion changes (display/mailer intensity and sales share on promotion).
Usage: python -m mi.decision.trend_check [CATEGORY] -> reports/trend_check_<category>.json
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from mi.config import load_config
from mi.ingest.load import load
from mi.paths import REPORTS

A, B = (2, 26), (27, 51)          # equal 25-week windows; week 1 (one day) and weeks 52-53 (holiday tail) excluded


def run(category="YOGURT", write=True) -> dict:
    cats = load_config()["categories"]
    tx, pr = load("transactions"), load("products")
    t = tx.merge(pr[["product_id", "product_category"]], on="product_id", how="left")
    inA, inB = t.week.between(*A), t.week.between(*B)
    activeA, activeB = set(t[inA].household_id), set(t[inB].household_id)
    out = {"category": category, "windows": {"A": A, "B": B}}
    rows = []
    for c in cats:
        g = t[t.product_category == c]
        bA, bB = set(g[g.week.between(*A)].household_id), set(g[g.week.between(*B)].household_id)
        rows.append({"category": c, "buyers_A": len(bA), "buyers_B": len(bB), "change": round(len(bB) / len(bA) - 1, 4),
                     "buyer_rate_A": round(len(bA) / len(activeA), 4), "buyer_rate_B": round(len(bB) / len(activeB), 4)})
    out["equal_windows_all_categories"] = rows
    g = t[t.product_category == category]
    bA, bB = set(g[g.week.between(*A)].household_id), set(g[g.week.between(*B)].household_id)
    lost = bA - bB
    out["composition"] = {"buyers_A": len(bA), "buyers_B": len(bB), "retained": len(bA & bB), "lost": len(lost), "new": len(bB - bA),
                          "lost_still_shopping_in_B": len(lost & activeB), "lost_left_panel_in_B": len(lost - activeB),
                          "active_households_A": len(activeA), "active_households_B": len(activeB)}
    # 4-week buyer counts across the year (relative to each category's own mean) -> slope per category
    win = (t.week - 2) // 4
    t4 = t[t.week.between(2, 53)].assign(win=win)
    slopes = {}
    for c in cats:
        s = t4[t4.product_category == c].groupby("win").household_id.nunique()
        s = s[s.index <= 12]
        rel = s / s.mean()
        slopes[c] = round(float(np.polyfit(rel.index.to_numpy(float), rel.to_numpy(), 1)[0]), 4)
    out["relative_4w_buyer_slope_per_window"] = slopes
    out["slope_rank_lowest_first"] = sorted(slopes, key=slopes.get)
    # store coverage and promotions
    pa = REPORTS / "promotions_audit.json"
    try:
        from mi.ingest.promotions import join_transactions, load_promotions
        promo = load_promotions()
        j = join_transactions(g[["product_id", "store_id", "week", "sales_value", "basket_id"]], promo)
        def promo_stats(w):
            x = j[j.week.between(*w)]
            k = x[x.promo_store_covered]
            flag = (k.on_display.fillna(False) | k.in_mailer.fillna(False)).astype(bool)
            return {"lines": int(len(x)), "lines_in_covered_stores": round(float(x.promo_store_covered.mean()), 4),
                    "sales_share_on_promotion_covered": round(float(k.sales_value[flag].sum() / k.sales_value.sum()), 4),
                    "stores_with_category_sales": int(x.store_id.nunique())}
        pids = set(pd.to_numeric(pr[pr.product_category == category].product_id))
        pc = promo[promo.product_id.isin(pids)]
        out["coverage_and_promotions"] = {"A": promo_stats(A), "B": promo_stats(B),
                                          "promoted_product_store_rows_per_week_A": round(float(pc[pc.week.between(*A)].shape[0] / 25), 1),
                                          "promoted_product_store_rows_per_week_B": round(float(pc[pc.week.between(*B)].shape[0] / 25), 1)}
    except FileNotFoundError:
        out["coverage_and_promotions"] = "promotions table not available"
    me = next(r for r in rows if r["category"] == category)
    out["verdict"] = (f"{category} buyers change {me['change']:+.1%} on equal 25-week windows (buyer rate {me['buyer_rate_A']:.1%} -> {me['buyer_rate_B']:.1%} of active households). "
                      "This is a SIGNAL for an operations check (stock, assortment, price moves), not evidence of a cause: one year cannot separate "
                      "seasonality, and promotion intensity / store coverage changes are reported alongside.")
    if write:
        (REPORTS / f"trend_check_{category.lower().replace('/', '_').replace(' ', '_')}.json").write_text(json.dumps(out, indent=2))
    return out


def main(argv=None) -> int:
    cat = (argv or sys.argv[1:] or ["YOGURT"])[0]
    r = run(cat)
    print(json.dumps({k: r[k] for k in ("composition", "relative_4w_buyer_slope_per_window", "coverage_and_promotions", "verdict")}, indent=1))
    print([(x["category"], x["change"], x["buyer_rate_A"], x["buyer_rate_B"]) for x in r["equal_windows_all_categories"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
