# Metric contracts and economics

Engine: `src/mi/decision/metrics.py`. Rules: **sum first, then divide**; a zero denominator returns `Undefined(reason)`; currencies must match; round only for display.

| Metric | Numerator / denominator | Available for the grocery case? |
|---|---|---|
| Completed net revenue | sales of completed orders, net of returns/cancellations | Partly. Sales are observed; **returns are not in the data** |
| AOV | net revenue / completed orders | Yes (per basket), descriptive only |
| CPA | spend / completed orders | **No**: no ad or contact spend in data |
| CAC | acquisition spend / new customers | **No**: no acquisition spend; panel holds existing households only |
| Shop / blended / platform ROAS | attributed revenue / ad spend | **No**: no spend |
| Break-even ROAS | 1 / contribution margin | Only as a formula; margin is ASSUMED |
| Contribution | incremental revenue × margin − incremental variable and marketing costs | Only in SIMULATION, and from a future pilot |
| ROI | (incremental contribution − cost) / cost | Future pilot only |

**Never displayed as measured for this case:** CAC, ROAS, net-of-returns profit, LTV.

## Pilot economics (SIMULATION; inputs labelled)
Per contacted household *h* (category *c*, segment *s*, channel *k*):

`v_h = Δq_s · (g_c − F_c) − c_k − q0_h · r · F_c`

- `g_c` = OBSERVED mean 4-week category spend among buyers × ASSUMED margin (e.g., frozen pizza $10.33 × 0.28 = $2.89)
- `F_c` = OBSERVED mean historical coupon discount (frozen pizza $0.90)
- `q0_h` = MODEL ESTIMATE of purchase without intervention; `r` = ASSUMED redemption share of would-buy households (0.35)
- `c_k` = ASSUMED contact cost (mail $0.50, digital $0.03); `Δq_s` = ASSUMED uplift (LAPSING 0.04)

Break-even uplift (per household, before fixed setup): `Δq* = (c_k + q̄0 · r · F_c) / (g_c − F_c)`.
Frozen pizza / lapsing / digital: (0.03 + 0.305 × 0.35 × 0.905) / (2.893 − 0.905) = **0.064**, which is 1.6× the assumed 0.04.
With fixed setup F: multiple needed = (F / (scale × reach share) + Σ(c + q0 r F_c)) / Σ Δq (g − F_c). This gives 4.2× at 40× scale, 2.6× at 100×, 2.0× at 250×.

Interpretation, with its assumption stated: **Assumption A1** approximates each household's no-coupon purchase probability by its historical propensity `q0`. Historical data cannot measure who would buy without a coupon. Under A1, coupon cost on purchases the coupon did not cause grows with `q0`, and with uplift held constant within a segment, lower-`q0` households look more valuable. That is why a "model-filtered" variant can win in a scenario. It is a **hypothesis for a stratified randomized pilot**, not evidence that the model identifies persuadable customers. A higher score is not automatically a better investment; only a holdout can measure response.

Scale-free check: per 1,000 contacted households before fixed setup, the best base-case plan is −$44 (Frozen Pizza/lapsing −$47; broad mailing −$651). The 40×/100×/250× "deployment scale" is a HYPOTHETICAL company size, not data.

## Pilot sizing (corrected 2026-11-14)
- **Purchase-rate proxy:** 866 per arm detects a 6.4 pp uplift *at* break-even. At break-even, contribution is zero, so this cannot support EXPAND on the primary metric.
- **Contribution-based:** n = (1.96 + 0.84)² · 2σ² / δ², with σ = 0.28 × SD of 4-week frozen-pizza spend among lapsing households in the historical test window (= $1.64, OBSERVED × ASSUMED). δ = (k − 1) · Δq* · (g − F).
  - k = 1.5 → 10,487 per arm; k = 2 → 2,623; k = 3 → 656.
- Minimum uplift needed for EXPAND by n per arm: 406 → 22.5 pp; 866 → 17.4 pp; 2,000 → 13.7 pp; 5,000 → 11.0 pp. Source: `reports/claim_audit.json`.

## FashionForward (synthetic course fixture, arithmetic check only)
`python -m mi.decision.fashionforward`: rules R1–R4 remove 135 duplicate orders and 12 test orders. Rule-less revenue is overstated by 19.6%. TikTok's platform-reported ROAS is 4.44 vs a shop-measured 1.47 (break-even 1.82 at the fixture's 55% margin). This fixture's customers and margin are **never** mixed with the grocery case.

## R$1 million CEO scenario
Not included. The official brief was not supplied, and the blueprint treats the R$ envelope as conditional. If the brief requires it, add a staged envelope labelled ILLUSTRATIVE, in a separate currency section, with tranches released only on gates (data rights → model beats rule → approved pilot → measured contribution). Never mix it with USD scenario numbers.
