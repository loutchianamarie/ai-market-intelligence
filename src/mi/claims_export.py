"""Export current claim values with provenance (for a later deck refresh) + a manager-facing decision card.

Every claim: id, value, unit, status (OBSERVED / MODEL ESTIMATE / SCENARIO / PENDING / METHOD EVIDENCE),
source (report file + key) and, where the deck shows an older figure, `deck_value_superseded`.
Usage: python -m mi.claims_export -> reports/current_claims.json, docs/decision_card.md
"""
from __future__ import annotations

import json
import sys

from mi.paths import REPORTS, ROOT


def _r(name):
    p = REPORTS / name
    return json.loads(p.read_text()) if p.exists() else {}


def claims() -> list[dict]:
    mr, ev, dg = _r("model_report.json"), _r("model_evaluation.json"), _r("model_diagnostic.json")
    ca, port, rv = _r("claim_audit.json"), _r("portfolio.json"), _r("decision_reversal.json")
    acc, pa, opp = _r("accounting_audit.json"), _r("promotions_audit.json"), _r("opportunities.json")
    hs, geo, man = _r("experiments/hillstrom_report.json"), _r("seo_geo_audit.json"), _r("run_manifest.json")
    sel = "model_" + mr["selected_model"]
    sp = ca["economics"]["same_plan_test_value"]
    boot = mr["bootstrap_model_minus_rule_repeat"]
    cap = {c["contacts"]: c for c in dg["commercial_reach_49"]["by_capacity"]}
    C = []
    add = lambda i, v, u, st, src, old=None: C.append({"id": i, "value": v, "unit": u, "status": st, "source": src,  # noqa: E731
                                                       **({"deck_value_superseded": old} if old is not None else {})})
    add("data.households", 2469, "households", "OBSERVED", "reports/data_audit.json#transactions.households")
    add("data.transaction_lines", 1469307, "lines", "OBSERVED", "reports/data_audit.json#tables.transactions.rows")
    add("data.promotions_rows", pa.get("rows"), "product x store x week rows", "OBSERVED", "reports/promotions_audit.json#rows")
    add("data.promotions_store_coverage_of_lines", pa.get("join", {}).get("all_lines", {}).get("lines_in_covered_stores"), "share", "OBSERVED", "reports/promotions_audit.json#join.all_lines")
    add("data.retailer_match_share_of_coupon_value", acc.get("retailer_match_share_of_manufacturer_coupon_value"), "share", "OBSERVED", "reports/accounting_audit.json")
    add("model.AP", round(mr["test"][sel]["AP"], 3), "average precision (window 49, repeated)", "OBSERVED backtest", "reports/model_report.json#test", 0.662)
    add("model.AP_rule", round(mr["test"]["rule_repeat"]["AP"], 3), "average precision", "OBSERVED backtest", "reports/model_report.json#test")
    add("model.AP_popularity", round(mr["test"]["rule_popularity"]["AP"], 3), "average precision", "OBSERVED backtest", "reports/model_report.json#test")
    add("model.AP_gain_ci95", [round(x, 3) for x in boot["AP_diff_95ci"]], "AP difference", "OBSERVED backtest", "reports/model_report.json#bootstrap_model_minus_rule_repeat", [0.037, 0.046])
    add("model.reach_gain_1000_contacts", cap[1000]["gain_over_rule"], "extra future purchases found vs recency rule per 1,000 contacts", "OBSERVED backtest (not persuasion)", "reports/model_diagnostic.json#commercial_reach_49")
    add("model.reach_gain_100_contacts", cap[100]["gain_over_rule"], "extra purchases per 100 contacts", "OBSERVED backtest", "reports/model_diagnostic.json#commercial_reach_49")
    add("model.promo_ablation_adopted", dg["ablation"]["adopted"], "bool", "OBSERVED (pre-registered rule)", "reports/model_diagnostic.json#ablation")
    add("decision.recommendation", port["recommended_base"], "-", "SCENARIO", "reports/portfolio.json#recommended_base")
    for r in port.get("ranked_actions", [])[:3]:
        add(f"decision.rank{r['rank']}", {"plan": r["plan_id"], "net_base": r["net_base"]}, "USD per 4-week cycle (assumed scale)", "SCENARIO", "reports/portfolio.json#ranked_actions")
    add("economics.unit_break_even_pp", sp["hurdles_pp"]["unit_break_even_pp"], "pp", "SCENARIO", "reports/claim_audit.json#economics.same_plan_test_value", 6.4)
    add("economics.test_n_per_arm", sp["n_per_arm"], "households", "DESIGN (ASSUMED effect)", "reports/claim_audit.json", 2623)
    s2 = sp["scenarios"]["sizing_2x_break_even"]
    add("economics.sized_for_uplift_pp", s2["uplift_pp"], "pp", "DESIGN", "reports/claim_audit.json", 12.7)
    add("economics.rollout_A_B_C_at_sized_uplift", [s2["rollout_cycle_net_4w"], s2["B_new_entrants_cycle_net_4w"], s2["C_one_time_remaining_pool_net"]],
        "USD per cycle / one-off", "SCENARIO", "reports/claim_audit.json", [-575, -931, -907])
    add("economics.hurdles_A_B_C_pp", [sp["hurdles_pp"]["A_full_pool_cycle_pp"], sp["hurdles_pp"]["B_new_entrants_cycle_pp"], sp["hurdles_pp"]["C_one_time_covers_setup_and_test_pp"]],
        "pp", "SCENARIO", "reports/claim_audit.json", [16.7, 23.1, 27.0])
    one = {r["input"]: r.get("flip_value") for r in rv.get("one_at_a_time", [])}
    add("reversal.one_at_a_time_flip_uplift_multiple", one.get("uplift_multiplier"), "x assumed uplift", "SCENARIO (one input varied)", "reports/decision_reversal.json")
    co = rv.get("combinations", {})
    add("reversal.combinations_flipping", f"{co.get('n_flip')} of {co.get('n_combinations')}", "joint scenarios", "SCENARIO", "reports/decision_reversal.json#combinations")
    add("opportunity.cards", [c["id"] + ": " + c["recommendation"] for c in opp.get("cards", [])], "-", "OBSERVED + HYPOTHESES", "reports/opportunities.json#cards")
    v = hs.get("average_effects", {})
    if v:
        add("hillstrom.visit_effect_mens_pp", round(100 * v["Mens E-Mail vs No E-Mail"]["visit"]["diff"], 1), "pp (2 weeks)", "METHOD EVIDENCE (other retailer)", "reports/experiments/hillstrom_report.json")
        add("hillstrom.visit_effect_womens_pp", round(100 * v["Womens E-Mail vs No E-Mail"]["visit"]["diff"], 1), "pp (2 weeks)", "METHOD EVIDENCE (other retailer)", "reports/experiments/hillstrom_report.json")
    add("geo.answers_logged", geo.get("answers_logged", 0), "of 20", "PENDING", "reports/seo_geo_audit.json")
    add("interviews.completed", 0, "of 2-3", "PENDING", "data/interviews/coding_sheet.csv")
    add("agents.live_llm", "PENDING (no runtime key)", "-", "PENDING", "configs/agents.json")
    add("run.dossier", man.get("dossier"), "-", "OBSERVED", "reports/run_manifest.json")
    return C


def card(C) -> str:
    v = {c["id"]: c["value"] for c in C}
    L = ["# Decision card: next CRM / category budget", "",
         f"**Recommendation now:** {v['decision.recommendation']} (no rollout, no funded coupon test).",
         f"Live dossier `{v['run.dossier']}`; a named person still has to reject or approve in app tab 4.", "",
         "## Why",
         f"- Every modelled coupon plan loses money at the stated assumptions (best: {v.get('decision.rank2', {}).get('plan')} {v.get('decision.rank2', {}).get('net_base'):+,.0f} USD per 4-week cycle at an assumed scale).",
         f"- A better purchase model does not rescue a negative incremental contribution. AP is {v['model.AP']} vs the rule's {v['model.AP_rule']}, and at 1,000 contacts the model finds {v['model.reach_gain_1000_contacts']:+d} more future buyers than recency; these are buyers *identified*, not persuaded.",
         f"- Varying one input at a time, only true response ≥ {v['reversal.one_at_a_time_flip_uplift_multiple']:.2f}× the assumption flips the choice.",
         f"- Varying inputs jointly over a grid (response 1–3×, retailer vs manufacturer funding, scale 40–250×, setup $750–1,500, margin 28–35%), "
         f"{v['reversal.combinations_flipping']} combinations flip it. Each grid value is an *assumed* alternative. "
         "The decision is therefore fragile to joint assumptions and holds only because none of these changes is confirmed.", "",
         "## Minimum evidence before any coupon action",
         "| input | why it decides | current status |", "|---|---|---|",
         "| who funds the coupon | manufacturer funding cuts the retailer's cost to its match share (≈35% for Frozen Pizza) | ASSUMED retailer-funded |",
         "| consented reachable pool | spreads the $1,500 setup; decides whether a decision-grade test fits | UNKNOWN |",
         "| unit margin | sets the value of each extra buyer | ASSUMED 28% |",
         "| communication cost and offer mechanics | contact cost; automatic offers subsidise habitual buyers | ASSUMED |",
         "| stock | no promotion without supply | UNKNOWN |",
         "| causal response (randomized) | the only way to know whether contact changes buying | UNKNOWN; history is selection |", "",
         "## What to do this week (zero spend)",
         "1. Ask the client for coupon funding, pool size, margin, costs and stock, then re-run `python -m mi.cli all`.",
         "2. Interviews: why did lapsed buyers stop? This decides between a coupon, the product, availability and no action.",
         "3. Operations check on the shrinking category (card C3).",
         "4. Collect the 20 GEO answers before any content work (card C4).", "",
         "Full cards: `docs/opportunity_cards.md`. Claims with provenance: `reports/current_claims.json`."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    C = claims()
    (REPORTS / "current_claims.json").write_text(json.dumps({"claims": C, "note": "deck_value_superseded = figure on the current slides that this value replaces; PPT not edited"}, indent=2, default=str))
    (ROOT / "docs" / "decision_card.md").write_text(card(C), encoding="utf-8")
    print(f"{len(C)} claims exported; superseded deck values: {sum(1 for c in C if 'deck_value_superseded' in c)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
