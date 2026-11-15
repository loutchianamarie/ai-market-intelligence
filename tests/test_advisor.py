"""Buyer-outcome arithmetic and the advisor work queue (simulated CRM)."""
import numpy as np
import pandas as pd
import pytest

from mi.decision.buyer_outcomes import additional_buyers, current_pattern_buyers, observed_outcome, summarize_observed
from mi.workflow.store import DossierStore, PermissionDenied, WorkflowError, WorkQueue


def test_current_pattern_buyers_are_bounded_unique_household_counts():
    q = np.array([0.9, 0.5, 0.1, 0.0])
    r = current_pattern_buyers(q, {"available": True, "ratio_ci95": [0.5, 3.0]})
    assert r["households"] == 4 and r["expected_buyers"] == 1.5
    lo, hi = r["poisson_binomial_95"]
    assert 0 <= lo <= 1.5 <= hi <= 4
    clo, chi = r["calibration_adjusted_range"]
    assert clo >= 0 and chi <= 4                       # never more buyers than eligible households


def test_additional_buyers_capped_at_headroom_and_break_even_consistent():
    add = additional_buyers(n_reach=100, mean_q0=0.95, dq_range=[0.02, 0.04, 0.5])
    assert add["high"] == add["cap_headroom"] == 5.0 and add["low"] == 2.0
    # break-even additional buyers make contribution zero: add*(g-F) - (n*c + n*q0*r*F + setup) = 0
    n, q0, g, F, c, r, setup = 7308, 0.2964, 2.893, 0.9046, 0.03, 0.35, 1500
    be = (n * c + n * q0 * r * F + setup) / (g - F)
    assert abs(be * (g - F) - (n * c + n * q0 * r * F + setup)) < 1e-6


def _pilot(randomized=True, n=2000, effect=0.1, seed=1):
    rng = np.random.default_rng(seed)
    arm = np.where(rng.random(n) < 0.5, "treatment", "control")
    buy = rng.random(n) < np.where(arm == "treatment", 0.3 + effect, 0.3)
    df = pd.DataFrame({"household_id": [f"H{i}" for i in range(n)], "arm": arm, "excluded_pre_treatment": 0,
                       "category_spend_usd": np.where(buy, 10.0, 0.0), "coupon_cost_usd": np.where((arm == "treatment") & buy, 0.9, 0.0),
                       "contact_cost_usd": np.where(arm == "treatment", 0.03, 0.0), "purchased": buy.astype(int), "opted_out": 0, "complaint": 0})
    meta = {"source": "SYNTHETIC test", "randomized": randomized, "assignment_method": "rng", "margin_rate": 0.28, "margin_status": "ASSUMED",
            "rollout_households": 7308, "rollout_fixed_setup_usd": 1500, "stockout_flag": False, "preregistration": "test"}
    return df, meta


def test_observed_outcome_never_attributes_without_randomized_control():
    df, meta = _pilot(randomized=False)
    r = summarize_observed(df[df.arm == "treatment"], meta)
    assert r["observed_distinct_buyers_treated"] > 0 and r["status"].startswith("OBSERVED")
    assert isinstance(r["estimated_additional_buyers"], str) and "not estimable" in r["estimated_additional_buyers"]


def test_randomized_control_gives_additional_buyers_with_interval():
    df, meta = _pilot(randomized=True, effect=0.1)
    r = summarize_observed(df, meta)
    e = r["estimated_additional_buyers"]
    n_t = int((df.arm == "treatment").sum())
    assert e["status"].startswith("ESTIMATED CAUSAL") and e["ci95"][0] < 0.1 * n_t < e["ci95"][1]


def test_no_action_run_means_no_observed_buyers(tmp_path):
    assert observed_outcome(tmp_path / "none.csv", tmp_path / "none.json").startswith("NOT RUN")


ITEM = {"kind": "research", "title": "t", "owner": "o", "segment": "S", "channel": "c", "draft": "d", "evidence": ["e"],
        "budget_usd": 0, "due_date": "2026-11-20", "success_metric": "m", "follow_up_date": "2026-11-25"}


def _q(tmp_path):
    s = DossierStore(tmp_path / "q.sqlite")
    oid = s.create({})["opportunity_id"]
    return s, WorkQueue(s), oid


def test_work_queue_zero_cost_ready_paid_blocked_and_idempotent(tmp_path):
    s, q, oid = _q(tmp_path)
    a = q.create(oid, ITEM, "k1", "activation_agent")
    assert a["status"] == "READY"
    assert q.create(oid, ITEM, "k1", "activation_agent")["duplicate"] is True and len(q.list(oid)) == 1
    p = q.create(oid, {**ITEM, "kind": "paid_contact", "budget_usd": 500}, "k2", "activation_agent")
    assert p["status"] == "BLOCKED_PENDING_APPROVAL"
    with pytest.raises(WorkflowError):
        q.create(oid, {"kind": "research"}, "k3", "activation_agent")            # required fields


def test_agent_cannot_decide_and_paid_approval_needs_consent_stock_and_reason(tmp_path):
    s, q, oid = _q(tmp_path)
    p = q.create(oid, {**ITEM, "kind": "paid_contact", "budget_usd": 500}, "k2", "activation_agent")
    with pytest.raises(PermissionDenied):
        q.decide(p["item_id"], "activation_agent", "agent", "approve", "self-approve")
    with pytest.raises(WorkflowError):
        q.decide(p["item_id"], "Jane", "approver", "approve", "  ")
    with pytest.raises(PermissionDenied, match="consent_verified"):
        q.decide(p["item_id"], "Jane", "approver", "approve", "looks fine")
    with pytest.raises(PermissionDenied):
        q.verify_requirement(p["item_id"], "consent_verified", True, "activation_agent", "agent", "crm")
    q.verify_requirement(p["item_id"], "consent_verified", True, "Jane", "approver", "CRM consent export 2026-11-20")
    q.verify_requirement(p["item_id"], "stock_confirmed", True, "Jane", "approver", "ops email")
    assert q.decide(p["item_id"], "Jane", "approver", "approve", "terms confirmed")["status"] == "APPROVED"
    p2 = q.create(oid, {**ITEM, "kind": "paid_contact", "budget_usd": 100}, "k3", "activation_agent")
    q.verify_requirement(p2["item_id"], "consent_verified", True, "Jane", "approver", "x")
    q.verify_requirement(p2["item_id"], "stock_confirmed", True, "Jane", "approver", "x")
    with pytest.raises(PermissionDenied, match="duplicate contact"):
        q.decide(p2["item_id"], "Jane", "approver", "approve", "second wave")
    ev = [e["event"] for e in s.events(oid)]
    assert "WORK_ITEM_BLOCKED" in ev and "WORK_ITEM_APPROVED" in ev


def test_completion_rules_and_observed_outcome(tmp_path):
    s, q, oid = _q(tmp_path)
    p = q.create(oid, {**ITEM, "kind": "paid_contact", "budget_usd": 500}, "k2", "activation_agent")
    with pytest.raises(PermissionDenied):
        q.complete(p["item_id"], "Jane", "approver", {"buyers": 10})              # paid item not approved
    r = q.create(oid, ITEM, "k1", "activation_agent")
    with pytest.raises(PermissionDenied):
        q.complete(r["item_id"], "activation_agent", "agent", {})
    done = q.complete(r["item_id"], "Charbel", "human", {"interviews": 3})
    assert done["status"] == "DONE" and done["payload"]["observed_outcome"]["status"].startswith("OBSERVED")
    d = q.decide(q.create(oid, ITEM, "k4", "activation_agent")["item_id"], "Jane", "approver", "defer", "wait for client")
    assert d["status"] == "DEFERRED"
    assert not any(hasattr(WorkQueue, m) for m in ("send", "launch", "spend", "publish"))
