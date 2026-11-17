"""Buyer-outcome panel for every proposed action (forecast / scenario / observed / causal, never mixed).

Objective and units (this panel cannot measure new-to-retailer acquisition or a live company's growth):
  * buyer       = a UNIQUE HOUSEHOLD buying the action's category at least once in the 4-week decision horizon
                  (one household-category pair per household, so household counts = pair counts here)
  * net sales   = retailer receipts (sales_value, USD) from the category over the horizon
  * contribution= receipts x ASSUMED margin, after coupon cost borne by the retailer, contact and setup (USD)
Rows of the panel:
  1. eligible households (panel and, separately, HYPOTHETICAL company scale), reachable, consent unknown
  2. expected buyers under CURRENT PATTERNS: sum of calibrated purchase probabilities (MODEL ESTIMATE) with a
     Poisson-binomial interval and a calibration check from the last evaluation window. This reflects buying under
     historical normal promotions; it is NOT a verified no-contact counterfactual.
  3. expected ADDITIONAL buyers only when an incremental-response parameter exists (config, ASSUMED range), capped
     so no household exceeds probability 1; total-with-action = current-pattern + additional (labelled SCENARIO)
  4. break-even additional buyers and incremental receipts/contribution only when the unit values exist
  5. observed outcome only after an action has run; additional buyers only from a randomized control
Usage: python -m mi.decision.buyer_outcomes -> reports/buyer_outcomes.json, docs/buyer_outcomes.md
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from mi.config import load_config
from mi.decision.scenario import assumptions_from_config, face_value
from mi.paths import PROCESSED, REPORTS, ROOT

HORIZON_WEEKS = 4
PILOT_CSV = ROOT / "data" / "pilot" / "pilot_outcomes.csv"
PILOT_META = ROOT / "data" / "pilot" / "pilot_meta.json"


def calibration_factor(category: str, segment: str | None, n_boot=500, seed=20261114) -> dict:
    """Observed / predicted buyers in the last evaluation window (49) for the same slice, household bootstrap CI."""
    t = pd.read_parquet(PROCESSED / "test_predictions.parquet")
    g = t[(t.product_category == category) & ((t.segment == segment) if segment else True)]
    if g.empty:
        return {"available": False}
    y, p = g.y.to_numpy(float), g.p_model.to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), (n_boot, len(g)))
    ratio = y[idx].sum(1) / p[idx].sum(1)
    return {"available": True, "window": "cutoff 49 (weeks 50-53, repeated evaluation)", "households": int(len(g)),
            "observed_buyers": int(y.sum()), "predicted_buyers": round(float(p.sum()), 1),
            "observed_over_predicted": round(float(y.sum() / p.sum()), 3),
            "ratio_ci95": [round(float(np.percentile(ratio, 2.5)), 3), round(float(np.percentile(ratio, 97.5)), 3)]}


def current_pattern_buyers(q0: np.ndarray, cal: dict) -> dict:
    mu = float(q0.sum())
    sd = math.sqrt(float((q0 * (1 - q0)).sum()))
    lo, hi = max(0.0, mu - 1.96 * sd), min(len(q0), mu + 1.96 * sd)
    out = {"households": int(len(q0)), "expected_buyers": round(mu, 1), "poisson_binomial_95": [round(lo, 1), round(hi, 1)],
           "expected_rate": round(mu / len(q0), 4) if len(q0) else None}
    if cal.get("available"):
        r0, r1 = cal["ratio_ci95"]
        out["calibration_adjusted_range"] = [round(max(0.0, lo * r0), 1), round(min(len(q0), hi * r1), 1)]
    return out


def additional_buyers(n_reach: float, mean_q0: float, dq_range: list[float]) -> dict:
    """Additional buyers = reach x dq (ASSUMED absolute points), capped at the headroom reach x (1 - q0)."""
    cap = n_reach * (1 - mean_q0)
    vals = [min(n_reach * d, cap) for d in dq_range]
    return {"low": round(vals[0], 1), "base": round(vals[1], 1), "high": round(vals[2], 1), "cap_headroom": round(cap, 1),
            "dq_range_points": dq_range, "status": "SCENARIO: ASSUMED incremental-response range (config), not measured"}


def coupon_action(cfg, category="FROZEN PIZZA", segment="LAPSING", channel="digital_coupon") -> dict:
    a = assumptions_from_config(cfg, "base")
    s = cfg["scenario"]
    rep = json.loads((REPORTS / "model_report.json").read_text())
    e = rep["economics_inputs_observed"]
    sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
    g_ = sc[(sc.product_category == category) & (sc.segment == segment)]
    q0 = g_.p_used.to_numpy(float)
    cal = calibration_factor(category, segment)
    panel = current_pattern_buyers(q0, cal)
    scale, reach_share = s["deployment_scale"]["value"], a.reach_share[channel]
    company_eligible = len(q0) * scale
    reachable = company_eligible * reach_share
    mq = float(q0.mean())
    dq_range = [v * a.uplift_multiplier for v in s["incremental_purchase_rate"][segment]]
    add = additional_buyers(reachable, mq, dq_range)
    spend = e["mean_4w_category_spend_among_buyers_test"][category]
    g = spend * a.margin_rate
    F = face_value(cfg, e["mean_coupon_disc_per_couponed_line"], category) * a.face_share(category)
    c, r, setup = a.contact_cost[channel], a.redemption_share, a.fixed_setup
    fixed_like = reachable * c + reachable * mq * r * F + setup
    be_add = fixed_like / (g - F) if g > F else None
    contrib = {k: round(add[k] * (g - F) - fixed_like, 2) for k in ("low", "base", "high")}
    receipts = {k: round(add[k] * spend, 2) for k in ("low", "base", "high")}
    return {
        "action": f"{category} / {segment} / {channel} coupon (plan A)", "unit": "unique households buying the category in 4 weeks",
        "eligible": {"panel_households": int(len(q0)), "panel_contactable": 0,
                     "company_eligible_hypothetical": round(company_eligible), "reachable_hypothetical": round(reachable),
                     "consent_unknown_or_suppressed_hypothetical": round(company_eligible - reachable),
                     "status": f"panel is anonymous and NOT contactable; company counts = panel x {scale} (COMPANY SCALE ASSUMED) x {reach_share} reach (ASSUMED)"},
        "current_pattern_buyers_panel": panel | {"status": "MODEL ESTIMATE (historical normal promotions; not a no-contact counterfactual)"},
        "calibration_check": cal,
        "current_pattern_buyers_reachable_hypothetical": round(reachable * mq, 1),
        "additional_buyers_reachable_hypothetical": add,
        "total_buyers_with_action_hypothetical": {k: round(reachable * mq + add[k], 1) for k in ("low", "base", "high")},
        "break_even_additional_buyers": round(be_add, 1) if be_add else None,
        "break_even_note": "additional buyers needed so that extra margin covers contact, the coupon subsidy to baseline buyers and setup",
        "incremental_receipts_usd": receipts, "incremental_contribution_usd": contrib,
        "unit_values": {"receipts_per_buyer_4w_observed": round(spend, 2), "margin_assumed": a.margin_rate, "retailer_coupon_cost": round(F, 4),
                        "funding_contract": "retailer share " + str(a.face_share(category)), "contact_cost": c, "setup": setup},
        "double_counting_guard": "additional buyers are added to the current-pattern total once; households already expected to buy contribute only the coupon subsidy",
        "observed_after_action": observed_outcome(),
    }


def yogurt_action(cfg) -> dict:
    tc = json.loads((REPORTS / "trend_check_yogurt.json").read_text()) if (REPORTS / "trend_check_yogurt.json").exists() else None
    sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
    q0 = sc[sc.product_category == "YOGURT"].p_used.to_numpy(float)
    panel = current_pattern_buyers(q0, calibration_factor("YOGURT", None))
    tgt = None
    if tc:
        c = tc["composition"]
        me = next(x for x in tc["equal_windows_all_categories"] if x["category"] == "YOGURT")
        need = round(me["buyer_rate_A"] * c["active_households_B"] - c["buyers_B"])
        tgt = {"metric": "unique yogurt buyers per 25-week window among active panel households",
               "baseline_latest_window": c["buyers_B"], "earlier_window": c["buyers_A"],
               "proposed_target": f"restore buyer rate to {me['buyer_rate_A']:.1%} (≈ +{need} households on the latest active base)",
               "status": "PROPOSED TARGET with observed baseline; not a forecast"}
    return {"action": "Yogurt availability / assortment / placement investigation (plan B)", "unit": "unique households buying yogurt",
            "eligible": {"panel_households_scored": int(len(q0)), "contact": "none needed (store / operations investigation)"},
            "current_pattern_buyers_panel": panel | {"status": "MODEL ESTIMATE (4 weeks after cutoff 53)"},
            "additional_buyers": "UNKNOWN: no sourced or assumed effect of a fix exists; cause not diagnosed",
            "break_even_additional_buyers": "not applicable ($0 investigation)", "incremental_contribution_usd": "unknown",
            "budget_usd": 0, "target": tgt, "observed_after_action": "NOT RUN"}


def content_action() -> dict:
    geo = json.loads((REPORTS / "seo_geo_audit.json").read_text()) if (REPORTS / "seo_geo_audit.json").exists() else {}
    return {"action": "Discovery content for the public analogue (plan C)", "unit": "assistant answers mentioning / recommending the analogue (of 20); owned-page search clicks if a site owner supplies Search Console",
            "eligible": "not linkable to the anonymous panel households", "current_pattern_buyers_panel": "not applicable",
            "additional_buyers": "UNKNOWN: content effects on buyers cannot be measured from this data",
            "answers_logged": geo.get("answers_logged", 0), "status": ("CONDITIONAL on 20 real GEO answers" if not geo.get("answers_logged") else "answers logged from two Claude models (not ChatGPT or Gemini); effect on buyers still UNKNOWN"), "budget_usd": 0,
            "observed_after_action": "NOT RUN"}


def none_action(coupon: dict) -> dict:
    return {"action": "No paid action / research first (plan D)", "unit": "unique households buying the category in 4 weeks",
            "current_pattern_buyers_panel": coupon["current_pattern_buyers_panel"], "additional_buyers": {"low": 0, "base": 0, "high": 0},
            "incremental_contribution_usd": {"low": 0, "base": 0, "high": 0}, "budget_usd": 0,
            "note": "buyers still buy under current patterns; no incremental cost or claimed effect"}


def observed_outcome(csv: Path = PILOT_CSV, meta: Path = PILOT_META) -> dict | str:
    """Only after an action ran: observed distinct buyers, net sales and costs; causal additional buyers only with a randomized control."""
    if not csv.exists() or not meta.exists():
        return "NOT RUN: no action has been executed; no observed buyers exist"
    df, m = pd.read_csv(csv), json.loads(meta.read_text())
    return summarize_observed(df, m)


def summarize_observed(df: pd.DataFrame, meta: dict) -> dict:
    t = df[df.arm == "treatment"]
    out = {"observed_distinct_buyers_treated": int(t.loc[t.purchased == 1, "household_id"].nunique()),
           "observed_net_sales_treated_usd": round(float(t.category_spend_usd.sum()), 2),
           "observed_costs_treated_usd": round(float(t.coupon_cost_usd.sum() + t.contact_cost_usd.sum()), 2),
           "status": "OBSERVED (treated households)", "source": meta.get("source")}
    if meta.get("randomized") is True and (df.arm == "control").any():
        from mi.outcome.pilot import analyze
        r = analyze(df, meta)
        n_t = r["arms"]["treatment"]
        out["estimated_additional_buyers"] = {"point": round(r["purchase_rate_diff"] * n_t, 1),
                                              "ci95": [round(x * n_t, 1) for x in r["purchase_rate_diff_ci95"]],
                                              "status": "ESTIMATED CAUSAL EFFECT vs randomized control"}
        out["decision"] = r["decision"]
    else:
        out["estimated_additional_buyers"] = "not estimable: no randomized control; observed buyers are NOT attributed to the action"
    return out


def run(write=True) -> dict:
    cfg = load_config()
    a = coupon_action(cfg)
    res = {"objective": {"primary": "increase unique category buyers (incl. returning lapsed buyers) and incremental contribution",
                         "not_measurable_here": "new-to-retailer acquisition; a live company's growth",
                         "decision_horizon_weeks": HORIZON_WEEKS,
                         "units": {"buyer": "unique household buying the category in the horizon", "net_sales": "retailer receipts (USD)",
                                   "contribution": "receipts x assumed margin after retailer coupon cost, contact, setup (USD)"},
                         "growth_target": "PROPOSED only: no business baseline beyond the panel exists"},
           "labels": {"forecast": "current-pattern MODEL ESTIMATE", "scenario": "with an ASSUMED response", "observed": "after an action ran",
                      "causal": "difference vs randomized control"},
           "actions": {"A_coupon": a, "B_yogurt_investigation": yogurt_action(cfg), "C_content": content_action(), "D_none": none_action(a)}}
    extra = REPORTS / "extra_opportunity.json"
    if extra.exists():
        res["actions"]["E_extra"] = json.loads(extra.read_text()).get("buyer_panel")
    if write:
        (REPORTS / "buyer_outcomes.json").write_text(json.dumps(res, indent=2, default=str))
        (ROOT / "docs" / "buyer_outcomes.md").write_text(to_md(res), encoding="utf-8")
    return res


def to_md(r) -> str:
    a = r["actions"]["A_coupon"]
    p, el, add = a["current_pattern_buyers_panel"], a["eligible"], a["additional_buyers_reachable_hypothetical"]
    L = ["# Buyer-outcome panel", "", f"**Objective:** {r['objective']['primary']}. Horizon {r['objective']['decision_horizon_weeks']} weeks. "
         f"Buyer = {r['objective']['units']['buyer']}. Not measurable here: {r['objective']['not_measurable_here']}.", "",
         f"## A. {a['action']}", "", "| row | value | label |", "|---|---|---|",
         f"| eligible panel households | {el['panel_households']:,} (contactable: 0) | OBSERVED |",
         f"| eligible / reachable / consent unknown (company) | {el['company_eligible_hypothetical']:,} / {el['reachable_hypothetical']:,} / {el['consent_unknown_or_suppressed_hypothetical']:,} | COMPANY SCALE ASSUMED |",
         f"| expected buyers in 4 weeks, current patterns (panel) | {p['expected_buyers']} of {p['households']} (95% {p['poisson_binomial_95']}; calibration-adjusted {p.get('calibration_adjusted_range')}) | MODEL ESTIMATE, not a no-contact counterfactual |",
         f"| calibration check (window 49) | observed {a['calibration_check']['observed_buyers']} vs predicted {a['calibration_check']['predicted_buyers']} (ratio {a['calibration_check']['observed_over_predicted']}, CI {a['calibration_check']['ratio_ci95']}) | OBSERVED backtest |",
         f"| current-pattern buyers among reachable (company) | {a['current_pattern_buyers_reachable_hypothetical']:,} | MODEL ESTIMATE × ASSUMED scale |",
         f"| ADDITIONAL buyers from the coupon (low / base / high) | {add['low']:,} / {add['base']:,} / {add['high']:,} (cap {add['cap_headroom']:,}) | SCENARIO (assumed {add['dq_range_points']} points) |",
         f"| total buyers with the coupon (low / base / high) | {a['total_buyers_with_action_hypothetical']['low']:,} / {a['total_buyers_with_action_hypothetical']['base']:,} / {a['total_buyers_with_action_hypothetical']['high']:,} | SCENARIO |",
         f"| break-even ADDITIONAL buyers | {a['break_even_additional_buyers']:,} | SCENARIO |",
         f"| incremental receipts (USD, low / base / high) | {a['incremental_receipts_usd']['low']:,} / {a['incremental_receipts_usd']['base']:,} / {a['incremental_receipts_usd']['high']:,} | SCENARIO |",
         f"| incremental contribution (USD, low / base / high) | {a['incremental_contribution_usd']['low']:,} / {a['incremental_contribution_usd']['base']:,} / {a['incremental_contribution_usd']['high']:,} | SCENARIO |",
         f"| observed after action | {a['observed_after_action']} | — |", "",
         f"Guard: {a['double_counting_guard']}.", ""]
    b = r["actions"]["B_yogurt_investigation"]
    L += [f"## B. {b['action']}", "", f"- Current-pattern buyers (panel, 4 weeks): {b['current_pattern_buyers_panel']['expected_buyers']} of {b['current_pattern_buyers_panel']['households']} scored households (MODEL ESTIMATE).",
          f"- Additional buyers: {b['additional_buyers']}.", f"- Target: {b['target']}", f"- Budget: ${b['budget_usd']}; observed: {b['observed_after_action']}.", ""]
    c = r["actions"]["C_content"]
    L += [f"## C. {c['action']}", "", f"- Unit: {c['unit']}.", f"- Answers logged: {c['answers_logged']}/20. {c['status']}. Additional buyers: {c['additional_buyers']}.", ""]
    d = r["actions"]["D_none"]
    L += [f"## D. {d['action']}", "", f"- {d['note']}. Additional buyers 0; incremental contribution $0.", ""]
    if r["actions"].get("E_extra"):
        e = r["actions"]["E_extra"]
        L += [f"## E. {e['action']}", "", f"- Current-pattern buyers (panel, 4 weeks): {e['current_pattern_buyers_panel']['expected_buyers']} of {e['current_pattern_buyers_panel']['households']} scored households (MODEL ESTIMATE).",
              f"- Additional buyers: {e['additional_buyers']}. Budget ${e['budget_usd']}.", ""]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    r = run()
    a = r["actions"]["A_coupon"]
    print(json.dumps({k: a[k] for k in ("eligible", "current_pattern_buyers_panel", "calibration_check", "additional_buyers_reachable_hypothetical",
                                         "break_even_additional_buyers", "incremental_contribution_usd")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
