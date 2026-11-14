"""Business-meaning regression tests (promotions join, receipts vs price, exposure, coupon funding)."""
import numpy as np
import pandas as pd
import pytest

from mi.ingest.promotions import join_transactions


def _promo():
    return pd.DataFrame({"product_id": [1, 1, 1, 2], "store_id": [10, 10, 11, 10], "week": np.array([5, 5, 5, 6], dtype="int8"),
                         "display_location": pd.Categorical(["3", "0", "0", "0"]),
                         "mailer_location": pd.Categorical(["0", "A", "D", "A"])})


def test_promotions_join_never_multiplies_lines_and_collapses_duplicate_keys():
    tx = pd.DataFrame({"product_id": ["1", "1", "2", "3"], "store_id": ["10", "10", "10", "99"], "week": [5, 5, 6, 5],
                       "sales_value": [1.0, 2.0, 3.0, 4.0]})
    j = join_transactions(tx, _promo())
    assert len(j) == len(tx)                                  # duplicate key (1,10,5) collapsed, not multiplied
    row = j.iloc[0]
    assert bool(row.on_display) and bool(row.in_mailer)       # 'any' rule across the duplicate rows


def test_absent_promotion_record_is_unknown_outside_covered_stores():
    tx = pd.DataFrame({"product_id": ["2", "2"], "store_id": ["11", "99"], "week": [9, 9], "sales_value": [1.0, 1.0]})
    j = join_transactions(tx, _promo())
    assert list(j.promo_status) == ["no_record_covered_store", "unknown_store_not_covered"]
    assert j.on_display.iloc[0] is False or j.on_display.iloc[0] == False  # noqa: E712  covered store, no record
    assert pd.isna(j.on_display.iloc[1])                       # uncovered store: unknown, never "not promoted"


def test_receipts_are_not_shopper_price_and_returns_are_not_computable():
    pytest.importorskip("pyreadr")
    from mi.ingest import accounting
    from mi.paths import RAW
    if not (RAW / "transactions.rds").exists():
        pytest.skip("raw data not present")
    a = accounting.audit()
    assert a["transactions"]["negative_any_money_or_quantity_lines"] == 0 and a["transactions"]["returns"].startswith("NOT REPRESENTED")
    assert a["coupon_match_only_with_manufacturer_coupon"] is True
    assert "16 coupons" in a["coupons"]["type_A_exposure"] and "cannot be reconstructed" in a["coupons"]["type_A_exposure"]
    assert any("retailer receipts" in x for x in a["economics_implications"])
    assert a["products"]["missing_share"]["package_size"] > 0.3      # catalog is incomplete; no descriptions/images exist
    assert "images" in a["products"]["fields_absent"]


def test_features_do_not_reconstruct_coupon_exposure_from_the_coupon_pool():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "mi" / "model" / "features.py").read_text(encoding="utf-8")
    assert 'load("coupons")' not in src and "coupon_upc" not in src


def test_coupon_funding_share_scales_the_retailer_cost():
    from mi.decision.scenario import Assumptions, household_value
    a = Assumptions(margin_rate=0.28, redemption_share=0.35, contact_cost={"d": 0.03}, reach_share={"d": 0.45}, fixed_setup=1500,
                    uplift={"LAPSING": 0.04}, coupon_retailer_share={"FROZEN PIZZA": 0.35})
    full = float(household_value(0.3, 0.04, 2.89, 0.90, 0.03, 0.35))
    shared = float(household_value(0.3, 0.04, 2.89, 0.90 * a.face_share("FROZEN PIZZA"), 0.03, 0.35))
    assert full < 0 < shared                                   # who funds the coupon changes the sign per household
    assert a.face_share("COFFEE") == 1.0                       # unspecified categories default to retailer-funded
