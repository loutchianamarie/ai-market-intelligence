# Client input form (send to the client; do not fill in on their behalf)

Answer only what you can confirm. Give a **source** (document, system or person) and a **date** for each answer.
Blank answers stay ASSUMED or UNKNOWN in the model. Return the answers as `data/client_inputs/client_inputs.json`, a copy of `client_inputs_TEMPLATE.json`.

| # | Question | Unit / allowed values | Scenario-engine field it sets |
|---|---|---|---|
| 1 | Who funds the EXACT proposed digital offer (retailer, manufacturer or shared), and who reimburses whom? | text: retailer / manufacturer / shared + reimbursement terms | `scenario.coupon_funding.contract.funder_and_reimbursement` |
| 2 | What share of the offer's face value does the RETAILER bear after any reimbursement (incl. any retailer match)? | 0..1 | `scenario.coupon_funding.retailer_share.value` |
| 3 | Face value of the proposed offer per redemption. | USD > 0 | `scenario.coupon_face_value.value` |
| 4 | How is the offer redeemed / opted into (clip to card, automatic at checkout, code at checkout)? | clip_to_card / automatic_at_checkout / code_at_checkout | `scenario.offer_mechanics.mechanic` |
| 5 | Of contacted households who would buy anyway, what share redeem the offer (from your past digital offers)? | 0..1 | `scenario.redemption_share_of_buyers.value` |
| 6 | Active loyalty households in the eligible base (all segments). | count | `scenario.deployment_scale.value (= answer / 2,469 panel households)` |
| 7 | Of those, households with valid consent for digital offers. | count | `scenario.channels.digital_coupon.reach_share.value (= answer / active_customer_households)` |
| 8 | Contribution margin on the category's retailer receipts (after cost of goods, before marketing). | 0..1 | `scenario.contribution_margin_rate.value` |
| 9 | One-off setup cost per campaign wave (creative, configuration, QA, legal review). | USD | `scenario.fixed_setup_per_plan.value` |
| 10 | Cost per digital contact (send + platform fee). | USD per household | `scenario.channels.digital_coupon.contact_cost.value` |
| 11 | For each category, how many purchasing households among CONTACTED households can stock support per 4 weeks (baseline + extra buyers)? | object {category: count} | `scenario.stock_capacity.value` |

**After the answers arrive:**
1. Run `python -m mi.decision.client_inputs check`.
2. Run `python -m mi.cli all`.
3. The dossier, decision card and claims export show which inputs became CLIENT-CONFIRMED.

**The historical match shares do not answer question 1 or 2.** Those shares (17% overall and 35% Frozen Pizza, value-weighted, on past coupon lines) describe past coupon accounting, not the terms of this offer.
