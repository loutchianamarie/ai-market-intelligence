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

Interpretation for marketing allocation: the subsidy term `q0 · r · F` grows with the model score. Coupons to likely buyers are money transferred to customers who would have bought anyway. That is why a higher score is not automatically a better investment, and why the model's role is to *exclude* households.

## FashionForward (synthetic course fixture, arithmetic check only)
`python -m mi.decision.fashionforward`: rules R1–R4 remove 135 duplicate orders and 12 test orders. Rule-less revenue is overstated by 19.6%. TikTok's platform-reported ROAS is 4.44 vs a shop-measured 1.47 (break-even 1.82 at the fixture's 55% margin). This fixture's customers and margin are **never** mixed with the grocery case.

## R$1 million CEO scenario
Not included. The official brief was not supplied, and the blueprint treats the R$ envelope as conditional. If the brief requires it, add a staged envelope labelled ILLUSTRATIVE, in a separate currency section, with tranches released only on gates (data rights → model beats rule → approved pilot → measured contribution). Never mix it with USD scenario numbers.
