"""Read-only data audit for the Complete Journey tables.

Reports counts, schema, nulls, date/week ranges, duplicates (reported, never deleted), join
coverage, value anomalies, campaign/coupon linkage and candidate-category penetration.
Writes reports/data_audit.json and reports/data_audit.md. Prints no household-level rows.

Usage: python -m mi.ingest.audit
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from mi.config import load_config
from mi.ingest.load import DataMissingError, load, manifest
from mi.paths import REPORTS


def audit_frames(tx: pd.DataFrame, products: pd.DataFrame, campaigns: pd.DataFrame,
                 camp_desc: pd.DataFrame, coupons: pd.DataFrame, redemptions: pd.DataFrame,
                 demographics: pd.DataFrame, categories: list[str]) -> dict:
    """Pure function: computes the audit dictionary without mutating any input."""
    out: dict = {}
    out["tables"] = {
        name: {"rows": int(len(df)), "columns": {c: str(t) for c, t in df.dtypes.items()},
               "null_rate": {c: round(float(v), 5) for c, v in df.isna().mean().items() if v > 0}}
        for name, df in [("transactions", tx), ("products", products), ("campaigns", campaigns),
                         ("campaign_descriptions", camp_desc), ("coupons", coupons),
                         ("coupon_redemptions", redemptions), ("demographics", demographics)]
    }
    out["transactions"] = {
        "households": int(tx.household_id.nunique()),
        "baskets": int(tx.basket_id.nunique()),
        "products": int(tx.product_id.nunique()),
        "stores": int(tx.store_id.nunique()),
        "timestamp_min": str(tx.transaction_timestamp.min()),
        "timestamp_max": str(tx.transaction_timestamp.max()),
        "week_min": int(tx.week.min()), "week_max": int(tx.week.max()),
        "rows_per_week_first_last": {int(k): int(v) for k, v in
                                     tx.groupby("week").size().iloc[[0, 1, -2, -1]].items()},
        "exact_duplicate_rows": int(tx.duplicated().sum()),
        "duplicate_basket_product_rows": int(tx.duplicated(["basket_id", "product_id"]).sum()),
        "zero_sales_value_rows": int((tx.sales_value == 0).sum()),
        "negative_sales_value_rows": int((tx.sales_value < 0).sum()),
        "zero_quantity_rows": int((tx.quantity == 0).sum()),
        "quantity_gt_100_rows": int((tx.quantity > 100).sum()),
        "discount_sign_convention": "positive magnitudes" if (tx.retail_disc >= 0).all()
        and (tx.coupon_disc >= 0).all() else "mixed",
        "rows_with_coupon_disc": int((tx.coupon_disc > 0).sum()),
        "duplicate_policy": "Report only. Identical-looking lines can be genuine; nothing deleted.",
    }
    prod_ids = set(products.product_id)
    out["joins"] = {
        "tx_product_coverage": round(float(tx.product_id.isin(prod_ids).mean()), 5),
        "demographics_household_coverage": round(
            float(pd.Series(tx.household_id.unique()).isin(set(demographics.household_id)).mean()), 4),
        "campaign_households_in_tx": round(float(campaigns.household_id.isin(set(tx.household_id)).mean()), 4),
        "coupon_products_in_products": round(float(coupons.product_id.isin(prod_ids).mean()), 4),
        "redemption_coupons_in_coupons": round(float(redemptions.coupon_upc.isin(set(coupons.coupon_upc)).mean()), 4),
    }
    q_outliers = tx[tx.quantity > 100].merge(products[["product_id", "department"]], on="product_id", how="left")
    out["anomalies"] = {
        "quantity_gt_100_by_department": {str(k): int(v) for k, v in
                                          q_outliers.department.value_counts().head(5).items()},
        "note": "Large quantities concentrate in FUEL/MISC; candidate categories exclude these departments.",
    }
    cd = camp_desc.copy()
    out["campaigns"] = {
        "n_campaigns": int(cd.campaign_id.nunique()),
        "types": {str(k): int(v) for k, v in cd.campaign_type.value_counts().items()},
        "start_min": str(cd.start_date.min().date()), "end_max": str(cd.end_date.max().date()),
        "household_campaign_pairs": int(len(campaigns)),
        "households_receiving_any": int(campaigns.household_id.nunique()),
        "redemptions": int(len(redemptions)),
        "redemption_date_range": [str(redemptions.redemption_date.min().date()),
                                  str(redemptions.redemption_date.max().date())],
        "assignment": "UNKNOWN / not documented as randomized. Treat as observational selection.",
    }
    txc = tx[["household_id", "basket_id", "product_id", "week", "sales_value"]].merge(
        products[["product_id", "product_category"]], on="product_id", how="left")
    txc = txc[txc.product_category.isin(categories)]
    hh_all = tx.household_id.nunique()
    cat_rows = []
    for cat, g in txc.groupby("product_category"):
        cat_rows.append({
            "category": cat, "lines": int(len(g)), "sales_value": round(float(g.sales_value.sum()), 2),
            "households_year": int(g.household_id.nunique()),
            "year_penetration": round(g.household_id.nunique() / hh_all, 4),
            "weekly_households_median": float(g.groupby("week").household_id.nunique().median()),
        })
    out["candidate_categories"] = cat_rows
    out["missing_for_business_case"] = [
        "product cost / margin", "inventory / stock", "returns", "ad or contact cost",
        "documented random assignment of campaigns", "customer consent / reachability",
        "retailer identity (anonymous by design)"]
    return out


def to_markdown(a: dict, man: dict) -> str:
    t = a["transactions"]
    lines = ["# Data audit: 84.51 Complete Journey (authentic CC0 package data)", "",
             "Status: **OBSERVED** facts computed by `python -m mi.ingest.audit`. Read-only; no rows deleted.", ""]
    if man:
        lines += [f"Source: {man.get('source_repo')} @ commit `{man.get('commit', '')[:12]}` (licence {man.get('licence')})", "",
                  "| file | bytes | sha256 (first 16) | retrieved |", "|---|---:|---|---|"]
        lines += [f"| {f['name']} | {f['bytes']:,} | `{f['sha256'][:16]}` | {f['retrieved_at']} |" for f in man.get("files", [])]
        lines.append("")
    lines += ["## Tables", "", "| table | rows | columns with nulls |", "|---|---:|---|"]
    for name, d in a["tables"].items():
        nulls = ", ".join(f"{c} {v:.1%}" for c, v in d["null_rate"].items()) or "none"
        lines.append(f"| {name} | {d['rows']:,} | {nulls} |")
    lines += ["", "## Transactions", ""]
    for k, v in t.items():
        lines.append(f"- **{k}**: {v}")
    lines += ["", "## Join coverage", ""] + [f"- {k}: {v}" for k, v in a["joins"].items()]
    lines += ["", "## Anomalies", "", f"- quantity > 100 by department: {a['anomalies']['quantity_gt_100_by_department']}",
              f"- {a['anomalies']['note']}"]
    c = a["campaigns"]
    lines += ["", "## Campaigns and coupons", ""] + [f"- {k}: {v}" for k, v in c.items()]
    lines += ["", "## Candidate categories (frozen in configs/policy.json)", "",
              "| category | lines | sales $ | households (year) | year penetration | median weekly buying households |",
              "|---|---:|---:|---:|---:|---:|"]
    for r in a["candidate_categories"]:
        lines.append(f"| {r['category']} | {r['lines']:,} | {r['sales_value']:,.0f} | {r['households_year']:,} | "
                     f"{r['year_penetration']:.1%} | {r['weekly_households_median']:.0f} |")
    lines += ["", "## Not in the data (must stay ASSUMED or UNKNOWN)", ""] + [f"- {m}" for m in a["missing_for_business_case"]]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    cfg = load_config()
    try:
        frames = {n: load(n) for n in ["transactions", "products", "campaigns", "campaign_descriptions",
                                        "coupons", "coupon_redemptions", "demographics"]}
    except DataMissingError as e:
        print(str(e), file=sys.stderr)
        return 2
    a = audit_frames(frames["transactions"], frames["products"], frames["campaigns"],
                     frames["campaign_descriptions"], frames["coupons"], frames["coupon_redemptions"],
                     frames["demographics"], cfg["categories"])
    man = manifest()
    a["manifest"] = man
    (REPORTS / "data_audit.json").write_text(json.dumps(a, indent=2, default=str))
    (REPORTS / "data_audit.md").write_text(to_markdown(a, man), encoding="utf-8")
    print(f"audit written: {REPORTS / 'data_audit.md'}")
    print(json.dumps(a["transactions"], indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
