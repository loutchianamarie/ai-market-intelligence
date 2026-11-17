# Campaign case: marketing brief and slide claims

Case `HILLSTROM_EMAIL_2008`, contract 1.0, run `CAMP-24B4793860DC`, model `hillstrom-conv-slearner-p2-3ce8fb1cd1`.
Export `reports/campaign_case.latest.json`, SHA-256 `a3ee6a640ad9a9021c10f7bb3601fd1d79ae2619cb87e1f5c7d4db1e76cd75e4`. Every figure below is copied from that file by code.

## The decision in one paragraph

Send the Mens e-mail to every eligible, consented existing customer except a 10% randomized no-e-mail holdout, but only after finance and CRM confirm that the full cost per e-mail is below the break-even for the confirmed margin. Do not use the targeting model to exclude customers yet. A named human approves; this system sends nothing.

## Did the targeting model beat random and the rule?

- Verdict: **MODEL_AHEAD_NOT_STABLE**.
- Point estimate beats random: yes. Statistically stable: no.
- Point estimate beats the primary rule: yes. Statistically stable: no.
- At a 25% contact cap, the model's top customers gave 10.0 additional buyers per 1,000 Mens e-mails (95% interval 2.8 to 17.2), against 7.4 for random contacts (difference +2.6, interval -3.5 to 8.7) and 8.6 for the recency rule (difference +1.4, interval -5.5 to 8.2). The model is ahead on the point estimate, but both intervals must exclude zero for a stable gain and they do not: no stable targeting gain is shown. The past-spend rule, which validation did not select as the primary rule, scored 11.6 (model minus that rule -1.6, interval -7.0 to 3.9).

## Why this is still a useful result

- Randomized evidence on 64,000 existing customers: 267 of 21,307 customers bought within two weeks after the Mens e-mail (1.25%) against 122 of 21,306 with no e-mail (0.57%).
- That is 6.8 additional purchasing customers per 1,000 e-mailed (95% interval 5.0 to 8.6). The Womens e-mail added 3.1 per 1,000 (interval 1.5 to 4.7) against the same control.
- On the held-out test split the Mens e-mail sent to everyone added 7.4 per 1,000 (interval 4.6 to 10.3), consistent with the full sample.
- The model is a negative finding for targeting; the randomized average effect is what supports the decision.

## Marketing rationale

- **Research question.** Among existing customers who bought in the past twelve months, does a merchandise e-mail create additional purchasing customers within two weeks compared with no e-mail, which of the two e-mails does it better, and is a targeting model worth using under a contact cap?
- **Audience.** Existing customers who purchased in the past twelve months (64,000 in the experiment). This is repeat-purchase stimulation of a known base, not acquisition of new customers.
- **Segmentation.** Bases available before the e-mail: months since last purchase, past-year spend, past-year purchase category (Mens, Womens or both; product history, not gender), new-in-the-past-year flag, zip type and purchase channel. Descriptive only, by past-year category: Mens e-mail: Mens merchandise only: 6.0 per 1,000 (interval 3.4 to 8.6); Womens merchandise only: 5.7 per 1,000 (interval 3.2 to 8.2); Both: 15.0 per 1,000 (interval 7.4 to 22.6). Womens e-mail: Mens merchandise only: 0.6 per 1,000 (interval -1.5 to 2.8); Womens merchandise only: 5.1 per 1,000 (interval 2.6 to 7.6); Both: 5.3 per 1,000 (interval -1.2 to 11.9).
- **Targeting.** Default target: every eligible, consented customer except the randomized holdout. The Mens e-mail added buyers in all three purchase categories; the Womens e-mail shows a clear effect only among customers who bought Womens merchandise. The model's ranking is not shown to beat random or a simple rule with a stable margin, so it is not used to suppress anyone.
- **Positioning.** For customers who bought from us this year: a timely reminder of new merchandise from a retailer they already know, giving a reason to return within two weeks. Lead with the Mens e-mail focus because it produced more additional buyers. Copy is a hypothesis: the 2008 creative is not available.
- **Four Ps.** Product: Lead with the Mens-merchandise e-mail. Price: No price or discount change is recommended. Place: E-mail to existing customers, compared with no contact. Promotion: Two draft messages prepared as hypotheses; a human approves or rejects them.
- **Human decision.** DRAFT_REQUIRES_HUMAN: a named manager approves or rejects; the system has no send tool.
- **Holdout.** A 10% randomized no-e-mail holdout is drawn and frozen before sending (at least 3,063 customers per arm to detect an effect of the 2008 size with 80% power).
- **No e-mail.** Always allowed. Without an e-mail 0.57% of customers still bought within two weeks; those purchases are not caused by the campaign. Choose no e-mail when cost per contact exceeds break-even, when consent is missing, or when a manager prefers to wait for a current pilot. Under the conservative assumption set the Womens e-mail loses money (-2,871 USD scenario contribution).

## Exact claims for slides

Quote the value with its tag and denominator. Do not round a difference into a win, and do not show a scenario as a result.

| Claim ID | Claim | Value | Tag | Denominator | Uncertainty |
|---|---|---|---|---|---|
| `CLM_DATA_ROWS` | Existing customers in the randomized e-mail experiment | 64,000 customers | OBSERVED | 64,000 rows, one per customer | - |
| `CLM_BUYERS_CONTROL` | Unique customers who purchased within two weeks, No E-Mail | 122 customers | OBSERVED | 21,306 customers randomized to No E-Mail | - |
| `CLM_BUYERS_MENS` | Unique customers who purchased within two weeks, Mens E-Mail | 267 customers | OBSERVED | 21,307 customers randomized to Mens E-Mail | - |
| `CLM_BUYERS_WOMENS` | Unique customers who purchased within two weeks, Womens E-Mail | 189 customers | OBSERVED | 21,387 customers randomized to Womens E-Mail | - |
| `CLM_RATE_CONTROL` | Purchase rate, No E-Mail | 0.5726 percent | OBSERVED | 122 buyers / 21,306 customers randomized to No E-Mail | - |
| `CLM_RATE_MENS` | Purchase rate, Mens E-Mail | 1.2531 percent | OBSERVED | 267 buyers / 21,307 customers randomized to Mens E-Mail | - |
| `CLM_RATE_WOMENS` | Purchase rate, Womens E-Mail | 0.8837 percent | OBSERVED | 189 buyers / 21,387 customers randomized to Womens E-Mail | - |
| `CLM_BUYERS_PER_1000_MENS` | Additional purchasing customers per 1,000 customers sent the Mens e-mail, versus no e-mail | 6.805 per 1,000 e-mailed | OBSERVED | 267/21,307 (Mens E-Mail) minus 122/21,306 (No E-Mail) | 95% interval, normal approximation: 5.00 to 8.61 |
| `CLM_BUYERS_PER_1000_WOMENS` | Additional purchasing customers per 1,000 customers sent the Womens e-mail, versus no e-mail | 3.111 per 1,000 e-mailed | OBSERVED | 189/21,387 (Womens E-Mail) minus 122/21,306 (No E-Mail) | 95% interval, normal approximation: 1.50 to 4.72 |
| `CLM_SPEND_PER_CONTACT_MENS` | Incremental spend per customer sent the Mens e-mail, versus no e-mail | 0.7698 USD per customer e-mailed | OBSERVED | mean spend of 21,307 (Mens E-Mail) minus mean spend of 21,306 (No E-Mail) | 95% interval, normal approximation: 0.49 to 1.05 |
| `CLM_SPEND_PER_CONTACT_WOMENS` | Incremental spend per customer sent the Womens e-mail, versus no e-mail | 0.4244 USD per customer e-mailed | OBSERVED | mean spend of 21,387 (Womens E-Mail) minus mean spend of 21,306 (No E-Mail) | 95% interval, normal approximation: 0.17 to 0.68 |
| `CLM_TEST_BUYERS` | Buyers in the held-out test split: no e-mail / Mens e-mail / Womens e-mail | 50 / 113 / 77 customers | OBSERVED | 8,523 / 8,524 / 8,556 held-out customers per arm | - |
| `CLM_TEST_SEND_ALL_MENS` | Held-out: additional buyers per 1,000 when every customer gets the Mens e-mail | 7.39 per 1,000 contacted | HELD_OUT_ESTIMATE | 113/8,524 e-mailed minus 50/8,523 not e-mailed, over the whole held-out arms | 95% interval, customer bootstrap (2000 resamples): 4.58 to 10.29 |
| `CLM_CAP25_MODEL` | Held-out, 25% contact cap, Mens e-mail: additional buyers per 1,000 contacted, model targeting | 10.02 per 1,000 contacted | HELD_OUT_ESTIMATE | 43/2,159 e-mailed minus 21/2,122 not e-mailed, inside the selected held-out customers | 95% interval, customer bootstrap (2000 resamples): 2.80 to 17.18 |
| `CLM_CAP25_RANDOM` | Held-out, 25% contact cap, Mens e-mail: additional buyers per 1,000 contacted, random contacts (expected value) | 7.39 per 1,000 contacted | HELD_OUT_ESTIMATE | 113/8,524 e-mailed minus 50/8,523 not e-mailed, over the whole held-out arms | 95% interval, customer bootstrap (2000 resamples): 4.58 to 10.29 |
| `CLM_CAP25_RULE` | Held-out, 25% contact cap, Mens e-mail: additional buyers per 1,000 contacted, recency rule | 8.603 per 1,000 contacted | HELD_OUT_ESTIMATE | 40/2,122 e-mailed minus 22/2,147 not e-mailed, inside the selected held-out customers | 95% interval, customer bootstrap (2000 resamples): 1.63 to 15.74 |
| `CLM_CAP25_OTHER_RULE` | Held-out, 25% contact cap, Mens e-mail: additional buyers per 1,000 contacted, past-spend rule | 11.583 per 1,000 contacted | HELD_OUT_ESTIMATE | 43/2,110 e-mailed minus 19/2,160 not e-mailed, inside the selected held-out customers | 95% interval, customer bootstrap (2000 resamples): 4.32 to 19.24 |
| `CLM_MODEL_VS_RANDOM` | Model targeting minus random contacts at the 25% cap (Mens e-mail) | 2.63 additional buyers per 1,000 contacts | HELD_OUT_ESTIMATE | model: 43/2,159 e-mailed minus 21/2,122 not e-mailed, inside the selected held-out customers; random: 113/8,524 e-mailed minus 50/8,523 not e-mailed, over the whole held-out arms | paired 95% interval, customer bootstrap (2000 resamples): -3.52 to 8.75; includes zero |
| `CLM_MODEL_VS_RULE` | Model targeting minus the recency rule at the 25% cap (Mens e-mail) | 1.417 additional buyers per 1,000 contacts | HELD_OUT_ESTIMATE | model: 43/2,159 e-mailed minus 21/2,122 not e-mailed, inside the selected held-out customers; rule: 40/2,122 e-mailed minus 22/2,147 not e-mailed, inside the selected held-out customers | paired 95% interval, customer bootstrap (2000 resamples): -5.50 to 8.16; includes zero |
| `CLM_MODEL_VERDICT` | Pre-registered verdict on model targeting versus random and the primary rule | MODEL_AHEAD_NOT_STABLE verdict | HELD_OUT_ESTIMATE | 25% cap on 25,603 held-out customers | stable only if both paired 95% intervals lie above zero |
| `CLM_BREAK_EVEN_COST_MENS_M35` | Break-even cost per e-mail, Mens e-mail, at an ASSUMED 35% margin (before setup) | 0.2694 USD per e-mail | ASSUMPTION | incremental spend per contact x 35% | 0.170 USD using the lower 95% bound of incremental spend |
| `CLM_SCENARIO_MENS_CENTRAL` | SCENARIO contribution, Mens e-mail to 57,600 customers, central assumptions (not measured profit) | 12,792 USD per campaign | ASSUMPTION | 57,600 assumed contacts; margin 35%, cost 0.030 USD per e-mail, setup 1,000 USD | range over the 95% interval of incremental spend: 7,053 to 18,531 USD |
| `CLM_SCENARIO_MENS_CONSERVATIVE` | SCENARIO contribution, Mens e-mail to 57,600 customers, conservative assumptions (not measured profit) | 1,108 USD per campaign | ASSUMPTION | 57,600 assumed contacts; margin 20%, cost 0.100 USD per e-mail, setup 2,000 USD | range over the 95% interval of incremental spend: -2,171 to 4,388 USD |
| `CLM_EXPECTED_BUYERS_BROAD` | SCENARIO: additional purchasing customers if the Mens e-mail goes to 57,600 customers and the 2008 effect holds | 392 customers | ASSUMPTION | 57,600 assumed contacts x 6.81 per 1,000 | 288 to 496 from the 95% interval of the effect; a 2008 effect is not a forecast for a current base |
| `CLM_HOLDOUT_PER_ARM` | Customers per arm needed in a future randomized test to detect an effect of the 2008 size (80% power, two-sided 5%) | 3,063 customers per arm | ASSUMPTION | control rate 0.0057, treated rate 0.0125 | design calculation; assumes the historical effect |
| `CLM_MARGIN` | Contribution margin on incremental sales | UNKNOWN share of revenue | UNKNOWN | - | not in the dataset; must be supplied by the business |
| `CLM_COST_PER_CONTACT` | Full cost per e-mail | UNKNOWN USD per e-mail | UNKNOWN | - | not in the dataset; must be supplied by the business |

Published reference figures (Radcliffe 2008, Table 2, page 3), for comparison only and never as our output: Published purchase rate, Mens e-mail (full sample): 1.25 percent; Published purchase rate, Womens e-mail (full sample): 0.88 percent; Published purchase rate, no e-mail control (full sample): 0.57 percent; Published purchase-rate uplift, Mens e-mail vs control: 0.68 percentage points; Published purchase-rate uplift, Womens e-mail vs control: 0.31 percentage points.

## Sentences that are safe to say

1. "In a randomized test on 64,000 existing customers, the Mens e-mail added 6.8 purchasing customers per 1,000 e-mailed in two weeks, compared with no e-mail."
2. "Our uplift model was ahead of random and of a simple rule at a 25% contact cap, but the difference was not statistically stable, so we do not use it to exclude customers."
3. "Margin and e-mail cost are unknown, so we report break-even thresholds and scenarios, not profit."
4. "The advisor recommends a broad send with a randomized holdout only after cost and consent are confirmed, and a human approves."

## Sentences to avoid

- "The model increases sales" or "the model beats the rule": not shown with a stable margin.
- "The campaign makes a profit of ...": every contribution figure is a scenario.
- "New customers": every customer in the data is an existing buyer.
- Any figure for the grocery retailer, FashionForward or a current customer base taken from this experiment.

## Capability status (seven capabilities, honest labels)

| Capability | Status | What is and is not shown |
|---|---|---|
| Research and RAG | PARTIAL | Source-backed explanation of this experiment from two primary sources; abstains on offer cost, retailer identity and creative. Grocery RAG tests are a separate case. |
| Customer intelligence | VERIFIED on this case | Conversion uplift model fitted and evaluated on held-out customers; no stable targeting gain. Not new-customer acquisition. |
| Portfolio optimization | VERIFIED as a campaign portfolio | Mens e-mail, Womens e-mail and no e-mail compared under contact caps. The product-portfolio optimizer is validated only on the separate grocery case, under assumptions. |
| Demand and risk | SCENARIO | Additional buyers per 1,000 with intervals; cost and margin scenarios and break-even thresholds. No long-term demand forecast. |
| Advisor and CRM | PENDING in this repo | The export, the draft messages and the owned action plan are ready for the ConsultAI agents. No send, spend, approve or publish tool exists. A live LLM run is not verified here. |
| SEO / GEO | PENDING (0 of 20 answers logged) | No SEO or GEO effect is attributed to e-mail data. The audit needs the 20 real answers first. |
| Outcome learning | HISTORICAL ONLY | Historical randomized control comparison plus a planned randomized holdout. No live deployment and no observed outcome of a new campaign. |

## What ConsultAI must integrate

1. Load `reports/campaign_case.latest.json` through the read-only adapter and verify the SHA-256 above.
2. Run `validate_case` and refuse to render on any error; `record_type` must be `COMPUTED_EXPORT`.
3. Render counts, intervals and tags from the file; do not recompute statistics.
4. Show the recommendation, its conditions, the no-e-mail option and the action plan; keep the send step blocked.
5. Cite `claim_id` and `source_id` for every number on a slide or in a trace.

## Human inputs still needed

- Contribution margin and full cost per e-mail (finance, CRM).
- Consent status of the current base (CRM, legal).
- A named approver and the holdout draw.
- The 20 GEO answers and 2-3 interviews for the separate research tracks.
