# Model card — run-0a53542e4e

**Status:** OBSERVED (historical backtest) — predicts observed purchase under historical conditions, NOT response to a coupon

- Target: household buys category in the next 4 weeks (any basket)
- Unit: (cutoff_week, household_id, product_category)
- Seed 20261114, config hash `562d203b67791ea9`, data commit `5b5d06192b98`
- Selected on validation AP: **hgb_small** ({"logreg_l2": 0.6615, "hgb_small": 0.6652, "hgb_deeper": 0.6626, "rule_repeat": 0.628, "rule_popularity": 0.3409})
- Calibration: isotonic regression fit on calibration window only

## Split

| split | cutoffs | rows | households | positives | prevalence |
|---|---|---:|---:|---:|---:|
| train | [13, 17, 21, 25, 29, 33, 37] | 128,112 | 2,439 | 34,655 | 0.271 |
| validation | [41] | 18,456 | 2,307 | 5,146 | 0.279 |
| calibration | [45] | 18,368 | 2,296 | 5,053 | 0.275 |
| test | [49] | 18,480 | 2,310 | 5,082 | 0.275 |

## Locked out-of-time test (cutoff 49 → weeks 50–53, evaluated once)

| scorer | AP | ROC AUC | Brier (calibrated) | precision top 10% | Recall@3 per household |
|---|---:|---:|---:|---:|---:|
| model_hgb_small | 0.6624 | 0.8179 | 0.1438 | 0.7960 | 0.6151 |
| rule_repeat | 0.6210 | 0.7865 | 0.1485 | 0.7830 | 0.6044 |
| rule_popularity | 0.3523 | 0.6125 | 0.1934 | 0.4259 | 0.4927 |

Prevalence 0.2750. Household-cluster bootstrap (200 draws), model − repeat rule: AP +0.0415 (95% CI +0.0376 to +0.0455); Brier -0.00469 (95% CI -0.00576 to -0.00360).
**Score used by the decision tools:** `model` (model is used only if the AP gain CI excludes 0).

## By category (test)

| category | prevalence | AP model | AP repeat rule |
|---|---:|---:|---:|
| BAG SNACKS | 0.432 | 0.763 | 0.727 |
| COFFEE | 0.168 | 0.580 | 0.537 |
| COLD CEREAL | 0.297 | 0.650 | 0.614 |
| FROZEN PIZZA | 0.285 | 0.639 | 0.593 |
| ICE CREAM/MILK/SHERBTS | 0.240 | 0.552 | 0.521 |
| REFRGRATD JUICES/DRNKS | 0.282 | 0.678 | 0.647 |
| SOUP | 0.333 | 0.677 | 0.644 |
| YOGURT | 0.163 | 0.612 | 0.583 |

## By segment (test)

| segment | n | prevalence | mean pred model | Brier model | Brier rule |
|---|---:|---:|---:|---:|---:|
| ACTIVE_NONBUYER | 5,564 | 0.127 | 0.132 | 0.1065 | 0.1110 |
| LAPSING | 3,226 | 0.299 | 0.293 | 0.2011 | 0.2077 |
| LOW_ACTIVITY | 4,071 | 0.073 | 0.071 | 0.0657 | 0.0693 |
| RECENT_LIGHT | 2,373 | 0.368 | 0.371 | 0.2175 | 0.2254 |
| REGULAR | 3,246 | 0.689 | 0.690 | 0.1949 | 0.1971 |

## Documented failure

- Weakest category vs rule: YOGURT (AP model 0.612 vs rule 0.583)
- Buyers given < 5% probability: 50 (1.0% of positives); mix {'LOW_ACTIVITY': 45, 'ACTIVE_NONBUYER': 5}
- Households with no category purchase in 12 weeks who then buy are near-unpredictable from behaviour alone; the model gives them low scores. This is the cold-start limit.

## Ablation (test AP, same config refit)

- no_campaign_coupon_features: 0.6640
- no_popularity_features: 0.6618
- backtest_cutoff_45_AP_model: 0.6652
- backtest_cutoff_45_AP_rule: 0.6217

## Limits

- Historical propensity ≠ incremental effect of a coupon. Campaign exposure was not randomized.
- Test window is the holiday period (weeks 50–53); seasonality may differ from other months.
- One anonymous retailer's 2,469-household panel; no margin, stock, consent or cost data.
- Demographics (801 households) deliberately excluded: incomplete and not needed for behavioural targeting.
