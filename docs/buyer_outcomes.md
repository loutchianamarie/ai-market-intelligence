# Buyer-outcome panel

**Objective:** increase unique category buyers (incl. returning lapsed buyers) and incremental contribution. Horizon 4 weeks. Buyer = unique household buying the category in the horizon. Not measurable here: new-to-retailer acquisition; a live company's growth.

## A. FROZEN PIZZA / LAPSING / digital_coupon coupon (plan A)

| row | value | label |
|---|---|---|
| eligible panel households | 406 (contactable: 0) | OBSERVED |
| eligible / reachable / consent unknown (company) | 16,240 / 7,308 / 8,932 | COMPANY SCALE ASSUMED |
| expected buyers in 4 weeks, current patterns (panel) | 120.3 of 406 (95% [103.0, 137.7]; calibration-adjusted [99.2, 173.3]) | MODEL ESTIMATE, not a no-contact counterfactual |
| calibration check (window 49) | observed 135 vs predicted 122.3 (ratio 1.104, CI [0.963, 1.259]) | OBSERVED backtest |
| current-pattern buyers among reachable (company) | 2,166.1 | MODEL ESTIMATE × ASSUMED scale |
| ADDITIONAL buyers from the coupon (low / base / high) | 146.2 / 292.3 / 511.6 (cap 5,141.9) | SCENARIO (assumed [0.02, 0.04, 0.07] points) |
| total buyers with the coupon (low / base / high) | 2,312.3 / 2,458.4 / 2,677.7 | SCENARIO |
| break-even ADDITIONAL buyers | 1,209.4 | SCENARIO |
| incremental receipts (USD, low / base / high) | 1,510.64 / 3,020.25 / 5,286.21 | SCENARIO |
| incremental contribution (USD, low / base / high) | -2,114.33 / -1,823.8 / -1,387.71 | SCENARIO |
| observed after action | NOT RUN: no action has been executed; no observed buyers exist | — |

Guard: additional buyers are added to the current-pattern total once; households already expected to buy contribute only the coupon subsidy.

## B. Yogurt availability / assortment / placement investigation (plan B)

- Current-pattern buyers (panel, 4 weeks): 422.0 of 2319 scored households (MODEL ESTIMATE).
- Additional buyers: UNKNOWN: no sourced or assumed effect of a fix exists; cause not diagnosed.
- Target: {'metric': 'unique yogurt buyers per 25-week window among active panel households', 'baseline_latest_window': 1111, 'earlier_window': 1194, 'proposed_target': 'restore buyer rate to 49.9% (≈ +93 households on the latest active base)', 'status': 'PROPOSED TARGET with observed baseline; not a forecast'}
- Budget: $0; observed: NOT RUN.

## C. Discovery content for the public analogue (plan C)

- Unit: assistant answers mentioning / recommending the analogue (of 20); owned-page search clicks if a site owner supplies Search Console.
- Answers logged: 20/20. answers logged from two Claude models (not ChatGPT or Gemini); effect on buyers still UNKNOWN. Additional buyers: UNKNOWN: content effects on buyers cannot be measured from this data.

## D. No paid action / research first (plan D)

- buyers still buy under current patterns; no incremental cost or claimed effect. Additional buyers 0; incremental contribution $0.

