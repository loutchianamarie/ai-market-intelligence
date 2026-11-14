"""Executable agent-worksheet checks and boundary tests (mocked/deterministic; no live LLM)."""
import json
from pathlib import Path

import pytest

from mi.agents.tools import ROLE_ALLOWLIST, Toolbox
from mi.workflow.store import DossierStore, StaleVersion

CFG = json.loads((Path(__file__).resolve().parents[1] / "configs" / "agents.json").read_text())
FORBIDDEN = ("approve", "reject", "send", "spend", "publish", "launch", "pay")
WORKSHEET_FIELDS = {"goal", "tools", "action_order", "human_checkpoint", "success_metric", "risk", "guardrail"}


def test_worksheet_fields_present_and_tools_match_enforced_allowlist():
    assert set(CFG["roles"]) == set(ROLE_ALLOWLIST)
    for role, spec in CFG["roles"].items():
        assert WORKSHEET_FIELDS <= set(spec), role
        assert set(spec["tools"]) == ROLE_ALLOWLIST[role], f"{role}: documented tools differ from enforced allowlist"
        assert any(ch.isdigit() for ch in spec["goal"]), f"{role}: goal needs a number"


def test_no_role_can_approve_send_spend_or_launch():
    for role, tools in ROLE_ALLOWLIST.items():
        for t in tools:
            assert not t.startswith(FORBIDDEN), f"{role} has forbidden tool {t}"
    assert not hasattr(Toolbox, "t_approve") and not hasattr(Toolbox, "t_send") and not hasattr(Toolbox, "t_launch")


def test_every_role_is_blocked_from_every_tool_outside_its_allowlist(tmp_path):
    tb = Toolbox(DossierStore(tmp_path / "a.sqlite"))
    all_tools = {n[2:] for n in dir(Toolbox) if n.startswith("t_")}
    for role, allowed in ROLE_ALLOWLIST.items():
        for t in all_tools - allowed:
            assert tb.dispatch(role, t, {}, None)["status"] == "blocked", (role, t)


def test_repeated_or_stale_writes_are_rejected(tmp_path):
    s = DossierStore(tmp_path / "w.sqlite")
    d = s.create({})
    s.update(d["opportunity_id"], 1, {"note": "first"}, "activation_agent", "agent")
    with pytest.raises(StaleVersion):                       # a second write from the same stale version
        s.update(d["opportunity_id"], 1, {"note": "again"}, "activation_agent", "agent")


def test_launch_preconditions_stay_unknown_in_drafted_pilots():
    """Absent stock/consent: the coordinator's draft lists them as UNKNOWN preconditions; no tool can mark them met."""
    src = (Path(__file__).resolve().parents[1] / "src" / "mi" / "agents" / "coordinator.py").read_text(encoding="utf-8")
    assert "stock confirmed by operations" in src and "eligible consented pool" in src and "UNKNOWN" in src
    assert all("precondition" not in t for tools in ROLE_ALLOWLIST.values() for t in tools)
