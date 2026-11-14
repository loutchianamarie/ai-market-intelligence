"""Build the Portfolio & Risk report: optimiser result, reversal scans, break-even table, demand baseline.

Usage: python -m mi.decision.report   -> reports/portfolio.json, reports/sensitivity.json, reports/portfolio.md
"""
from __future__ import annotations

from mi.decision.scenario import face_value  # noqa: E402

import json
import sys

import numpy as np

from mi.config import load_config
from mi.decision.demand import demand_summary, weekly_series
from mi.decision.optimizer import compact, load_inputs, optimise, reversal_scan
from mi.ingest.load import load
from mi.paths import REPORTS

SCANS = {
    "uplift_multiplier": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
    "margin_rate": [0.20, 0.25, 0.28, 0.32, 0.35, 0.40],
    "fixed_setup": [0, 500, 1000, 1500, 2500],
    "scale": [10, 40, 100, 250],
}


def first_reversal(rows):
    base = rows[0]["recommended_base"]
    for r in rows[1:]:
        if r["recommended_base"] != base:
            return {"from": base, "to": r["recommended_base"], "at": r["value"]}
    return None


def run() -> dict:
    cfg = load_config()
    scores, econ, rep = load_inputs()
    res = optimise(scores, econ, cfg)
    res["model_run_id"] = rep["run_id"]
    scans = {p: reversal_scan(scores, econ, cfg, p, v) for p, v in SCANS.items()}
    # contact-cost scan for the digital channel only
    scans["digital_contact_cost"] = reversal_scan(scores, econ, cfg, "contact_cost",
                                                  [{"digital_coupon": x} for x in [0.0, 0.01, 0.03, 0.05, 0.08]])
    rev = {p: first_reversal(r) for p, r in scans.items()}
    # break-even uplift per cohort (base assumptions, digital channel, ALL targeting)
    be = []
    from mi.decision.scenario import assumptions_from_config, break_even_uplift
    a = assumptions_from_config(cfg, "base")
    sp, fc = econ["mean_4w_category_spend_among_buyers_test"], econ["mean_coupon_disc_per_couponed_line"]
    for cat in cfg["categories"]:
        for seg in ["REGULAR", "RECENT_LIGHT", "LAPSING", "ACTIVE_NONBUYER"]:
            sub = scores[(scores.product_category == cat) & (scores.segment == seg)]
            if sub.empty:
                continue
            q0 = float(sub.p_used.mean())
            for ch in a.contact_cost:
                x = break_even_uplift(q0, sp[cat] * a.margin_rate, fc[cat], a.contact_cost[ch], a.redemption_share)
                be.append({"category": cat, "segment": seg, "channel": ch, "panel_households": int(len(sub)),
                           "mean_q0": q0, "assumed_dq_base": a.dq(seg),
                           "break_even_dq": x if isinstance(x, float) else None,
                           "ratio_needed_to_assumed": (x / a.dq(seg)) if isinstance(x, float) else None})
    be.sort(key=lambda r: (r["ratio_needed_to_assumed"] if r["ratio_needed_to_assumed"] is not None else 1e9))
    # exact uplift multiple needed INCLUDING fixed setup (net is linear in the multiplier for a fixed audience)
    full_be = []
    for scale in (40, 100, 250):
        for cat in cfg["categories"]:
            for seg in ["REGULAR", "RECENT_LIGHT", "LAPSING", "ACTIVE_NONBUYER"]:
                sub = scores[(scores.product_category == cat) & (scores.segment == seg)]
                if sub.empty:
                    continue
                g, F = sp[cat] * a.margin_rate, face_value(cfg, fc, cat) * a.face_share(cat)
                for ch in a.contact_cost:
                    w = a.reach_share[ch] * scale
                    fixed_cost_terms = (a.contact_cost[ch] + sub.p_used * a.redemption_share * F).sum()
                    gain_per_unit = (a.dq(seg) * (g - F)) * len(sub)
                    m_star = (a.fixed_setup / w + fixed_cost_terms) / gain_per_unit if gain_per_unit > 0 else None
                    full_be.append({"scale": scale, "category": cat, "segment": seg, "channel": ch,
                                    "reach": float(len(sub) * w), "uplift_multiple_needed": m_star})
    full_be.sort(key=lambda r: (r["scale"], r["uplift_multiple_needed"] or 1e9))
    grid = []
    for m in [1.0, 2.0, 3.0, 4.0, 5.0]:
        for scale in [40, 100, 250]:
            r = optimise(scores, econ, cfg, {"uplift_multiplier": m, "scale": scale})
            top = r["top3"][0] if r["top3"] else None
            grid.append({"uplift_multiplier": m, "scale": scale, "recommended_base": r["recommended_base"],
                         "best_net_base": top["base"]["net"] if top else 0.0})
    dem = demand_summary(weekly_series(load("transactions"), load("products"), cfg["categories"]))
    out = {"portfolio": compact(res), "scans": scans, "reversals": rev, "break_even": be,
           "break_even_with_fixed": full_be, "reversal_grid": grid, "demand": dem, "status": res["status"]}
    (REPORTS / "portfolio.json").write_text(json.dumps(compact(res), indent=2, default=float))
    (REPORTS / "sensitivity.json").write_text(json.dumps({k: v for k, v in out.items() if k != "portfolio"}, indent=2, default=float))
    (REPORTS / "portfolio.md").write_text(to_md(out, cfg), encoding="utf-8")
    return out


def to_md(o, cfg) -> str:
    p = o["portfolio"]
    L = ["# Portfolio & risk report", "", f"**Status:** {o['status']}", "",
         f"Config `{p['config_hash']}` · model run `{p.get('model_run_id')}` · {p['n_candidates']} candidate plans · "
         f"{p['n_portfolios_feasible']} feasible portfolios enumerated exactly among top-{len(p['top_k_screen'])} candidates.", "",
         f"- **Recommended (base case):** {p['recommended_base']}", f"- **Recommended (worst case / robust):** {p['recommended_robust']}", "",
         "## Top feasible portfolios vs heuristic vs no action (USD, 4-week pilot at deployment scale)", "",
         "| plan | net low | net base | net high | cost base | reach |", "|---|---:|---:|---:|---:|---:|"]
    for q in p["top3"]:
        reach = sum(c["reach"] for c in q["base"]["components"])
        L.append(f"| {q['plan_id']} | {q['low']['net']:,.0f} | {q['base']['net']:,.0f} | {q['high']['net']:,.0f} | {q['base']['cost']:,.0f} | {reach:,.0f} |")
    h = p["heuristic"]
    L.append(f"| {h['plan_id']} | {h['low']['net'] if h.get('low') else float('nan'):,.0f} | {h['base']['net']:,.0f} | "
             f"{h['high']['net'] if h.get('high') else float('nan'):,.0f} | {h['base']['cost']:,.0f} | "
             f"{sum(c['reach'] for c in h['base']['components']):,.0f} |")
    L.append("| NONE: research / measure first | 0 | 0 | 0 | 0 | 0 |")
    L += ["", "## What reverses the recommendation", ""]
    for k, v in o["reversals"].items():
        L.append(f"- **{k}**: " + (f"switches from *{v['from']}* to *{v['to']}* at {v['at']}" if v else "no switch within scanned range"))
    L += ["", "## Break-even incremental purchase rate (base assumptions; 10 cohorts nearest viability)", "",
          "| category | segment | channel | panel hh | mean q0 | assumed Δq | break-even Δq | needed ÷ assumed |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for r in o["break_even"][:10]:
        L.append(f"| {r['category']} | {r['segment']} | {r['channel']} | {r['panel_households']} | {r['mean_q0']:.3f} | {r['assumed_dq_base']:.3f} | "
                 f"{r['break_even_dq']:.3f} | {r['ratio_needed_to_assumed']:.1f}× |")
    L += ["", "Fixed setup is excluded from this per-household break-even; it raises the bar further for small cells.", "",
          "## Uplift multiple needed to break even INCLUDING fixed setup (best 3 cohorts per deployment scale)", "",
          "| scale | category | segment | channel | reach | × assumed uplift needed |", "|---:|---|---|---|---:|---:|"]
    for sc in (40, 100, 250):
        for r in [x for x in o["break_even_with_fixed"] if x["scale"] == sc and x["uplift_multiple_needed"]][:3]:
            L.append(f"| {sc} | {r['category']} | {r['segment']} | {r['channel']} | {r['reach']:,.0f} | {r['uplift_multiple_needed']:.2f}× |")
    L += ["", "## Reversal grid (recommended plan, base assumptions otherwise)", "", "| uplift × | scale | recommendation | best net |", "|---:|---:|---|---:|"]
    for g in o["reversal_grid"]:
        L.append(f"| {g['uplift_multiplier']} | {g['scale']} | {g['recommended_base']} | {g['best_net_base']:,.0f} |")
    L += ["",
          "## Demand baseline (OBSERVED history, next-4-week trailing baseline)", "",
          "| category | weekly sales (last 8) | weekly buying hh | 4-week low | base | high | trend | WAPE naive | WAPE trailing-8 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for d in o["demand"]:
        L.append(f"| {d['category']} | {d['weekly_sales_mean_last8']:,.0f} | {d['weekly_households_mean_last8']:.0f} | {d['next4w_sales_low']:,.0f} | "
                 f"{d['next4w_sales_base']:,.0f} | {d['next4w_sales_high']:,.0f} | {d['trend_last8_vs_prev8']:.2f} | "
                 f"{d['WAPE_naive_last4']:.3f} | {d['WAPE_trailing8_mean']:.3f} |")
    L += ["", "Panel-level sales (2,469 households), not chain demand. No stock data: capacity remains a human check."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    o = run()
    print(json.dumps(o["reversals"], indent=1))
    for r in o["break_even"][:6]:
        print(r["category"], r["segment"], r["channel"], round(r["break_even_dq"], 4), round(r["ratio_needed_to_assumed"], 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
