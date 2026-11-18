"""Dashboard interpretation (wording follows the numbers) and the marketing strategy plan (consistent with the card, gated, checked)."""
from __future__ import annotations

import copy
import re

import pytest

from mi.config import load_config
from mi.decision import decision_card as dc
from mi.decision import interpret as it
from mi.decision import strategy_plan as sp
from mi.paths import PROCESSED

FIELDS = {"title", "shows", "so_what", "do", "watch_out", "evidence"}


def _ok(box):
    assert FIELDS <= set(box) and all(isinstance(box[k], str) and box[k] for k in FIELDS)
    assert not re.search(r"\b(will increase|will boost|guarantee)\b", " ".join(box.values()), re.I)


# ------------------------------------------------------------------------------------------------ interpretation
def test_performance_calls_a_small_proven_gain_modest():
    b = it.interpret_performance(0.672, 0.621, 0.352, 0.050, 0.045, 0.056, 0.827)
    _ok(b)
    assert "modestly" in b["so_what"] and "modest" in b["so_what"] and "0.672" in b["shows"] and "excludes zero" in b["so_what"]


def test_performance_says_not_proven_when_the_interval_includes_zero():
    b = it.interpret_performance(0.60, 0.59, 0.35, 0.01, -0.02, 0.04, 0.80)
    assert "not demonstrably" in b["so_what"] and "not proven" in b["so_what"]


def test_performance_calls_a_large_gain_substantial():
    assert "substantial" in it.interpret_performance(0.80, 0.60, 0.35, 0.20, 0.15, 0.25, 0.9)["so_what"]


def test_calibration_wording_follows_the_gap():
    good = [{"mean_pred": 0.1 * i, "observed": 0.1 * i + 0.01, "n": 100} for i in range(1, 6)]
    bad = good[:-1] + [{"mean_pred": 0.5, "observed": 0.2, "n": 100}]
    assert "real probabilities" in it.interpret_calibration(good)["so_what"]
    b = it.interpret_calibration(bad)
    assert "only roughly" in b["so_what"] and "30.0%" in b["shows"]
    _ok(b)


def test_gains_says_the_edge_is_small_when_model_and_rule_match():
    b = it.interpret_gains(0.49, 0.48, 0.20, 2.45, 2.40)
    assert "49%" in b["shows"] and "small" in b["so_what"] and "20%" in b["shows"]
    _ok(b)
    assert "points more" in it.interpret_gains(0.60, 0.48, 0.20, 3.0, 2.4)["so_what"]
    assert "points fewer" in it.interpret_gains(0.40, 0.48, 0.20, 2.0, 2.4)["so_what"]


TIERS = [{"rfm_segment": "Champions", "households": 300}, {"rfm_segment": "Loyal", "households": 200}, {"rfm_segment": "At risk", "households": 400},
         {"rfm_segment": "Hibernating", "households": 100}, {"rfm_segment": "Need attention", "households": 1000}]


def test_rfm_reports_shares_and_the_trend():
    ret = [{"retention": 0.90}, {"retention": 0.80}]
    b = it.interpret_rfm(TIERS, ret)
    _ok(b)
    assert "25%" in b["so_what"] and "down" in b["so_what"] and "Need attention" in b["shows"]       # at risk + hibernating = 500 / 2000
    assert "up" in it.interpret_rfm(TIERS, [{"retention": 0.70}, {"retention": 0.90}])["so_what"]


RANK = [{"category": "COFFEE", "verdict": "PAYS ONLY IF OPTIMISTIC", "needed_response_multiple": 1.6},
        {"category": "SOUP", "verdict": "PAYS ONLY IF OPTIMISTIC", "needed_response_multiple": 2.4},
        {"category": "YOGURT", "verdict": "DOES NOT PAY", "needed_response_multiple": 4.5}]


def test_portfolio_says_none_pays_at_base_and_names_where_to_learn():
    b = it.interpret_portfolio(RANK)
    _ok(b)
    assert "None of the 3" in b["so_what"] and "Coffee" in b["do"] and "1.6x" in b["shows"] and "Spend nothing paid" in b["do"]


def test_portfolio_recommends_a_test_when_something_pays():
    r = [{"category": "COFFEE", "verdict": "PAYS IN THE BASE CASE", "needed_response_multiple": 0.8}] + RANK[1:]
    b = it.interpret_portfolio(r)
    assert "1 of 3 categories pay at base" in b["so_what"] and "Test Coffee first" in b["do"]


def test_segments_point_at_where_buyers_come_from():
    segs = [{"segment": "REGULAR", "households": 200, "mean_chance_of_buying": 0.6, "expected_buyers_4w": 120},
            {"segment": "ACTIVE_NONBUYER", "households": 900, "mean_chance_of_buying": 0.07, "expected_buyers_4w": 63}]
    b = it.interpret_segments(segs, "COFFEE")
    assert "Regular supplies the most buyers" in b["shows"] and "Active Nonbuyer is the biggest group" in b["shows"] and "183" in b["shows"]


def test_geo_flags_a_content_gap_only_when_there_is_one():
    gap = {"Learn": {"n": 8, "mentioned": 5, "recommended": 0}, "Browse": {"n": 6, "mentioned": 6, "recommended": 6}, "Buy": {"n": 6, "mentioned": 6, "recommended": 6}}
    b = it.interpret_geo(gap, 17, 12, 8, 20, "Kroger")
    assert "content gap" in b["so_what"] and "not a lost sale" in b["so_what"] and "Learn" in b["do"]
    _ok(b)
    fine = {k: {"n": 6, "mentioned": 6, "recommended": 5} for k in gap}
    assert "content gap" not in it.interpret_geo(fine, 18, 15, 10, 18, "Kroger")["so_what"]


@pytest.mark.parametrize("verdict,needle", [("READY", "Everything the design needs"), ("PARTIAL", "caveats"), ("NOT_READY", "missing")])
def test_readiness_wording_follows_the_verdict(verdict, needle):
    res = {"verdict": verdict, "checks": [{"requirement": "History of at least 53 weeks", "status": "PARTIAL" if verdict == "PARTIAL" else "NOT_READY" if verdict == "NOT_READY" else "PASS"}]}
    b = it.interpret_readiness(res)
    _ok(b)
    assert needle in b["so_what"]


# ------------------------------------------------------------------------------------------------ strategy plan
pytestmark_data = pytest.mark.skipif(not (PROCESSED / "scores_latest.parquet").exists(), reason="run python -m mi.model.train first")


@pytest.fixture(scope="module")
def plans():
    cfg = load_config()
    return {c: sp.build_plan(c, cfg) for c in cfg["categories"]}


@pytest.fixture(scope="module")
def cards():
    cfg = load_config()
    return {c: dc.build_card(c, cfg) for c in cfg["categories"]}


@pytestmark_data
def test_every_plan_passes_its_checker_and_stays_pending(plans):
    assert len(plans) == 8
    for cat, p in plans.items():
        assert p["checker"] == [], (cat, p["checker"])
        assert p["approval"]["state"] == "PENDING_HUMAN" and p["approval"]["sandbox_only"] is True
        assert p["schema_version"] == "marketing_plan.v1"


@pytestmark_data
def test_paid_items_exist_only_when_the_card_allows_a_paid_offer(plans):
    for cat, p in plans.items():
        paid = p["decision_from_card"] != "NO PAID OFFER"
        arms = {a["kind"] for a in p["budget"]["arms"]}
        channels = {c["kind"] for c in p["marketing_mix"]["channels"]}
        acts = {a["kind"] for ph in p["roadmap"] for a in ph["activities"]}
        assert ("paid" in arms) == paid and ("paid" in channels) == paid and ("paid" in acts) == paid, cat


@pytestmark_data
def test_the_plan_decision_equals_the_card_decision(plans, cards):
    for cat in plans:
        assert plans[cat]["decision_from_card"] == cards[cat]["headline"]["decision"]
        assert plans[cat]["stp"]["targeting"]["primary"] == cards[cat]["recommendation"]["segment"]


@pytestmark_data
def test_everything_that_contacts_or_spends_is_behind_consent_stock_and_launch_gates(plans):
    for p in plans.values():
        for ph in p["roadmap"]:
            for a in ph["activities"]:
                if a["kind"] in ("owned", "paid"):
                    assert {"G2", "G4"} <= set(a["gates"])


@pytestmark_data
def test_roadmap_covers_weeks_zero_to_thirteen_in_order(plans):
    for p in plans.values():
        w = [ph["weeks"] for ph in p["roadmap"]]
        assert w[0][0] == 0 and w[-1][1] == 13
        assert all(a[1] <= b[0] or a[1] + 1 == b[0] for a, b in zip(w, w[1:])) and all(x[0] <= x[1] for x in w)


@pytestmark_data
def test_the_hurdle_is_the_cards_break_even_not_a_forecast(plans, cards):
    for cat, p in plans.items():
        f = p["stp"]["targeting"]["primary"]
        o = next(x for x in cards[cat]["options"] if x["segment"] == f)
        expect = o["needed_response_multiple"] * o["assumed_response_points"][1] * 100
        m = next(x for x in p["metrics"] if x["id"] == "p_be_points")
        assert m["value"] == pytest.approx(expect) and m["tag"] == "SCENARIO"
        assert "not a forecast" in p["objective"]["status"]


@pytestmark_data
def test_budget_adds_up_and_free_actions_cost_nothing(plans):
    for p in plans.values():
        b = p["budget"]
        assert b["free_actions_usd"] == 0
        assert b["total_test_usd"] == pytest.approx(b["setup_usd"] + sum(a["cost_usd"] for a in b["arms"]), abs=0.05)
        assert next(a for a in b["arms"] if a["kind"] == "control")["cost_usd"] == 0


@pytestmark_data
def test_message_drafts_never_state_a_price_discount_or_number(plans):
    for p in plans.values():
        assert p["message_drafts"]
        for m in p["message_drafts"]:
            assert not sp.BAD_COPY.search(m["draft_subject"]) and "not sent" in m["status"]


@pytestmark_data
def test_regular_buyers_are_never_a_target_for_offers(plans):
    for p in plans.values():
        assert "REGULAR" not in [p["stp"]["targeting"]["primary"]] + p["stp"]["targeting"]["secondary"]
        assert any(x["segment"] == "REGULAR" for x in p["stp"]["targeting"]["do_not_target_with_offers"])


@pytest.fixture()
def good(plans):
    return copy.deepcopy(plans["COFFEE"])


@pytest.fixture()
def good_no_paid(plans):
    return copy.deepcopy(plans["YOGURT"])


def _contact_activity(p):
    return next(a for ph in p["roadmap"] for a in ph["activities"] if a["kind"] in ("owned", "paid"))


@pytestmark_data
@pytest.mark.parametrize("name,mutate,needle", [
    ("approved", lambda p: p["approval"].update(state="APPROVED"), "PENDING_HUMAN"),
    ("ungated send", lambda p: _contact_activity(p).update(gates=[]), "without gates"),
    ("only one gate", lambda p: _contact_activity(p).update(gates=["G2"]), "without gates"),
    ("sale message", lambda p: p["message_drafts"][0].update(draft_subject="50% off your coffee"), "price, discount"),
    ("unregistered number", lambda p: p["objective"].update(statement="Reach 4,321 households."), "not a registered metric"),
    ("profit claim", lambda p: p["objective"].update(statement="This delivers profit."), "profit is claimed"),
    ("promise", lambda p: p["objective"].update(statement="The reminder will increase sales."), "promise of effect"),
    ("phase order", lambda p: p["roadmap"][2].update(weeks=[0, 0]), "out of order"),
])
def test_plan_checker_catches_each_tamper(good, name, mutate, needle):
    mutate(good)
    assert any(needle in x for x in sp.check_plan(good)), (name, sp.check_plan(good))


@pytestmark_data
def test_a_paid_arm_in_a_no_paid_plan_is_caught(good_no_paid):
    good_no_paid["budget"]["arms"].append({"arm": "Coupon", "kind": "paid", "cost_usd": 100.0})
    assert any("no paid offer" in x for x in sp.check_plan(good_no_paid))


@pytestmark_data
def test_markdown_has_every_section_and_the_checker_line(plans):
    md = sp.to_markdown(plans["COFFEE"])
    for h in ["## 1. Objective", "## 2. Segmentation", "## 5. 13-week roadmap", "## 6. Budget", "## 10. Risks", "## 11. What we need from the client"]:
        assert h in md
    assert "Checker: PASS" in md and "PENDING_HUMAN" in md
