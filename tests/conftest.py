import hashlib

import pandas as pd
import pytest

from mi.paths import PROCESSED, RAW, REPORTS

HAVE_DATA = (RAW / "transactions.rds").exists()
HAVE_ARTIFACTS = (PROCESSED / "scores_latest.parquet").exists() and (REPORTS / "sensitivity.json").exists()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="run python -m mi.ingest.download")
needs_artifacts = pytest.mark.skipif(not HAVE_ARTIFACTS, reason="run the pipeline (python -m mi.cli all)")


@pytest.fixture
def tiny():
    """Synthetic fixture: 3 households, 2 categories, weeks 1..10. Includes a genuine multi-unit line,
    a duplicated-looking line, an unknown product id and a product with missing category."""
    ts = lambda w: pd.Timestamp("2017-01-01") + pd.Timedelta(weeks=int(w) - 1, hours=10)
    rows = []
    def add(hh, basket, prod, week, val, q=1.0, coup=0.0):
        rows.append({"household_id": hh, "store_id": "1", "basket_id": basket, "product_id": prod, "quantity": q,
                     "sales_value": val, "retail_disc": 0.0, "coupon_disc": coup, "coupon_match_disc": 0.0,
                     "week": week, "transaction_timestamp": ts(week)})
    add("A", "b1", "p1", 1, 2.0)
    add("A", "b2", "p1", 3, 2.0, q=3.0)
    add("A", "b2", "p2", 3, 1.0)
    add("A", "b3", "p1", 6, 2.0)       # A buys CAT1 in week 6
    add("B", "b4", "p2", 2, 1.5)
    add("B", "b4", "p2", 2, 1.5)       # identical line (could be genuine) -> reported, not deleted
    add("B", "b5", "pX", 4, 9.9)       # unknown product
    add("C", "b6", "p3", 5, 1.0)       # product with missing category
    add("C", "b7", "p1", 9, 2.0)
    tx = pd.DataFrame(rows)
    products = pd.DataFrame({"product_id": ["p1", "p2", "p3"], "manufacturer_id": ["m", "m", "m"],
                             "department": ["GROCERY", "GROCERY", "GROCERY"], "brand": ["National", "Private", "National"],
                             "product_category": ["CAT1", "CAT2", None], "product_type": ["t", "t", None], "package_size": [None] * 3})
    campaigns = pd.DataFrame({"campaign_id": ["1"], "household_id": ["A"]})
    camp_desc = pd.DataFrame({"campaign_id": ["1"], "campaign_type": ["Type A"],
                              "start_date": [pd.Timestamp("2017-01-20")], "end_date": [pd.Timestamp("2017-02-20")]})
    coupons = pd.DataFrame({"coupon_upc": ["c1"], "product_id": ["p1"], "campaign_id": ["1"]})
    red = pd.DataFrame({"household_id": ["A"], "coupon_upc": ["c1"], "campaign_id": ["1"],
                        "redemption_date": [pd.Timestamp("2017-01-25")]})
    demo = pd.DataFrame({"household_id": ["A"], "age": ["35-44"]})
    return {"tx": tx, "products": products, "campaigns": campaigns, "camp_desc": camp_desc,
            "coupons": coupons, "red": red, "demo": demo}


# ---------------------------------------------------------------------------------------------------------------
# Live demo artifacts must survive a test run untouched: a test that writes a throwaway dossier over the saved trace,
# the campaign brief or the local dossier stores would make the demo show test data. Tests use tmp stores; this guard
# proves it by hashing the files the demo reads before and after the whole session.
from mi.paths import DOCS, PROCESSED  # noqa: E402

GUARDED = [REPORTS / "marketing_agent_trace.json", REPORTS / "marketing_blocked_demo.json", REPORTS / "agent_trace_latest.json",
           REPORTS / "buyer_decision_backup.html", REPORTS / "campaign_case.latest.json", REPORTS / "campaign_case.latest.sha256",
           REPORTS / "seo_geo_audit.json", REPORTS / "run_manifest.json", REPORTS / "current_claims.json",
           REPORTS / "demo_fallback" / "grocery_demo_backup.html", DOCS / "marketing_decision_brief.md", DOCS / "marketing_brief.md", PROCESSED / "dossier.sqlite", PROCESSED / "campaign_dossier.sqlite"]


def _digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


@pytest.fixture(scope="session", autouse=True)
def live_demo_artifacts_untouched():
    before = {p: _digest(p) for p in GUARDED}
    yield
    changed = [p.name for p in GUARDED if _digest(p) != before[p]]
    assert not changed, f"tests modified live demo artifacts: {changed}"
