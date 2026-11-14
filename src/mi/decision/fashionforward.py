"""FashionForward (course Module 04 TP) as an INDEPENDENT, SYNTHETIC arithmetic fixture for the metric engine.

Applies the workbook rules R1-R4 and reports the naive (rule-less) answer next to the cleaned one, to
demonstrate why definitions matter. Never merged with the grocery case; its 55% margin is never reused.
Usage: python -m mi.decision.fashionforward [--dir "<folder with ff_*.csv>"]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from mi.decision import metrics as M
from mi.paths import REPORTS, ROOT

DEFAULT_DIR = ROOT.parent  # course folder holding ff_*.csv


def run(folder: Path) -> dict:
    o = pd.read_csv(folder / "ff_orders.csv")
    cmap = pd.read_csv(folder / "ff_channel_map.csv")
    ads = pd.read_csv(folder / "ff_ads_daily.csv")
    naive = {"rows": len(o), "revenue_all_rows": round(float(o.order_value_eur.sum()), 2)}
    dup = int(o.duplicated("order_id").sum())
    o1 = o.drop_duplicates("order_id")                                   # R1
    test = int(o1.customer_id.str.startswith("TEST").sum())
    o2 = o1[~o1.customer_id.str.startswith("TEST")]                      # R2
    comp = o2[o2.status == "completed"]                                   # R3
    o2 = o2.merge(cmap, on="channel_raw", how="left")                    # R4
    unmapped = int(o2.channel.isna().sum())
    net = float(comp.order_value_eur.sum())
    out = {"status": "SYNTHETIC course fixture (FashionForward) — arithmetic check only",
           "naive_no_rules": naive, "duplicates_removed_R1": dup, "test_orders_removed_R2": test,
           "N1_orders_after_cleaning": int(len(o2)), "N2_completed_orders": int(len(comp)),
           "N3_net_revenue": round(net, 2), "N4_AOV": round(M.aov(net, len(comp)), 2),
           "N5_return_rate_pct": round(100 * M.return_rate(int((o2.status == "returned").sum()), len(comp)), 1),
           "unmapped_channel_rows": unmapped,
           "naive_revenue_overstatement_pct": round(100 * (naive["revenue_all_rows"] / net - 1), 1)}
    tot = ads.groupby("channel")[["spend_eur", "impressions", "clicks", "platform_revenue_eur"]].sum()
    o2c = o2[o2.status == "completed"].groupby("channel").order_value_eur.agg(["sum", "count"])
    rows = {}
    for ch, r in tot.iterrows():
        rev = float(o2c.loc[ch, "sum"]) if ch in o2c.index else 0.0
        n = int(o2c.loc[ch, "count"]) if ch in o2c.index else 0
        rows[ch] = {"spend": round(r.spend_eur, 2), "CTR_pct": round(100 * M.ctr([r.clicks], [r.impressions]), 2),
                    "CPM": round(M.cpm([r.spend_eur], [r.impressions]), 2), "CPC": round(M.ratio(r.spend_eur, r.clicks), 2),
                    "CPA_shop": round(M.cpa(r.spend_eur, n), 2), "ROAS_shop": round(M.roas(rev, r.spend_eur), 2),
                    "ROAS_platform": round(M.roas(r.platform_revenue_eur, r.spend_eur), 2),
                    "above_break_even_1.82": M.roas(rev, r.spend_eur) > M.break_even_roas(0.55)}
    out["channels"] = rows
    out["N6_total_ad_spend"] = round(float(tot.spend_eur.sum()), 2)
    out["blended_ROAS"] = round(M.roas(net, float(tot.spend_eur.sum())), 2)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    a = ap.parse_args(argv)
    folder = Path(a.dir)
    if not (folder / "ff_orders.csv").exists():
        print(f"ff_orders.csv not found in {folder}", file=sys.stderr)
        return 2
    out = run(folder)
    (REPORTS / "fashionforward_metrics.json").write_text(json.dumps(out, indent=2, default=bool))
    print(json.dumps(out, indent=1, default=bool))
    return 0


if __name__ == "__main__":
    sys.exit(main())
