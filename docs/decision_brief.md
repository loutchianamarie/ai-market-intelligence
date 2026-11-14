# Manager memo: CRM budget decision (dossier CJ-GROCERY-001)

**Labels:** HISTORICAL OBSERVATION · MODEL ESTIMATE · ASSUMPTION · SIMULATED WORKFLOW · FUTURE EXPERIMENT · COMPANY SCALE ASSUMED.
Revised 2026-11-14 after the verification pass (`docs/verification_and_claim_audit.md`). This supersedes the overnight version; dossier `OPP-80476CCD` (866/arm design) is superseded and must not be approved.

**To:** Category & CRM manager (hypothetical role; finance approves budget, legal/privacy approves contact)
**Decision:** where to put the next limited CRM budget (category × existing-household segment × channel), and what to test before expanding.
**Recommendation:** **Do not roll out at these assumptions.** First do the cheap research below. Run a randomized learn-first test only if its launch conditions are met and its cost is justified.

## 1. What the real data show (HISTORICAL OBSERVATION; 2,469 anonymized frequent-shopper households, 2017)
- A fitted model ranks *who buys a category in the next 4 weeks* better than a "bought it recently" rule. Average precision is 0.662 vs 0.621 (popularity 0.352; base rate 0.275) on an untouched final window.
  - The gap is similar in all three non-training windows (+0.037, +0.043, +0.041).
  - A paired household bootstrap gives +0.037 to +0.046. That interval reflects household sampling within one holiday window only.
- **What the model is not:** it estimates purchase *under historical conditions*. It does **not** tell us who would buy without a coupon, or whom a coupon would persuade.
- Households that received past campaigns spent **2.0–2.6× more per week before** those campaigns. Ever-recipients vs never-recipients differ 4.1× in early weeks. Campaign history shows **selection**, not campaign effect.
- The model is weak for households with no recent category history: AP 0.198 against a base rate of 0.104. The repeat rule has no signal there at all.

## 2. Segment, positioning, 4 Ps
- **Segment (behavioural, measurable):** LAPSING frozen-pizza buyers, who bought in weeks −12..−5 and not in the last 4. There are 406 in the panel; model mean probability of buying in the next 4 weeks is 0.305 (MODEL ESTIMATE).
  - It changes the action: it is the cohort closest to break-even.
  - It is **reachable only with consent and a digital account**. Every analogue retailer's digital offers require sign-in (§5). The panel households themselves are anonymized and cannot be contacted.
- **Positioning hypothesis (to test in interviews):** *For lapsing frozen-pizza buyers who already shop with us weekly, a one-tap digital coupon makes the category easy to restart, unlike broad paper circulars that reach everyone, including habitual buyers.*
- **4 Ps:**
  - Product: existing frozen pizza range; stock is UNKNOWN.
  - Price: $0.90 coupon (historical mean).
  - Place: stores + app.
  - Promotion: one digital message with opt-out, no price superlatives.
- **Journey (Learn → Browse → Buy → Keep):** the likely friction is *Keep*, i.e. a lapsed habit. Awareness is not the problem for weekly shoppers. If interviews point to price or product (e.g., switching to store brand), a coupon is the wrong lever.

## 3. Options (ASSUMPTION-based scenarios; per contacted household first, then company scale)

| Option | Per 1,000 contacted, before setup | 4-week net at **assumed** 40× scale | Status |
|---|---:|---:|---|
| Popularity-led broad mailing (status quo) | −$651 | −$61,914 | **Infeasible** (over the $25k cap) |
| Best targeted plan: Coffee / lapsing / digital | −$44 | −$1,781 (favourable case +$875) | feasible, loses at base |
| Frozen Pizza / lapsing / digital | −$47 | −$1,843 | feasible, loses at base; closest to break-even (needs 1.6× the assumed uplift per household) |
| **NONE: research first** | $0 | $0 | recommended at base |

A negative per-1,000 value means the plan loses on *every* contacted household before fixed costs, so **no company scale rescues it**. The reversals in the app (e.g., Frozen Pizza at 2× uplift with ~250k households) need *both* higher true uplift *and* a hypothetical company scale. The 100k/250k figures are not in the data.

The "model-filtered" audience wins in some scenarios only because of **Assumption A1**: coupon cost to baseline buyers is approximated by historical propensity, and uplift is constant within a segment. That makes it a **stratification hypothesis** for a test, not measured targeting.

## 4. Break-even and the test (FUTURE EXPERIMENT, not performed)
- **Break-even uplift for Frozen Pizza / lapsing / digital:** **6.4 pp** of extra 4-week purchase, vs 4.0 pp assumed.
- **The overnight 866-per-arm design was wrong for this decision.** It only detects uplift *at* break-even, where contribution is zero. With 866 per arm, an EXPAND decision would need true uplift ≥ 17.4 pp.
- **Decision-grade design:** a contribution-based 50/50 holdout, stratified by model-score half, needs about **2,623 households per arm** if true uplift is 2× break-even.
  - If true uplift is only 1.5× break-even, it needs ~10,500 per arm.
  - It requires **≥ 5,246 eligible, consented households**. That is feasible only under the *assumed* company scale (7,308).
  - Assumed cost: **$1,927** (2,623 × $0.163 + $1,500 setup).
- **Worth-it check (SIMULATION):** at the assumed scale, the best plan's *favourable* case nets ~$875 per 4-week cycle, so the test pays back only after ~2 favourable cycles and never at base assumptions.
- **Launch preconditions (all UNKNOWN today):** consented pool ≥ 5,246; stock confirmed; margin confirmed by finance; consent/legal sign-off; decision value > test cost.
- **Prewritten rule:** EXPAND if the 95% CI lower bound of incremental contribution per household is > 0 and guardrails pass (opt-out ≤ 2%, complaints ≤ 0.5%, no stock-outs). STOP if the upper bound is < 0 or any guardrail fails. CHANGE if positive but uncertain; otherwise INCONCLUSIVE.

## 5. Public market comparison (analogue only; search summaries of official pages, retrieved 2026-11-14; verify verbatim before quoting)

| Retailer | Digital-offer mechanic (official page) | Implication |
|---|---|---|
| Kroger ([coupons](https://www.kroger.com/savings/cl/coupons/), [cash-back FAQ](https://www.kroger.com/hc/help/faqs/ways-to-save/cash-back)) | Clip to a digital account / Shopper's Card; applied at checkout; a household load limit is mentioned | Reach requires a digital account: consent share is a real gate |
| Target ([Circle offers help](https://www.target.com/help/articles/target-circle/target-circle-offers)) | Sign in and save offers; most apply at checkout via app/Wallet or phone number | Same account gate |
| Walmart ([manufacturer offers](https://www.walmart.com/cp/manufacturer-offers/7524254)) | Offers claimed in the app pay out as Walmart Cash after purchase, not a register discount | A rebate model, not a coupon discount |
| ALDI ([FAQ](https://www.aldi.us/about-us/faqs/aldi-gift-cards/)) | No manufacturer coupons; no online coupons; occasional printed or mailed regional coupons | Everyday-low-price positioning: the alternative to couponing altogether |

These describe *public* offer mechanics. They cannot be joined to the anonymized households, and they say nothing about those retailers' results.

## 6. What to do this week (cheap research before any spend)
1. 2–3 consented interviews with lapsed and nonbuying shoppers (`docs/team_tasks.md`).
2. 20 GEO answers (the discovery question; separate from sales).
3. Ask the hypothetical client for the four missing inputs: consented digital pool size, margin, contact cost, stock.
4. Re-run the app with those inputs. Approve a test **only** if the per-1,000 value turns positive under plausible uplift **and** the pool supports the contribution-based sample size.
