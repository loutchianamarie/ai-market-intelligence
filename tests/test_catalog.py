import pandas as pd
import pytest

from mi.content.catalog import CatalogError, validate


def _df():
    return pd.DataFrame({"sku": ["S1", "S2"], "public_name": ["Item One 250 g", "ITEM TWO"],
                         "description": ["A description that is clearly long enough to pass the eighty character minimum check.", ""],
                         "price": ["2.50", "x"], "currency": ["USD", "usd"], "valid_from": ["2026-11-01", "nope"],
                         "image_ref": ["img/s1.jpg", ""], "availability": ["in_stock", "unknown"], "customer_phone": ["1", "2"]})


def test_catalog_drops_personal_fields_and_flags_gaps():
    r = validate(_df(), "test")
    assert r["personal_columns_dropped"] == ["customer_phone"] and not r["valid"]
    issues = {i["issue"] for i in r["validation_issues"]}
    assert any("price" in i for i in issues) and any("currency" in i for i in issues)
    g = {x["sku"]: x for x in r["content_gaps"]}
    assert g["S1"]["gaps"] == [] and "250 g" in g["S1"]["proposed_copy_DRAFT"] and "Price 2.50 USD" in g["S1"]["proposed_copy_DRAFT"]
    assert "missing description" in g["S2"]["gaps"] and g["S2"]["proposed_copy_DRAFT"] == "ITEM TWO"   # no invented facts
    assert all(x["review"].startswith("HUMAN REVIEW") for x in r["content_gaps"])


def test_catalog_requires_schema():
    with pytest.raises(CatalogError, match="missing required"):
        validate(pd.DataFrame({"sku": ["S1"]}))
