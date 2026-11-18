# Decision card: Ice Cream/Milk/Sherbts

**Decision: NO PAID OFFER.** Ice Cream/Milk/Sherbts: 579 of 2,319 scored households are expected to buy in the next 4 weeks (model estimate); no paid offer.

**Action:** Free actions only: availability and range check, owned-channel reminders, content
**Approval:** PENDING_HUMAN (sandbox only; nothing is sent, spent or published).

## 1. Who (model estimate, history only)

| segment | households | chance of buying | expected buyers | what it means |
|---|---:|---:|---:|---|
| REGULAR | 296 | 66% | 194 | buys the category in 3+ of the last 12 weeks |
| LAPSING | 444 | 27% | 121 | bought earlier in the 12 weeks, nothing in the last 4 |
| ACTIVE_NONBUYER | 744 | 15% | 114 | shops often but has not bought the category in 12 weeks |
| RECENT_LIGHT | 311 | 35% | 109 | bought 1-2 times in 12 weeks, at least once in the last 4 |
| LOW_ACTIVITY | 524 | 8% | 40 | few baskets in 12 weeks |

## 2. Does a paid offer pay? (scenario, not measured)

| segment | verdict | contribution low / base / high (USD per 4 weeks) | response needed vs assumed |
|---|---|---|---:|
| LAPSING | **DOES NOT PAY** | -2,849 / -2,652 / -1,922 | 14.23x |
| ACTIVE_NONBUYER | **DOES NOT PAY** | -2,906 / -2,795 / -2,356 | 24.67x |
| RECENT_LIGHT | **DOES NOT PAY** | -2,792 / -2,536 / -2,350 | 28.17x |
| REGULAR | **DOES NOT PAY** | -2,955 / -3,256 / -4,007 | 121.99x |

## 3. Next best action by segment

| segment | do now (free) | paid offer | KPI |
|---|---|---|---|
| REGULAR | No discount: these households buy anyway, so a coupon mostly gives margin away. Recognise loyalty and cross-sell a partner category. | DOES NOT PAY | category purchase frequency and basket size; discount cost per buyer stays at zero |
| RECENT_LIGHT | Replenishment reminder and recipe or usage content in owned channels before any discount; confirm the product is in stock. | DOES NOT PAY | share who buy again within 4 weeks |
| LAPSING | Check availability, assortment and price versus competitors first (a reason to stop buying is often stock or range), then a reminder message. | DOES NOT PAY | distinct buyers back within 4 weeks, versus a randomized no-message holdout |
| ACTIVE_NONBUYER | Educational content and placement near related categories; no paid offer until a test shows response. | DOES NOT PAY | first-time category buyers in 4 weeks, versus holdout |
| LOW_ACTIVITY | General brand communication only; no category action. | NOT EVALUATED (no paid action for this segment) | none (no action) |

## 4. Recommendation

No coupon plan for this category pays under the assumptions, even when every assumption is favourable. Use free actions, check stock and range, and learn more before any paid offer.

**Conditions:** Consent to contact is verified (UNKNOWN today); Stock is confirmed for the category (UNKNOWN today); Finance confirms margin and cost per message (ASSUMED today); A named person approves the exact plan

**Would reverse if:** A randomized test shows a measured response above the break-even response; A manufacturer funds the coupon, or the confirmed margin is higher than assumed; Stock or range problems are found: fix those first

## 5. How to learn the real response (LAPSING)

- Design: randomized: eligible households split at random into message and no-message holdout (about 10-20% holdout)
- Primary metric: incremental contribution per randomized eligible household after coupon and contact cost, 28 days
- Households per arm: 2,026 for the assumed response, 11 for the break-even response
- Expand if: 95% CI lower bound > 0 and all guardrails pass; stop if: 95% CI upper bound < 0 or any guardrail fails
- Guardrails: {'opt_out_rate_max': 0.02, 'complaint_rate_max': 0.005, 'stockout_flag': False}

## 7. Discovery (observed audit of a public analogue)

Kroger: mentioned in 5 of 8 Learn answers and recommended in 0. Shoppers who are still learning are not being recommended a store. Publish a factual page for the learning questions (how digital coupons work, store brand versus name brand); needs human approval; no sales effect is claimed.

## 8. Marketing mix

- **Product:** Confirm Ice Cream/Milk/Sherbts availability and range first
- **Price:** No blanket discount; a coupon only where the test shows response and the margin covers it
- **Place:** Digital owned channels and in-store placement near related categories
- **Promotion:** Reminder and content in owned channels; a paid coupon only after a randomized test

## 9. What we are sure of, and what we are not

- **who is likely to buy:** MEDIUM-HIGH (MODEL ESTIMATE). locked test average precision 0.672 versus 0.621 for the repeat rule; gain +0.050 (95% interval +0.045 to +0.056); history only, 2017
- **what an offer would do:** LOW (UNKNOWN). coupon exposure was not randomized; response is an assumed range
- **profit:** NONE (UNKNOWN). margin, cost, consent and stock are not confirmed; contributions are scenarios

**Unknown or assumed:** contribution margin (ASSUMED); cost per message (ASSUMED); consent to contact (UNKNOWN); stock and capacity (UNKNOWN); who funds the coupon (ASSUMED); real response to an offer (UNKNOWN)

_Rule: robust: positive even with every assumption unfavourable; base case: positive under base assumptions; only if optimistic: positive only with every assumption favourable; does not pay: never positive._
_Checker: PASS._
