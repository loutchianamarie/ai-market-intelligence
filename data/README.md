# Data

`data/raw/` and `data/processed/` are **gitignored**. Never commit raw data or household-level files.

## Get the data (one command)
```
python -m mi.ingest.download        # fetches the authentic 84.51 Complete Journey tables, writes manifest.json with sha256
```
- Source: R package maintainers, https://github.com/bradleyboehmke/completejourney, pinned commit `5b5d06192b98…`. The package `DESCRIPTION` declares **License: CC0**; the data originate from 84.51° Complete Journey 2.0 source files.
- Files: transactions.rds (1,469,307 lines), products, campaigns, campaign_descriptions, coupons, coupon_redemptions, demographics. promotions.rds (25 MB) is optional (`--with-promotions`).
- **Do not use `completejourney_py`**: its README states the data are simulated.

If the download fails, `python -m mi.ingest.audit` reports the missing files and these instructions. It never loads a mirror silently.

## H&M route (not used)
The H&M Personalized Fashion Recommendations data require Kaggle sign-in and acceptance of the competition rules (noncommercial/academic use). If the team later obtains access, place the official CSVs locally and record the acceptance in `docs/dataset_decision.md`. Do not download from mirrors.

## Other folders
- `data/sources/corpus.jsonl`: short, dated extracts used for retrieval (committed). `data/sources/_cache/` holds fetched pages (gitignored).
- `data/seo/`: frozen prompt panel and the team's answer log.
