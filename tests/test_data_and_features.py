import pandas as pd
import pytest

from mi.ingest.audit import audit_frames
from mi.model.features import assert_no_leakage, build_cutoff, prepare

CFG_T = {"lookback_weeks": 4, "horizon_weeks": 4}


def test_audit_counts_and_does_not_mutate(tiny):
    before = tiny["tx"].copy()
    a = audit_frames(tiny["tx"], tiny["products"], tiny["campaigns"], tiny["camp_desc"], tiny["coupons"],
                     tiny["red"], tiny["demo"], ["CAT1", "CAT2"])
    pd.testing.assert_frame_equal(before, tiny["tx"])           # input unmodified
    t = a["transactions"]
    assert a["tables"]["transactions"]["rows"] == 9              # nothing deleted
    assert t["households"] == 3 and t["baskets"] == 7
    assert t["exact_duplicate_rows"] == 1                        # reported...
    assert "nothing deleted" in t["duplicate_policy"]            # ...not removed
    assert a["joins"]["tx_product_coverage"] == pytest.approx(8 / 9, abs=1e-4)   # pX unknown
    assert a["joins"]["demographics_household_coverage"] == pytest.approx(1 / 3, abs=1e-3)
    assert "product cost / margin" in a["missing_for_business_case"]


def _prep(tiny):
    return prepare(tiny["tx"], tiny["products"], ["CAT1", "CAT2"])


def test_features_use_only_pre_cutoff_and_label_only_horizon(tiny):
    f = build_cutoff(_prep(tiny), 5, 4, 4, tiny["red"], tiny["campaigns"], tiny["camp_desc"])
    a1 = f[(f.household_id == "A") & (f.product_category == "CAT1")].iloc[0]
    assert a1.cat_baskets_4w == 1        # week 3 only (weeks 2..5); week 1 is outside the lookback
    assert a1.y == 1                      # bought in week 6 (horizon 6..9)
    assert a1.cat_weeks_since_last == 2
    c1 = f[(f.household_id == "C") & (f.product_category == "CAT1")].iloc[0]
    assert c1.y == 1 and c1.cat_baskets_12w == 0     # buys in week 9 with no category history


def test_future_changes_do_not_change_features(tiny):
    f1 = build_cutoff(_prep(tiny), 5, 4, 4, tiny["red"], tiny["campaigns"], tiny["camp_desc"])
    tx2 = tiny["tx"].copy()
    tx2.loc[tx2.week > 5, "sales_value"] *= 100            # perturb only the future
    tx2 = pd.concat([tx2, tx2[tx2.week > 5]])               # and add future rows
    p2 = prepare(tx2, tiny["products"], ["CAT1", "CAT2"])
    f2 = build_cutoff(p2, 5, 4, 4, tiny["red"], tiny["campaigns"], tiny["camp_desc"])
    from mi.model.features import FEATURES
    feats = list(FEATURES)                                   # every model feature, incl. the long-history ones
    pd.testing.assert_frame_equal(f1[feats].reset_index(drop=True), f2[feats].reset_index(drop=True))


def test_eligibility_uses_pre_cutoff_activity_only(tiny):
    f = build_cutoff(_prep(tiny), 2, 4, 4, tiny["red"], tiny["campaigns"], tiny["camp_desc"])
    assert set(f.household_id) == {"A", "B"}   # C first shops in week 5 -> not eligible at cutoff 2


def test_redemption_after_cutoff_not_counted(tiny):
    f = build_cutoff(_prep(tiny), 3, 4, 4, tiny["red"], tiny["campaigns"], tiny["camp_desc"])
    assert f[f.household_id == "A"].hh_redemptions_12w.max() == 0   # redemption on 2017-01-25 (week 4)
    f = build_cutoff(_prep(tiny), 5, 4, 4, tiny["red"], tiny["campaigns"], tiny["camp_desc"])
    assert f[f.household_id == "A"].hh_redemptions_12w.max() == 1


def test_leakage_guard_raises():
    df = pd.DataFrame({"cutoff": [5], "feature_max_week": [6]})
    with pytest.raises(ValueError):
        assert_no_leakage(df)
