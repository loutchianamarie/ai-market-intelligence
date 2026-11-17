# Model card: buyer-uplift model for the e-mail campaign case (HILLSTROM_EMAIL_2008)

Model version `hillstrom-conv-slearner-p2-3ce8fb1cd1`. Run `CAMP-24B4793860DC`. Generated 2026-11-17T19:50:43Z by `python -m mi.campaign.export`. Every figure is computed from the local raw file.

## Verdict

At a 25% contact cap, the model's top customers gave 10.0 additional buyers per 1,000 Mens e-mails (95% interval 2.8 to 17.2), against 7.4 for random contacts (difference +2.6, interval -3.5 to 8.7) and 8.6 for the recency rule (difference +1.4, interval -5.5 to 8.2). The model is ahead on the point estimate, but both intervals must exclude zero for a stable gain and they do not: no stable targeting gain is shown. The past-spend rule, which validation did not select as the primary rule, scored 11.6 (model minus that rule -1.6, interval -7.0 to 3.9).

Pre-registered verdict: **MODEL_AHEAD_NOT_STABLE**. The model is not used to exclude customers. The randomized average effect carries the decision.

## Intended use

- Rank existing customers by the expected difference in two-week purchase probability between an e-mail and no e-mail, to study whether targeting beats simple rules under a contact cap.
- Support a manager's decision together with the randomized arm comparison, the cost thresholds and a new holdout.
- Not for: individual-level causal claims, new-customer acquisition, another retailer, a current customer base without a new pilot, or automatic sending.

## Training data

- Source: Hillstrom MineThatData e-mail challenge (2008). SHA-256 `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece`, 64,000 rows, one per existing customer.
- Arms: No E-Mail 21,306; Mens E-Mail 21,307; Womens E-Mail 21,387. Each e-mail is compared with the same no-e-mail control.
- Outcome: `conversion`, a purchase in the two weeks after the e-mail. 578 buyers in total (0.90%).
- Fully identical rows beyond the first: 6,562; kept, because the file has no customer id.
- The raw file stays local: the source page states no redistribution terms.

## Features and timing

- Read by the model (all describe the twelve months before the e-mail): `recency`, `history`, `mens`, `womens`, `newbie`, `zip_code`, `channel`. `history` enters as log1p.
- `mens` and `womens` are past-year product purchases, not gender.
- `segment` is the randomized assignment and enters only as the treatment indicator.
- Forbidden as predictors or ranking inputs: `visit`, `conversion`, `spend` (all measured after the e-mail). A test fails if any of them reaches the design matrix.

## Split and fitting

- Seeded customer-level split, stratified by arm (seed 20261117): train 25,598, validation 12,799, test 25,603.
- One L2 logistic regression used as an S-learner: 9 base features, 2 treatment indicators and 18 treatment x feature interactions (29 coefficients).
- Regularisation chosen on validation log loss: C = 0.01: 0.05252; C = 0.1: 0.05247; C = 1.0: 0.05285. Chosen C = 0.1.
- Refitted once on train+validation (38,397 customers, 338 buyers), then the test split was read.
- Chosen on train+validation only: best overall arm = Mens E-Mail (Mens E-Mail 6.4 per 1,000; Womens E-Mail 3.1 per 1,000); primary rule = RULE_RECENCY (RULE_RECENCY 14.2; RULE_HISTORY 10.7 per 1,000 at the cap on validation).

## Baselines

No e-mail; one e-mail to everyone; random contacts (expected value, estimated on the whole held-out arms); most-recent-purchase rule; highest-past-spend rule.

## Primary metric: additional buyers per 1,000 contacted, 25% cap, Mens E-Mail

| Policy | E-mailed in test | Buyers / customers e-mailed | Buyers / customers not e-mailed | Additional buyers per 1,000 contacted (95% interval) | Small cell |
|---|---:|---:|---:|---:|---|
| Mens E-Mail to a random 25% (expected value: the average effect over the whole held-out arms) **(primary)** | 6,401 | 113 / 8,524 | 50 / 8,523 | 7.4 (4.6 to 10.3) | no |
| Mens E-Mail to the 25% who purchased most recently **(primary)** | 6,401 | 40 / 2,122 | 22 / 2,147 | 8.6 (1.6 to 15.7) | no |
| Mens E-Mail to the 25% with the highest past-year spend | 6,401 | 43 / 2,110 | 19 / 2,160 | 11.6 (4.3 to 19.2) | no |
| Mens E-Mail to the 25% with the highest model-predicted uplift for that e-mail **(primary)** | 6,401 | 43 / 2,159 | 21 / 2,122 | 10.0 (2.8 to 17.2) | no |
| Model picks the e-mail per customer; contact the 25% with the highest predicted uplift | 6,401 | 40 / 2,182 | 23 / 2,126 | 7.6 (0.4 to 14.9) | no |

## Same metric at the 50% cap, Mens E-Mail

| Policy | E-mailed in test | Buyers / customers e-mailed | Buyers / customers not e-mailed | Additional buyers per 1,000 contacted (95% interval) | Small cell |
|---|---:|---:|---:|---:|---|
| Mens E-Mail to a random 50% (expected value: the average effect over the whole held-out arms) | 12,802 | 113 / 8,524 | 50 / 8,523 | 7.4 (4.6 to 10.3) | no |
| Mens E-Mail to the 50% who purchased most recently | 12,802 | 64 / 4,210 | 32 / 4,294 | 7.7 (3.6 to 12.4) | no |
| Mens E-Mail to the 50% with the highest past-year spend | 12,802 | 72 / 4,254 | 34 / 4,241 | 8.9 (4.2 to 13.7) | no |
| Mens E-Mail to the 50% with the highest model-predicted uplift for that e-mail | 12,802 | 68 / 4,204 | 34 / 4,244 | 8.2 (3.5 to 12.8) | no |
| Model picks the e-mail per customer; contact the 50% with the highest predicted uplift | 12,802 | 70 / 4,263 | 33 / 4,238 | 8.6 (4.0 to 13.4) | no |

## Every customer contacted

| Policy | E-mailed in test | Buyers / customers e-mailed | Buyers / customers not e-mailed | Additional buyers per 1,000 contacted (95% interval) | Small cell |
|---|---:|---:|---:|---:|---|
| Mens E-Mail to every eligible customer | 25,603 | 113 / 8,524 | 50 / 8,523 | 7.4 (4.6 to 10.3) | no |
| Womens E-Mail to every eligible customer | 25,603 | 77 / 8,556 | 50 / 8,523 | 3.1 (0.5 to 5.7) | no |
| Model picks the e-mail per customer; contact every eligible customer | 25,603 | 113 / 8,561 | 50 / 8,523 | 7.3 (4.5 to 10.2) | no |

## Interval method

- Held-out figures: customer-level bootstrap of the test split, 2000 resamples, percentile 95% interval. Differences between policies use the same resamples.
- Policy scores are held fixed, so the intervals cover test-sampling uncertainty only, not the variability of refitting the model.
- Full-sample arm comparisons: unpooled normal approximation.

## Secondary metrics

Qini coefficient on test (area between the Qini curve and the random line, divided by that area for the optimum curve without negative effects):

| E-mail | Ranking | Qini coefficient | 95% interval |
|---|---|---:|---|
| Mens E-Mail | model predicted uplift | 0.061 | -0.229 to 0.322 |
| Mens E-Mail | recency rule | 0.032 | -0.300 to 0.259 |
| Mens E-Mail | history rule | 0.121 | -0.136 to 0.374 |
| Womens E-Mail | model predicted uplift | 0.256 | -0.497 to 1.029 |
| Womens E-Mail | recency rule | -0.363 | -2.673 to 0.096 |
| Womens E-Mail | history rule | -0.212 | -2.137 to 0.308 |

Every Qini interval includes zero. The normalisation divides by a small total uplift, so the Womens e-mail values are unstable.

## Calibration on test

| Arm | Customers | Buyers | Observed rate | Mean predicted rate |
|---|---:|---:|---:|---:|
| No E-Mail | 8,523 | 50 | 0.587% | 0.603% |
| Mens E-Mail | 8,524 | 113 | 1.326% | 1.177% |
| Womens E-Mail | 8,556 | 77 | 0.900% | 0.864% |

## Failure segments

Observed uplift by quartile of predicted uplift on test (Q4 = highest predicted). A useful ranking would rise from Q1 to Q4.

**Mens E-Mail**

| Quartile | Buyers / e-mailed | Buyers / not e-mailed | Observed additional buyers per 1,000 (95% interval) | Mean predicted | Small cell |
|---|---:|---:|---:|---:|---|
| Q1 | 25 / 2,166 | 11 / 2,116 | 6.3 (0.9 to 11.8) | 2.4 | no |
| Q2 | 20 / 2,154 | 5 / 2,164 | 7.0 (2.4 to 11.5) | 3.9 | yes |
| Q3 | 25 / 2,045 | 13 / 2,121 | 6.1 (0.3 to 11.9) | 5.8 | no |
| Q4 | 43 / 2,159 | 21 / 2,122 | 10.0 (2.8 to 17.3) | 11.0 | no |

**Womens E-Mail**

| Quartile | Buyers / e-mailed | Buyers / not e-mailed | Observed additional buyers per 1,000 (95% interval) | Mean predicted | Small cell |
|---|---:|---:|---:|---:|---|
| Q1 | 7 / 2,113 | 14 / 2,179 | -3.1 (-7.3 to 1.0) | -0.1 | yes |
| Q2 | 25 / 2,148 | 7 / 2,122 | 8.3 (3.2 to 13.5) | 1.2 | yes |
| Q3 | 19 / 2,128 | 12 / 2,124 | 3.3 (-1.8 to 8.4) | 2.8 | no |
| Q4 | 26 / 2,167 | 17 / 2,098 | 3.9 (-2.1 to 9.9) | 6.5 | no |

- The ranking is weak: for the Mens e-mail only the top quartile stands apart, and for the Womens e-mail the quartiles are not ordered.
- The model predicts a negative effect of the Womens e-mail for 15% of test customers; the lowest quartile's observed effect has an interval that includes zero.
- Letting the model choose the e-mail per customer assigns the Mens e-mail to 88% of customers and adds nothing over sending everyone the Mens e-mail.
- Descriptive segmentation by past-year purchase category (full sample, hypothesis-generating):

| Past-year purchases | E-mail | Buyers / e-mailed | Buyers / not e-mailed | Additional buyers per 1,000 (95% interval) |
|---|---|---:|---:|---:|
| Mens merchandise only | Mens E-Mail | 110 / 9,558 | 53 / 9,638 | 6.0 (3.4 to 8.6) |
| Mens merchandise only | Womens E-Mail | 59 / 9,622 | 53 / 9,638 | 0.6 (-1.5 to 2.8) |
| Womens merchandise only | Mens E-Mail | 104 / 9,568 | 49 / 9,519 | 5.7 (3.2 to 8.2) |
| Womens merchandise only | Womens E-Mail | 99 / 9,647 | 49 / 9,519 | 5.1 (2.6 to 7.6) |
| Both | Mens E-Mail | 53 / 2,181 | 20 / 2,149 | 15.0 (7.4 to 22.6) |
| Both | Womens E-Mail | 31 / 2,118 | 20 / 2,149 | 5.3 (-1.2 to 11.9) |

## Coefficients

Intercept -4.8762. Reference levels: zip_code = Rural, channel = Multichannel. Numeric features are standardised.

| Term | Coefficient |
|---|---:|
| `recency` | -0.2597 |
| `log_history` | +0.1281 |
| `mens` | +0.1112 |
| `womens` | +0.1401 |
| `newbie` | -0.3792 |
| `zip_code=Surburban` | -0.1936 |
| `zip_code=Urban` | -0.1760 |
| `channel=Phone` | -0.2082 |
| `channel=Web` | -0.0072 |
| `T_mens` | +0.1227 |
| `T_womens` | +0.1145 |
| `T_mens x recency` | +0.0785 |
| `T_mens x log_history` | +0.1326 |
| `T_mens x mens` | +0.3190 |
| `T_mens x womens` | +0.3135 |
| `T_mens x newbie` | +0.1663 |
| `T_mens x zip_code=Surburban` | +0.0798 |
| `T_mens x zip_code=Urban` | -0.1392 |
| `T_mens x channel=Phone` | +0.1434 |
| `T_mens x channel=Web` | +0.1360 |
| `T_womens x recency` | -0.0670 |
| `T_womens x log_history` | +0.0204 |
| `T_womens x mens` | -0.0150 |
| `T_womens x womens` | +0.3693 |
| `T_womens x newbie` | +0.2158 |
| `T_womens x zip_code=Surburban` | -0.0326 |
| `T_womens x zip_code=Urban` | -0.0199 |
| `T_womens x channel=Phone` | -0.1880 |
| `T_womens x channel=Web` | -0.0186 |

## Caveats

- REPEATED EVALUATION: the dataset was analysed before; the test split is not untouched data.
- RARE OUTCOME: 578 buyers among 64,000 customers. Top-k and subgroup cells hold few buyers, so targeting comparisons are imprecise.
- GROUP EFFECTS ONLY: differences between randomized groups estimate additional repeat buyers for a population; they are not an individual's effect and not customer acquisition.
- HISTORICAL: a 2008 effect for one anonymous apparel retailer. Do not transfer it to another retailer or to a current base without a new randomized pilot.
- ECONOMICS ARE SCENARIOS: margin and cost per e-mail are unknown; no contribution figure is a measured profit.
- No e-mail is ever sent, scheduled or approved by this system; a named human decides.

## Reproduce

`python -m mi.campaign.export` with the raw file at `data/raw/hillstrom/hillstrom_2008.csv`. Split hashes, seed, feature list, code commit and package versions are in `reports/campaign/run_manifest.json`.
