# Model card — run-fb9020ccd9

**Status:** OBSERVED (historical backtest) — predicts observed purchase under historical conditions, NOT response to a coupon

**Intended use:** rank existing households by the probability of buying a category in the next 4 weeks under historical conditions (audience sizing, demand context, test stratification). **Not** coupon uplift, persuadability or a demand forecast.
- Features (20): cat_baskets_4w, cat_baskets_12w, cat_weeks_active_12w, cat_weeks_since_last, cat_spend_12w, cat_share_spend_12w, hh_baskets_4w, hh_baskets_12w, hh_weeks_active_12w, hh_spend_12w, hh_distinct_cats_12w, cat_pop_4w, cat_pop_trend, hh_coupon_disc_12w, hh_redemptions_12w, hh_campaigns_started, cat_private_share_12w, cat_weeks_active_prior14, cat_bought_before_lookback, history_weeks_available
- Long-history features adopted 2026-11-14 under the pre-registered protocol `data/eval/model_eval_protocol_v1.json`; full evaluation (rolling origin, calibration drift, contact sizes, subgroups with CIs) in `reports/model_evaluation.md`.
- `history_weeks_available` is a time index (weeks of data before the lookback); trees treat later cutoffs as the training maximum.
- Target: household buys category in the next 4 weeks (any basket)
- Unit: (cutoff_week, household_id, product_category)
- Seed 20261114, config hash `562d203b67791ea9`, data commit `5b5d06192b98`
- Selected on validation AP: **hgb_small** ({"logreg_l2": 0.6743, "hgb_small": 0.679, "hgb_deeper": 0.6783, "rule_repeat": 0.628, "rule_popularity": 0.3409})
- Calibration: isotonic regression fit on calibration window only

## Split

| split | cutoffs | rows | households | positives | prevalence |
|---|---|---:|---:|---:|---:|
| train | [13, 17, 21, 25, 29, 33, 37] | 128,112 | 2,439 | 34,655 | 0.271 |
| validation | [41] | 18,456 | 2,307 | 5,146 | 0.279 |
| calibration | [45] | 18,368 | 2,296 | 5,053 | 0.275 |
| test | [49] | 18,480 | 2,310 | 5,082 | 0.275 |

## Out-of-time evaluation window (cutoff 49 → weeks 50–53; inspected in earlier passes, so this is REPEATED evaluation)

| scorer | AP | ROC AUC | Brier (calibrated) | precision top 10% | Recall@3 per household |
|---|---:|---:|---:|---:|---:|
| model_hgb_small | 0.6717 | 0.8269 | 0.1412 | 0.8063 | 0.6254 |
| rule_repeat | 0.6210 | 0.7865 | 0.1485 | 0.7830 | 0.6044 |
| rule_popularity | 0.3523 | 0.6125 | 0.1934 | 0.4259 | 0.4927 |

Prevalence 0.2750. Household-cluster bootstrap (200 draws), model − repeat rule: AP +0.0504 (95% CI +0.0453 to +0.0556); Brier -0.00732 (95% CI -0.00844 to -0.00595).
**Score used by the decision tools:** `model` (model is used only if the AP gain CI excludes 0).

## By category (test)

| category | prevalence | AP model | AP repeat rule |
|---|---:|---:|---:|
| BAG SNACKS | 0.432 | 0.768 | 0.727 |
| COFFEE | 0.168 | 0.610 | 0.537 |
| COLD CEREAL | 0.297 | 0.659 | 0.614 |
| FROZEN PIZZA | 0.285 | 0.654 | 0.593 |
| ICE CREAM/MILK/SHERBTS | 0.240 | 0.567 | 0.521 |
| REFRGRATD JUICES/DRNKS | 0.282 | 0.687 | 0.647 |
| SOUP | 0.333 | 0.678 | 0.644 |
| YOGURT | 0.163 | 0.630 | 0.583 |

## By segment (test)

| segment | n | prevalence | mean pred model | Brier model | Brier rule |
|---|---:|---:|---:|---:|---:|
| ACTIVE_NONBUYER | 5,564 | 0.127 | 0.132 | 0.1041 | 0.1110 |
| LAPSING | 3,226 | 0.299 | 0.292 | 0.1973 | 0.2077 |
| LOW_ACTIVITY | 4,071 | 0.073 | 0.074 | 0.0652 | 0.0693 |
| RECENT_LIGHT | 2,373 | 0.368 | 0.363 | 0.2141 | 0.2254 |
| REGULAR | 3,246 | 0.689 | 0.684 | 0.1907 | 0.1971 |

## Documented failure

- Weakest category vs rule: SOUP (AP model 0.678 vs rule 0.644)
- Buyers given < 5% probability: 73 (1.4% of positives); mix {'LOW_ACTIVITY': 52, 'ACTIVE_NONBUYER': 21}
- Households with no category purchase in 12 weeks who then buy are near-unpredictable from behaviour alone; the model gives them low scores. This is the cold-start limit.

## Ablation (test AP, same config refit)

- no_campaign_coupon_features: 0.6744
- no_popularity_features: 0.6729
- backtest_cutoff_45_AP_model: 0.6745
- backtest_cutoff_45_AP_rule: 0.6217

## Limits

- Historical propensity ≠ incremental effect of a coupon. Campaign exposure was not randomized.
- Test window is the holiday period (weeks 50–53); seasonality may differ from other months.
- One anonymous retailer's 2,469-household panel; no margin, stock, consent or cost data.
- Demographics (801 households) deliberately excluded: incomplete and not needed for behavioural targeting.
