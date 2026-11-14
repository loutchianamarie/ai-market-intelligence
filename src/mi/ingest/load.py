"""Read the authentic Complete Journey R files into typed pandas frames (cached as Parquet).

Raw files are never modified. The Parquet cache lives in data/processed (gitignored).
"""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from mi.paths import PROCESSED, RAW

TABLES = {
    "transactions": ("transactions.rds", None),
    "products": ("products.rda", "products"),
    "campaigns": ("campaigns.rda", "campaigns"),
    "campaign_descriptions": ("campaign_descriptions.rda", "campaign_descriptions"),
    "coupons": ("coupons.rda", "coupons"),
    "coupon_redemptions": ("coupon_redemptions.rda", "coupon_redemptions"),
    "demographics": ("demographics.rda", "demographics"),
}


class DataMissingError(RuntimeError):
    pass


FALLBACK_HELP = (
    "Complete Journey raw files not found in data/raw/. Run:\n"
    "    python -m mi.ingest.download\n"
    "This fetches the CC0 files from the R package maintainer (github.com/bradleyboehmke/completejourney).\n"
    "Do NOT substitute the `completejourney_py` package: it declares its data simulated."
)


def _read_r(fname: str, key):
    import pyreadr

    path = RAW / fname
    if not path.exists():
        raise DataMissingError(FALLBACK_HELP)
    res = pyreadr.read_r(str(path))
    return res[key] if key in res else next(iter(res.values()))


@lru_cache(maxsize=None)
def load(name: str) -> pd.DataFrame:
    cache = PROCESSED / f"{name}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    fname, key = TABLES[name]
    df = _read_r(fname, key)
    for col in df.columns:
        if isinstance(df[col].dtype, pd.CategoricalDtype):
            df[col] = df[col].astype("string")
    if name in ("campaign_descriptions",):
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"] = pd.to_datetime(df["end_date"])
    if name == "coupon_redemptions":
        df["redemption_date"] = pd.to_datetime(df["redemption_date"])
    df.to_parquet(cache, index=False)
    return df


def manifest() -> dict:
    p = RAW / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}
