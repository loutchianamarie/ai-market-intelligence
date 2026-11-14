# Decision brief and manager memo: dossier CJ-GROCERY-001

Status labels: **OBSERVED** (historical data/sources) · **MODEL ESTIMATE** · **ASSUMPTION** · **SIMULATION** · **FUTURE TEST**.

## One-page decision brief

| Item | Content |
|---|---|
| Decision owner | Category & CRM manager at the (anonymous) retailer. This is a hypothetical role. Finance approves budget; legal/privacy approves customer contact. |
| Costly problem | CRM budgets tend to go to the most *popular* categories and the *heaviest* buyers. Coupons sent to people who would buy anyway are subsidy, not growth (course primer §4: value net of cost to serve, not size). |
| Status-quo alternative | Popularity-led broad mailing of top categories. In our engine it is **over budget and loses ≈ $62k** in the base case (SIMULATION). |
| Options compared | (1) targeted category × segment × channel pilots; (2) popularity-led broad mailing; (3) **NONE: research/measure first** |
| Segment (behavioural, measurable) | **LAPSING category buyers**: bought the category in weeks −12..−5 but not in the last 4 weeks (OBSERVED from pre-cutoff data). Reachability requires consented contacts, which are UNKNOWN in public data. |
| Product scope | 8 food categories chosen by a written rule (`configs/policy.json`); alcohol/tobacco excluded as a guardrail. |
| Positioning hypothesis | *For lapsing frozen-pizza buyers who already shop with us weekly, a one-tap digital coupon makes the category easy to restart, unlike broad paper circulars, which reach everyone and mostly subsidise habitual buyers.* (Hypothesis to test, not a proven advantage.) |
| Named alternatives | Walmart, Target, Aldi (store alternatives); a paper circular or broad mailing (channel alternative) |
| 4 Ps | Product: frozen pizza (existing assortment; stock must be confirmed). Price: $0.90 coupon (OBSERVED historical mean). Place: existing stores + app. Promotion: one digital coupon with an opt-out line. |
| Journey (find → compare → buy → keep) | Find: weekly shop / app deals. Compare: price vs store brand vs other stores. Buy: redeem in basket. Keep: repeat in the next 4–8 weeks. Hypothesised friction: *lapsed habit*, not awareness. |
| Qualitative question (buyers **and** nonbuyers) | "Tell me about the last time you bought frozen pizza. What did you buy instead in the weeks you didn't?" Ask lapsed buyers *and* shoppers who never buy the category. |
| Budget constraint | $25,000 illustrative cap (ASSUMPTION); pilot draft $1,641 (SIMULATION) |
| Decision-changing research question | *Is the coupon-driven uplift among lapsing buyers at least the break-even rate (6.4 pp at base assumptions)?* |
| Primary metric / horizon | Incremental contribution per randomized eligible household after coupon and contact costs, 28 days (+56-day follow-up) |
| Guardrails | opt-out ≤ 2%, complaints ≤ 0.5%, no stock-outs, no age-restricted categories |
| Uncertain inputs | margin, redemption among would-buy households, contact cost, digital reach, deployment scale, uplift (all ASSUMPTION) |

## Agent goal (proposed plan, not an achieved result)

Within seven project days, produce **one** evidence-backed pilot chosen from at least **three** feasible options plus NONE, under an illustrative capped budget, with a 28-day randomized holdout whose primary metric is incremental contribution per eligible household. Prototype metric: one approved sandbox pilot and zero unsafe actions (the blocked-path log proves this). Commercial metric: incremental contribution after costs, measurable only in a future real pilot.

## Manager memo (conditional)

**To:** Category & CRM manager · **Re:** next CRM budget · **Recommendation: no rollout. Fund one small randomized learn-first test.**

1. **What the data show (OBSERVED).** A fitted model ranks next-4-week category buyers better than a "bought it recently" rule. Average precision is 0.662 vs 0.621; the household-bootstrap 95% CI for the gain is +0.038 to +0.045. Both are far better than category popularity (0.352). Past campaign recipients already spent **2.0–2.6× more per week before** campaigns began, so past campaign results cannot be read as effects.
2. **What the money says (SIMULATION, labelled assumptions).** At base assumptions (28% margin, 35% of would-buy households redeem, $0.50 mail / $0.03 digital contact, 40× deployment scale), **no plan breaks even**. Every mailed coupon loses money on every household; the popularity-led mailing is the worst option. The model's value is in *excluding* likely buyers to cut subsidy, and that matters only if uplift is high enough.
3. **What would change the choice.** The plan flips to *Frozen Pizza / lapsing / digital / model-filtered* if true uplift is about **2× the assumption at ~250k households** or **3× at ~100k**. Per household, that cohort needs a **6.4 pp** incremental purchase rate vs the 4.0 pp assumed (1.6×), which is the closest of any cohort.
4. **Therefore.** Run a 50/50 customer-level holdout on consented lapsing frozen-pizza buyers: **866 households per arm** detects the break-even uplift at 80% power. Simulated cost ≈ $1,641, mostly the assumed setup fee. Finance must confirm margin; operations must confirm stock; legal must confirm consent. **Expand only if the CI lower bound of incremental contribution is > 0 and guardrails pass. Stop if the upper bound is < 0.**
5. **What this is not.** It is not a profit forecast and not a claim that coupons work. The 2,469-household panel is too small to run the test itself (406 lapsing frozen-pizza households), so it must run on the retailer's consented base.
