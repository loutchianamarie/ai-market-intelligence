# Model commercial diagnostic (protocol v2)

Reproduction of production AP on window 49: recomputed 0.671737 vs reported 0.671737 → exact: **True**.

## Promotion-context ablation (pre-registered rule)

Gain @41 -0.0001; rolling @45 -0.0002; no-recent-history @41 +0.0002 → **adopted: False** (model used below: `production`).

## Commercial reach at fixed contact capacity (window 49, repeated evaluation)

| contacts (household × category rows) | purchases found: model | rule | gain (95% CI) | precision model / rule | unique households model / rule |
|---:|---:|---:|---|---|---|
| 100 | 96 | 97 | -1 (-5 to +2) | 0.960 / 0.970 | 84 / 87 |
| 1,000 | 873 | 851 | +22 (+0 to +35) | 0.873 / 0.851 | 530 / 551 |
| 2,000 | 1,594 | 1,544 | +50 (+26 to +79) | 0.797 / 0.772 | 835 / 897 |

Per category, top 100 contacts: BAG SNACKS 97 vs 94; COFFEE 86 vs 77; COLD CEREAL 87 vs 90; FROZEN PIZZA 91 vs 83; ICE CREAM/MILK/SHERBTS 77 vs 75; REFRGRATD JUICES/DRNKS 95 vs 93; SOUP 85 vs 85; YOGURT 87 vs 87

## Subgroups (window 49)

| group | rows | households | buyers | prevalence | AP model | AP rule | AP diff 95% CI |
|---|---:|---:|---:|---:|---:|---:|---|
| new_to_category | 5,023 | 1,731 | 280 | 0.0557 | 0.1235 | 0.0557 | [0.0493, 0.1032] |
| lapsing | 3,226 | 1,584 | 966 | 0.2994 | 0.4245 | 0.3533 | [0.043, 0.0987] |
| active | 5,619 | 1,682 | 3,112 | 0.5538 | 0.7914 | 0.7637 | [0.0214, 0.0341] |
| no_recent_history | 9,635 | 2,198 | 1,004 | 0.1042 | 0.2232 | 0.1042 | [0.1015, 0.1457] |

## By month

| cutoff | AP model | AP rule | prevalence |
|---|---:|---:|---:|
| 41 | 0.679 | 0.628 | 0.2788 |
| 45 | 0.6745 | 0.6217 | 0.2751 |
| 49 | 0.6717 | 0.621 | 0.275 |

*Purchases reached are buyers identified, NOT buyers persuaded by contact; no model score is coupon uplift.*

Windows 41/45 were used for selection/calibration in earlier passes; 49 is repeated evaluation.
