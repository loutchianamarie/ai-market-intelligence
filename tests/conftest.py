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
