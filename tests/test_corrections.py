"""Tests added in the verification pass (2026-11-14)."""
import json
from types import SimpleNamespace

import pytest

from mi.agents.llm import LLMClient
from mi.agents.tools import Toolbox
from mi.outcome.learning import contribution_sample_size, pilot_design
from mi.workflow.store import DossierStore, PermissionDenied, WorkflowError, pilot_hash

from .conftest import needs_artifacts

PILOT = {"plan_id": "P1", "audience": {"segment": "LAPSING"}, "channel": "digital_coupon",
         "offer": {"value_usd": 0.9}, "message": "Coupon added. Reply STOP to opt out.", "budget": {"total": 100}}


def test_rejection_path_blocks_sandbox_and_allows_redraft(tmp_path):
    s = DossierStore(tmp_path / "r.sqlite")
    d = s.create({})
    d = s.update(d["opportunity_id"], 1, {"pilot": PILOT}, "activation_agent", "agent")
    d = s.request_review(d["opportunity_id"], d["version"], "activation_agent")
    with pytest.raises(PermissionDenied):
        s.reject(d["opportunity_id"], "activation_agent", "agent", "self-reject")
    d = s.reject(d["opportunity_id"], "Jane Approver", "approver", "message too pushy")
    assert d["state"] == "REJECTED"
    with pytest.raises(PermissionDenied):
        s.record_sandbox_action(d["opportunity_id"], "k", "activation_agent")
    assert "STATE_REJECTED" in [e["event"] for e in s.events(d["opportunity_id"])]


def test_contribution_sample_size_textbook():
    # sigma 1, delta 0.1 -> 2 * (1.96 + 0.8416)^2 / 0.01 = 1569.8 -> 1570
    assert contribution_sample_size(1.0, 0.1) == 1570
    with pytest.raises(ValueError):
        contribution_sample_size(1.0, 0.0)


def test_purchase_proxy_n_cannot_support_expand():
    d = pilot_design(q0=0.3049, g=2.8932, face=0.9046, contact=0.03, redemption=0.35, sigma=1.6352, assumed_dq=0.04)
    assert d["n_purchase_proxy"] == 866
    # with 866 per arm, EXPAND needs far more uplift than break-even
    assert d["mde_by_n_per_arm"]["866"]["uplift_needed_for_expand"] > 2.5 * d["break_even_uplift"]
    assert d["n_contribution"]["2.0"]["n_per_arm"] > 2 * d["n_purchase_proxy"]
    assert d["n_contribution"]["3.0"]["n_per_arm"] < d["n_contribution"]["2.0"]["n_per_arm"] < d["n_contribution"]["1.5"]["n_per_arm"]


@needs_artifacts
def test_pilot_design_tool_labels_scale_and_feasibility(tmp_path):
    r = Toolbox(DossierStore(tmp_path / "p.sqlite")).dispatch("activation", "pilot_design",
                                                              {"category": "FROZEN PIZZA", "segment": "LAPSING", "channel": "digital_coupon"})
    assert r["status"] == "ok"
    f = r["data"]["feasibility"]
    assert f["panel_contactable"] is False and "ASSUMED" in f["assumed_company_reachable_status"]
    assert f["eligible_consented_households_needed"] == 2 * r["data"]["sizing_choice"]["n_per_arm"]


def test_decision_value_same_plan_arithmetic():
    from mi.outcome.learning import decision_value
    # FROZEN PIZZA / LAPSING / digital inputs from the pipeline; break-even uplift 0.0636
    dv = decision_value(q0=0.3049, g=2.8932, face=0.9046, contact=0.03, redemption=0.35, n_per_arm=2623,
                        reachable=7308, fixed=1500, uplifts={"base": 0.04, "sizing": 0.1272, "3x": 0.1908})
    s = dv["scenarios"]
    assert s["base"]["v_per_contacted_hh"] < 0 and s["base"]["whole_cycles_to_cover_test"] is None
    # at the sizing uplift the rollout cycle still loses after setup -> no payback claim allowed
    assert s["sizing"]["rollout_cycle_net"] < 0 and s["sizing"]["whole_cycles_to_cover_test"] is None
    # rollout break-even lies between the sizing and 3x uplift; whole cycles are rounded UP
    assert 0.1272 < dv["rollout_break_even_uplift"] < 0.1908
    assert s["3x"]["whole_cycles_to_cover_test"] == 3
    assert abs(7308 * (dv["rollout_break_even_uplift"] * (2.8932 - 0.9046) - 0.03 - 0.3049 * 0.35 * 0.9046) - 1500) < 5


def test_payback_only_under_full_pool_upper_bound():
    """Reusing the full 7,308 pool every cycle is an upper bound; with only new entrants or a one-off on the households
    not yet offered, 3x break-even does NOT recover the test."""
    from mi.outcome.learning import decision_value
    dv = decision_value(q0=0.3049, g=2.8932, face=0.9046, contact=0.03, redemption=0.35, n_per_arm=2623,
                        reachable=7308, fixed=1500, uplifts={"3x": 0.1908}, share_new=0.616)
    s = dv["scenarios"]["3x"]
    assert s["whole_cycles_to_cover_test"] == 3                       # A: upper bound
    assert s["new_entrants_cycle_net"] < 0 and s["whole_new_entrant_cycles_to_cover_test"] is None   # B
    assert s["one_time_remaining_pool_net"] < 0 and not s["one_time_covers_test"]                      # C
    assert dv["remaining_never_offered"] == 7308 - 2623
    h = dv["hurdles"]
    assert h["unit_break_even_before_setup"] < h["A_full_pool_cycle_break_even"] < h["B_new_entrants_cycle_break_even"]
    assert h["A_full_pool_cycle_break_even"] < h["C_one_time_remaining_covers_setup_and_test"]


def test_reject_with_research_followup_records_checklist_only(tmp_path):
    s = DossierStore(tmp_path / "rj.sqlite")
    d = s.create({})
    oid = d["opportunity_id"]
    d = s.update(oid, 1, {"pilot": PILOT}, "activation_agent", "agent")
    d = s.request_review(oid, d["version"], "activation_agent")
    tb = Toolbox(s)
    # before any human decision the agent cannot record research follow-up
    assert tb.dispatch("activation", "record_research_followup", {"opportunity_id": oid, "idempotency_key": "k1"})["status"] == "blocked"
    with pytest.raises(WorkflowError):
        s.reject(oid, "Jane Approver", "approver", "  ")                # a reason is required
    plan = [{"id": "R1", "task": "interviews", "owner": "L", "cost_usd": 0}]
    d = s.reject(oid, "Jane Approver", "approver", "test not worth funding at assumed scale", follow_up=plan)
    assert d["state"] == "REJECTED" and d["decision_record"]["follow_up_approved_by"] == "Jane Approver"
    assert d["decision_record"]["follow_up_research"][0]["status"].startswith("PLANNED")
    r = tb.dispatch("activation", "record_research_followup", {"opportunity_id": oid, "idempotency_key": "k2"})
    assert r["status"] == "ok" and r["data"]["kind"] == "research_task_record" and r["provenance"]["live_send"] is False
    assert tb.dispatch("activation", "record_research_followup", {"opportunity_id": oid, "idempotency_key": "k2"})["data"]["duplicate"]
    assert s.get(oid)["state"] == "REJECTED"                            # no state change, no coupon record
    assert tb.dispatch("activation", "record_sandbox_action", {"opportunity_id": oid, "idempotency_key": "k3"})["status"] == "blocked"
    assert tb.dispatch("research", "record_research_followup", {"opportunity_id": oid, "idempotency_key": "k4"})["status"] == "blocked"
    ev = [e["event"] for e in s.events(oid)]
    assert "RESEARCH_TASKS_RECORDED" in ev and "RESEARCH_RECORD_BLOCKED" in ev


@needs_artifacts
def test_worth_it_check_uses_the_test_plan_not_another_plan(tmp_path):
    r = Toolbox(DossierStore(tmp_path / "w.sqlite")).dispatch("activation", "pilot_design",
                                                              {"category": "FROZEN PIZZA", "segment": "LAPSING", "channel": "digital_coupon"})
    dv, cc = r["data"]["decision_value"], r["data"]["candidate_choice"]
    assert dv["plan"] == "FROZEN PIZZA|LAPSING|digital_coupon" == cc["candidate"]
    assert dv["n_per_arm"] == r["data"]["sizing_choice"]["n_per_arm"]
    # the candidate is chosen because it needs the smallest uplift multiple, not because it is the best base plan
    assert cc["candidate_rank_closest_to_break_even"] == 1
    assert cc["uplift_multiple_to_break_even_per_hh"]["candidate"] < cc["uplift_multiple_to_break_even_per_hh"]["best_base"]


@needs_artifacts
def test_scale_free_view_is_independent_of_scale():
    from mi.config import load_config
    from mi.decision.optimizer import load_inputs, optimise
    cfg = load_config()
    s, e, _ = load_inputs()
    a = optimise(s, e, cfg, {"scale": 40.0})["top3"][0]["base"]["components"][0]
    b = optimise(s, e, cfg, {"scale": 250.0})
    comp = [c for p in b["top3"] for c in p["base"]["components"] if c["candidate_id"] == a["candidate_id"]]
    if comp:
        assert comp[0]["net_per_1000_contacted_before_fixed"] == pytest.approx(a["net_per_1000_contacted_before_fixed"])
    assert "ASSUMED" in a["reach_status"]


class _FakeMessages:
    """MOCKED Anthropic client: exercises our loop/allowlist logic only. Not a live LLM call."""
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def create(self, **kw):
        self.calls.append(kw)
        return self.script.pop(0)


def _block(**k):
    return SimpleNamespace(**k)


def test_llm_loop_enforces_dispatch_and_round_limit_with_mock():
    tool_turn = SimpleNamespace(stop_reason="tool_use", model="mock", content=[
        _block(type="tool_use", id="t1", name="record_sandbox_action", input={"opportunity_id": "X", "idempotency_key": "k"})])
    final = SimpleNamespace(stop_reason="end_turn", model="mock", content=[_block(type="text", text='{"claims": []}')])
    c = LLMClient.__new__(LLMClient)
    c.model, c.effort, c.available = "mock", "medium", True
    fake = _FakeMessages([tool_turn, final])
    c._client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    tb = Toolbox.__new__(Toolbox)  # dispatcher allowlist check happens before any store access
    tb.store = None
    out = c.run_role("sys", "user", [], lambda n, i: tb.dispatch("research", n, i, None))
    assert out["status"] == "ok" and out["calls"][0]["status"] == "blocked"   # research cannot record actions
    assert fake.calls[0]["fallbacks"] == "default" and fake.calls[0]["thinking"] == {"type": "adaptive"}
    # round limit
    fake2 = _FakeMessages([tool_turn] * 3)
    c._client = SimpleNamespace(beta=SimpleNamespace(messages=fake2))
    assert c.run_role("s", "u", [], lambda n, i: {"status": "ok"}, max_rounds=3)["status"] == "round_limit"


def test_refusal_is_returned_not_raised():
    c = LLMClient.__new__(LLMClient)
    c.model, c.effort, c.available = "mock", "medium", True
    c._client = SimpleNamespace(beta=SimpleNamespace(messages=_FakeMessages([SimpleNamespace(stop_reason="refusal", content=[], stop_details=None)])))
    assert c.run_role("s", "u", [], lambda n, i: {})["status"] == "refused"
