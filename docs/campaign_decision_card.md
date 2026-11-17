# Manager decision card: e-mail to existing customers

Case `HILLSTROM_EMAIL_2008`. Run `CAMP-24B4793860DC`. Status: **DRAFT_REQUIRES_HUMAN**. Nothing has been sent.

## The buyer problem

We have an existing customer base (64,000 customers who bought in the past year), a limit on how often we may contact them, two possible merchandise e-mails, and a contribution margin to protect. Which e-mail, to whom, creates additional purchasing customers, and at what cost does it stop paying?

## Recommendation

**Send the Mens e-mail to every eligible, consented existing customer except a 10% randomized no-e-mail holdout, but only after finance and CRM confirm that the full cost per e-mail is below the break-even for the confirmed margin. Do not use the targeting model to exclude customers yet. A named human approves; this system sends nothing.**

Conditions:

1. Finance confirms the contribution margin on incremental sales and CRM confirms the full cost per e-mail (delivery, offer, handling); the cost must be below margin x 0.77 USD, and below margin x 0.49 USD to be safe on the lower bound.
2. The legal basis for e-mailing each recipient is verified for their jurisdiction (US CAN-SPAM is an opt-out regime; EU/UK and other rules can require opt-in), the opt-out list is applied and unsubscribe requests are honored within 10 business days (SRC_FTC_CANSPAM).
3. A 10% randomized no-e-mail holdout is drawn and frozen before sending (at least 3,063 customers per arm to detect an effect of the 2008 size with 80% power).
4. A named human approves the final draft; any change to the plan requires a new review.
5. The 2008 effect is a prior, not a forecast: the first send is itself the pilot and is judged on its own holdout.

## What the experiment observed (all customers, two weeks)

| Arm | Customers | Buyers | Purchase rate | Additional buyers per 1,000 e-mailed (95% interval) | Incremental spend per e-mail (95% interval) |
|---|---:|---:|---:|---:|---:|
| No E-Mail | 21,306 | 122 | 0.57% | reference | reference |
| Mens E-Mail | 21,307 | 267 | 1.25% | 6.8 (5.0 to 8.6) | 0.77 USD (0.49 to 1.05) |
| Womens E-Mail | 21,387 | 189 | 0.88% | 3.1 (1.5 to 4.7) | 0.42 USD (0.17 to 0.68) |

Tag: OBSERVED. Each e-mail is compared with the same no-e-mail control. These are additional repeat buyers for a group, not new customers and not an individual's effect.

## Does a targeting model help under a 25% contact cap? (held-out customers)

| Policy | E-mailed in test | Buyers / customers e-mailed | Buyers / customers not e-mailed | Additional buyers per 1,000 contacted (95% interval) | Small cell |
|---|---:|---:|---:|---:|---|
| Mens E-Mail to a random 25% (expected value: the average effect over the whole held-out arms) **(primary)** | 6,401 | 113 / 8,524 | 50 / 8,523 | 7.4 (4.6 to 10.3) | no |
| Mens E-Mail to the 25% who purchased most recently **(primary)** | 6,401 | 40 / 2,122 | 22 / 2,147 | 8.6 (1.6 to 15.7) | no |
| Mens E-Mail to the 25% with the highest past-year spend | 6,401 | 43 / 2,110 | 19 / 2,160 | 11.6 (4.3 to 19.2) | no |
| Mens E-Mail to the 25% with the highest model-predicted uplift for that e-mail **(primary)** | 6,401 | 43 / 2,159 | 21 / 2,122 | 10.0 (2.8 to 17.2) | no |
| Model picks the e-mail per customer; contact the 25% with the highest predicted uplift | 6,401 | 40 / 2,182 | 23 / 2,126 | 7.6 (0.4 to 14.9) | no |

Tag: HELD_OUT_ESTIMATE. At a 25% contact cap, the model's top customers gave 10.0 additional buyers per 1,000 Mens e-mails (95% interval 2.8 to 17.2), against 7.4 for random contacts (difference +2.6, interval -3.5 to 8.7) and 8.6 for the recency rule (difference +1.4, interval -5.5 to 8.2). The model is ahead on the point estimate, but both intervals must exclude zero for a stable gain and they do not: no stable targeting gain is shown. The past-spend rule, which validation did not select as the primary rule, scored 11.6 (model minus that rule -1.6, interval -7.0 to 3.9).

## Segment, target, position

- **Segment.** Bases available before the e-mail: months since last purchase, past-year spend, past-year purchase category (Mens, Womens or both; product history, not gender), new-in-the-past-year flag, zip type and purchase channel. Descriptive only, by past-year category: Mens e-mail: Mens merchandise only: 6.0 per 1,000 (interval 3.4 to 8.6); Womens merchandise only: 5.7 per 1,000 (interval 3.2 to 8.2); Both: 15.0 per 1,000 (interval 7.4 to 22.6). Womens e-mail: Mens merchandise only: 0.6 per 1,000 (interval -1.5 to 2.8); Womens merchandise only: 5.1 per 1,000 (interval 2.6 to 7.6); Both: 5.3 per 1,000 (interval -1.2 to 11.9).
- **Target.** Default target: every eligible, consented customer except the randomized holdout. The Mens e-mail added buyers in all three purchase categories; the Womens e-mail shows a clear effect only among customers who bought Womens merchandise. The model's ranking is not shown to beat random or a simple rule with a stable margin, so it is not used to suppress anyone.
- **Position.** For customers who bought from us this year: a timely reminder of new merchandise from a retailer they already know, giving a reason to return within two weeks. Lead with the Mens e-mail focus because it produced more additional buyers. Copy is a hypothesis: the 2008 creative is not available.

## Four Ps

| P | Decision | Alternatives | Evidence | Note |
|---|---|---|---|---|
| Product | Lead with the Mens-merchandise e-mail. | Womens e-mail: 3.1 additional buyers per 1,000 (interval 1.5 to 4.7); No e-mail | OBSERVED | Product here means the merchandise focus of the e-mail. The dataset has no SKU, assortment or stock data. |
| Price | No price or discount change is recommended. | Test a plain reminder against an offer in the next randomized pilot | UNKNOWN | Price and discount terms of the 2008 e-mails are unknown; any offer cost belongs in cost per contact. |
| Place | E-mail to existing customers, compared with no contact. | No e-mail (the randomized control); Other channels: not tested in this experiment | OBSERVED | The customer's past purchase channel (phone, web, multichannel) is a feature, not the campaign channel. |
| Promotion | Two draft messages prepared as hypotheses; a human approves or rejects them. | Merchandise-matched variant for Womens-category buyers, to be tested rather than assumed | ASSUMPTION | The actual creative, subject line and products shown in 2008 are not available. Drafts are never sent by this system. |

## Economics: scenarios, not measured profit

`contribution = contacts * (incremental_spend_per_contact * assumed_margin - cost_per_contact) - fixed_setup_cost`

Margin and cost per e-mail are **UNKNOWN**. The break-even cost per e-mail at an assumed margin, before setup:

| E-mail | Assumed margin | Break-even cost per e-mail | Using the lower bound of incremental spend |
|---|---:|---:|---:|
| Mens E-Mail | 20% | 0.154 USD | 0.097 USD |
| Mens E-Mail | 35% | 0.269 USD | 0.170 USD |
| Mens E-Mail | 50% | 0.385 USD | 0.243 USD |
| Womens E-Mail | 20% | 0.085 USD | 0.034 USD |
| Womens E-Mail | 35% | 0.149 USD | 0.059 USD |
| Womens E-Mail | 50% | 0.212 USD | 0.084 USD |

Scenario contribution for a broad send to 57,600 customers (assumed base of 64,000 less the holdout):

| E-mail | Assumption set | Margin | Cost per e-mail | Setup | Scenario contribution (range from the spend interval) |
|---|---|---:|---:|---:|---:|
| Mens E-Mail | unknown inputs | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Mens E-Mail | conservative | 20% | 0.100 USD | 2,000 USD | +1,108 USD (-2,171 to +4,388) |
| Mens E-Mail | central | 35% | 0.030 USD | 1,000 USD | +12,792 USD (+7,053 to +18,531) |
| Mens E-Mail | favourable | 50% | 0.005 USD | 500 USD | +21,383 USD (+13,184 to +29,582) |
| Womens E-Mail | unknown inputs | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Womens E-Mail | conservative | 20% | 0.100 USD | 2,000 USD | -2,871 USD (-5,814 to +72) |
| Womens E-Mail | central | 35% | 0.030 USD | 1,000 USD | +5,828 USD (+678 to +10,978) |
| Womens E-Mail | favourable | 50% | 0.005 USD | 500 USD | +11,435 USD (+4,078 to +18,792) |

If the 2008 effect held for that send, it would mean about 392 additional purchasing customers (288 to 496). This is a scenario: a 2008 effect is not a forecast for a current base.

## The no-e-mail choice

Always allowed. Without an e-mail 0.57% of customers still bought within two weeks; those purchases are not caused by the campaign. Choose no e-mail when cost per contact exceeds break-even, when consent is missing, or when a manager prefers to wait for a current pilot. Under the conservative assumption set the Womens e-mail loses money (-2,871 USD scenario contribution).

## If the model stays inconclusive

If only a share of customers may be contacted, do not present the model as a proven gain. At a 25% cap the model (10.0), the recency rule (8.6) and the past-spend rule (11.6) all sit above random (7.4) on the point estimate, none with an interval that excludes zero. Use the simplest auditable ranking (past-year spend or recency) to fill the cap, and randomize e-mail versus no e-mail inside both the selected and the unselected group, so the next campaign measures whether targeting works.

## What would reverse this decision

- Verified cost per e-mail above the break-even for the verified margin (point: margin x 0.77 USD): choose no e-mail.
- Consent cannot be verified, or unsubscribe and complaint costs are material: choose no e-mail or a smaller consented group.
- A new randomized pilot on the current base gives an interval for additional buyers that includes zero: stop and research before spending more.
- A larger test shows the model beating random and the simple rule with intervals above zero: switch to model-targeted sending.
- A binding contact cap (budget or frequency policy): prioritise by a simple auditable rule and randomize inside the cap, as described in the alternative.

## Action plan (owners are roles; names are assigned by the manager)

| Step | Owner | Action | Status |
|---:|---|---|---|
| 1 | CRM owner | Review the eligible segment (purchased in the past twelve months) and report its current size. | PENDING_HUMAN |
| 2 | CRM owner with legal | Check the draft and the send list against the FTC CAN-SPAM requirements (SRC_FTC_CANSPAM): accurate sender and subject, message identified as an ad, valid postal address, working opt-out honored within 10 business days, opted-out customers suppressed. Confirm the legal basis for each recipient's jurisdiction (the US is opt-out; EU/UK and others can require opt-in). | PENDING_HUMAN |
| 3 | Finance with CRM owner | Supply the contribution margin and the full cost per e-mail; compare with the break-even thresholds. | PENDING_HUMAN |
| 4 | Analyst | Draw and freeze a 10% randomized no-e-mail holdout before any send. | PENDING_HUMAN |
| 5 | Marketing manager | Approve or reject the draft with name, reason and plan version; re-review after any change. | PENDING_HUMAN |
| 6 | Marketing operations (human) | Send only after step 5 is approved. This system has no send tool. | BLOCKED_UNTIL_APPROVED |
| 7 | Analyst with marketing manager | After two weeks, compare unique buyers, incremental spend, cost and unsubscribes between e-mailed customers and the holdout; decide to continue, change or stop. | PENDING_HUMAN |

Success metric: Additional unique purchasing customers per 1,000 e-mailed versus the randomized holdout within two weeks, with a 95% interval above zero. Secondary: incremental spend per contact times margin minus cost per contact. Guardrail: unsubscribe and complaint rate.

## Caveats

- REPEATED EVALUATION: the dataset was analysed before; the test split is not untouched data.
- RARE OUTCOME: 578 buyers among 64,000 customers. Top-k and subgroup cells hold few buyers, so targeting comparisons are imprecise.
- GROUP EFFECTS ONLY: differences between randomized groups estimate additional repeat buyers for a population; they are not an individual's effect and not customer acquisition.
- HISTORICAL: a 2008 effect for one anonymous apparel retailer. Do not transfer it to another retailer or to a current base without a new randomized pilot.
- ECONOMICS ARE SCENARIOS: margin and cost per e-mail are unknown; no contribution figure is a measured profit.
- No e-mail is ever sent, scheduled or approved by this system; a named human decides.
