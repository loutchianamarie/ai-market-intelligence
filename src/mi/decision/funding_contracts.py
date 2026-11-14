"""The SAME Frozen Pizza / lapsing / digital plan under explicit offer-funding contracts.

The retailer's cost per redeemed coupon is (retailer share) x face value. Shares are CONTRACT ASSUMPTIONS:
  RETAILER_FUNDED 1.0 (current base) | SHARED_50_50 0.5 | MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE 0.35
  (value-weighted historical match on Frozen Pizza couponed lines, reports/funding_audit.json; an analogue, not our
  offer) | MANUFACTURER_FUNDED_NO_MATCH 0.0.
For each: incremental contribution per contacted household at the assumed response, break-even response,
reachable pool needed to cover setup, cost lines, stock/consent requirements, test sizes (design rule and
rollout-hurdle rule), rollout A/B/C, and the optimizer's ranking. The grid of contracts x other inputs is a set of
SELECTED cases, not a sample from any probability distribution: counts of flipping cases are not probabilities.

Usage: python -m mi.decision.funding_contracts -> reports/funding_contracts.json, docs/funding_contracts.md
"""
from __future__ import annotations

from mi.decision.scenario import face_value  # noqa: E402

import json
import math
import sys

import numpy as np
import pandas as pd

from mi.config import load_config
from mi.decision.optimizer import load_inputs, optimise
from mi.decision.scenario import assumptions_from_config
from mi.outcome.learning import contribution_sample_size, decision_value, pilot_design
from mi.paths import PROCESSED, REPORTS, ROOT

CONTRACTS = {"RETAILER_FUNDED": 1.0, "SHARED_50_50": 0.5, "MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE": 0.35,
             "MANUFACTURER_FUNDED_NO_MATCH": 0.0}
CAT, SEG, CH = "FROZEN PIZZA", "LAPSING", "digital_coupon"
Z = 1.959964 + 0.841621


def same_plan(share: float, cfg=None) -> dict:
    cfg = cfg or load_config()
    a = assumptions_from_config(cfg, "base")
    rep = json.loads((REPORTS / "model_report.json").read_text())
    e = rep["economics_inputs_observed"]
    sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
    q0 = float(sc[(sc.product_category == CAT) & (sc.segment == SEG)].p_used.mean())
    panel = int(((sc.product_category == CAT) & (sc.segment == SEG)).sum())
    g = e["mean_4w_category_spend_among_buyers_test"][CAT] * a.margin_rate
    face = face_value(cfg, e["mean_coupon_disc_per_couponed_line"], CAT)
    F = face * share
    c, r, dq = a.contact_cost[CH], a.redemption_share, a.dq(SEG)
    sigma = a.margin_rate * e["test_window_category_segment_stats"][f"{CAT}|{SEG}"]["spend_sd"]
    reach = panel * a.reach_share[CH] * cfg["scenario"]["deployment_scale"]["value"]
    turn = json.loads((REPORTS / "cohort_turnover.json").read_text()).get("mean_share_new") if (REPORTS / "cohort_turnover.json").exists() else None
    v = dq * (g - F) - c - q0 * r * F
    be = (c + q0 * r * F) / (g - F)
    d = pilot_design(q0, g, F, c, r, sigma, dq)
    n_rule = d["n_contribution"]["2.0"]["n_per_arm"]
    hurdle_v = a.fixed_setup / reach                         # contribution per household needed to cover setup (scenario A)
    n_hurdle = contribution_sample_size(sigma, v - hurdle_v) if v > hurdle_v else None
    dv = decision_value(q0, g, F, c, r, n_rule, reach, a.fixed_setup,
                        {"assumed": dq, "sizing (x break-even)": 2 * be}, share_new=turn)
    return {"retailer_share_of_face": share, "face_value_usd": round(face, 4), "retailer_cost_per_redemption_usd": round(F, 4),
            "inputs": {"q0_mean": round(q0, 4), "g_margin_per_extra_buyer": round(g, 4), "contact_cost": c, "redemption_share": r,
                       "assumed_uplift": dq, "setup_usd": a.fixed_setup, "assumed_reachable_households": round(reach), "sigma": round(sigma, 4)},
            "contribution_per_contacted_hh_at_assumed_uplift": round(v, 4), "per_1000_contacted": round(1000 * v, 1),
            "break_even_uplift_pp": round(100 * be, 2), "assumed_uplift_pp": 100 * dq,
            "reachable_pool_needed_to_cover_setup_at_assumed_uplift": (math.ceil(a.fixed_setup / v) if v > 0 else "none: negative per household"),
            "cost_lines_per_cycle_at_assumed_pool": {"contact_usd": round(reach * c, 2), "setup_usd": a.fixed_setup,
                                                     "coupon_cost_to_retailer_usd": round(reach * (q0 * r + dq) * F, 2)},
            "requirements": {"consented_eligible_households": f">= {math.ceil(a.fixed_setup / v)} for setup cover (if v > 0)" if v > 0 else "no pool size suffices",
                             "stock": f"~{round(reach * (q0 + dq))} purchasing households per cycle at the assumed pool (units per purchase UNKNOWN)",
                             "offer_contract": "written funding/reimbursement terms for this exact offer"},
            "test_size": {"design_rule_2x_break_even_n_per_arm": n_rule, "design_rule_feasible_in_assumed_pool": 2 * n_rule <= reach,
                          "show_contribution_above_setup_hurdle_n_per_arm": n_hurdle,
                          "hurdle_rule_feasible_in_assumed_pool": (2 * n_hurdle <= reach) if n_hurdle else False,
                          "note": "hurdle rule uses the ASSUMED 4 pp as the true effect; None means 4 pp does not clear the hurdle"},
            "rollout": {k: {"uplift_pp": round(100 * x["true_uplift"], 2), "A_full_pool_cycle": x["rollout_cycle_net"],
                            "B_new_entrants_cycle": x["new_entrants_cycle_net"], "C_one_off_remaining": x["one_time_remaining_pool_net"],
                            "test_net_cost": x["test_net_cost_vs_none"]} for k, x in dv["scenarios"].items()},
            "hurdles_pp": {k: (round(100 * v_, 2) if v_ is not None else None) for k, v_ in dv["hurdles"].items()}}


def ranking(share: float, cfg=None) -> dict:
    cfg = cfg or load_config()
    scores, econ, _ = load_inputs()
    r = optimise(scores, econ, cfg, {"coupon_retailer_share": share})
    return {"recommendation": r["recommended_base"], "ranked_actions": r["ranked_actions"][:4]}


def grid(cfg=None) -> dict:
    import itertools
    cfg = cfg or load_config()
    scores, econ, _ = load_inputs()
    G = {"contract": list(CONTRACTS), "uplift_multiplier": [1.0, 1.5, 2.0], "scale": [40.0, 100.0, 250.0],
         "fixed_setup": [1500.0, 750.0], "margin_rate": [0.28, 0.35]}
    rows = []
    for combo in itertools.product(*G.values()):
        d = dict(zip(G, combo))
        ov = {"coupon_retailer_share": CONTRACTS[d["contract"]], "uplift_multiplier": d["uplift_multiplier"], "scale": d["scale"],
              "fixed_setup": d["fixed_setup"], "margin_rate": d["margin_rate"]}
        r = optimise(scores, econ, cfg, ov)
        rows.append({**d, "recommendation": r["recommended_base"], "flips": not r["recommended_base"].startswith("NONE")})
    keys = [k for k in G if k != "contract"]
    level = {k: {v: i for i, v in enumerate(G[k])} for k in keys}
    out = {}
    for ct in CONTRACTS:
        fl = [x for x in rows if x["contract"] == ct and x["flips"]]
        dom = lambda a, b: all(level[k][b[k]] <= level[k][a[k]] for k in keys) and any(level[k][b[k]] < level[k][a[k]] for k in keys)  # noqa: E731
        minimal = [{k: x[k] for k in keys} | {"plan": x["recommendation"]} for x in fl if not any(dom(x, o) for o in fl if o is not x)]
        out[ct] = {"selected_cases": sum(1 for x in rows if x["contract"] == ct), "cases_reversing_NONE": len(fl),
                   "flips_at_all_base_values": any(x["flips"] and x["uplift_multiplier"] == 1.0 and x["scale"] == 40.0 and x["fixed_setup"] == 1500.0
                                                   and x["margin_rate"] == 0.28 for x in fl),
                   "minimal_reversing_combinations": minimal}
    return {"grid": G, "by_contract": out,
            "reading": "Cases were SELECTED by us (plausible-looking levels), not sampled from a distribution; a count of reversing cases is NOT a probability. Use the minimal combinations as a checklist of what would have to be confirmed."}


def run(write=True) -> dict:
    cfg = load_config()
    res = {"plan": f"{CAT}|{SEG}|{CH}|ALL", "contracts": {k: same_plan(v, cfg) for k, v in CONTRACTS.items()},
           "rankings": {k: ranking(v, cfg) for k, v in CONTRACTS.items()}, "reversal_grid": grid(cfg),
           "observed_vs_unknown": "Historical match shares are OBSERVED for past coupon lines (reports/funding_audit.json); the funding of the proposed digital offer is UNKNOWN until the client confirms the contract.",
           "status": "SCENARIO; contracts are assumptions"}
    if write:
        (REPORTS / "funding_contracts.json").write_text(json.dumps(res, indent=2, default=str))
        (ROOT / "docs" / "funding_contracts.md").write_text(to_md(res), encoding="utf-8")
    return res


def to_md(r) -> str:
    L = ["# Same plan, explicit offer-funding contracts (Frozen Pizza / lapsing / digital)", "", r["observed_vs_unknown"], "",
         "| contract | retailer cost per redemption | contribution per contacted hh @4 pp | break-even response | pool needed to cover $1,500 setup @4 pp | test n/arm (2× break-even rule) | n/arm to beat setup hurdle @4 pp | A / B / C @4 pp (USD) | optimizer recommends |",
         "|---|---:|---:|---:|---|---:|---|---|---|"]
    for k, c in r["contracts"].items():
        ro = c["rollout"]["assumed"]
        th = c["test_size"]
        cval = f"{ro['C_one_off_remaining']:+,.0f}" if ro["C_one_off_remaining"] is not None else "n/a (test > pool)"
        fits = "" if th["design_rule_feasible_in_assumed_pool"] else " (exceeds pool)"
        L.append(f"| {k} | ${c['retailer_cost_per_redemption_usd']:.2f} | ${c['contribution_per_contacted_hh_at_assumed_uplift']:+.3f} | {c['break_even_uplift_pp']} pp | "
                 f"{c['reachable_pool_needed_to_cover_setup_at_assumed_uplift']} | {th['design_rule_2x_break_even_n_per_arm']:,}{fits} | "
                 f"{th['show_contribution_above_setup_hurdle_n_per_arm'] or 'n/a (4 pp below hurdle)'} | {ro['A_full_pool_cycle']:+,.0f} / {ro['B_new_entrants_cycle']:+,.0f} / {cval} | "
                 f"{r['rankings'][k]['recommendation']} |")
    L += ["", "Assumed reachable pool 7,308 (COMPANY SCALE ASSUMED); setup $1,500 and contact $0.03 per household (ASSUMED); response 4 pp (ASSUMED).", "",
          "## Ranking under each contract (top 4, base other inputs)", ""]
    for k, rk in r["rankings"].items():
        L.append(f"- **{k}:** " + "; ".join(f"{x['rank']}. {x['plan_id']} ({x['net_base']:+,.0f})" for x in rk["ranked_actions"]))
    g = r["reversal_grid"]
    L += ["", "## Combinations that reverse NONE (selected grid; not probabilities)", "", g["reading"], ""]
    for k, v in g["by_contract"].items():
        L.append(f"- **{k}:** {v['cases_reversing_NONE']} of {v['selected_cases']} selected cases; reverses at all-base values: {v['flips_at_all_base_values']}. Minimal combinations:")
        L += [f"  - {m}" for m in v["minimal_reversing_combinations"]] or ["  - none"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    r = run()
    for k, c in r["contracts"].items():
        print(k, c["contribution_per_contacted_hh_at_assumed_uplift"], c["break_even_uplift_pp"], c["reachable_pool_needed_to_cover_setup_at_assumed_uplift"],
              c["test_size"]["design_rule_2x_break_even_n_per_arm"], c["test_size"]["show_contribution_above_setup_hurdle_n_per_arm"], c["rollout"]["assumed"], r["rankings"][k]["recommendation"])
    for k, v in r["reversal_grid"]["by_contract"].items():
        print(k, v["cases_reversing_NONE"], "/", v["selected_cases"], "base flips:", v["flips_at_all_base_values"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
