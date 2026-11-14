# Decision card: next CRM / category budget

**Recommendation now:** NONE: research / measure first (no rollout, no funded coupon test).
Live dossier `OPP-5A2E65C8`; a named person still has to reject or approve in app tab 4.

## Why
- Every modelled coupon plan loses money at the stated assumptions (best: COFFEE/LAPSING/digital_coupon/ALL -1,724 USD per 4-week cycle at an assumed scale).
- A better purchase model does not rescue a negative incremental contribution. AP is 0.672 vs the rule's 0.621, and at 1,000 contacts the model finds +22 more future buyers than recency; these are buyers *identified*, not persuaded.
- Varying one input at a time, only true response ≥ 4.14× the assumption flips the choice.
- Varying inputs jointly over a grid (response 1–3×, retailer vs manufacturer funding, scale 40–250×, setup $750–1,500, margin 28–35%), 55 of 96 combinations flip it. Each grid value is an *assumed* alternative. The decision is therefore fragile to joint assumptions and holds only because none of these changes is confirmed.

## Minimum evidence before any coupon action
| input | why it decides | current status |
|---|---|---|
| who funds the coupon | manufacturer funding cuts the retailer's cost to its match share (≈35% for Frozen Pizza) | ASSUMED retailer-funded |
| consented reachable pool | spreads the $1,500 setup; decides whether a decision-grade test fits | UNKNOWN |
| unit margin | sets the value of each extra buyer | ASSUMED 28% |
| communication cost and offer mechanics | contact cost; automatic offers subsidise habitual buyers | ASSUMED |
| stock | no promotion without supply | UNKNOWN |
| causal response (randomized) | the only way to know whether contact changes buying | UNKNOWN; history is selection |

## What to do this week (zero spend)
1. Ask the client for coupon funding, pool size, margin, costs and stock, then re-run `python -m mi.cli all`.
2. Interviews: why did lapsed buyers stop? This decides between a coupon, the product, availability and no action.
3. Operations check on the shrinking category (card C3).
4. Collect the 20 GEO answers before any content work (card C4).

Full cards: `docs/opportunity_cards.md`. Claims with provenance: `reports/current_claims.json`.
