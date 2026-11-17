"""Manager-facing marketing brief generated from the CURRENT dossier, reports and work queue.

Every evidence line carries a class: MEASURED (panel data), MODEL ESTIMATE, ASSUMED, HYPOTHESIS, VERIFIED EXTERNAL
(fetched official page / documentation), or PENDING. RAG lookups cite source IDs or abstain.
Usage: python -m mi.decision.marketing_brief -> docs/marketing_brief.md, docs/slide_sync_list.md
"""
from __future__ import annotations

import json
import sys

from mi.paths import REPORTS, ROOT


def _r(n):
    p = REPORTS / n
    return json.loads(p.read_text()) if p.exists() else {}


def rag_cite(q: str) -> str:
    from mi.evidence.rag import answer
    a = answer(q)
    if a.get("conflicts"):
        return "CONFLICT between sources: " + "; ".join(f"{v} ({', '.join(s)})" for c in a["conflicts"] for v, s in c["values"].items())
    if a["abstained"]:
        return "ABSTAIN: corpus does not support an answer"
    return "cites " + ", ".join(sorted({c["source_id"] for c in a["supported_claims"]}))


def agenda() -> list[dict]:
    tc, fa, opp = _r("trend_check_yogurt.json"), _r("funding_audit.json"), _r("opportunities.json")
    geo = _r("seo_geo_audit.json")
    fp = next((c for c in opp.get("cards", []) if c["id"] == "C1"), {})
    return [
        {"problem": "Lapsing frozen-pizza buyers (406 panel households) and whether to contact them",
         "question": "Why did they stop: habit, price, store brand, stock, taste?",
         "evidence": [("MEASURED", "return to category, cohort turnover (reports/opportunities.json, reports/cohort_turnover.json)"),
                      ("MODEL ESTIMATE", "120 of 406 expected to buy in 4 weeks under current patterns (reports/buyer_outcomes.json)"),
                      ("ASSUMED", "4 pp coupon response; funding contract; margin; pool"),
                      ("HYPOTHESIS", fp.get("hypothesized_need", "lapsed habit")),
                      ("PENDING", "0 interviews")],
         "rag": rag_cite("What is the retailer's actual product gross margin on frozen pizza?"),
         "task": "R1 interviews; R4 client form", "changes": "coupon vs product/availability vs no action (plan A)"},
        {"problem": "Yogurt buyer loss", "question": "Is the drop an availability, assortment, price or seasonal effect?",
         "evidence": [("MEASURED", f"equal-window buyers {tc.get('composition', {}).get('buyers_A')} -> {tc.get('composition', {}).get('buyers_B')}; not attrition, promotion or coverage (reports/trend_check_yogurt.json)"),
                      ("HYPOTHESIS", "availability / assortment fit; seasonality not separable"), ("PENDING", "store operations data")],
         "rag": rag_cite("Did the retailer have yogurt stock-outs or delistings in the second half of 2017?"),
         "task": "OPS1 operations check", "changes": "whether plan B becomes a product/place fix"},
        {"problem": "Unverified discovery of offers (public analogue)", "question": "Do assistants surface the analogue, and which sources are cited?",
         "evidence": [("OBSERVED (two Claude models)" if geo.get('answers_logged', 0) else "PENDING", f"{geo.get('answers_logged', 0)}/20 answers"),
                      ("VERIFIED EXTERNAL", "Google: no special requirements to appear in AI features (google_ai_features)")],
         "rag": rag_cite("Does Google require special markup or schema to appear in AI Overviews?"),
         "task": "R2 GEO answers", "changes": "whether plan C is worth doing"},
        {"problem": "Expensive / unconfirmed contact economics", "question": "Who funds the offer, how many consented households, what margin and costs?",
         "evidence": [("MEASURED", f"historical retailer match {fa.get('all_couponed_lines', {}).get('value_weighted_match_share')} of manufacturer coupon value (past lines only)"),
                      ("ASSUMED", "retailer-funded base; 7,308 reachable; $1,500 setup; $0.03 contact"),
                      ("VERIFIED EXTERNAL", "ALDI online terms allow promotion codes (fetched); Kroger/Target/Walmart pages UNVERIFIED")],
         "rag": rag_cite("How many households are in the Complete Journey panel?"),
         "task": "R4 client form; R3 retailer checks", "changes": "the contract-specific pool thresholds that could reopen plan A"},
    ]


def brief() -> str:
    bo, fc, cl = _r("buyer_outcomes.json"), _r("funding_contracts.json"), _r("current_claims.json")
    ev, ex = _r("advisor_eval.json"), _r("extra_opportunity.json")
    man = _r("run_manifest.json")
    claims = {c["id"]: c["value"] for c in cl.get("claims", [])}
    from mi.workflow.store import DossierStore, WorkQueue
    st = DossierStore()
    oid = man.get("dossier")
    rec = st.get(oid).get("advisor_recommendation") or {} if oid else {}
    items = WorkQueue(st).list(oid) if oid else []
    a = bo["actions"]["A_coupon"]
    p, add = a["current_pattern_buyers_panel"], a["additional_buyers_reachable_hypothetical"]
    L = ["# Marketing brief (generated from the current dossier)", "",
         f"Dossier `{oid}` · advisor status **{rec.get('decision')}** · base case: {rec.get('base_case')}.", "",
         "## 1. Objective",
         f"- **Goal:** {bo['objective']['primary']}.",
         f"- **Buyer:** {bo['objective']['units']['buyer']}.",
         f"- **Horizon:** {bo['objective']['decision_horizon_weeks']} weeks.",
         f"- **Net sales:** {bo['objective']['units']['net_sales']}.",
         f"- **Contribution:** {bo['objective']['units']['contribution']}.",
         f"- **Not measurable here:** {bo['objective']['not_measurable_here']}.",
         f"- **Growth target:** {bo['objective']['growth_target']}.", "",
         "## 2. Market and segment problems → research questions", "",
         "| problem | research question | evidence (class) | RAG check | collection task | decision it changes |", "|---|---|---|---|---|---|"]
    for g in agenda():
        L.append(f"| {g['problem']} | {g['question']} | " + "; ".join(f"**{k}**: {v}" for k, v in g["evidence"]) + f" | {g['rag']} | {g['task']} | {g['changes']} |")
    L += ["", "## 3. Options compared (STP and 4 Ps; the lever must fit the diagnosed barrier)", "",
          "| plan | segment (measurable / reachable / substantial) | lever and why | Product / Price / Place / Promotion | buyers (4 weeks) | contribution | status |", "|---|---|---|---|---|---|---|",
          f"| A Frozen Pizza coupon | lapsing; 406 panel hh / consent unknown / 7,308 assumed | price lever only if price or habit is the barrier (unknown) | as is / $0.90 coupon / app / one message | {p['expected_buyers']} expected (current patterns, panel); +{add['low']:,.0f} to +{add['high']:,.0f} additional at assumed response (company); break-even +{a['break_even_additional_buyers']:,.0f} | {a['incremental_contribution_usd']['low']:+,.0f} to {a['incremental_contribution_usd']['high']:+,.0f} USD | no paid test (DEFER) |",
          f"| B Yogurt investigation | all yogurt buyers; store-level / no contact | product or place if the cause is availability or assortment; no discount until diagnosed | assortment review / check price moves / stock and shelf / none | {bo['actions']['B_yogurt_investigation']['current_pattern_buyers_panel']['expected_buyers']} expected (panel); additional: unknown | unknown ($0 check) | READY task OPS1 |",
          "| C Discovery content | public analogue; not linkable to the panel | promotion via content only if assistants show a gap | none / none / owned pages / content | not measurable from this data | unknown | conditional on 20 answers |",
          "| D No paid action | — | default until evidence arrives | — | current patterns continue | $0 | **current choice** |",
          f"| E extra category (pre-registered criteria) | {ex.get('selected') or 'none qualified'} | — | — | — | — | {ex.get('result', '')} |", "",
          "Cross-sell is kept as a **negative finding**: only 1 of 56 pairs beats a popularity suggestion, by 0.06 pp.", "",
          "## 4. Current decision and what reopens it",
          f"**{rec.get('decision')}**. Under the retailer-funded base, every coupon plan loses money. Under the shared or manufacturer contracts, setup needs this many consented households: "
          + ", ".join(f"{k} {v['reachable_pool_needed_to_cover_setup_at_assumed_uplift']}" for k, v in fc.get("contracts", {}).items() if isinstance(v['reachable_pool_needed_to_cover_setup_at_assumed_uplift'], int))
          + " (the assumed pool is 7,308).", "", "Verified inputs that would reopen it:"] + [f"- {x}" for x in rec.get("reopen_if", [])]
    L += ["", "## 5. Work queue", "", "| item | status | kind | title | owner | budget | due | success metric |", "|---|---|---|---|---|---:|---|---|"]
    L += [f"| {w['item_id']} | {w['status']} | {w['payload']['kind']} | {w['payload']['title']} | {w['payload']['owner']} | ${w['payload']['budget_usd']:,.0f} | {w['payload']['due_date']} | {w['payload']['success_metric']} |" for w in items]
    L += ["", "READY items are $0 research or operations tasks. BLOCKED items need a named approver with a reason, plus verified consent and stock. "
          "No agent can approve, send, spend or launch.", "",
          "## 6. Measurement plan",
          "- **Before any action:** current-pattern buyers (MODEL ESTIMATE) and a scenario range (ASSUMED response). These are always shown separately.",
          "- **After an action:** observed distinct buyers, net sales and costs in the 4-week window. Load outcomes into `data/pilot/pilot_outcomes.csv` with `pilot_meta.json`.",
          "- **After a randomized test:** additional buyers and incremental contribution versus control, with intervals, from `mi.outcome.pilot`. The decision rule EXPANDs only above the rollout hurdle.",
          "- **Without a randomized control:** observed buyers are never attributed to the action.", "",
          f"Advisor evaluation on pre-registered cases: {ev.get('passed')}/{ev.get('total')} passed (`reports/advisor_eval.json`; deterministic roles, live LLM PENDING)."]
    return "\n".join(L) + "\n"


def slide_sync() -> str:
    cl = _r("current_claims.json")
    sup = [c for c in cl.get("claims", []) if "deck_value_superseded" in c]
    L = ["# Slide claims to synchronize after the evidence is frozen (the PPT was NOT edited)", "",
         "| claim id | deck shows | current value | source |", "|---|---|---|---|"]
    L += [f"| {c['id']} | {c['deck_value_superseded']} | {c['value']} | {c['source']} |" for c in sup]
    L += ["", "**Wording and status changes:**",
          "- **Slide 10 and notes:** \"ADVISOR RECOMMENDS: REJECT FUNDING (DEFER)\" becomes **DEFER FUNDING / NO SPEND WHILE TERMS ARE UNCONFIRMED** (base case: retailer-funded). Add the contract table from `docs/funding_contracts.md` and the work queue.",
          "- **Slide 9:** replace \"If it is mentioned, discovery is not the barrier\" with the qualified wording in `docs/seo_geo_protocol.md`.",
          "- **Slide 11 and the appendix:** three-cycle payback stays appendix-only, as an upper-bound hypothetical. Hurdles: 6.23 / 16.55 / 22.99 / 26.87 pp.",
          "- **Slide 8:** add that funding changes the ranking (Frozen Pizza leads under non-retailer funding), and that reversals are selected grid cases, not probabilities.",
          "- **New content for slides 4 and 11:** the buyer-outcome panel. Plan A: 120 current-pattern buyers in the panel; +146 to +512 additional buyers at an assumed response (company scale); break-even +1,209.",
          "- **Slide 12:** the test count, and the advisor evaluation (6/6, pre-registered)."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    (ROOT / "docs" / "marketing_brief.md").write_text(brief(), encoding="utf-8")
    (ROOT / "docs" / "slide_sync_list.md").write_text(slide_sync(), encoding="utf-8")
    print("docs/marketing_brief.md and docs/slide_sync_list.md written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
