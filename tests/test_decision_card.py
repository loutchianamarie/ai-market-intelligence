"""Decision card: consistent with the portfolio engine, refuses unsupported text, never approves anything."""
from __future__ import annotations

import copy
import json
import re

import pandas as pd
import pytest

from mi.config import load_config
from mi.decision import decision_card as dc
from mi.paths import PROCESSED, REPORTS

pytestmark = pytest.mark.skipif(not (PROCESSED / "scores_latest.parquet").exists(), reason="run python -m mi.model.train first")


@pytest.fixture(scope="module")
def cards():
    cfg = load_config()
    return {c: dc.build_card(c, cfg) for c in cfg["categories"]}


def test_every_category_card_passes_its_own_checker(cards):
    assert len(cards) == 8
    for cat, c in cards.items():
        assert c["checker"] == [], (cat, c["checker"])
        assert c["schema_version"] == "decision_card.v1"


def test_no_card_ever_approves_or_sends(cards):
    for c in cards.values():
        assert c["approval"]["state"] == "PENDING_HUMAN" and c["approval"]["sandbox_only"] is True
        blob = json.dumps(c).lower()
        assert not re.search(r"approved by|sent to", blob)


def test_card_numbers_equal_the_portfolio_file(cards):
    port = {r["plan_id"]: r for r in json.loads((REPORTS / "portfolio.json").read_text())["ranked_actions"]}
    checked = 0
    for c in cards.values():
        for o in c["options"]:
            pid = f"{c['category']}/{o['segment']}/digital_coupon/ALL"
            if pid in port:
                assert o["contribution_usd"]["base"] == pytest.approx(port[pid]["net_base"], abs=0.01)
                assert o["contribution_usd"]["low"] == pytest.approx(port[pid]["net_low"], abs=0.01)
                assert o["contribution_usd"]["high"] == pytest.approx(port[pid]["net_high"], abs=0.01)
                checked += 1
    assert checked >= 4


def test_segment_counts_add_up_to_the_scored_households(cards):
    sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
    for cat, c in cards.items():
        n = int((sc.product_category == cat).sum())
        assert c["situation"]["households_scored"] == n == sum(s["households"] for s in c["situation"]["segments"])
        assert c["situation"]["expected_buyers_4w"] == pytest.approx(float(sc[sc.product_category == cat].p_model.sum()))


def test_verdict_follows_the_stated_rule(cards):
    for c in cards.values():
        for o in c["options"]:
            x = o["contribution_usd"]
            expect = ("PAYS (assumed, robust)" if x["low"] > 0 else "PAYS IN THE BASE CASE" if x["base"] > 0
                      else "PAYS ONLY IF OPTIMISTIC" if x["high"] > 0 else "DOES NOT PAY")
            assert o["verdict"] == expect


def test_decision_follows_the_best_option(cards):
    for c in cards.values():
        best = c["options"][0]
        d = c["headline"]["decision"]
        if best["verdict"] in ("PAYS (assumed, robust)", "PAYS IN THE BASE CASE"):
            assert d == "TEST THEN SCALE"
        elif best["verdict"] == "PAYS ONLY IF OPTIMISTIC":
            assert d.startswith("LEARN FIRST") and c["test_design"]["households_per_arm_for_assumed_response"] > 0
        else:
            assert d == "NO PAID OFFER"


def test_options_are_ranked_best_first(cards):
    order = ["PAYS (assumed, robust)", "PAYS IN THE BASE CASE", "PAYS ONLY IF OPTIMISTIC", "DOES NOT PAY"]
    for c in cards.values():
        r = [order.index(o["verdict"]) for o in c["options"]]
        assert r == sorted(r)


def test_regular_buyers_are_never_given_a_discount_action(cards):
    for c in cards.values():
        reg = next(a for a in c["next_best_action"] if a["segment"] == "REGULAR")
        assert "No discount" in reg["do_now_free"]


def test_unknowns_carry_no_number_and_the_margin_is_labelled_assumed(cards):
    for c in cards.values():
        for u in c["unknowns"]:
            if u["status"] == "UNKNOWN":
                assert u["value"] is None
        assert {u["item"]: u["status"] for u in c["unknowns"]}["contribution margin"] == "ASSUMED"
        assert c["confidence"]["profit"]["level"] == "NONE" and c["confidence"]["what_an_offer_would_do"]["tag"] == "UNKNOWN"


def test_cross_sell_only_lists_pairs_that_survived_the_held_out_weeks(cards):
    for c in cards.values():
        for x in c["cross_sell"]:
            assert x["lift_H2_ci95"][0] > 1 and "not proof" in x["status"]


def test_unknown_category_is_refused():
    with pytest.raises(ValueError):
        dc.build_card("PET FOOD")


# ------------------------------------------------------------------ the checker catches what it is meant to catch
@pytest.fixture()
def good(cards):
    return copy.deepcopy(cards["COFFEE"])


def _first_scenario_metric(c):
    return next(m for m in c["metrics"] if m["tag"] == "SCENARIO")


@pytest.mark.parametrize("name,mutate,needle", [
    ("approved", lambda c: c["approval"].update(state="APPROVED"), "PENDING_HUMAN"),
    ("not sandbox", lambda c: c["approval"].update(sandbox_only=False), "sandbox"),
    ("scenario as observed", lambda c: _first_scenario_metric(c).update(tag="OBSERVED"), "scenario is tagged OBSERVED"),
    ("unknown with a number", lambda c: c["unknowns"][2].update(value=0), "carries a number"),
    ("unregistered number", lambda c: c["recommendation"].update(why="The coupon covers 4,321 buyers."), "not a registered metric"),
    ("profit claim", lambda c: c["recommendation"].update(why="This is profit for the retailer."), "profit is claimed"),
    ("promise of effect", lambda c: c["recommendation"].update(why="The coupon will increase sales."), "promise of effect"),
    ("missing metric", lambda c: c["options"][0]["metric_ids"].append("nope"), "missing metric"),
    ("option not scenario", lambda c: c["options"][0].update(status="OBSERVED result"), "not labelled a scenario"),
])
def test_checker_catches_each_tamper(good, name, mutate, needle):
    mutate(good)
    problems = dc.check_card(good)
    assert any(needle in p for p in problems), (name, problems)


def test_ranking_orders_by_how_close_a_paid_offer_is_to_paying(cards):
    r = dc.rank_cards(list(cards.values()))
    m = r.needed_response_multiple.tolist()
    assert m == sorted(m)
    assert r.iloc[0].category in ("FROZEN PIZZA", "COFFEE")


def test_markdown_states_the_rule_and_the_checker_result(cards):
    md = dc.to_markdown(cards["YOGURT"])
    assert "PENDING_HUMAN" in md and "Rule:" in md and "Checker: PASS" in md and "scenario, not measured" in md
