"""Full Complete Journey promotions table (product x store x week display / mailer placement).

Source: data/promotions.rds at the same pinned maintainer commit as the transactions (CC0). Documented as
20,940,529 rows x 5 variables (https://bradleyboehmke.github.io/completejourney/reference/promotions.html).

The raw R file is read ONCE, immediately compacted (integer ids, int8 week, categorical codes) and cached as
Parquet keyed by the raw file's SHA-256. Checks: row count, key uniqueness of (product_id, store_id, week),
documented code values. Joins to transactions are on (product_id, store_id, week) with an explicit
multiplicity rule. Promotion exposure is OBSERVATIONAL context: it can describe association with buying,
never the causal effect of a display or mailer.

Usage: python -m mi.ingest.promotions   -> data/processed/promotions.parquet, reports/promotions_audit.json
"""
from __future__ import annotations

import gc
import hashlib
import json
import sys
import time

import numpy as np
import pandas as pd

from mi.paths import PROCESSED, RAW, REPORTS

RAW_FILE = RAW / "promotions.rds"
CACHE = PROCESSED / "promotions.parquet"
EXPECTED_ROWS = 20_940_529
DISPLAY = {"0": "Not on Display", "1": "Store Front", "2": "Store Rear", "3": "Front End Cap", "4": "Mid-Aisle End Cap",
           "5": "Rear End Cap", "6": "Side-Aisle End Cap", "7": "In-Aisle", "9": "Secondary Location Display", "A": "In-Shelf"}
MAILER = {"0": "Not on ad", "A": "Interior page feature", "C": "Interior page line item", "D": "Front page feature",
          "F": "Back page feature", "H": "Wrap from feature", "J": "Wrap interior coupon", "L": "Wrap back feature",
          "P": "Interior page coupon", "X": "Free on interior page", "Z": "Free on front page, back page or wrap"}


def _sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_promotions() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError("promotions.rds missing: python -m mi.ingest.download --with-promotions")
    src = _sha(RAW_FILE)
    meta = CACHE.with_suffix(".parquet.source.json")
    if CACHE.exists() and meta.exists() and json.loads(meta.read_text()).get("source_sha256") == src:
        return pd.read_parquet(CACHE)
    import pyreadr
    raw = next(iter(pyreadr.read_r(str(RAW_FILE)).values()))
    df = pd.DataFrame({
        "product_id": pd.to_numeric(raw.pop("product_id"), downcast="integer"),
        "store_id": pd.to_numeric(raw.pop("store_id"), downcast="integer"),
        "week": pd.to_numeric(raw.pop("week"), downcast="integer").astype("int8"),
        "display_location": raw.pop("display_location").astype(str).astype("category"),
        "mailer_location": raw.pop("mailer_location").astype(str).astype("category")})
    del raw
    gc.collect()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE, index=False)
    meta.write_text(json.dumps({"source_file": RAW_FILE.name, "source_sha256": src}))
    return df


def audit(df: pd.DataFrame) -> dict:
    dup = int(df.duplicated(["product_id", "store_id", "week"]).sum())
    disp, mail = df.display_location.astype(str), df.mailer_location.astype(str)
    return {"rows": int(len(df)), "rows_match_documentation": int(len(df)) == EXPECTED_ROWS,
            "duplicate_product_store_week_keys": dup,
            "products": int(df.product_id.nunique()), "stores": int(df.store_id.nunique()),
            "weeks": [int(df.week.min()), int(df.week.max())],
            "display_codes": {k: int(v) for k, v in disp.value_counts().items()},
            "mailer_codes": {k: int(v) for k, v in mail.value_counts().items()},
            "undocumented_display_codes": sorted(set(disp.unique()) - set(DISPLAY)),
            "undocumented_mailer_codes": sorted(set(mail.unique()) - set(MAILER)),
            "rows_on_display": int((disp != "0").sum()), "rows_in_mailer": int((mail != "0").sum()),
            "rows_neither": int(((disp == "0") & (mail == "0")).sum())}


def join_transactions(tx: pd.DataFrame, promo: pd.DataFrame) -> pd.DataFrame:
    """Left-join promotion context onto transaction lines on (product_id, store_id, week).

    Multiplicity rule: the key is checked unique in the audit; if duplicates ever appear, they are collapsed first
    (on_display = any non-'0' display code, in_mailer = any non-'0' mailer code), so the join can never multiply
    transaction lines. Lines without a promotions row get promo_record = False (absence of a record is NOT
    evidence of no promotion; it is unknown)."""
    p = promo.assign(on_display=(promo.display_location.astype(str) != "0"),
                     in_mailer=(promo.mailer_location.astype(str) != "0"))
    p = p.groupby(["product_id", "store_id", "week"], observed=True, sort=False)[["on_display", "in_mailer"]].max().reset_index()
    t = tx.assign(product_id=pd.to_numeric(tx.product_id), store_id=pd.to_numeric(tx.store_id))
    out = t.merge(p, on=["product_id", "store_id", "week"], how="left", validate="many_to_one", indicator=True)
    out["promo_record"] = out.pop("_merge") == "both"
    # The table lists only promoted product-store-weeks (no 0/0 rows) and covers 112 of 457 stores.
    # Covered store + no record -> no promotion recorded; uncovered store -> UNKNOWN (NaN), never "not promoted".
    out["promo_store_covered"] = out.store_id.isin(set(promo.store_id.unique()))
    for c in ("on_display", "in_mailer"):
        out[c] = out[c].astype("boolean")
        out.loc[out.promo_store_covered & ~out.promo_record, c] = False
    out["promo_status"] = np.select([out.promo_record, out.promo_store_covered], ["promoted", "no_record_covered_store"],
                                    default="unknown_store_not_covered")
    assert len(out) == len(tx), "join changed the number of transaction lines"
    return out


def main(argv=None) -> int:
    t0 = time.time()
    df = load_promotions()
    a = audit(df)
    if not a["rows_match_documentation"]:
        print(f"DATA INTEGRITY FAILURE: promotions has {a['rows']:,} rows, documented {EXPECTED_ROWS:,}", file=sys.stderr)
        return 2
    from mi.config import load_config
    from mi.ingest.load import load
    cats = load_config()["categories"]
    tx, products = load("transactions"), load("products")
    j = join_transactions(tx[["product_id", "store_id", "week", "sales_value", "basket_id"]], df)
    j = j.merge(products[["product_id", "product_category"]].assign(product_id=lambda d: pd.to_numeric(d.product_id)),
                on="product_id", how="left")
    def cover(x):
        k = x[x.promo_store_covered]
        flag = (k.on_display.fillna(False) | k.in_mailer.fillna(False)).astype(bool)
        return {"lines": int(len(x)), "lines_in_covered_stores": round(float(x.promo_store_covered.mean()), 4),
                "with_promo_record": round(float(x.promo_record.mean()), 4),
                "on_display_covered": round(float(k.on_display.astype(float).mean()), 4), "in_mailer_covered": round(float(k.in_mailer.astype(float).mean()), 4),
                "sales_share_on_display_or_mailer_covered": round(float(k.sales_value[flag].sum() / k.sales_value.sum()), 4),
                "status_counts": {s: int(v) for s, v in x.promo_status.value_counts().items()}}
    a["join"] = {"key": ["product_id", "store_id", "week"], "rule": join_transactions.__doc__.split("\n\n")[1].strip(),
                 "all_lines": cover(j), "candidate_categories": cover(j[j.product_category.isin(cats)]),
                 "by_category": {c: cover(g) for c, g in j[j.product_category.isin(cats)].groupby("product_category")}}
    a["status"] = "OBSERVED placement records; association only, not a randomized treatment"
    a["seconds"] = round(time.time() - t0, 1)
    (REPORTS / "promotions_audit.json").write_text(json.dumps(a, indent=2))
    print(json.dumps({k: v for k, v in a.items() if k not in ("by_category",)}, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
