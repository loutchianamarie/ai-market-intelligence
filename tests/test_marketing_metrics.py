"""Marketing metrics on data where the right answer is known by construction."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mi.model import marketing_metrics as mm


def test_perfect_scores_capture_every_buyer_in_the_top_decile():
    y = np.r_[np.ones(100), np.zeros(900)]
    s = y + np.linspace(0, 0.01, 1000)          # buyers score highest
    g = mm.gains_table(y, s)
    assert g.loc[0, "rate"] == 1.0 and g.loc[0, "cum_buyers_share"] == 1.0 and g.loc[0, "lift"] == pytest.approx(10.0)
    assert g.buyers.sum() == 100 and g.households.sum() == 1000 and g.cum_buyers_share.iloc[-1] == pytest.approx(1.0)


def test_random_scores_have_lift_near_one_and_a_diagonal_gain_curve():
    rng = np.random.default_rng(0)
    y = (rng.random(20000) < 0.2).astype(float)
    g = mm.gains_table(y, rng.random(20000))
    assert g.lift.between(0.85, 1.15).all()
    assert (g.cum_buyers_share - g.cum_households_share).abs().max() < 0.03


def test_reversed_scores_have_lift_below_one_at_the_top():
    y = np.r_[np.ones(100), np.zeros(900)]
    assert mm.gains_table(y, -y).loc[0, "lift"] == 0.0


def test_lift_at_matches_hand_calculation():
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0])
    s = np.array([.9, .8, .7, .1, .1, .1, .1, .1, .1, .1])
    r = mm.lift_at(y, s, 0.3)                      # top 3 = scores .9 .8 .7 -> buyers 1,0,1
    assert r["contacts"] == 3 and r["rate"] == pytest.approx(2 / 3) and r["base_rate"] == 0.2
    assert r["lift"] == pytest.approx((2 / 3) / 0.2) and r["buyers_captured_share"] == 1.0


def test_gains_table_rejects_bad_input():
    with pytest.raises(ValueError):
        mm.gains_table([1, 0, 1], [0.1, 0.2], bins=10)


def _tx():
    rows = []
    for h in range(1, 11):                          # household h shops weeks 1..(10+h): bigger h = more recent, more baskets, more spend
        for w in range(1, 11 + h):
            rows.append((f"H{h}", f"B{h}-{w}", w, 5.0 * h))
    rows.append(("H1", "Bfuture", 99, 1000.0))       # after the cut-off: must be ignored
    return pd.DataFrame(rows, columns=["household_id", "basket_id", "week", "sales_value"])


def test_rfm_ignores_the_future_and_scores_the_most_active_household_highest():
    t = mm.rfm_table(_tx(), cutoff_week=20, window=12)
    assert t.loc["H1", "monetary"] < 100                   # the 1000 USD basket at week 99 is not counted
    assert t.loc["H10", ["R", "F", "M"]].tolist() == [5, 5, 5] and t.loc["H10", "rfm_segment"] == "Champions"
    assert t.loc["H1", ["R", "F", "M"]].tolist() == [1, 1, 1] and t.loc["H1", "rfm_segment"] == "Hibernating"
    assert t[["R", "F", "M"]].min().min() >= 1 and t[["R", "F", "M"]].max().max() <= 5


def test_households_with_the_same_recency_get_the_same_score():
    rows = [(f"H{h}", f"B{h}-{w}", w, 5.0) for h in range(1, 7) for w in (19, 20)]       # everyone last shopped at week 20
    t = mm.rfm_table(pd.DataFrame(rows, columns=["household_id", "basket_id", "week", "sales_value"]), cutoff_week=20)
    assert t.R.nunique() == 1


def test_value_proxy_known_cases():
    assert mm.value_proxy(100, 0.3, 0.0) == 0.0
    assert mm.value_proxy(100, 0.3, 1.0, cycles=13, annual_discount=0.0) == pytest.approx(13 * 100 * 0.3)
    assert mm.value_proxy(100, 0.3, 0.9) < mm.value_proxy(100, 0.3, 0.95) < mm.value_proxy(100, 0.3, 1.0)
    assert mm.value_proxy(100, 0.3, 0.9, annual_discount=0.2) < mm.value_proxy(100, 0.3, 0.9, annual_discount=0.0)
    for bad in [dict(retention_per_cycle=1.2), dict(margin=-0.1), dict(spend_per_cycle=-1)]:
        args = dict(spend_per_cycle=10, margin=0.3, retention_per_cycle=0.9) | bad
        with pytest.raises(ValueError):
            mm.value_proxy(**args)


def test_retention_counts_households_active_in_both_windows():
    rows = [("A", w) for w in range(1, 25)] + [("B", w) for w in range(1, 9)] + [("C", 13), ("C", 17)]
    t = mm.retention_table(pd.DataFrame(rows, columns=["household_id", "week"]), last_week=24, window=4, periods=3)
    first = t.iloc[0]                                      # weeks 9-12 active: A only -> next window (13-16): A and C? C not active in 9-12
    assert first["active"] == 1 and first["active_next_window"] == 1 and first["retention"] == 1.0
    assert (t.retention + t.lapse_rate).round(9).eq(1).all()
