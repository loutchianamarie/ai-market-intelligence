# Model evaluation (pre-registered protocol v1)

Protocol: `data\eval\model_eval_protocol_v1.json`. Production: `hgb_small`. **Adopted after the rule: `hgb_small_longhist`.**
Window 49 (Dec 2017) was inspected in earlier passes, so its numbers are *repeated evaluation*, not an untouched test.
Purchase probability under historical conditions is **not** coupon uplift.

## Adoption rule

Replace hgb_small only if a candidate improves AP by >= 0.005 on the selection window 41 AND on the rolling-origin window 45, AND does not lower AP on the no-recent-history subgroup (LOW_ACTIVITY + ACTIVE_NONBUYER) at window 41. Otherwise keep hgb_small and report the negative result.

| candidate | AP gain @41 | AP gain rolling @45 | no-recent-history AP change @41 | passes |
|---|---:|---:|---:|---|
| logreg_l2 | -0.0037 | -0.0053 | -0.0228 | False |
| hgb_small_longhist | +0.0138 | +0.0100 | +0.0311 | True |

## Rolling-origin AP (refit on all earlier label windows)

| target | prevalence | rule_popularity | rule_repeat | logreg_l2 | hgb_small | hgb_small_longhist |
|---|---:|---:|---:|---:|---:|---:|
| 41 | 0.279 | 0.341 | 0.628 | 0.661 | 0.665 | 0.679 |
| 45 | 0.275 | 0.344 | 0.622 | 0.661 | 0.666 | 0.676 |
| 49 | 0.275 | 0.352 | 0.621 | 0.664 | 0.664 | 0.674 |

## Calibration (isotonic fit on 45, evaluated on 49; drift: fit on 41)

| scorer | Brier 45→49 | ECE 45→49 | ECE 41→45 | ECE 41→49 |
|---|---:|---:|---:|---:|
| rule_popularity | 0.1934 | 0.0248 | 0.0108 | 0.0196 |
| rule_repeat | 0.1485 | 0.0076 | 0.0165 | 0.0134 |
| logreg_l2 | 0.1438 | 0.0047 | 0.0081 | 0.0082 |
| hgb_small | 0.1438 | 0.0058 | 0.0089 | 0.0123 |
| hgb_small_longhist | 0.1412 | 0.0089 | 0.0060 | 0.0122 |

## Contact-size precision / recall on 49 (18,480 household-category rows)

| scorer | AP | top 5% P / R | top 10% P / R | top 20% P / R |
|---|---:|---:|---:|---:|
| rule_popularity | 0.352 | 0.413 / 0.075 | 0.426 / 0.155 | 0.396 / 0.288 |
| rule_repeat | 0.621 | 0.860 / 0.156 | 0.783 / 0.285 | 0.661 / 0.481 |
| logreg_l2 | 0.662 | 0.880 / 0.160 | 0.789 / 0.287 | 0.673 / 0.490 |
| hgb_small | 0.662 | 0.868 / 0.158 | 0.796 / 0.289 | 0.675 / 0.491 |
| hgb_small_longhist | 0.672 | 0.878 / 0.160 | 0.806 / 0.293 | 0.674 / 0.490 |

## Subgroups on 49 (adopted model vs repeat rule; CI only with >= 100 positives)

| slice | n | positives | prevalence | AP model | AP rule | AP diff 95% CI | Brier model | Brier rule |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| all | 18480 | 5082 | 0.275 | 0.672 | 0.621 | [0.0453, 0.0556] | 0.141 | 0.149 |
| category=BAG SNACKS | 2310 | 998 | 0.432 | 0.768 | 0.727 | [0.0327, 0.0497] | 0.179 | 0.195 |
| category=FROZEN PIZZA | 2310 | 659 | 0.285 | 0.654 | 0.593 | [0.0488, 0.0754] | 0.150 | 0.158 |
| category=COLD CEREAL | 2310 | 685 | 0.297 | 0.659 | 0.614 | [0.0305, 0.0603] | 0.156 | 0.162 |
| category=SOUP | 2310 | 769 | 0.333 | 0.678 | 0.644 | [0.0227, 0.0485] | 0.165 | 0.170 |
| category=ICE CREAM/MILK/SHERBTS | 2310 | 554 | 0.240 | 0.567 | 0.521 | [0.0299, 0.0618] | 0.144 | 0.149 |
| category=YOGURT | 2310 | 377 | 0.163 | 0.630 | 0.583 | [0.0303, 0.0599] | 0.095 | 0.101 |
| category=COFFEE | 2310 | 389 | 0.168 | 0.610 | 0.537 | [0.0512, 0.0901] | 0.097 | 0.105 |
| category=REFRGRATD JUICES/DRNKS | 2310 | 651 | 0.282 | 0.687 | 0.647 | [0.0273, 0.0533] | 0.143 | 0.148 |
| segment=ACTIVE_NONBUYER | 5564 | 705 | 0.127 | 0.243 | 0.127 | [0.0965, 0.146] | 0.104 | 0.111 |
| segment=LAPSING | 3226 | 966 | 0.299 | 0.424 | 0.353 | [0.043, 0.0987] | 0.197 | 0.208 |
| segment=LOW_ACTIVITY | 4071 | 299 | 0.073 | 0.167 | 0.073 | [0.0661, 0.1241] | 0.065 | 0.069 |
| segment=RECENT_LIGHT | 2373 | 874 | 0.368 | 0.525 | 0.428 | [0.0681, 0.1285] | 0.214 | 0.225 |
| segment=REGULAR | 3246 | 2238 | 0.689 | 0.845 | 0.820 | [0.0171, 0.0326] | 0.191 | 0.197 |
| no_recent_history | 9635 | 1004 | 0.104 | 0.223 | 0.104 | [0.1015, 0.1457] | 0.088 | 0.093 |

## By window (month)

| cutoff | month | prevalence | AP model | AP rule |
|---|---|---:|---:|---:|
| 41 | Oct 2017 | 0.279 | 0.679 | 0.628 |
| 45 | Nov 2017 | 0.275 | 0.674 | 0.622 |
| 49 | Dec 2017 | 0.275 | 0.672 | 0.621 |

Window 41 also chose the production model; 45 calibrated it. AP on 41/45 is therefore not independent of model choice.
