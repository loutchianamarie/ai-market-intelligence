"""Read-only product-catalog intake (e.g. an AUTHORIZED Odoo export) -> validation + content-gap report.

No Odoo export exists in this project; real integration is PENDING. The validator runs on any CSV with the
schema below; data/catalog/example_catalog_SYNTHETIC.csv is an invented, non-sensitive example used only to
exercise the code. Catalog SKUs are NEVER mapped to anonymous Complete Journey product_ids. Personal fields are
dropped before any processing. Proposed copy uses only source fields and is a DRAFT for human review; structured
data or better copy does not guarantee ranking or AI-answer inclusion.

Usage: python -m mi.content.catalog validate <file.csv> -> reports/catalog_content_gap.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from mi.paths import REPORTS

REQUIRED = ["sku", "public_name", "description", "price", "currency", "valid_from", "image_ref", "availability"]
OPTIONAL = ["category", "margin_rate"]
AVAILABILITY = {"in_stock", "out_of_stock", "limited", "unknown"}
PERSONAL = re.compile(r"(email|e_mail|phone|mobile|customer|partner|address|street|zip|birth|first_name|last_name|contact)", re.I)
SIZE = re.compile(r"\b\d+(\.\d+)?\s?(g|kg|ml|cl|l|oz|lb|pack|pcs|x)\b", re.I)


class CatalogError(ValueError):
    pass


def validate(df: pd.DataFrame, source: str = "unspecified") -> dict:
    personal = [c for c in df.columns if PERSONAL.search(c)]
    df = df.drop(columns=personal)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise CatalogError(f"missing required columns {missing}; expected {REQUIRED}")
    issues = []
    dup = df.sku[df.sku.duplicated()].tolist()
    if dup:
        issues.append({"issue": "duplicate sku", "skus": dup})
    price = pd.to_numeric(df.price, errors="coerce")
    bad_price = df.sku[price.isna() | (price < 0)].tolist()
    if bad_price:
        issues.append({"issue": "price missing, non-numeric or negative", "skus": bad_price})
    bad_cur = df.sku[~df.currency.astype(str).str.fullmatch(r"[A-Z]{3}")].tolist()
    if bad_cur:
        issues.append({"issue": "currency not an ISO-4217 code", "skus": bad_cur})
    ts = pd.to_datetime(df.valid_from, errors="coerce", utc=True)
    if ts.isna().any():
        issues.append({"issue": "valid_from not a timestamp", "skus": df.sku[ts.isna()].tolist()})
    bad_av = df.sku[~df.availability.astype(str).isin(AVAILABILITY)].tolist()
    if bad_av:
        issues.append({"issue": f"availability not in {sorted(AVAILABILITY)}", "skus": bad_av})
    gaps = []
    names = df.public_name.astype(str)
    dup_names = set(names[names.str.strip().str.lower().duplicated(keep=False)].str.strip().str.lower())
    for _, r in df.iterrows():
        desc = "" if pd.isna(r.description) else str(r.description).strip()
        name = str(r.public_name)
        g = []
        if not desc:
            g.append("missing description")
        elif len(desc) < 80:
            g.append("description shorter than 80 characters")
        if pd.isna(r.image_ref) or not str(r.image_ref).strip():
            g.append("missing image reference")
        if name != name.strip() or name.isupper() or len(name) > 70:
            g.append("title formatting (whitespace, ALL CAPS or > 70 chars)")
        if name.strip().lower() in dup_names:
            g.append("title shared with another SKU")
        if not SIZE.search(f"{name} {desc}"):
            g.append("buyer question unanswered: size / quantity")
        if str(r.availability) in ("unknown", "nan"):
            g.append("buyer question unanswered: availability")
        draft = None
        if desc or name:
            size = SIZE.search(f"{name} {desc}")
            first = re.split(r"(?<=[.!?])\s", desc)[0] if desc else ""
            draft = (f"{name.strip()}" + (f" ({size.group(0)})" if size else "") + (f". {first}" if first else "")
                     + (f" Price {float(price[_]):.2f} {r.currency}." if pd.notna(price[_]) else ""))
        gaps.append({"sku": r.sku, "gaps": g, "proposed_copy_DRAFT": draft,
                     "draft_sources": ["public_name", "description", "price", "currency"],
                     "review": "HUMAN REVIEW REQUIRED before publishing; no claims beyond source fields"})
    return {"source": source, "rows": int(len(df)), "personal_columns_dropped": personal, "validation_issues": issues,
            "valid": not issues, "content_gaps": gaps,
            "skus_with_gaps": int(sum(1 for x in gaps if x["gaps"])),
            "boundaries": ["catalog SKUs are not mapped to anonymous Complete Journey product_ids",
                           "structured data / copy does not guarantee search ranking or AI-answer inclusion",
                           "Search Console impressions/clicks (owned site) and assistant prompt logs are separate measurements"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate"])
    ap.add_argument("csv")
    a = ap.parse_args(argv)
    p = Path(a.csv)
    try:
        res = validate(pd.read_csv(p), source=p.name)
    except CatalogError as e:
        print(f"CATALOG REJECTED: {e}", file=sys.stderr)
        return 2
    (REPORTS / "catalog_content_gap.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps({k: res[k] for k in ("source", "rows", "personal_columns_dropped", "valid", "skus_with_gaps")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
