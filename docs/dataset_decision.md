# Dataset decision (spike completed 2026-11-14)

**Decision:** 84.51° Complete Journey, using the **authentic** tables published by the R package maintainers (github.com/bradleyboehmke/completejourney, `DESCRIPTION: License: CC0`, pinned commit `5b5d0619`), read in Python with `pyreadr`.
**Rejected for this build:** H&M Personalized Fashion Recommendations. It is not worse; it was *blocked*. Its official files need a Kaggle sign-in and competition-rule acceptance, and there are no Kaggle credentials in this environment. No mirror was used.
**Not used:** `completejourney_py`. Its own README says *"This package contains simulated data based on real grocery shopping patterns … should not be used for academic research"*. It also reports 801 households, while the maintainers document 2,469. 801 is the size of the demographics subset, as our audit confirms.

The business question is unchanged from the blueprint: *where should a retailer put its next limited commercial budget, across product categories × existing customer segments × channel, and what should it test before expanding?*

## Option comparison against the SAME product × customer × budget × pilot decision

| Criterion | H&M (Kaggle) | Complete Journey (chosen) |
|---|---|---|
| Access in this environment | **Blocked**: gated; no credentials | Open: CC0 files from the maintainers, downloaded with a checksum manifest |
| Grain / keys | transactions (date, customer, article), customers, articles | transactions (household, basket, product, week, timestamp, sales, discounts), products, campaigns, coupons, redemptions, demographics (801 of 2,469) |
| Size / span | ~3.5 GB transactions, 2018–2020 | 1,469,307 lines, 2,469 households, 155,848 baskets, 2017 (weeks 1–53) |
| Marketing contact | none | 27 campaigns (types A/B/C), 6,589 household-campaign pairs, 2,102 redemptions. **Not documented as randomized** |
| Model target fit | next-period customer × category purchase | next-4-week household × category purchase (built and tested) |
| Leakage risks | future popularity, profile updates | future redemptions, campaigns that start after the cutoff (both guarded and tested) |
| Same-brand SEO/GEO | strong (named brand) | **weak**: retailer is anonymous, so the GEO audit uses a *labelled public analogue* |
| Missing for economics | cost, stock, returns, exposure | cost/margin, stock, returns, contact cost, consent, random assignment |
| Build effort | high (large, gated) | low: whole pipeline runs in ~1.5 min on a laptop |

## What this data lets the presentation claim

| Claim | Allowed? | Evidence |
|---|---|---|
| A fitted model beats simple rules at predicting next-4-week category purchase among existing households | **Yes (OBSERVED backtest)** | `reports/model_card.md` |
| The model predicts coupon response or incremental sales | **No** | No randomized treatment in the data |
| Historical campaigns worked | **No**. We can show only that recipients were heavier shoppers *before* campaigns (selection) | `campaign_history()` |
| Plan X is profitable | **No**. Only *conditional on labelled assumptions* | `reports/portfolio.md` |
| The audited brand's AI-search visibility | Only for the analogue (20 real answers from two Claude models are logged; see `docs/geo_audit_results.md`) | `data/seo/` |
| The households are Kroger's customers | **No**. The dataset is anonymous; the GEO analogue is a separate public brand | — |

**Fallbacks not needed:** Olist (it reframes the project as B2B seller acquisition) and X5 (a treatment benchmark with unverified rights and assignment) were not evaluated further because a core route worked.
