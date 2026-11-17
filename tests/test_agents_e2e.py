import pytest

from mi.agents.coordinator import AgentOutput, Run
from mi.agents.llm import LLMClient
from mi.agents.tools import ROLE_ALLOWLIST, Toolbox
from mi.workflow.store import DossierStore, pilot_hash

from .conftest import needs_artifacts


class NoLLM(LLMClient):
    def __init__(self):
        self.available = False


def test_allowlists_are_least_privilege():
    writers = {"draft_pilot", "request_approval", "record_sandbox_action", "record_outcome"}
    for role, tools in ROLE_ALLOWLIST.items():
        assert "approve" not in tools
        if role not in ("activation", "measurement"):
            assert not (tools & writers), role
    assert "record_sandbox_action" in ROLE_ALLOWLIST["activation"]


def test_number_without_tool_call_is_flagged(tmp_path):
    r = Run(DossierStore(tmp_path / "a.sqlite"), llm=NoLLM())
    out = AgentOutput(role="portfolio", mode="deterministic")
    out.numbers.append({"name": "roi", "value": 3.2, "unit": "x", "status": "ASSUMED", "tool": "compare_plans"})
    assert r.validate(out).violations


def test_tool_errors_are_returned_not_raised(tmp_path):
    tb = Toolbox(DossierStore(tmp_path / "b.sqlite"))
    assert tb.dispatch("intelligence", "segment_profile", {"category": "NOT A CATEGORY"})["status"] in ("blocked", "error")


@needs_artifacts
def test_end_to_end_single_dossier_trace(tmp_path):
    store = DossierStore(tmp_path / "e2e.sqlite")
    run = Run(store, llm=NoLLM())
    run.persist_traces = False          # throwaway store: never overwrite the live reports/agent_trace_latest.json
    oid = run.run_to_checkpoint()
    d = store.get(oid)
    assert d["state"] == "REVIEW_REQUESTED" and d["pilot"]["budget"]["total"] <= d["pilot"]["budget"]["cap"]
    # premature resume is blocked and logged
    run.activation_record(oid)
    assert "UNAPPROVED_ACTION_BLOCKED" in [e["event"] for e in store.events(oid)]
    # TEST FIXTURE approver (not a real person's approval)
    store.approve(oid, "TEST_FIXTURE_APPROVER", "approver", pilot_hash(store.get(oid)["pilot"]), "test")
    resumed = Run(store, llm=NoLLM())
    resumed.persist_traces = False
    state = resumed.resume_after_approval(oid)
    assert state in ("EXPAND", "CHANGE", "STOP", "INCONCLUSIVE")
    d = store.get(oid)
    roles = [t["role"] for t in d["agent_trace"]]
    for r in ("research", "intelligence", "portfolio", "activation", "measurement"):
        assert r in roles
    assert all(not t["violations"] for t in d["agent_trace"])
    assert len(store.crm_actions(oid)) == 1 and d["outcome"]["provenance"].startswith("SIMULATED")
