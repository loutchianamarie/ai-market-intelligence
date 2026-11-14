import itertools

import numpy as np
import pandas as pd
import pytest

from mi.decision import metrics as M
from mi.decision.optimizer import Universe
from mi.decision.scenario import Assumptions, break_even_uplift, household_value


# ---------------- metric contracts (independent hand-computed expectations)
def test_sum_first_then_divide_not_average_of_ratios():
    clicks, imps = [1, 99], [100, 900]                  # daily CTRs 1% and 11%; true CTR 100/1000 = 10%
    assert M.ctr(clicks, imps) == pytest.approx(0.10)
    assert np.mean([c / i for c, i in zip(clicks, imps)]) == pytest.approx(0.06)   # the trap


def test_zero_denominators_are_undefined_with_reason():
    for v in (M.cpa(100, 0), M.roas(50, 0), M.cac(10, 0), M.ctr([1], [0]), M.break_even_roas(0)):
        assert isinstance(v, M.Undefined) and v.reason


def test_break_even_roas_and_roi():
    assert M.break_even_roas(0.55) == pytest.approx(1 / 0.55)  # 1.818..., course workbook Part 3
    assert M.roi(1260, 1000) == pytest.approx(0.26)


def test_currency_mismatch_rejected():
    with pytest.raises(ValueError):
        M.sum_money([M.Money(1, "USD"), M.Money(1, "BRL")])


def test_return_rate():
    assert M.return_rate(10, 90) == pytest.approx(0.10)


# ---------------- scenario arithmetic
def test_household_value_hand_computed():
    # dq=.04, g=2.89, F=.90, contact=.03, r=.35, q0=.30 -> .04*1.99 - .03 - .30*.35*.90 = .0796-.03-.0945 = -.0449
    assert household_value([0.30], 0.04, 2.89, 0.90, 0.03, 0.35)[0] == pytest.approx(-0.0449, abs=1e-6)


def test_break_even_uplift_zeroes_value():
    q0, g, F, c, r = 0.25, 2.2, 0.77, 0.03, 0.35
    dq = break_even_uplift(q0, g, F, c, r)
    assert household_value([q0], dq, g, F, c, r)[0] == pytest.approx(0, abs=1e-12)


def test_break_even_undefined_when_coupon_exceeds_contribution():
    assert isinstance(break_even_uplift(0.2, 0.5, 0.9, 0.03, 0.35), M.Undefined)
    assert isinstance(break_even_uplift(0.2, None, 0.9, 0.03, 0.35), M.Undefined)


def test_probability_validation():
    with pytest.raises(ValueError):
        household_value([1.2], 0.01, 2, 1, 0.03, 0.35)


# ---------------- optimizer on a tiny universe with a brute-force oracle
def _toy(budget=1000.0, fixed=0.0):
    rng = np.random.default_rng(0)
    rows = []
    for i in range(60):
        for cat in ("C1", "C2"):
            seg = ["REGULAR", "LAPSING", "ACTIVE_NONBUYER"][i % 3]
            rows.append({"household_id": f"h{i}", "product_category": cat, "segment": seg,
                         "p_used": float(rng.uniform(0.01, 0.6)), "cat_weeks_active_12w": i % 4})
    scores = pd.DataFrame(rows)
    econ = {"mean_4w_category_spend_among_buyers_test": {"C1": 20.0, "C2": 12.0},
            "mean_coupon_disc_per_couponed_line": {"C1": 1.0, "C2": 0.8}}
    cfg = {"categories": ["C1", "C2"], "scenario": {
        "budget_cap": {"value": budget}, "max_category_share_of_spend": {"value": 1.0},
        "min_reach_per_plan": {"value": 1}, "max_plans_in_portfolio": {"value": 3},
        "coupon_face_value": {"fallback": 1.0}}}
    a = Assumptions(margin_rate=0.3, redemption_share=0.35, contact_cost={"digital_coupon": 0.03},
                    reach_share={"digital_coupon": 1.0}, fixed_setup=fixed,
                    uplift={"REGULAR": 0.01, "LAPSING": 0.08, "ACTIVE_NONBUYER": 0.02, "RECENT_LIGHT": 0.02, "BROAD": 0.01})
    return scores, econ, cfg, a


def test_one_contact_dedup_and_oracle():
    scores, econ, cfg, a = _toy()
    U = Universe(scores, econ, cfg, a)
    # oracle: brute-force best household-level assignment for every pair of candidates
    for j, k in itertools.combinations(range(len(U.cands)), 2):
        ev = U.evaluate([j, k])
        oracle = 0.0
        for h in range(U.V.shape[0]):
            vals = [v for v in (U.V[h, j], U.V[h, k]) if np.isfinite(v)]
            oracle += max(vals) if vals else 0.0
        assert ev["net"] == pytest.approx(oracle, abs=1e-9)
        assert sum(c["reach"] for c in ev["components"]) <= U.V.shape[0]   # nobody contacted twice


def test_budget_one_unit_over_cap_is_infeasible():
    scores, econ, cfg, a = _toy()
    U = Universe(scores, econ, cfg, a)
    cost = U.evaluate([0])["cost"]
    cfg["scenario"]["budget_cap"]["value"] = cost - 1.0
    assert not Universe(scores, econ, cfg, a).evaluate([0])["feasible"]
    cfg["scenario"]["budget_cap"]["value"] = cost + 1.0
    assert Universe(scores, econ, cfg, a).evaluate([0])["feasible"]


def test_model_filtered_never_worse_than_all_for_same_cohort():
    scores, econ, cfg, a = _toy()
    U = Universe(scores, econ, cfg, a)
    ids = {c["candidate_id"]: j for j, c in enumerate(U.cands)}
    for cid, j in ids.items():
        if cid.endswith("|ALL") and cid.replace("|ALL", "|MODEL_FILTERED") in ids:
            assert U.evaluate([ids[cid.replace("|ALL", "|MODEL_FILTERED")]])["net"] >= U.evaluate([j])["net"] - 1e-9
