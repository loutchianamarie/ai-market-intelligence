# Marketing strategy and plan: Cold Cereal

**Decision from the card: NO PAID OFFER.** Cold Cereal: 655 of 2,319 scored households are expected to buy in the next 4 weeks (model estimate); no paid offer.
**Approval:** PENDING_HUMAN (sandbox only: nothing is sent, spent or published).

## 1. Objective

Within 13 weeks, find out whether a reminder brings back lapsing Cold Cereal households, measured against a randomized no-message holdout, and decide whether to scale, change or stop.

- **Baseline:** 421 lapsing households; model estimate of their chance of buying in the next 4 weeks is 29%.
- **Hurdle:** Act on a measured lift of at least 14.2 percentage points in the 4-week purchase rate (the break-even response under assumed economics).
- _PROPOSED TARGET: a hurdle to test against, not a forecast._

## 2. Segmentation, targeting, positioning

| segment | households | what it means | approach |
|---|---:|---|---|
| ACTIVE_NONBUYER | 638 | shops often but has not bought the category in 12 weeks | Educate |
| LAPSING | 421 | bought earlier in the 12 weeks, nothing in the last 4 | Win back |
| LOW_ACTIVITY | 503 | few baskets in 12 weeks | Do not spend |
| RECENT_LIGHT | 324 | bought 1-2 times in 12 weeks, at least once in the last 4 | Nurture |
| REGULAR | 433 | buys the category in 3+ of the last 12 weeks | Defend |

**Target first:** LAPSING. **Then:** RECENT_LIGHT, ACTIVE_NONBUYER.
**Do not target with offers:** REGULAR (They buy anyway: a discount gives margin away. Defend with recognition and cross-sell, no price offer.); LOW_ACTIVITY (Few baskets: no category action is worth its cost.)

**Positioning (hypothesis):** Your usual Cold Cereal, easy to find and easy to pick up again. Often bought together with Yogurt (association in baskets, validated on held-out weeks)

## 3. Strategy by segment

| segment | approach | what we do | paid offer | KPI |
|---|---|---|---|---|
| ACTIVE_NONBUYER | Educate | Educational content and placement near related categories; no paid offer until a test shows response. | DOES NOT PAY | first-time category buyers in 4 weeks, versus holdout |
| LAPSING | Win back | Check availability, assortment and price versus competitors first (a reason to stop buying is often stock or range), then a reminder message. | DOES NOT PAY | distinct buyers back within 4 weeks, versus a randomized no-message holdout |
| LOW_ACTIVITY | Do not spend | General brand communication only; no category action. | NOT EVALUATED (no paid action for this segment) | none (no action) |
| RECENT_LIGHT | Nurture | Replenishment reminder and recipe or usage content in owned channels before any discount; confirm the product is in stock. | DOES NOT PAY | share who buy again within 4 weeks |
| REGULAR | Defend | No discount: these households buy anyway, so a coupon mostly gives margin away. Recognise loyalty and cross-sell a partner category. | DOES NOT PAY | category purchase frequency and basket size; discount cost per buyer stays at zero |

## 4. Marketing mix and channels

- **Product:** Confirm Cold Cereal availability and range first; partner offer: Yogurt
- **Price:** No blanket discount; a coupon only where the test shows response and the margin covers it
- **Place:** Digital owned channels and in-store placement near related categories
- **Promotion:** Reminder and content in owned channels; a paid coupon only after a randomized test

| channel | role | type | cost |
|---|---|---|---|
| In-store availability, range and placement | fix reasons for lapsing first; place beside related categories | free | no media cost |
| Owned digital message (e-mail or app) | reminder and content, no discount | owned | 0.03 USD per message (ASSUMED) |
| Content page for the learning questions (SEO/GEO) | be recommended when shoppers are still choosing | free | staff time; needs approval G3 |

## 5. 13-week roadmap

| phase | weeks | task | owner | deliverable | type | gates |
|---|---|---|---|---|---|---|
| 0. Approve | 0 | Review and approve (or change) this plan | Marketing lead (named approver) | Signed-off plan | free | G1 |
| 1. Diagnose | 1-2 | Check Cold Cereal availability, range and price against competitors | Store operations | Short findings note | free | - |
|  |  | Run 2 to 3 short interviews with lapsed shoppers: price, habit, stock or switching? | Marketing analyst | Coded interview sheet | free | - |
|  |  | Collect margin, message cost, consent pool, coupon funding and stock capacity | Finance and CRM | Completed client input form | free | - |
|  |  | Verify consent and stock | CRM and operations | Verification record | free | G2 |
| 2. Prepare | 3-4 | Randomize eligible lapsing households into holdout and reminder only (no discount) | Analytics | Randomized list with a fixed seed | free | - |
|  |  | Finalize message drafts (no price or discount in reminders) | Marketing | Approved drafts | free | - |
|  |  | Draft the factual page for the learning questions | Content and SEO | Draft page | free | G3 |
|  |  | Set up daily guardrail monitoring: opt-outs, complaints, stock-outs | CRM and operations | Guardrail dashboard | free | - |
|  |  | Approve the test launch | Marketing lead (named approver) | Launch decision | free | G4 |
| 3. Run | 5-8 | Send reminders to the reminder arm | CRM | Send log (outside this tool) | owned | G2, G4 |
|  |  | Keep the holdout untouched and monitor guardrails weekly | Analytics | Weekly guardrail note | free | - |
| 4. Read | 9-10 | Analyse purchase rate and contribution per household in the 28-day window with a 95% interval | Analytics | Result table and chart | free | - |
| 5. Decide | 11-13 | Apply the decision rule and update the plan with confirmed margin and cost | Marketing lead and finance | Decision memo | free | G5 |

**Gates:** G1 = Plan approved by a named person; G2 = Consent to contact and stock confirmed (UNKNOWN today); G3 = Public content approved by a named person; G4 = Test launch approved: arms, holdout and guardrails; G5 = Decision meeting: expand, stop or change

## 6. Budget (scenario: assumed contact cost, redemption, coupon value and setup)

Households per arm: 179.

| arm | type | cost (USD) |
|---|---|---:|
| Holdout (no message) | control | 0 |
| Reminder, no discount | owned | 5 |
| Fixed setup (assumed) | | 1,500 |
| **Total** | | **1,505** |

Paid items stay blocked until gates G2 and G4 pass; nothing is spent by this plan.

## 7. KPIs and decision rules

- **Primary:** incremental contribution per randomized eligible household after coupon and contact cost, 28 days
- **Secondary:** distinct buyers in the category; repeat purchase within 4 weeks; opt-out rate
- **Guardrails:** {'opt_out_rate_max': 0.02, 'complaint_rate_max': 0.005, 'stockout_flag': False}
- **Expand if:** 95% CI lower bound > 0 and all guardrails pass
- **Stop if:** 95% CI upper bound < 0 or any guardrail fails
- **Change if:** point estimate > 0 but CI includes 0 and guardrails pass

## 8. Message drafts (not sent)

| segment | angle | draft subject |
|---|---|---|
| REGULAR | recognise loyalty, show what is new | Thanks for being a regular: what is new in cold cereal |
| RECENT_LIGHT | make restocking easy | Your cold cereal is easy to restock |
| LAPSING | a reminder that the habit is easy to pick up again | Your usual cold cereal, back on your list |
| ACTIVE_NONBUYER | help choosing, no offer | How to choose cold cereal: a short guide |

## 9. Discovery (SEO/GEO)

Kroger (public analogue): recommended in 0 of 8 Learn answers. Publish a factual page for the learning questions (how digital coupons work, store brand versus name brand); needs human approval; no sales effect is claimed.

## 10. Risks and how we handle them

| risk | mitigation | owner |
|---|---|---|
| Discounting people who would buy anyway | No price offer to regular buyers; the coupon arm is limited to the target segment; the holdout shows the real response | Marketing |
| Promoting a product that is out of stock | Stock confirmed before launch (gate G2) and a stock-out guardrail during the test | Operations |
| Contacting people without consent | Only the consented pool is contacted (gate G2); opt-out rate is a stop condition | CRM and legal |
| A misleading result from seasonality or contamination | Randomize inside the same weeks, keep the holdout clean, and read the interval, not the point estimate | Analytics |
| Over-trusting the model | Use it to order lists. Basis: on held-out weeks the model beats the simple repeat rule by 0.050 average precision (95% interval 0.045 to 0.056), history only. Success is judged on the holdout, not on the score | Analytics |
| Assumed margin, cost or response are wrong | Finance confirms them in phase 1 and the break-even is recomputed before any scale-up | Finance |
| The discovery content has no proven sales effect | Track visibility in assistant answers only; do not claim sales | Content and SEO |

## 11. What we need from the client

- Consent: how many households can be contacted, and how (UNKNOWN)
- Margin on the category (ASSUMED)
- Cost per message and per coupon redemption (ASSUMED)
- Who funds the coupon: retailer or manufacturer (ASSUMED)
- Stock and capacity for the category (UNKNOWN)
- The campaign calendar, to avoid clashes (UNKNOWN)

_Checker: PASS._
