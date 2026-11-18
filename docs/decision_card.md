# Decision card: next CRM / category budget

**Advisor status:** DEFER FUNDING / NO SPEND WHILE TERMS ARE UNCONFIRMED. **Base case:** RETAILER-FUNDED offer (retailer pays the full coupon face value): the current base case.
**Recommendation now:** NONE: research / measure first: no rollout, no funded coupon test, no spend or send. Live dossier `OPP-7177E5FC`; a named person still has to decide in app tab 4.

## Why
- Under the retailer-funded base case every modelled coupon plan loses money (best: COFFEE/LAPSING/digital_coupon/ALL -1,724 USD per 4-week cycle at an assumed scale).
- A better purchase model does not rescue negative incremental contribution. AP is 0.672 vs the rule's 0.621, and the model finds +22 more future buyers per 1,000 contacts; these are buyers *identified*, not persuaded.
- Historical retailer match on past coupon lines is 17.2% of manufacturer coupon value overall and 35.0% for Frozen Pizza (value-weighted). This is OBSERVED for past lines; it does not tell us who would fund OUR offer.

## Same Frozen Pizza plan under each funding contract (assumed 4 pp response, 7,308 assumed pool, $1,500 setup)

| contract | contribution per contacted household | break-even response | pool needed to cover setup | recommendation | selected grid cases reversing NONE |
|---|---:|---:|---|---|---|
| RETAILER_FUNDED | -0.044 | 6.23 pp | none: negative per household | NONE: research / measure first | 9 of 36 (not a probability) |
| SHARED_50_50 | +0.021 | 3.15 pp | 72422 | NONE: research / measure first | 22 of 36 (not a probability) |
| MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE | +0.040 | 2.44 pp | 37299 | NONE: research / measure first | 24 of 36 (not a probability) |
| MANUFACTURER_FUNDED_NO_MATCH | +0.086 | 1.04 pp | 17498 | NONE: research / measure first | 30 of 36 (not a probability) |

Grid cases were selected by us, so counts are not probabilities. The minimal reversing combinations are in `docs/funding_contracts.md`.

## Verified inputs that would reopen the decision
- a WRITTEN funding/reimbursement contract for the exact proposed offer (who pays the face value, who reimburses, any retailer match)
- if the contract is SHARED_50_50 (retailer share 0.5): a verified count of >= 72,422 eligible, consented, reachable households per cycle at the assumed 4 pp response and $1,500 setup (break-even response 3.15 pp)
- if the contract is MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE (retailer share 0.35): a verified count of >= 37,299 eligible, consented, reachable households per cycle at the assumed 4 pp response and $1,500 setup (break-even response 2.44 pp)
- if the contract is MANUFACTURER_FUNDED_NO_MATCH (retailer share 0.0): a verified count of >= 17,498 eligible, consented, reachable households per cycle at the assumed 4 pp response and $1,500 setup (break-even response 1.04 pp)
- finance-confirmed contribution margin and quoted setup and contact costs (re-run the scenario engine with them)
- redemption / opt-in mechanics of the offer (clip vs automatic), which set the subsidy to habitual buyers
- operations-confirmed stock capacity for the expected purchasing households
- credible response evidence (interviews pointing to price/habit, or a randomized result) supporting the response the plan needs

## What to do this week (zero spend)
1. Send the client input form (`docs/client_input_form.md`); load the answers with `python -m mi.decision.client_inputs` and re-run `python -m mi.cli all`.
2. Interviews: why did lapsed buyers stop? This decides between a coupon, the product, availability and no action.
3. Operations check on the Yogurt signal (card C3); keep the weak cross-sell (C2) as a negative finding.
4. Before any content work (card C4): the GEO audit is complete (20/20, Claude models only): score impact and effort, then re-run the frozen panel in ChatGPT and Gemini.

Full cards: `docs/opportunity_cards.md`. Claims with provenance: `reports/current_claims.json`.
