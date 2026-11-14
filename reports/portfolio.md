# Portfolio & risk report

**Status:** SIMULATION — conditional on ASSUMED uplift, margin, redemption, contact cost, reach and scale; q0 is a MODEL ESTIMATE

Config `562d203b67791ea9` · model run `run-fb9020ccd9` · 74 candidate plans · 159 feasible portfolios enumerated exactly among top-12 candidates.

- **Recommended (base case):** NONE: research / measure first
- **Recommended (worst case / robust):** NONE: research / measure first

## Top feasible portfolios vs heuristic vs no action (USD, 4-week pilot at deployment scale)

| plan | net low | net base | net high | cost base | reach |
|---|---:|---:|---:|---:|---:|
| COFFEE/LAPSING/digital_coupon/ALL | -2,663 | -1,724 | 984 | 2,287 | 6,390 |
| COFFEE/RECENT_LIGHT/digital_coupon/ALL | -2,620 | -1,795 | -624 | 1,999 | 3,708 |
| FROZEN PIZZA/LAPSING/digital_coupon/ALL | -2,732 | -1,824 | 2,074 | 2,669 | 7,308 |
| HEURISTIC: BAG SNACKS/BROAD/mail_coupon/ALL (INFEASIBLE) | nan | -62,080 | nan | 63,560 | 92,760 |
| NONE: research / measure first | 0 | 0 | 0 | 0 | 0 |

## What reverses the recommendation

- **uplift_multiplier**: no switch within scanned range
- **margin_rate**: no switch within scanned range
- **fixed_setup**: no switch within scanned range
- **scale**: no switch within scanned range
- **digital_contact_cost**: no switch within scanned range

## Break-even incremental purchase rate (base assumptions; 10 cohorts nearest viability)

| category | segment | channel | panel hh | mean q0 | assumed Δq | break-even Δq | needed ÷ assumed |
|---|---|---|---:|---:|---:|---:|---:|
| FROZEN PIZZA | LAPSING | digital_coupon | 406 | 0.296 | 0.040 | 0.062 | 1.6× |
| COFFEE | LAPSING | digital_coupon | 355 | 0.231 | 0.040 | 0.065 | 1.6× |
| COFFEE | ACTIVE_NONBUYER | digital_coupon | 983 | 0.071 | 0.015 | 0.034 | 2.3× |
| SOUP | LAPSING | digital_coupon | 502 | 0.285 | 0.040 | 0.096 | 2.4× |
| FROZEN PIZZA | ACTIVE_NONBUYER | digital_coupon | 679 | 0.150 | 0.015 | 0.039 | 2.6× |
| FROZEN PIZZA | RECENT_LIGHT | digital_coupon | 322 | 0.364 | 0.025 | 0.073 | 2.9× |
| COFFEE | RECENT_LIGHT | digital_coupon | 206 | 0.317 | 0.025 | 0.081 | 3.2× |
| COLD CEREAL | LAPSING | digital_coupon | 421 | 0.294 | 0.040 | 0.142 | 3.6× |
| SOUP | ACTIVE_NONBUYER | digital_coupon | 509 | 0.150 | 0.015 | 0.065 | 4.4× |
| YOGURT | LAPSING | digital_coupon | 330 | 0.253 | 0.040 | 0.180 | 4.5× |

Fixed setup is excluded from this per-household break-even; it raises the bar further for small cells.

## Uplift multiple needed to break even INCLUDING fixed setup (best 3 cohorts per deployment scale)

| scale | category | segment | channel | reach | × assumed uplift needed |
|---:|---|---|---|---:|---:|
| 40 | FROZEN PIZZA | LAPSING | digital_coupon | 7,308 | 4.14× |
| 40 | COFFEE | LAPSING | digital_coupon | 6,390 | 5.71× |
| 40 | COFFEE | ACTIVE_NONBUYER | digital_coupon | 17,694 | 6.23× |
| 100 | FROZEN PIZZA | LAPSING | digital_coupon | 18,270 | 2.59× |
| 100 | COFFEE | LAPSING | digital_coupon | 15,975 | 3.25× |
| 100 | COFFEE | ACTIVE_NONBUYER | digital_coupon | 44,235 | 3.86× |
| 250 | FROZEN PIZZA | LAPSING | digital_coupon | 45,675 | 1.97× |
| 250 | COFFEE | LAPSING | digital_coupon | 39,938 | 2.27× |
| 250 | COFFEE | ACTIVE_NONBUYER | digital_coupon | 110,588 | 2.92× |

## Reversal grid (recommended plan, base assumptions otherwise)

| uplift × | scale | recommendation | best net |
|---:|---:|---|---:|
| 1.0 | 40 | NONE: research / measure first | -1,724 |
| 1.0 | 100 | NONE: research / measure first | -1,475 |
| 1.0 | 250 | NONE: research / measure first | -1,436 |
| 2.0 | 40 | NONE: research / measure first | -1,205 |
| 2.0 | 100 | NONE: research / measure first | -763 |
| 2.0 | 250 | FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED | 342 |
| 3.0 | 40 | NONE: research / measure first | -661 |
| 3.0 | 100 | FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED | 598 |
| 3.0 | 250 | FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED + COFFEE/LAPSING/digital_coupon/MODEL_FILTERED | 4,769 |
| 4.0 | 40 | NONE: research / measure first | -80 |
| 4.0 | 100 | FROZEN PIZZA/LAPSING/digital_coupon/ALL + COFFEE/LAPSING/digital_coupon/ALL | 2,258 |
| 4.0 | 250 | FROZEN PIZZA/LAPSING/digital_coupon/ALL + COFFEE/LAPSING/digital_coupon/ALL | 10,145 |
| 5.0 | 40 | FROZEN PIZZA/LAPSING/digital_coupon/ALL | 501 |
| 5.0 | 100 | FROZEN PIZZA/LAPSING/digital_coupon/ALL + COFFEE/LAPSING/digital_coupon/ALL + COFFEE/ACTIVE_NONBUYER/digital_coupon/ALL | 5,007 |
| 5.0 | 250 | COFFEE/LAPSING/digital_coupon/ALL + SOUP/LAPSING/digital_coupon/ALL | 9,463 |

## Demand baseline (OBSERVED history, next-4-week trailing baseline)

| category | weekly sales (last 8) | weekly buying hh | 4-week low | base | high | trend | WAPE naive | WAPE trailing-8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BAG SNACKS | 1,685 | 393 | 6,206 | 6,741 | 7,275 | 1.08 | 0.036 | 0.040 |
| COFFEE | 805 | 136 | 2,772 | 3,219 | 3,666 | 1.01 | 0.048 | 0.066 |
| COLD CEREAL | 1,158 | 237 | 4,061 | 4,630 | 5,200 | 0.96 | 0.043 | 0.034 |
| FROZEN PIZZA | 1,650 | 229 | 5,845 | 6,601 | 7,358 | 1.04 | 0.036 | 0.039 |
| ICE CREAM/MILK/SHERBTS | 783 | 181 | 2,857 | 3,132 | 3,408 | 0.88 | 0.082 | 0.104 |
| REFRGRATD JUICES/DRNKS | 788 | 239 | 2,935 | 3,154 | 3,372 | 1.11 | 0.042 | 0.055 |
| SOUP | 1,192 | 284 | 4,341 | 4,770 | 5,198 | 1.04 | 0.120 | 0.164 |
| YOGURT | 553 | 150 | 1,802 | 2,212 | 2,621 | 0.85 | 0.062 | 0.072 |

Panel-level sales (2,469 households), not chain demand. No stock data: capacity remains a human check.
