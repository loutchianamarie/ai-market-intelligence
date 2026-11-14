# Data audit: 84.51 Complete Journey (authentic CC0 package data)

Status: **OBSERVED** facts computed by `python -m mi.ingest.audit`. Read-only; no rows deleted.

Source: https://github.com/bradleyboehmke/completejourney @ commit `5b5d06192b98` (licence CC0 (package DESCRIPTION))

| file | bytes | sha256 (first 16) | retrieved |
|---|---:|---|---|
| transactions.rds | 12,775,661 | `1fa0700033f1e5d9` | 2026-11-13T23:55:32+00:00 |
| products.rda | 869,019 | `a80c6df33623b4af` | 2026-11-13T23:55:34+00:00 |
| campaigns.rda | 8,264 | `33c7b3dc1bc722d4` | 2026-11-13T23:55:34+00:00 |
| campaign_descriptions.rda | 496 | `601bd17ea1a6de92` | 2026-11-13T23:55:35+00:00 |
| coupons.rda | 324,969 | `4d87effce5b8813c` | 2026-11-13T23:55:36+00:00 |
| coupon_redemptions.rda | 8,370 | `4b68148175ed1930` | 2026-11-13T23:55:36+00:00 |
| demographics.rda | 4,237 | `8b80455bc841003b` | 2026-11-13T23:55:37+00:00 |

## Tables

| table | rows | columns with nulls |
|---|---:|---|
| transactions | 1,469,307 | none |
| products | 92,331 | product_category 0.6%, product_type 0.6%, package_size 33.1% |
| campaigns | 6,589 | none |
| campaign_descriptions | 27 | none |
| coupons | 116,204 | none |
| coupon_redemptions | 2,102 | none |
| demographics | 801 | home_ownership 29.1%, marital_status 17.1% |

## Transactions

- **households**: 2469
- **baskets**: 155848
- **products**: 68509
- **stores**: 457
- **timestamp_min**: 2017-01-01 11:53:26
- **timestamp_max**: 2018-01-01 04:01:20
- **week_min**: 1
- **week_max**: 53
- **rows_per_week_first_last**: {1: 3722, 2: 31454, 52: 33126, 53: 24886}
- **exact_duplicate_rows**: 0
- **duplicate_basket_product_rows**: 0
- **zero_sales_value_rows**: 11226
- **negative_sales_value_rows**: 0
- **zero_quantity_rows**: 8869
- **quantity_gt_100_rows**: 13510
- **discount_sign_convention**: positive magnitudes
- **rows_with_coupon_disc**: 21889
- **duplicate_policy**: Report only. Identical-looking lines can be genuine; nothing deleted.

## Join coverage

- tx_product_coverage: 0.99671
- demographics_household_coverage: 0.3244
- campaign_households_in_tx: 1.0
- coupon_products_in_products: 0.9999
- redemption_coupons_in_coupons: 1.0

## Anomalies

- quantity > 100 by department: {'FUEL': 11830, 'MISCELLANEOUS': 1679, 'PRODUCE': 1}
- Large quantities concentrate in FUEL/MISC; candidate categories exclude these departments.

## Campaigns and coupons

- n_campaigns: 27
- types: {'Type B': 17, 'Type C': 6, 'Type A': 4}
- start_min: 2016-11-14
- end_max: 2018-02-28
- household_campaign_pairs: 6589
- households_receiving_any: 1559
- redemptions: 2102
- redemption_date_range: ['2017-01-01', '2017-12-31']
- assignment: UNKNOWN / not documented as randomized. Treat as observational selection.

## Candidate categories (frozen in configs/policy.json)

| category | lines | sales $ | households (year) | year penetration | median weekly buying households |
|---|---:|---:|---:|---:|---:|
| BAG SNACKS | 38,088 | 84,944 | 2,149 | 87.0% | 385 |
| COFFEE | 7,795 | 36,875 | 1,273 | 51.6% | 118 |
| COLD CEREAL | 21,397 | 63,009 | 1,867 | 75.6% | 252 |
| FROZEN PIZZA | 23,998 | 81,175 | 1,766 | 71.5% | 218 |
| ICE CREAM/MILK/SHERBTS | 16,088 | 46,877 | 1,853 | 75.0% | 195 |
| REFRGRATD JUICES/DRNKS | 17,317 | 40,721 | 1,824 | 73.9% | 239 |
| SOUP | 25,789 | 49,027 | 1,932 | 78.2% | 240 |
| YOGURT | 25,554 | 34,439 | 1,493 | 60.5% | 181 |

## Not in the data (must stay ASSUMED or UNKNOWN)

- product cost / margin
- inventory / stock
- returns
- ad or contact cost
- documented random assignment of campaigns
- customer consent / reachability
- retailer identity (anonymous by design)
