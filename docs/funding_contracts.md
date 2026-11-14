# Same plan, explicit offer-funding contracts (Frozen Pizza / lapsing / digital)

Historical match shares are OBSERVED for past coupon lines (reports/funding_audit.json); the funding of the proposed digital offer is UNKNOWN until the client confirms the contract.

| contract | retailer cost per redemption | contribution per contacted hh @4 pp | break-even response | pool needed to cover $1,500 setup @4 pp | test n/arm (2× break-even rule) | n/arm to beat setup hurdle @4 pp | A / B / C @4 pp (USD) | optimizer recommends |
|---|---:|---:|---:|---|---:|---|---|---|
| RETAILER_FUNDED | $0.90 | $-0.044 | 6.23 pp | none: negative per household | 2,737 | n/a (4 pp below hurdle) | -1,824 / -1,699 / -1,703 | NONE: research / measure first |
| SHARED_50_50 | $0.45 | $+0.021 | 3.15 pp | 72422 | 7,094 (exceeds pool) | n/a (4 pp below hurdle) | -1,349 / -1,407 / n/a (test > pool) | NONE: research / measure first |
| MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE | $0.32 | $+0.040 | 2.44 pp | 37299 | 10,628 (exceeds pool) | n/a (4 pp below hurdle) | -1,206 / -1,319 / n/a (test > pool) | NONE: research / measure first |
| MANUFACTURER_FUNDED_NO_MATCH | $0.00 | $+0.086 | 1.04 pp | 17498 | 46,638 (exceeds pool) | n/a (4 pp below hurdle) | -874 / -1,114 / n/a (test > pool) | NONE: research / measure first |

Assumed reachable pool 7,308 (COMPANY SCALE ASSUMED); setup $1,500 and contact $0.03 per household (ASSUMED); response 4 pp (ASSUMED).

## Ranking under each contract (top 4, base other inputs)

- **RETAILER_FUNDED:** 1. NONE: research / measure first (+0); 2. COFFEE/LAPSING/digital_coupon/ALL (-1,724); 3. COFFEE/RECENT_LIGHT/digital_coupon/ALL (-1,795); 4. FROZEN PIZZA/LAPSING/digital_coupon/ALL (-1,824)
- **SHARED_50_50:** 1. NONE: research / measure first (+0); 2. FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED (-1,334); 3. FROZEN PIZZA/LAPSING/digital_coupon/ALL (-1,349); 4. COFFEE/LAPSING/digital_coupon/MODEL_FILTERED (-1,409)
- **MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE:** 1. NONE: research / measure first (+0); 2. FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED (-1,206); 3. FROZEN PIZZA/LAPSING/digital_coupon/ALL (-1,206); 4. COFFEE/LAPSING/digital_coupon/MODEL_FILTERED (-1,337)
- **MANUFACTURER_FUNDED_NO_MATCH:** 1. NONE: research / measure first (+0); 2. FROZEN PIZZA/LAPSING/digital_coupon/ALL (-874); 3. FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED (-874); 4. BAG SNACKS/LAPSING/digital_coupon/ALL (-1,103)

## Combinations that reverse NONE (selected grid; not probabilities)

Cases were SELECTED by us (plausible-looking levels), not sampled from a distribution; a count of reversing cases is NOT a probability. Use the minimal combinations as a checklist of what would have to be confirmed.

- **RETAILER_FUNDED:** 9 of 36 selected cases; reverses at all-base values: False. Minimal combinations:
  - {'uplift_multiplier': 1.5, 'scale': 100.0, 'fixed_setup': 750.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
  - {'uplift_multiplier': 1.5, 'scale': 250.0, 'fixed_setup': 1500.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
  - {'uplift_multiplier': 2.0, 'scale': 100.0, 'fixed_setup': 1500.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
  - {'uplift_multiplier': 2.0, 'scale': 250.0, 'fixed_setup': 1500.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
- **SHARED_50_50:** 22 of 36 selected cases; reverses at all-base values: False. Minimal combinations:
  - {'uplift_multiplier': 1.0, 'scale': 100.0, 'fixed_setup': 750.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
  - {'uplift_multiplier': 1.0, 'scale': 250.0, 'fixed_setup': 1500.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
  - {'uplift_multiplier': 1.0, 'scale': 250.0, 'fixed_setup': 750.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
  - {'uplift_multiplier': 1.5, 'scale': 40.0, 'fixed_setup': 750.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 1.5, 'scale': 100.0, 'fixed_setup': 1500.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 1.5, 'scale': 100.0, 'fixed_setup': 750.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 1.5, 'scale': 250.0, 'fixed_setup': 1500.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL + COFFEE/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 2.0, 'scale': 40.0, 'fixed_setup': 750.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 2.0, 'scale': 100.0, 'fixed_setup': 1500.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
- **MANUFACTURER_FUNDED_HISTORICAL_MATCH_ANALOGUE:** 24 of 36 selected cases; reverses at all-base values: False. Minimal combinations:
  - {'uplift_multiplier': 1.0, 'scale': 100.0, 'fixed_setup': 750.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 1.0, 'scale': 250.0, 'fixed_setup': 1500.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/MODEL_FILTERED'}
  - {'uplift_multiplier': 1.5, 'scale': 40.0, 'fixed_setup': 750.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 1.5, 'scale': 100.0, 'fixed_setup': 1500.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 2.0, 'scale': 40.0, 'fixed_setup': 750.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
- **MANUFACTURER_FUNDED_NO_MATCH:** 30 of 36 selected cases; reverses at all-base values: False. Minimal combinations:
  - {'uplift_multiplier': 1.0, 'scale': 40.0, 'fixed_setup': 750.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 1.0, 'scale': 100.0, 'fixed_setup': 1500.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 1.5, 'scale': 40.0, 'fixed_setup': 750.0, 'margin_rate': 0.28, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
  - {'uplift_multiplier': 2.0, 'scale': 40.0, 'fixed_setup': 1500.0, 'margin_rate': 0.35, 'plan': 'FROZEN PIZZA/LAPSING/digital_coupon/ALL'}
