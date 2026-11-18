"""Dataset readiness: synthetic retail files with different column names, and the project's own data as the reference."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from mi import data_readiness as dr
from mi.paths import PROCESSED


def make_tx(households=1500, weeks=60, seed=1, names=None, categories=None, treatment=False):
    """A transactions table where each household buys each category with its own habit (so there is signal and repeat behaviour)."""
    rng = np.random.default_rng(seed)
    cats = categories or {"DAIRY": 0.30, "SNACKS": 0.22, "CEREAL": 0.18, "COFFEE": 0.16, "SOUP": 0.14, "JUICE": 0.20}
    start = pd.Timestamp("2023-01-02")
    rows = []
    habit = {c: rng.beta(2, 5 / max(p, 0.05) * 0.6, households) for c, p in cats.items()}
    for w in range(weeks):
        shop = rng.random(households) < 0.7
        for h in np.flatnonzero(shop):
            for c in cats:
                if rng.random() < habit[c][h]:
                    rows.append((f"H{h}", start + pd.Timedelta(days=7 * w + int(rng.integers(0, 7))), c, round(float(rng.gamma(2, 3)), 2), f"B{h}-{w}"))
    df = pd.DataFrame(rows, columns=["cust_no", "order_date", "department", "line_total", "order_id"])
    if treatment:
        df["test_group"] = df.cust_no.map(lambda x: hash(x) % 2)
    n = names or {}
    return df.rename(columns=n)


def verdict(df, **kw):
    return dr.assess(df, **kw)


def test_a_clean_file_with_other_column_names_is_ready():
    r = verdict(make_tx())
    assert r["verdict"] in ("READY", "PARTIAL"), [c for c in r["checks"] if c["status"] not in ("PASS", "INFO")]
    assert r["mapping"]["household_id"] == "cust_no" and r["mapping"]["category"] == "department" and r["mapping"]["amount"] == "line_total"
    assert r["proposed_temporal"]["design"] == "full"
    assert r["can_do"]["propensity_model_who_buys_next"] is True


def test_profit_is_never_claimed_possible():
    assert verdict(make_tx())["can_do"]["profit_or_roi"] is False


def test_too_short_history_is_not_ready():
    r = verdict(make_tx(weeks=30))
    assert r["verdict"] == "NOT_READY"
    assert next(c for c in r["checks"] if c["id"] == "D02")["status"] == "NOT_READY"


def test_mid_length_history_is_partial_with_the_reduced_design():
    r = verdict(make_tx(weeks=45))
    assert next(c for c in r["checks"] if c["id"] == "D02")["status"] == "PARTIAL"
    assert r["proposed_temporal"]["design"] == "reduced"


def test_missing_category_column_is_not_ready_and_says_why():
    df = make_tx().drop(columns=["department"])
    r = verdict(df)
    assert r["verdict"] == "NOT_READY" and "category" in r["checks"][0]["detail"]


def test_category_can_come_from_a_products_table():
    df = make_tx()
    prod = pd.DataFrame({"sku": [f"S-{c}" for c in df.department.unique()], "category": df.department.unique()})
    df["sku"] = "S-" + df.department
    r = verdict(df.drop(columns=["department"]), products=prod)
    assert r["mapping"].get("product_id") == "sku" and r["verdict"] in ("READY", "PARTIAL")


def test_few_customers_is_not_ready():
    assert next(c for c in verdict(make_tx(households=120, weeks=60))["checks"] if c["id"] == "D03")["status"] == "NOT_READY"


def test_guardrail_categories_never_qualify():
    cats = {"FUEL": 0.3, "BEER": 0.3, "FRESH BEEF": 0.3, "DAIRY": 0.3, "SNACKS": 0.25, "CEREAL": 0.2, "COFFEE": 0.2, "SOUP": 0.2}
    r = verdict(make_tx(categories=cats))
    q = set(r["recommended_categories"])
    assert not q & {"FUEL", "BEER", "FRESH BEEF"}
    assert {"DAIRY", "SNACKS"} <= q | set()


def test_a_treatment_column_enables_the_uplift_flag_and_its_absence_does_not():
    assert verdict(make_tx(treatment=True))["can_do"]["uplift_or_coupon_effect"] is True
    assert verdict(make_tx())["can_do"]["uplift_or_coupon_effect"] is False


def test_mapping_override_wins():
    df = make_tx().rename(columns={"line_total": "weird_col_x"})
    assert verdict(df)["verdict"] == "NOT_READY"
    r = verdict(df, mapping={"amount": "weird_col_x"})
    assert r["mapping"]["amount"] == "weird_col_x" and r["verdict"] in ("READY", "PARTIAL")


def test_returns_and_duplicates_are_flagged():
    df = make_tx()
    df.loc[df.sample(frac=0.05, random_state=2).index, "line_total"] *= -1
    d7 = next(c for c in verdict(df)["checks"] if c["id"] == "D07")
    assert d7["status"] == "PARTIAL" and "negative" in d7["detail"]


def test_full_design_cutoffs_equal_the_grocery_policy():
    pol = json.load(open("configs/policy.json"))["temporal"]
    t = dr.proposed_temporal(53)
    assert t["train_cutoffs"] == pol["train_cutoffs"] and t["validation_cutoff"] == pol["validation_cutoff"]
    assert (t["calibration_cutoff"], t["test_cutoff"], t["scoring_cutoff"]) == (pol["calibration_cutoff"], pol["test_cutoff"], pol["scoring_cutoff"])
    assert dr.proposed_temporal(dr.MIN_WEEKS - 1) is None and dr.proposed_temporal(dr.MIN_WEEKS)["design"] == "reduced"


@pytest.mark.skipif(not (PROCESSED / "transactions.parquet").exists(), reason="Complete Journey not downloaded")
def test_the_project_own_dataset_is_ready_and_proposes_its_own_split():
    r = dr.demo_complete_journey()
    assert r["verdict"] == "READY"
    pol = json.load(open("configs/policy.json"))["temporal"]
    assert r["proposed_temporal"]["train_cutoffs"] == pol["train_cutoffs"]
    assert "BEEF" not in r["recommended_categories"]


@pytest.mark.parametrize("span", range(dr.MIN_WEEKS, 80))
def test_no_training_outcome_window_ever_reaches_past_the_validation_cutoff(span):
    t = dr.proposed_temporal(span)
    assert t["train_cutoffs"][-1] + dr.HORIZON <= t["validation_cutoff"]
    assert t["validation_cutoff"] + dr.HORIZON <= t["calibration_cutoff"] and t["calibration_cutoff"] + dr.HORIZON <= t["test_cutoff"]
    assert t["test_cutoff"] + dr.HORIZON <= span
