# Hillstrom targeting on the VISIT outcome (pre-registered protocol v5)

*Generated from `results.json`.* Protocol: `data/eval/hillstrom_protocol_v5_visit.json`, committed before any fitting. Same data, split, candidates and rules as the purchase lab (v3); only the outcome differs.

**This is an intermediate outcome.** A visit is not a purchase and not revenue. Numbers below are *additional visits*, never buyers or profit. About 14.7% of customers visit (about 15 times more events than purchases), so the test has more power.

## Selection on train + validation (cross-fitted Qini area, visits)

| Candidate | Mean AUQ (visits) | Paired 90% interval vs baseline |
|---|---|---|
| S_LOGIT | 57.4 | baseline |
| S_LOGIT_SPARSE | 71.7 | +8.2 to +37.0 |
| T_LOGIT | 54.8 | -7.8 to -1.3 |
| S_HGB | 56.9 | -8.6 to +14.7 |
| T_HGB | 49.8 | -14.7 to +19.6 |
| TO_RIDGE | 58.8 | -8.5 to +11.6 |
| TO_HGB | 44.7 | -24.7 to +12.5 |
| ENSEMBLE | 55.2 | -6.2 to +3.7 |

Selected: **S_LOGIT_SPARSE** (a challenger was shown better than the baseline). Note: `S_LOGIT_SPARSE` was motivated by segment effects seen in the purchase data before this protocol (disclosed in the protocol).

**Permutation test.** Selected model's out-of-fold AUQ 72.1 against a shuffled-label 95th percentile of 26.3 (p = 0.024).

## Single confirmation on the untouched test split (25,603 customers; additional visits per 1,000 contacts, Mens e-mail)

| Comparison | Value | 95% interval |
|---|---|---|
| MODEL_MENS_25 minus RANDOM_MENS_25 | +12.0 | -8.4 to +32.8 |
| MODEL_MENS_25 minus RULE_RECENCY_MENS_25 | +3.1 | -20.6 to +27.2 |
| MODEL_MENS_25 minus RULE_HISTORY_MENS_25 | -5.1 | -28.2 to +19.3 |
| MODEL_MENS_25: S_LOGIT_SPARSE minus S_LOGIT baseline | +2.3 | -18.3 to +23.7 |
| MODEL_MENS_50 minus RANDOM_MENS_50 | +8.1 | -2.7 to +19.8 |
| MODEL_MENS_50 minus RULE_RECENCY_MENS_50 | +1.3 | -10.8 to +14.4 |
| MODEL_MENS_50 minus RULE_HISTORY_MENS_50 | +1.4 | -10.6 to +13.5 |
| MODEL_MENS_50: S_LOGIT_SPARSE minus S_LOGIT baseline | +3.1 | -7.5 to +14.2 |

## Reading (pre-registered rule)

The pre-registered test is whether MODEL_MENS_25 minus RANDOM_MENS_25 has a 95% interval above zero: here it is +12.0 (-8.4 to +32.8), so targeting is **NOT detectable** on the test split even on the more frequent outcome. There is an in-sample hint (the permutation test on the selection data and the challenger gain), but it does not hold up on the untouched test split, so it stays a hypothesis for a larger test. Nothing here changes the purchase conclusions.
