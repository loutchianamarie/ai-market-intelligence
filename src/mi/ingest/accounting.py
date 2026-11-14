"""Business-meaning audit of the Complete Journey money, coupon and product fields + data dictionary.

Grounded in the maintainer guide (https://bradleyboehmke.github.io/completejourney/articles/completejourney.html):
  * sales_value is NOT the price the shopper paid; it is what the retailer receives. "If a customer uses a coupon,
    the actual price paid will be less than the sales_value."
  * coupon_disc = manufacturer coupon (reimbursed to the retailer); coupon_match_disc = the retailer's match.
  * Type A recipients received 16 coupons out of a pool; WHICH 16 is not recorded, so exact exposure cannot be
    reconstructed from the coupon pool. Type B/C recipients receive all campaign coupons; assignment is undocumented.
Outputs: reports/accounting_audit.json and docs/data_dictionary.md. Usage: python -m mi.ingest.accounting
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from mi.config import load_config
from mi.ingest.load import load
from mi.paths import REPORTS, ROOT


def audit() -> dict:
    tx, pr = load("transactions"), load("products")
    cp, cd, red, ca = load("coupons"), load("campaign_descriptions"), load("coupon_redemptions"), load("campaigns")
    cats = load_config()["categories"]
    q0 = tx.quantity == 0
    money = {c: {"sum": round(float(tx[c].sum()), 2), "lines_gt0": int((tx[c] > 0).sum()), "lines_lt0": int((tx[c] < 0).sum())}
             for c in ["sales_value", "retail_disc", "coupon_disc", "coupon_match_disc"]}
    match_ratio = tx.coupon_match_disc.sum() / tx.coupon_disc.sum()
    tc = tx.merge(pr[["product_id", "product_category"]], on="product_id", how="left")
    by_cat = {}
    for c, g in tc[tc.product_category.isin(cats)].groupby("product_category"):
        cpn = g[g.coupon_disc > 0]
        by_cat[c] = {"lines": int(len(g)), "couponed_lines": int(len(cpn)),
                     "mean_manufacturer_coupon_per_couponed_line": round(float(cpn.coupon_disc.mean()), 4) if len(cpn) else None,
                     "retailer_match_share_of_coupon_value": round(float(cpn.coupon_match_disc.sum() / cpn.coupon_disc.sum()), 4) if len(cpn) else None,
                     "loyalty_discount_share_of_sales": round(float(g.retail_disc.sum() / g.sales_value.sum()), 4)}
    pool = cp.merge(cd, on="campaign_id").groupby("campaign_type").coupon_upc.nunique().to_dict()
    red_tx_lines = int((tx.coupon_disc > 0).sum())
    return {
        "source": "maintainer guide + CC0 package data at commit 5b5d0619",
        "transactions": {"lines": int(len(tx)), "zero_quantity_lines": int(q0.sum()), "zero_sales_lines": int((tx.sales_value == 0).sum()),
                         "negative_any_money_or_quantity_lines": int(((tx[["sales_value", "retail_disc", "coupon_disc", "coupon_match_disc", "quantity"]] < 0).any(axis=1)).sum()),
                         "returns": "NOT REPRESENTED: no negative quantity or value lines; a return rate cannot be computed",
                         "lines_retail_disc_exceeds_sales_value": int((tx.retail_disc > tx.sales_value).sum()),
                         "lines_coupon_disc_exceeds_sales_value": int((tx.coupon_disc > tx.sales_value).sum())},
        "money_fields": money,
        "retailer_match_share_of_manufacturer_coupon_value": round(float(match_ratio), 4),
        "coupon_match_only_with_manufacturer_coupon": bool(((tx.coupon_match_disc > 0) & (tx.coupon_disc == 0)).sum() == 0),
        "by_candidate_category": by_cat,
        "coupons": {"campaign_coupon_redemptions": int(len(red)), "lines_with_manufacturer_coupon": red_tx_lines,
                    "share_of_coupon_lines_that_are_campaign_redemptions": round(len(red) / max(1, red_tx_lines), 4),
                    "coupon_pool_size_by_campaign_type": {k: int(v) for k, v in pool.items()},
                    "type_A_exposure": "each Type A recipient got 16 coupons from the pool; WHICH 16 is not recorded -> exact exposure cannot be reconstructed",
                    "assignment": "undocumented for all types -> observational, not randomized",
                    "campaign_households": int(ca.household_id.nunique())},
        "products": {"rows": int(len(pr)), "missing_share": {c: round(float(pr[c].isna().mean()), 4) for c in pr.columns},
                     "brand_values": {k: int(v) for k, v in pr.brand.value_counts().items()},
                     "transaction_lines_without_product_metadata": int((~tx.product_id.isin(pr.product_id)).sum()),
                     "fields_absent": ["prose descriptions", "images", "price list", "cost / margin", "stock", "supplier"]},
        "economics_implications": [
            "Category 'spend' in the economics is retailer receipts (sales_value), not shopper outlay; margin is applied to receipts.",
            "The coupon face value used (mean coupon_disc per couponed line) averages ALL manufacturer coupons; only "
            f"{len(red)} of {red_tx_lines} couponed lines are campaign redemptions, so it is not a measured campaign-coupon value.",
            "Manufacturer coupons are reimbursed to the retailer. Separately, the retailer recorded a match on 47% of couponed lines "
            f"(usually equal to the coupon), which sums to {100 * match_ratio:.0f}% of manufacturer coupon VALUE (value-weighted; reports/funding_audit.json). "
            "That describes past coupon accounting, not who would fund a NEW offer: the offer contract is an ASSUMPTION "
            "(coupon_funding.retailer_share; base 1.0 = retailer-funded) until the client confirms it.",
            "Unit prices: sales_value / quantity is undefined on zero-quantity lines; no price list exists."]}


DICT = [
    ("transactions.sales_value", "USD per line", "amount the RETAILER receives for the line (not the shopper's outlay); includes manufacturer coupon reimbursement", "guide"),
    ("transactions.retail_disc", "USD per line, positive magnitude", "loyalty-card discount (retailer programme)", "guide"),
    ("transactions.coupon_disc", "USD per line, positive magnitude", "manufacturer coupon discount (reimbursed to the retailer)", "guide"),
    ("transactions.coupon_match_disc", "USD per line, positive magnitude", "retailer's match of a manufacturer coupon (retailer-funded)", "guide"),
    ("transactions.quantity", "units (fuel in gallons)", "quantity; zero on some lines; FUEL/MISC carry very large values", "audit"),
    ("transactions.week", "1-53", "week of the transaction; week 1 is a single day", "audit"),
    ("products.*", "-", "product_id, manufacturer_id, department, brand (National/Private), product_category, product_type, package_size; NO descriptions, images, prices, cost or stock", "guide + audit"),
    ("coupons", "coupon_upc x product_id x campaign_id", "products ELIGIBLE for a campaign coupon; not what a household received", "guide"),
    ("campaigns", "household x campaign", "households that received a campaign; Type A recipients got 16 of the pool (which 16 unknown); assignment undocumented", "guide"),
    ("coupon_redemptions", "household x coupon x campaign x date", "campaign coupons actually redeemed", "guide"),
    ("promotions", "product x store x week", "display_location / mailer_location codes; ONLY promoted rows; 112 stores (98.7% of transaction lines)", "reference + audit"),
    ("label y (model)", "0/1 per household x category x cutoff", "any purchase of the category in weeks cutoff+1..cutoff+4", "repo"),
    ("q0 (model)", "probability", "calibrated probability of buying under historical conditions; NOT a no-coupon counterfactual", "repo"),
]


def to_md(a: dict) -> str:
    L = ["# Data dictionary and business-meaning audit (Complete Journey, 2017)", "",
         "Source: maintainer guide https://bradleyboehmke.github.io/completejourney/articles/completejourney.html and "
         "reference https://bradleyboehmke.github.io/completejourney/reference/promotions.html; data CC0 at commit 5b5d0619 "
         "(hashes in `data/manifest.lock.json`). Counts from `reports/accounting_audit.json` and `reports/promotions_audit.json`.", "",
         "| field / table | unit | definition | basis |", "|---|---|---|---|"]
    L += [f"| {f} | {u} | {d} | {b} |" for f, u, d, b in DICT]
    t, c = a["transactions"], a["coupons"]
    L += ["", "## Quality counts", "",
          f"- {t['lines']:,} lines; {t['zero_quantity_lines']:,} zero-quantity; {t['zero_sales_lines']:,} zero-value; "
          f"{t['negative_any_money_or_quantity_lines']} lines with any negative value → **returns are not represented**.",
          f"- Loyalty discount exceeds the line's sales_value on {t['lines_retail_disc_exceeds_sales_value']:,} lines; manufacturer coupon exceeds it on {t['lines_coupon_disc_exceeds_sales_value']:,}.",
          f"- Retailer match = {100 * a['retailer_match_share_of_manufacturer_coupon_value']:.1f}% of manufacturer coupon value; match only occurs with a manufacturer coupon: {a['coupon_match_only_with_manufacturer_coupon']}.",
          f"- {c['campaign_coupon_redemptions']:,} campaign redemptions vs {c['lines_with_manufacturer_coupon']:,} manufacturer-coupon lines ({100 * c['share_of_coupon_lines_that_are_campaign_redemptions']:.1f}%).",
          f"- Coupon pool by campaign type: {c['coupon_pool_size_by_campaign_type']}. {c['type_A_exposure']}.",
          f"- Products: {a['products']['rows']:,}; package_size missing {100 * a['products']['missing_share']['package_size']:.1f}%; "
          f"category missing {100 * a['products']['missing_share']['product_category']:.2f}%; {a['products']['transaction_lines_without_product_metadata']:,} transaction lines lack product metadata.",
          "", "## What changes in the economics", ""] + [f"- {x}" for x in a["economics_implications"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    a = audit()
    (REPORTS / "accounting_audit.json").write_text(json.dumps(a, indent=2))
    (ROOT / "docs" / "data_dictionary.md").write_text(to_md(a), encoding="utf-8")
    print(json.dumps({k: a[k] for k in ("transactions", "retailer_match_share_of_manufacturer_coupon_value", "coupons")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
