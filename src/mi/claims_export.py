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
    add("reversal.combinations", "see contract.* claims (selected grid cases per funding contract; not probabilities)", "-", "SCENARIO", "reports/funding_contracts.json#reversal_grid")
    add("opportunity.cards", [c["id"] + ": " + c["recommendation"] for c in opp.get("cards", [])], "-", "OBSERVED + HYPOTHESES", "reports/opportunities.json#cards")
    v = hs.get("average_effects", {})
    if v:
        add("hillstrom.visit_effect_mens_pp", round(100 * v["Mens E-Mail vs No E-Mail"]["visit"]["diff"], 1), "pp (2 weeks)", "METHOD EVIDENCE (other retailer)", "reports/experiments/hillstrom_report.json")
        add("hillstrom.visit_effect_womens_pp", round(100 * v["Womens E-Mail vs No E-Mail"]["visit"]["diff"], 1), "pp (2 weeks)", "METHOD EVIDENCE (other retailer)", "reports/experiments/hillstrom_report.json")
    add("geo.answers_logged", geo.get("answers_logged", 0), "of 20", "PENDING" if not geo.get("answers_logged") else "OBSERVED (two Claude models, not ChatGPT or Gemini)", "reports/seo_geo_audit.json")
    add("interviews.completed", 0, "of 2-3", "PENDING", "data/interviews/coding_sheet.csv")
    add("agents.live_llm", "PENDING (no runtime key)", "-", "PENDING", "configs/agents.json")
    add("run.dossier", man.get("dossier"), "-", "OBSERVED", "reports/run_manifest.json")
    rec = {}
    if man.get("dossier"):
        from mi.workflow.store import DossierStore
        rec = DossierStore().get(man["dossier"]).get("advisor_recommendation") or {}
    add("advisor.status", rec.get("decision"), "-", "ADVISORY (a named human decides)", f"dossier {man.get('dossier')}#advisor_recommendation")
    add("advisor.base_case", rec.get("base_case"), "-", "ASSUMPTION", f"dossier {man.get('dossier')}#advisor_recommendation")
    add("advisor.reopen_if", rec.get("reopen_if"), "-", "CHECKLIST", f"dossier {man.get('dossier')}#advisor_recommendation")
    bo, ev, ex = _r("buyer_outcomes.json"), _r("advisor_eval.json"), _r("extra_opportunity.json")
    if bo:
        A = bo["actions"]["A_coupon"]
        add("buyers.planA_current_pattern_panel", A["current_pattern_buyers_panel"]["expected_buyers"], "unique households buying in 4 weeks (of 406)",
            "MODEL ESTIMATE (not a no-contact counterfactual)", "reports/buyer_outcomes.json#A_coupon")
        add("buyers.planA_additional_low_base_high", [A["additional_buyers_reachable_hypothetical"][k] for k in ("low", "base", "high")],
            "additional unique households (company scale)", "SCENARIO (assumed response)", "reports/buyer_outcomes.json#A_coupon")
        add("buyers.planA_break_even_additional", A["break_even_additional_buyers"], "additional households", "SCENARIO", "reports/buyer_outcomes.json#A_coupon")
        add("buyers.planA_observed", A["observed_after_action"], "-", "OBSERVED only after a run", "reports/buyer_outcomes.json#A_coupon")
    if ev:
        add("advisor.eval_cases_passed", f"{ev['passed']}/{ev['total']}", "pre-registered cases", "OBSERVED (deterministic roles)", "reports/advisor_eval.json")
    if ex:
        add("opportunity.extra_category", ex.get("selected") or "none qualified", "-", "OBSERVED (pre-registered criteria)", "reports/extra_opportunity.json")
    if man.get("dossier"):
        from mi.workflow.store import DossierStore, WorkQueue
        wq = WorkQueue(DossierStore()).list(man["dossier"])
        add("queue.items", {w["item_id"]: f"{w['status']} {w['payload']['kind']} ${w['payload']['budget_usd']:,.0f}" for w in wq}, "-", "SANDBOX", f"dossier {man['dossier']} work_items")
    fa, fc = _r("funding_audit.json"), _r("funding_contracts.json")
    if fa:
        add("funding.historical_match_share_all", fa["all_couponed_lines"]["value_weighted_match_share"], "value-weighted share of manufacturer coupon value",
            "OBSERVED (past coupon lines; not our offer)", "reports/funding_audit.json#all_couponed_lines")
        add("funding.historical_match_share_frozen_pizza", fa["by_category_all_couponed"]["FROZEN PIZZA"]["value_weighted_match_share"],
            "value-weighted; 543 lines", "OBSERVED (past coupon lines; not our offer)", "reports/funding_audit.json#by_category_all_couponed")
    if fc:
        for k, v in fc["contracts"].items():
            add(f"contract.{k}", {"contribution_per_contacted_hh": v["contribution_per_contacted_hh_at_assumed_uplift"],
                                  "break_even_pp": v["break_even_uplift_pp"], "pool_needed": v["reachable_pool_needed_to_cover_setup_at_assumed_uplift"],
                                  "recommendation": fc["rankings"][k]["recommendation"],
                                  "selected_reversing_cases": f"{fc['reversal_grid']['by_contract'][k]['cases_reversing_NONE']} of {fc['reversal_grid']['by_contract'][k]['selected_cases']} (not a probability)"},
                "-", "SCENARIO (contract ASSUMED)", "reports/funding_contracts.json")
    return C


def card(C) -> str:
    v = {c["id"]: c["value"] for c in C}
    con = {k[len("contract."):]: x for k, x in v.items() if k.startswith("contract.")}
    L = ["# Decision card: next CRM / category budget", "",
         f"**Advisor status:** {v.get('advisor.status')}. **Base case:** {v.get('advisor.base_case')}.",
         f"**Recommendation now:** {v['decision.recommendation']}: no rollout, no funded coupon test, no spend or send. "
         f"Live dossier `{v['run.dossier']}`; a named person still has to decide in app tab 4.", "",
         "## Why",
         f"- Under the retailer-funded base case every modelled coupon plan loses money (best: {v.get('decision.rank2', {}).get('plan')} {v.get('decision.rank2', {}).get('net_base'):+,.0f} USD per 4-week cycle at an assumed scale).",
         f"- A better purchase model does not rescue negative incremental contribution. AP is {v['model.AP']} vs the rule's {v['model.AP_rule']}, and the model finds {v['model.reach_gain_1000_contacts']:+d} more future buyers per 1,000 contacts; these are buyers *identified*, not persuaded.",
         f"- Historical retailer match on past coupon lines is {100 * (v.get('funding.historical_match_share_all') or 0):.1f}% of manufacturer coupon value overall "
         f"and {100 * (v.get('funding.historical_match_share_frozen_pizza') or 0):.1f}% for Frozen Pizza (value-weighted). This is OBSERVED for past lines; it does not tell us who would fund OUR offer.",
         "", "## Same Frozen Pizza plan under each funding contract (assumed 4 pp response, 7,308 assumed pool, $1,500 setup)", "",
         "| contract | contribution per contacted household | break-even response | pool needed to cover setup | recommendation | selected grid cases reversing NONE |", "|---|---:|---:|---|---|---|"]
    for k, x in con.items():
        L.append(f"| {k} | {x['contribution_per_contacted_hh']:+.3f} | {x['break_even_pp']} pp | {x['pool_needed']} | {x['recommendation']} | {x['selected_reversing_cases']} |")
    L += ["", "Grid cases were selected by us, so counts are not probabilities. The minimal reversing combinations are in `docs/funding_contracts.md`.", "",
          "## Verified inputs that would reopen the decision"] + [f"- {x}" for x in (v.get("advisor.reopen_if") or [])] + [
          "", "## What to do this week (zero spend)",
          "1. Send the client input form (`docs/client_input_form.md`); load the answers with `python -m mi.decision.client_inputs` and re-run `python -m mi.cli all`.",
          "2. Interviews: why did lapsed buyers stop? This decides between a coupon, the product, availability and no action.",
          "3. Operations check on the Yogurt signal (card C3); keep the weak cross-sell (C2) as a negative finding.",
          f"4. Before any content work (card C4): {_geo_step()}.", "",
          "Full cards: `docs/opportunity_cards.md`. Claims with provenance: `reports/current_claims.json`."]
    return "\n".join(L) + "\n"


def _geo_step() -> str:
    from mi.seo.geo import geo_state
    g = geo_state()
    if g["complete"]:
        return "the GEO audit is complete (20/20, Claude models only): score impact and effort, then re-run the frozen panel in ChatGPT and Gemini"
    return f"collect the remaining {g['answers_remaining']} of {g['answers_target']} GEO answers"


def main(argv=None) -> int:
    C = claims()
    (REPORTS / "current_claims.json").write_text(json.dumps({"claims": C, "note": "deck_value_superseded = figure on the current slides that this value replaces; PPT not edited"}, indent=2, default=str))
    (ROOT / "docs" / "decision_card.md").write_text(card(C), encoding="utf-8")
    print(f"{len(C)} claims exported; superseded deck values: {sum(1 for c in C if 'deck_value_superseded' in c)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
