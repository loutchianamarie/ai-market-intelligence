# Decision card: Coffee

**Decision: LEARN FIRST (NO PAID SCALE-UP).** Coffee: 374 of 2,319 scored households are expected to buy in the next 4 weeks (model estimate); learn first (no paid scale-up).

**Action:** Free actions now, plus a randomized holdout test design for the lapsing segment
**Approval:** PENDING_HUMAN (sandbox only; nothing is sent, spent or published).

## 1. Who (model estimate, history only)

| segment | households | chance of buying | expected buyers | what it means |
|---|---:|---:|---:|---|
| REGULAR | 213 | 63% | 135 | buys the category in 3+ of the last 12 weeks |
| LAPSING | 355 | 23% | 82 | bought earlier in the 12 weeks, nothing in the last 4 |
| ACTIVE_NONBUYER | 983 | 7% | 70 | shops often but has not bought the category in 12 weeks |
| RECENT_LIGHT | 206 | 32% | 65 | bought 1-2 times in 12 weeks, at least once in the last 4 |
| LOW_ACTIVITY | 562 | 4% | 23 | few baskets in 12 weeks |

## 2. Does a paid offer pay? (scenario, not measured)

| segment | verdict | contribution low / base / high (USD per 4 weeks) | response needed vs assumed |
|---|---|---|---:|
| LAPSING | **PAYS ONLY IF OPTIMISTIC** | -2,663 / -1,724 / 984 | 1.61x |
| ACTIVE_NONBUYER | **PAYS ONLY IF OPTIMISTIC** | -2,804 / -1,988 / 1,276 | 2.28x |
| RECENT_LIGHT | **DOES NOT PAY** | -2,620 / -1,795 / -624 | 3.22x |
| REGULAR | **DOES NOT PAY** | -2,704 / -2,214 / -1,866 | 14.0x |

## 3. Next best action by segment

| segment | do now (free) | paid offer | KPI |
|---|---|---|---|
| REGULAR | No discount: these households buy anyway, so a coupon mostly gives margin away. Recognise loyalty and cross-sell a partner category. | DOES NOT PAY | category purchase frequency and basket size; discount cost per buyer stays at zero |
| RECENT_LIGHT | Replenishment reminder and recipe or usage content in owned channels before any discount; confirm the product is in stock. | DOES NOT PAY | share who buy again within 4 weeks |
| LAPSING | Check availability, assortment and price versus competitors first (a reason to stop buying is often stock or range), then a reminder message. | PAYS ONLY IF OPTIMISTIC | distinct buyers back within 4 weeks, versus a randomized no-message holdout |
| ACTIVE_NONBUYER | Educational content and placement near related categories; no paid offer until a test shows response. | PAYS ONLY IF OPTIMISTIC | first-time category buyers in 4 weeks, versus holdout |
| LOW_ACTIVITY | General brand communication only; no category action. | NOT EVALUATED (no paid action for this segment) | none (no action) |

## 4. Recommendation

No segment pays in the base case. The lapsing coupon is positive only if every assumption is favourable at once, so measure the real response before spending.

**Conditions:** Consent to contact is verified (UNKNOWN today); Stock is confirmed for the category (UNKNOWN today); Finance confirms margin and cost per message (ASSUMED today); A named person approves the exact plan

**Would reverse if:** A randomized test shows a measured response above the break-even response; A manufacturer funds the coupon, or the confirmed margin is higher than assumed; Stock or range problems are found: fix those first

## 5. How to learn the real response (LAPSING)

- Design: randomized: eligible households split at random into message and no-message holdout (about 10-20% holdout)
- Primary metric: incremental contribution per randomized eligible household after coupon and contact cost, 28 days
- Households per arm: 1,846 for the assumed response, 734 for the break-even response
- Expand if: 95% CI lower bound > 0 and all guardrails pass; stop if: 95% CI upper bound < 0 or any guardrail fails
- Guardrails: {'opt_out_rate_max': 0.02, 'complaint_rate_max': 0.005, 'stockout_flag': False}

## 6. Cross-sell (observed association, validated on held-out weeks)
- Baskets containing Coffee also contain Soup 2.84 times as often as chance (95% interval 2.68 to 3.01); an association, not proof of cause
- Baskets containing Coffee also contain Cold Cereal 2.64 times as often as chance (95% interval 2.48 to 2.79); an association, not proof of cause

## 7. Discovery (observed audit of a public analogue)

Kroger: mentioned in 5 of 8 Learn answers and recommended in 0. Shoppers who are still learning are not being recommended a store. Publish a factual page for the learning questions (how digital coupons work, store brand versus name brand); needs human approval; no sales effect is claimed.

## 8. Marketing mix

- **Product:** Confirm Coffee availability and range first; partner offer: Soup
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
