"""The shared grocery bundle: the dataset we worked on, as plain CSV files a visitor can upload to ConsultAI.

  python -m mi.decision.demo_bundle            -> handoff/grocery_demo_bundle/ (+ grocery_demo_bundle.zip), git-ignored

Contents: transactions.csv (every purchase line of the 84.51 Complete Journey panel, 2017), products.csv (department, brand, category),
households.csv (every household id; demographics only where the panel has them), and bundle_manifest.json.

The manifest records the extraction rule, row counts, date range, columns, SHA-256 of each file, what the bundle can and cannot reproduce,
and REFERENCE METRICS computed here by our own code. ConsultAI computes the same metrics from the upload; the marketing web shows
"N of N match", so the consultant's numbers are checked, not trusted. Nothing here is a model score or a coupon effect.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import date

import pandas as pd

from mi.config import load_config
from mi.ingest.load import load
from mi.paths import REPORTS, ROOT

OUT = ROOT / "handoff" / "grocery_demo_bundle"
H1, H2 = (1, 26), (27, 53)            # the half-year windows used by the opportunity cards
LAPSE_ACTIVE, LAPSE_RECENT = (38, 49), (50, 53)   # simple descriptive lapsing rule (NOT the trained model's segment)
TX_COLS = ["household_id", "basket_id", "product_id", "week", "transaction_timestamp", "quantity", "sales_value", "retail_disc", "coupon_disc", "coupon_match_disc"]
PROD_COLS = ["product_id", "manufacturer_id", "department", "brand", "product_category", "product_type", "package_size"]
CASE_ID = "GROCERY_84_51_2017_BUNDLE"
MANIFEST_COPY = REPORTS / "grocery_bundle_manifest.json"


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _metric(mid, label, value, unit, period, denominator, formula):
    return {"metric_id": mid, "label": label, "value": value, "unit": unit, "period": period, "denominator": denominator, "formula": formula}


def slug(cat: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in cat.upper()).strip("_")


def reference_metrics(t: pd.DataFrame, cats: list[str]) -> list[dict]:
    """Descriptive metrics from the merged table ``t`` (transactions + product_category). Distinct households, never lines, for buyers."""
    m = [
        _metric("households_total", "Households with at least one purchase line", int(t.household_id.nunique()), "households", "2017", None, "count distinct household_id"),
        _metric("lines_total", "Purchase lines", int(len(t)), "lines", "2017", None, "count rows of transactions"),
        _metric("baskets_total", "Baskets", int(t.basket_id.nunique()), "baskets", "2017", None, "count distinct basket_id"),
        _metric("sales_total", "Total sales value", round(float(t.sales_value.sum()), 2), "USD", "2017", None, "sum sales_value"),
    ]
    for c in cats:
        g = t[t.product_category == c]
        s = slug(c)
        a = set(g[g.week.between(*H1)].household_id)
        b = set(g[g.week.between(*H2)].household_id)
        m += [
            _metric(f"distinct_buyers_h1__{s}", f"Distinct buyers of {c}, weeks 1-26", len(a), "households", "weeks 1-26", int(t.household_id.nunique()),
                    "count distinct household_id with a line in this category in weeks 1-26"),
            _metric(f"distinct_buyers_h2__{s}", f"Distinct buyers of {c}, weeks 27-53", len(b), "households", "weeks 27-53", int(t.household_id.nunique()),
                    "count distinct household_id with a line in this category in weeks 27-53"),
            _metric(f"lines_h1__{s}", f"Purchase lines of {c}, weeks 1-26", int(len(g[g.week.between(*H1)])), "lines", "weeks 1-26", None, "count rows (lines are NOT buyers)"),
            _metric(f"buyer_change__{s}", f"Change in distinct buyers of {c}, second half against first", round(len(b) / max(1, len(a)) - 1, 4), "ratio", "weeks 27-53 vs 1-26",
                    len(a), "distinct_buyers_h2 / distinct_buyers_h1 - 1"),
        ]
    if "YOGURT" in cats:        # category-only lapse versus left the retailer, for the default diagnosis case
        g = t[t.product_category == "YOGURT"]
        a = set(g[g.week.between(*H1)].household_id)
        b = set(g[g.week.between(*H2)].household_id)
        stopped = a - b
        active_h2 = set(t[t.week.between(*H2)].household_id)
        stayed = stopped & active_h2
        m += [
            _metric("yogurt_stopped_category", "Yogurt buyers in weeks 1-26 who did not buy yogurt in weeks 27-53", len(stopped), "households", "weeks 27-53", len(a),
                    "households in H1 yogurt buyers minus H2 yogurt buyers"),
            _metric("yogurt_stopped_but_still_shopping", "...of those, still bought something else in weeks 27-53", len(stayed), "households", "weeks 27-53", len(stopped),
                    "stopped yogurt households with any line in weeks 27-53"),
            _metric("yogurt_left_retailer", "...of those, no purchase of any kind in weeks 27-53", len(stopped - stayed), "households", "weeks 27-53", len(stopped),
                    "stopped yogurt households with no line in weeks 27-53"),
        ]
    for c in cats:        # simple descriptive lapsing rule (a plain-language version, not the trained model's activity-week segment)
        g = t[t.product_category == c]
        before = set(g[g.week.between(*LAPSE_ACTIVE)].household_id)
        recent = set(g[g.week.between(*LAPSE_RECENT)].household_id)
        m.append(_metric(f"lapsing_simple__{slug(c)}", f"Simple lapsing households in {c}", len(before - recent), "households", "weeks 38-53", len(before),
                         "bought the category in weeks 38-49 and not in weeks 50-53"))
    return m


def build(out=OUT, zip_it=True) -> dict:
    cfg = load_config()
    cats = list(cfg["categories"])
    tx, pr, dem = load("transactions"), load("products"), load("demographics")
    t = tx.merge(pr[["product_id", "product_category"]], on="product_id", how="left")
    out.mkdir(parents=True, exist_ok=True)
    tx[TX_COLS].to_csv(out / "transactions.csv", index=False)
    pr[PROD_COLS].to_csv(out / "products.csv", index=False)
    hh = pd.DataFrame({"household_id": sorted(tx.household_id.unique())}).merge(dem, on="household_id", how="left")
    hh.to_csv(out / "households.csv", index=False)
    files = {}
    for name, df in (("transactions.csv", tx[TX_COLS]), ("products.csv", pr[PROD_COLS]), ("households.csv", hh)):
        files[name] = {"rows": int(len(df)), "bytes": (out / name).stat().st_size, "sha256": sha256_file(out / name), "columns": list(df.columns)}
    cohorts = json.loads((REPORTS / "opportunities.json").read_text(encoding="utf-8")).get("cohorts", {}) if (REPORTS / "opportunities.json").exists() else {}
    manifest = {
        "schema": "grocery_demo_bundle.v1", "case_id": CASE_ID, "generated": date.today().isoformat(),
        "source": "84.51 Complete Journey panel (anonymous US grocery retailer), calendar 2017; derived CSV copy of the project's processed tables",
        "extraction_rule": ("transactions.csv = every purchase line (no filtering), the columns listed; products.csv = the full product table; "
                            "households.csv = every household id that has at least one line, with demographics where the panel provides them (801 of 2,469). Built by python -m mi.decision.demo_bundle."),
        "complete_dataset": True, "date_first": str(tx.transaction_timestamp.min())[:10], "date_last": str(tx.transaction_timestamp.max())[:10],
        "weeks": [int(tx.week.min()), int(tx.week.max())], "focus_categories": cats, "files": files,
        "can_reproduce": ["row and household counts", "sales over time", "distinct buyers by category and period", "category-only lapse versus left the retailer",
                          "descriptive lapsing segments", "basket cross-sell"],
        "cannot_reproduce": ["the trained purchase-propensity model's scores (needs the project's feature pipeline and coupon tables)",
                             "any coupon or campaign effect (exposure was not randomized; the campaign tables are not in the bundle)",
                             "stock, margin, consent, contact constraints, any year other than 2017"],
        "model_segment_note": {"text": "The trained model uses a stricter activity-week lapsing segment; its counts are not reference metrics for this bundle.",
                               "model_lapsing_counts_at_week_53": {c: v.get("lapsing_53") for c, v in cohorts.items()}},
        "reference_metrics": reference_metrics(t, cats),
    }
    mp = out / "bundle_manifest.json"
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    (out / "bundle_manifest.sha256").write_text(sha256_file(mp) + "  bundle_manifest.json\n", encoding="utf-8", newline="\n")
    if out == OUT:          # a small derived copy (no raw rows) that the web and CI can read without the git-ignored bundle
        import shutil
        shutil.copyfile(mp, MANIFEST_COPY)
        MANIFEST_COPY.with_suffix(".sha256").write_text(sha256_file(mp) + "  grocery_bundle_manifest.json
", encoding="utf-8", newline="
")
    if zip_it:
        z = out.with_suffix(".zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
            for p in sorted(out.iterdir()):
                f.write(p, f"{out.name}/{p.name}")
    return manifest


def main() -> int:
    m = build()
    print(f"wrote {OUT} ({m['files']['transactions.csv']['rows']:,} lines, {len(m['reference_metrics'])} reference metrics); manifest sha "
          f"{sha256_file(OUT / 'bundle_manifest.json')[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
