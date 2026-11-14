"""Audit of the historical coupon-funding figures (retailer match vs manufacturer coupon value).

Definitions (maintainer guide): coupon_disc = manufacturer coupon discount; coupon_match_disc = retailer's match.
Figures reported, each with numerator, denominator, weighting, filters and n:
  * value-weighted match share  = sum(coupon_match_disc) / sum(coupon_disc) over couponed lines (coupon_disc > 0)
  * line-weighted match share   = mean over couponed lines of coupon_match_disc / coupon_disc
  * match incidence             = share of couponed lines with any retailer match
Campaign-linked lines: transactions carry no coupon code, so a redemption is linked to a line only when the same
household bought, on the redemption date, a product eligible for that coupon_upc, with coupon_disc > 0.
These describe HISTORICAL coupon lines. The funding of a NEW digital offer is not observed anywhere in the data.

Usage: python -m mi.ingest.funding_audit -> reports/funding_audit.json
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from mi.config import load_config
from mi.ingest.load import load
from mi.paths import REPORTS

SEED = 20261114


def _shares(d: pd.DataFrame, n_boot=1000, seed=SEED) -> dict:
    if len(d) == 0:
        return {"couponed_lines": 0}
    c, m = d.coupon_disc.to_numpy(float), d.coupon_match_disc.to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), (n_boot, len(d)))
    vw_boot = m[idx].sum(1) / c[idx].sum(1)
    return {"couponed_lines": int(len(d)), "households": int(d.household_id.nunique()),
            "sum_manufacturer_coupon_usd": round(float(c.sum()), 2), "sum_retailer_match_usd": round(float(m.sum()), 2),
            "value_weighted_match_share": round(float(m.sum() / c.sum()), 4),
            "value_weighted_ci95_line_bootstrap": [round(float(np.percentile(vw_boot, 2.5)), 4), round(float(np.percentile(vw_boot, 97.5)), 4)],
            "line_weighted_mean_match_ratio": round(float(np.mean(m / c)), 4),
            "match_incidence_lines": round(float(np.mean(m > 0)), 4),
            "match_ratio_when_matched_median": round(float(np.median((m / c)[m > 0])), 4) if (m > 0).any() else None}


def link_redemptions(tx: pd.DataFrame, red: pd.DataFrame, coupons: pd.DataFrame) -> pd.DataFrame:
    """Mark couponed lines that can be linked to a campaign redemption (same household, same date, eligible product)."""
    t = tx[tx.coupon_disc > 0].copy()
    t["date"] = t.transaction_timestamp.dt.normalize()
    r = red.assign(date=red.redemption_date.dt.normalize()).merge(coupons[["coupon_upc", "product_id", "campaign_id"]],
                                                                   on=["coupon_upc", "campaign_id"])
    hit = t.merge(r[["household_id", "date", "product_id", "campaign_id"]].drop_duplicates(),
                  on=["household_id", "date", "product_id"], how="left")
    hit = hit.groupby(t.index.name or "index", dropna=False) if False else hit  # keep simple; dedupe below
    hit = hit.drop_duplicates(subset=["basket_id", "product_id", "household_id", "date"])
    hit["campaign_linked"] = hit.campaign_id.notna()
    return hit


def run(write=True) -> dict:
    cats = load_config()["categories"]
    tx, pr = load("transactions"), load("products")
    red, cp, cd = load("coupon_redemptions"), load("coupons"), load("campaign_descriptions")
    lines = link_redemptions(tx, red, cp).merge(pr[["product_id", "product_category"]], on="product_id", how="left")
    linked_red = lines[lines.campaign_linked][["household_id", "date", "campaign_id"]].drop_duplicates()
    red_d = red.assign(date=red.redemption_date.dt.normalize())
    n_red_linked = int(red_d.merge(linked_red, on=["household_id", "date", "campaign_id"]).drop_duplicates(
        ["household_id", "coupon_upc", "campaign_id", "redemption_date"]).shape[0])
    out = {"definitions": __doc__.split("Usage:")[0].strip(),
           "all_couponed_lines": _shares(lines),
           "campaign_linked_lines": _shares(lines[lines.campaign_linked]),
           "not_campaign_linked_lines": _shares(lines[~lines.campaign_linked]),
           "redemption_linkage": {"campaign_redemptions": int(len(red)), "redemptions_linked_to_a_line": n_red_linked,
                                  "linkage_rate": round(n_red_linked / len(red), 4),
                                  "rule": "same household + same calendar date + product eligible for that coupon_upc + coupon_disc > 0"},
           "by_category_all_couponed": {c: _shares(g) for c, g in lines[lines.product_category.isin(cats)].groupby("product_category")},
           "by_category_campaign_linked": {c: _shares(g) for c, g in lines[lines.campaign_linked & lines.product_category.isin(cats)].groupby("product_category")},
           "by_campaign_type_linked": {t: _shares(g) for t, g in lines[lines.campaign_linked].merge(cd[["campaign_id", "campaign_type"]], on="campaign_id").groupby("campaign_type")},
           "supported_wording": [
               "Historically, on lines with a manufacturer coupon, the retailer's recorded match equals X% of the manufacturer coupon VALUE (value-weighted; most couponed lines carry no match).",
               "This is an observed accounting share for past coupon lines, not the funding share of a new retailer digital offer.",
               "Whether campaign coupons were manufacturer- or retailer-funded is not recorded; coupon_disc is defined as a manufacturer discount."],
           "unsupported_wording": ["'the retailer pays 17% of a coupon'", "'manufacturer funding cuts the retailer's cost to 35%' as a fact about OUR offer"]}
    if write:
        (REPORTS / "funding_audit.json").write_text(json.dumps(out, indent=2))
    return out


def main(argv=None) -> int:
    r = run()
    for k in ("all_couponed_lines", "campaign_linked_lines", "not_campaign_linked_lines"):
        print(k, r[k])
    print("linkage", r["redemption_linkage"])
    print("FROZEN PIZZA all", r["by_category_all_couponed"].get("FROZEN PIZZA"))
    print("FROZEN PIZZA linked", r["by_category_campaign_linked"].get("FROZEN PIZZA"))
    print("by type linked", {k: (v["couponed_lines"], v["value_weighted_match_share"]) for k, v in r["by_campaign_type_linked"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
