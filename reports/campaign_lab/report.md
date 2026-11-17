# Model lab report (protocol v3, pre-registered)

Case `HILLSTROM_EMAIL_2008`. Protocol `data/eval/hillstrom_protocol_v3_lab.json` was committed before any candidate was fitted. This is a **repeated evaluation**: the data were analysed before (disclosed in the protocol). Frozen export, contract and slides are untouched.

## Result in one paragraph

Eight candidate models (logistic and gradient-boosted S-, T- and transformed-outcome learners, a sparse domain-informed variant and an ensemble) were scored by cross-fitted Qini area on train+validation. **No challenger was shown better than the v2 baseline** (best challenger `S_LOGIT_SPARSE`, paired 90% interval -1.02 to +4.94, which includes zero), so the baseline `S_LOGIT` was retained. Against shuffled arm labels the baseline's out-of-fold signal is **not distinguishable from noise** on train+validation (real 4.56; null 95th percentile 7.48; p = 0.146). The single test-split confirmation reproduces v2: at a 25% cap the Mens e-mail model minus random is +2.6 (95% interval -3.5 to +8.7) and minus the recency rule +1.4 (95% interval -5.5 to +8.2). **A better model cannot be demonstrated with 578 buyers.**

## 1. Selection (train+validation, 5 folds x 3 repeats, out-of-fold)

AUQ = area between the Qini curve and the random line, in buyers (mean of the Mens and Womens e-mail curves).

| Candidate | Mean AUQ | SD over repeats | Paired 90% interval vs baseline |
|---|---|---|---|
| S_LOGIT | 4.85 | 0.32 | baseline |
| S_LOGIT_SPARSE | 7.13 | 0.55 | -1.02 to +4.94 |
| T_LOGIT | 5.29 | 0.04 | -0.83 to +2.40 |
| S_HGB | 4.42 | 1.61 | -2.68 to +6.63 |
| T_HGB | 5.67 | 1.42 | -5.13 to +4.64 |
| TO_RIDGE | 5.55 | 0.15 | -1.00 to +2.86 |
| TO_HGB | 2.09 | 1.78 | -8.07 to +1.22 |
| ENSEMBLE | 5.46 | 0.28 | -0.51 to +2.01 |
| RULE_RECENCY | 2.66 | 0.00 | reference |
| RULE_HISTORY | 6.48 | 0.00 | reference |
| RANDOM_ORDER | 7.48 | 0.00 | reference |

How noisy is AUQ? Random orders of the same customers score +0.23 on average with a standard deviation of **3.38** (95th percentile 5.91; 300 random orders). Differences of a few buyers between candidates are inside that noise. The one fixed random order used as a reference scored 7.48, above every model: that is luck inside the noise, not signal.

## 2. Is there any signal? (exploratory, all 64,000 customers)

Cross-fitted AUQ on all customers (descriptive, selection-biased across candidates): S_LOGIT 9.7, S_LOGIT_SPARSE 7.6, ENSEMBLE 10.0, RULE_RECENCY 0.5, RULE_HISTORY 6.7, RANDOM_ORDER -2.9. On all 64,000 customers random orders score +0.40 with sd 3.97 (95th percentile 7.5); above that 95th percentile: S_LOGIT, S_LOGIT_SPARSE, ENSEMBLE; at or below it: RULE_RECENCY, RULE_HISTORY, RANDOM_ORDER. Encouraging but descriptive and selection-biased, not confirmatory.

Likelihood-ratio test for effect modification (does any pre-e-mail feature change the e-mail effect?): global LR = 27.1 on 18 df, p = 0.0766. Per feature (2 df each, Holm-adjusted):

| Feature | p (raw) | p (Holm) |
|---|---|---|
| newbie | 0.0072 | 0.0650 |
| mens | 0.0231 | 0.1845 |
| recency | 0.2781 | 1.0000 |
| womens | 0.5502 | 1.0000 |
| log_history | 0.6555 | 1.0000 |
| zip_code=Surburban | 1.0000 | 1.0000 |

## 3. Test-split confirmation (once; selected model `S_LOGIT`)

| Comparison (25% cap) | Additional buyers per 1,000 contacts |
|---|---|
| Mens: model minus random | +2.6 (95% interval -3.5 to +8.7) |
| Mens: model minus recency rule | +1.4 (95% interval -5.5 to +8.2) |
| Mens: model minus past-spend rule | -1.6 (95% interval -7.0 to +3.9) |
| Womens: model minus random | +0.8 (95% interval -4.1 to +6.0) |
| Womens: model minus recency rule | +4.8 (95% interval -0.5 to +10.0) |

Stable against random: False. Stable against the recency rule: False.

## 4. What it would take to prove a targeting gain

If the estimated gap of +2.6 per 1,000 were real, a confirmatory test needs about **284,012 customers** (80% power, 5% two-sided), versus 25,603 in this test split. At today's size the smallest gap it could detect is about 8.8 per 1,000. rough: assumes the estimated gap is the true gap and that interval width scales with 1/sqrt(n); the estimated gap itself is uncertain

## Conclusion

The honest best result on this file is the **randomized average effect** (Mens e-mail +6.8 buyers per 1,000, interval 5.0 to 8.6) plus a model that ranks customers slightly better than chance but not provably better than random or a simple rule. Further model complexity does not help: the limit is the number of buyers, not the algorithm. The productive next step is a larger randomized pilot with a holdout, sized as above, which is already the recommendation.

Figures: `reports/campaign_lab/fig1..fig6*.png`. Raw numbers: `reports/campaign_lab/results.json`, `extras.json`.
