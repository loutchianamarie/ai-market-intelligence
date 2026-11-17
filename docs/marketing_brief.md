# Marketing brief (generated from the current dossier)

Dossier `OPP-B2B80821` · advisor status **DEFER FUNDING / NO SPEND WHILE TERMS ARE UNCONFIRMED** · base case: RETAILER-FUNDED offer (retailer pays the full coupon face value): the current base case.

## 1. Objective
- **Goal:** increase unique category buyers (incl. returning lapsed buyers) and incremental contribution.
- **Buyer:** unique household buying the category in the horizon.
- **Horizon:** 4 weeks.
- **Net sales:** retailer receipts (USD).
- **Contribution:** receipts x assumed margin after retailer coupon cost, contact, setup (USD).
- **Not measurable here:** new-to-retailer acquisition; a live company's growth.
- **Growth target:** PROPOSED only: no business baseline beyond the panel exists.

## 2. Market and segment problems → research questions

| problem | research question | evidence (class) | RAG check | collection task | decision it changes |
|---|---|---|---|---|---|
| Lapsing frozen-pizza buyers (406 panel households) and whether to contact them | Why did they stop: habit, price, store brand, stock, taste? | **MEASURED**: return to category, cohort turnover (reports/opportunities.json, reports/cohort_turnover.json); **MODEL ESTIMATE**: 120 of 406 expected to buy in 4 weeks under current patterns (reports/buyer_outcomes.json); **ASSUMED**: 4 pp coupon response; funding contract; margin; pool; **HYPOTHESIS**: an easy dinner restarted after a lapse (HYPOTHESIS); **PENDING**: 0 interviews | ABSTAIN: corpus does not support an answer | R1 interviews; R4 client form | coupon vs product/availability vs no action (plan A) |
| Yogurt buyer loss | Is the drop an availability, assortment, price or seasonal effect? | **MEASURED**: equal-window buyers 1194 -> 1111; not attrition, promotion or coverage (reports/trend_check_yogurt.json); **HYPOTHESIS**: availability / assortment fit; seasonality not separable; **PENDING**: store operations data | ABSTAIN: corpus does not support an answer | OPS1 operations check | whether plan B becomes a product/place fix |
| Unverified discovery of offers (public analogue) | Do assistants surface the analogue, and which sources are cited? | **OBSERVED (two Claude models)**: 20/20 answers; **VERIFIED EXTERNAL**: Google: no special requirements to appear in AI features (google_ai_features) | cites google_ai_features | R2 GEO answers | whether plan C is worth doing |
| Expensive / unconfirmed contact economics | Who funds the offer, how many consented households, what margin and costs? | **MEASURED**: historical retailer match 0.1723 of manufacturer coupon value (past lines only); **ASSUMED**: retailer-funded base; 7,308 reachable; $1,500 setup; $0.03 contact; **VERIFIED EXTERNAL**: ALDI online terms allow promotion codes (fetched); Kroger/Target/Walmart pages UNVERIFIED | CONFLICT between sources: 2469 (cj_pkg_index); 801 (cj_py_port_readme, report_model_card) | R4 client form; R3 retailer checks | the contract-specific pool thresholds that could reopen plan A |

## 3. Options compared (STP and 4 Ps; the lever must fit the diagnosed barrier)

| plan | segment (measurable / reachable / substantial) | lever and why | Product / Price / Place / Promotion | buyers (4 weeks) | contribution | status |
|---|---|---|---|---|---|---|
| A Frozen Pizza coupon | lapsing; 406 panel hh / consent unknown / 7,308 assumed | price lever only if price or habit is the barrier (unknown) | as is / $0.90 coupon / app / one message | 120.3 expected (current patterns, panel); +146 to +512 additional at assumed response (company); break-even +1,209 | -2,114 to -1,388 USD | no paid test (DEFER) |
| B Yogurt investigation | all yogurt buyers; store-level / no contact | product or place if the cause is availability or assortment; no discount until diagnosed | assortment review / check price moves / stock and shelf / none | 422.0 expected (panel); additional: unknown | unknown ($0 check) | READY task OPS1 |
| C Discovery content | public analogue; not linkable to the panel | promotion via content only if assistants show a gap | none / none / owned pages / content | not measurable from this data | unknown | conditional on 20 answers |
| D No paid action | — | default until evidence arrives | — | current patterns continue | $0 | **current choice** |
| E extra category (pre-registered criteria) | none qualified | — | — | — | — | report that no additional category meets the criteria |

Cross-sell is kept as a **negative finding**: only 1 of 56 pairs beats a popularity suggestion, by 0.06 pp.

## 4. Current decision and what reopens it
**DEFER FUNDING / NO SPEND WHILE TERMS ARE UNCONFIRMED**. Under the retailer-funded base, every coupon plan loses money. Under the shared or manufacturer contracts, setup needs this many consented households: SHARED_50_50 72422, MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE 37299, MANUFACTURER_FUNDED_NO_MATCH 17498 (the assumed pool is 7,308).

Verified inputs that would reopen it:
- a WRITTEN funding/reimbursement contract for the exact proposed offer (who pays the face value, who reimburses, any retailer match)
- if the contract is SHARED_50_50 (retailer share 0.5): a verified count of >= 72,422 eligible, consented, reachable households per cycle at the assumed 4 pp response and $1,500 setup (break-even response 3.15 pp)
- if the contract is MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE (retailer share 0.35): a verified count of >= 37,299 eligible, consented, reachable households per cycle at the assumed 4 pp response and $1,500 setup (break-even response 2.44 pp)
- if the contract is MANUFACTURER_FUNDED_NO_MATCH (retailer share 0.0): a verified count of >= 17,498 eligible, consented, reachable households per cycle at the assumed 4 pp response and $1,500 setup (break-even response 1.04 pp)
- finance-confirmed contribution margin and quoted setup and contact costs (re-run the scenario engine with them)
- redemption / opt-in mechanics of the offer (clip vs automatic), which set the subsidy to habitual buyers
- operations-confirmed stock capacity for the expected purchasing households
- credible response evidence (interviews pointing to price/habit, or a randomized result) supporting the response the plan needs

## 5. Work queue

| item | status | kind | title | owner | budget | due | success metric |
|---|---|---|---|---|---:|---|---|
| WI-F2031770 | READY | research | 2-3 consented interviews (lapsed frozen-pizza buyers, 1 nonbuyer) | Loutchiana (I01-I02), Charbel (I03) | $0 | 2026-11-24 | mi.evidence.interviews check = OK; barrier codes recorded |
| WI-66880A54 | READY | research | Freeze GEO panel and collect 20 fresh-chat answers | Loutchiana (Assistant 1), Charbel (Assistant 2) | $0 | 2026-11-24 | mi.seo.geo check complete_rows = 20 |
| WI-DA062A84 | READY | research | Verify Kroger / Target / Walmart / ALDI offer pages by hand | Charbel | $0 | 2026-11-22 | each row VERIFIED with date or stays UNVERIFIED |
| WI-682EC652 | READY | research | Send the client input form and load confirmed answers | both | $0 | 2026-11-22 | mi.decision.client_inputs check applies funding, pool, margin, costs, stock |
| WI-BFF5C649 | READY | operations | Yogurt availability / assortment / placement check | client store operations (via team) | $0 | 2026-11-27 | cause identified or ruled out (stock / assortment / price / none) |
| WI-673F452D | BLOCKED_PENDING_APPROVAL | public_content | Discovery content for the public analogue (only after R2 shows a gap) | both (draft only) | $0 | 2026-12-08 | mention/recommendation rate on a re-run panel; owned-page clicks (separately) |
| WI-7B888BD2 | BLOCKED_PENDING_APPROVAL | paid_contact | Frozen Pizza lapsing digital coupon test (design only) | category manager (named approver) | $1,938 | 2026-12-17 | incremental contribution per randomized household above the rollout hurdle |

READY items are $0 research or operations tasks. BLOCKED items need a named approver with a reason, plus verified consent and stock. No agent can approve, send, spend or launch.

## 6. Measurement plan
- **Before any action:** current-pattern buyers (MODEL ESTIMATE) and a scenario range (ASSUMED response). These are always shown separately.
- **After an action:** observed distinct buyers, net sales and costs in the 4-week window. Load outcomes into `data/pilot/pilot_outcomes.csv` with `pilot_meta.json`.
- **After a randomized test:** additional buyers and incremental contribution versus control, with intervals, from `mi.outcome.pilot`. The decision rule EXPANDs only above the rollout hurdle.
- **Without a randomized control:** observed buyers are never attributed to the action.

Advisor evaluation on pre-registered cases: 6/6 passed (`reports/advisor_eval.json`; deterministic roles, live LLM PENDING).
