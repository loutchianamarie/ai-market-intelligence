"""Apply the pre-registered criteria (data/eval/extra_opportunity_criteria_v1.json) to pick at most one extra category.

Usage: python -m mi.decision.extra_opportunity -> reports/extra_opportunity.json
"""
from __future__ import annotations

import json
import math
import sys

import numpy as np
import pandas as pd

from mi.decision.trend_check import run as trend_run
from mi.paths import PROCESSED, REPORTS, ROOT

CRITERIA = ROOT / "data" / "eval" / "extra_opportunity_criteria_v1.json"


def run(write=True) -> dict:
    crit = json.loads(CRITERIA.read_text())
    saved = REPORTS / "trend_check_yogurt.json"          # reuse the pipeline's trend check instead of recomputing it
    t = json.loads(saved.read_text()) if saved.exists() else trend_run("YOGURT", write=False)
    opp = json.loads((REPORTS / "opportunities.json").read_text())
    facts = {f["category"]: f for f in opp["category_facts"]}
    nA, nB = t["composition"]["active_households_A"], t["composition"]["active_households_B"]
    rows = []
    for r in t["equal_windows_all_categories"]:
        c = r["category"]
        if c in ("FROZEN PIZZA", "YOGURT"):
            continue
        pA, pB = r["buyer_rate_A"], r["buyer_rate_B"]
        se = math.sqrt(pA * (1 - pA) / nA + pB * (1 - pB) / nB)
        d = pB - pA
        f = facts[c]
        checks = {"buyer_rate_rises_ci_excludes_0": d - 1.96 * se > 0, "year_penetration_below_50pct": f["penetration_year"] < 0.5,
                  "return_to_category_at_least_70pct": f["return_to_category_H1_to_H2"] >= 0.70}
        rows.append({"category": c, "buyer_rate_A": pA, "buyer_rate_B": pB, "diff": round(d, 4), "diff_ci95": [round(d - 1.96 * se, 4), round(d + 1.96 * se, 4)],
                     "penetration_year": f["penetration_year"], "return_to_category": f["return_to_category_H1_to_H2"], "checks": checks,
                     "qualifies": all(checks.values())})
    q = sorted([r for r in rows if r["qualifies"]], key=lambda r: -r["diff"])
    chosen = q[0] if q else None
    res = {"criteria": crit["criteria_all_required"], "evaluated": rows, "selected": chosen["category"] if chosen else None,
           "note_ci": "two-proportion normal approximation; windows share households, so the interval is approximate"}
    if chosen:
        sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
        q0 = sc[sc.product_category == chosen["category"]].p_used.to_numpy(float)
        from mi.decision.buyer_outcomes import calibration_factor, current_pattern_buyers
        res["buyer_panel"] = {"action": f"{chosen['category']}: visibility / assortment investigation for a growing, under-penetrated category (plan E)",
                              "unit": "unique households buying the category in 4 weeks",
                              "current_pattern_buyers_panel": current_pattern_buyers(q0, calibration_factor(chosen["category"], None)) | {"status": "MODEL ESTIMATE"},
                              "additional_buyers": "UNKNOWN: no sourced effect for a visibility/assortment change", "budget_usd": 0,
                              "evidence": [f"buyer rate {chosen['buyer_rate_A']:.1%} -> {chosen['buyer_rate_B']:.1%} (diff CI {chosen['diff_ci95']})",
                                           f"year penetration {chosen['penetration_year']:.1%}; return to category {chosen['return_to_category']:.1%}"],
                              "contrary_evidence": ["the later window includes holiday weeks (seasonality cannot be separated with one year)",
                                                    "a rising or under-penetrated category is not proof of unmet need",
                                                    "the money value of new buyers depends on ASSUMED margin; no effect estimate exists"]}
    else:
        res["result"] = crit["if_none_qualifies"]
    if write:
        (REPORTS / "extra_opportunity.json").write_text(json.dumps(res, indent=2, default=float))
    return res


def main(argv=None) -> int:
    r = run()
    for x in r["evaluated"]:
        print(x["category"], x["diff"], x["diff_ci95"], x["penetration_year"], x["return_to_category"], x["qualifies"])
    print("selected:", r["selected"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
