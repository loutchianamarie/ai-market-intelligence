"""Manager home (app/manager_home.py): the advisor reacts to its inputs, reads the verified export and refuses a changed one.

Everything runs on throwaway stores and tmp copies; the live export, trace and dossiers are never touched (conftest guards them).
"""
import hashlib
import json
import shutil

import pytest

from mi.consumer import gate as G
from mi.consumer import manager_view as MV
from mi.consumer import source_check as SC
from mi.consumer import viewmodel as VM
from mi.consumer.adapter import CHECKSUM_PATH, EXPORT_PATH, CaseResult, load_case
from mi.consumer.advisor import CampaignRun
from mi.workflow.store import DossierStore, PermissionDenied, WorkflowError, WorkQueue, pilot_hash

pytestmark = pytest.mark.skipif(not EXPORT_PATH.exists(), reason="campaign export not present")

OK_INPUTS = dict(margin=0.35, cost_per_email=0.03, setup=1000, consent_verified=True, holdout_drawn=True)


@pytest.fixture(scope="module")
def case():
    c = load_case()
    assert c.ok
    return c


def run(case, inputs, tmp_path, name="x"):
    store = DossierStore(tmp_path / f"{name}.sqlite")
    r = CampaignRun(case, store, persist=False, commercial=inputs)
    out = r.run_to_checkpoint()
    return r, store, out, store.get(out["opportunity_id"])


# ---------------------------------------------------------------- the gate follows the inputs
@pytest.mark.parametrize("name,inputs,decision", [
    ("none provided", {}, "HOLD_FOR_INPUTS"),
    ("everything verified", OK_INPUTS, "READY_FOR_HUMAN_APPROVAL"),
    ("cost above break-even", {**OK_INPUTS, "cost_per_email": 0.40}, "NO_EMAIL"),
    ("consent removed", {**OK_INPUTS, "consent_verified": False}, "HOLD_FOR_INPUTS"),
    ("holdout not drawn", {**OK_INPUTS, "holdout_drawn": False}, "HOLD_FOR_INPUTS"),
    ("model exclusion requested", {**OK_INPUTS, "exclude_with_model": True}, "REJECTED_MODEL_EXCLUSION"),
    ("cost near break-even", {**OK_INPUTS, "cost_per_email": 0.25, "setup": 0}, "PILOT_ONLY"),
])
def test_gate_decisions(case, name, inputs, decision):
    assert G.evaluate(case, inputs)["decision"] == decision, name


def test_break_even_comes_from_the_export_and_unknowns_are_not_invented(case):
    g = G.evaluate(case, OK_INPUTS)
    spend = case.claim("CLM_SPEND_PER_CONTACT_MENS")["value"]
    assert g["break_even_cost"]["point"] == pytest.approx(spend * 0.35, abs=1e-4)     # the claim is the rounded display of the full-precision effect
    none = G.evaluate(case, None)
    assert none["scenario"] is None and none["break_even_cost"]["point"] is None          # no margin -> no number
    assert any("margin" in b for b in none["blockers"]) and any("cost per e-mail" in b for b in none["blockers"])
    assert "no named human approval (marketing manager)" in G.evaluate(case, OK_INPUTS)["blockers"]   # a human is always still required


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        G.normalize({"margin": 1.5})
    with pytest.raises(ValueError):
        G.normalize({"cost_per_email": -1})


# ---------------------------------------------------------------- the specialists really re-run (not a replay)
def test_advisor_output_changes_with_inputs(case, tmp_path):
    seen = {}
    for name, inputs in (("hold", {}), ("ready", OK_INPUTS), ("costly", {**OK_INPUTS, "cost_per_email": 0.40}), ("excl", {**OK_INPUTS, "exclude_with_model": True})):
        seen[name] = run(case, inputs, tmp_path, name)
    hold, ready, costly, excl = (seen[k][3] for k in ("hold", "ready", "costly", "excl"))
    assert pilot_hash(hold["pilot"]) != pilot_hash(ready["pilot"])                                   # a different plan, not a transcript
    assert ready["pilot"]["budget"]["total"] == pytest.approx(57_600 * 0.03 + 1000)                  # budget computed from the typed inputs
    assert hold["pilot"]["budget"]["total"] is None
    assert ready["state"] == "REVIEW_REQUESTED" and hold["state"] == "REVIEW_REQUESTED"
    # economics fail: no e-mail draft, no approval request, only $0 no-send work
    assert "pilot" not in costly and costly["state"] == "DRAFT"
    assert costly["checker_verdict"]["verdict"] == "PASS_NO_SEND"
    kinds = {w["payload"]["kind"] for w in WorkQueue(seen["costly"][1]).list(seen["costly"][2]["opportunity_id"])}
    assert "paid_contact" not in kinds
    # model exclusion: the checker rejects it and it never reaches an approver
    assert excl["checker_verdict"]["verdict"].startswith("REJECTED") and excl["state"] == "DRAFT"
    assert any("exclude customers" in p for p in excl["checker_verdict"]["problems"])


def test_default_run_keeps_the_saved_plan(case, tmp_path):
    """No commercial inputs: the plan is exactly what the saved-run path always produced (export recommendation status, UNKNOWN budget)."""
    _, _, _, d = run(case, None, tmp_path)
    assert d["pilot"]["recommendation_status"] == case.doc["recommendation"]["status"]
    assert d["pilot"]["budget"]["total"] is None and d["checker_verdict"]["verdict"] == "PASS_DRAFT_HOLD_FOR_INPUTS"
    assert "commercial_gate" not in d


def test_run_advisor_is_fast_offline_and_never_approves(case):
    r = MV.run_advisor(case, OK_INPUTS)
    assert r["ok"] and r["mode"] == "DETERMINISTIC_SPECIALISTS" and r["state"] == "REVIEW_REQUESTED"
    assert r["runtime_ms"] < 5000 and r["export_sha256"] == case.sha256
    assert not any("approve" in t or "send" in t for s in r["steps"] for t in s["tools"])
    assert MV.strip_state(r, True)[-1] == ("Human review", False)                                   # the system never completes the human step


def test_approval_stays_a_bound_human_act(case, tmp_path):
    _, store, out, d = run(case, OK_INPUTS, tmp_path)
    oid, h = out["opportunity_id"], pilot_hash(d["pilot"])
    with pytest.raises((PermissionDenied, WorkflowError)):
        store.approve(oid, "strategist_agent", "agent", h, "self-approval")                          # an agent cannot approve
    with pytest.raises((PermissionDenied, WorkflowError)):
        store.approve(oid, "A. Person", "approver", "0" * 64, "wrong plan hash")                     # approval is bound to the exact plan
    assert store.get(oid).get("approval") is None


# ---------------------------------------------------------------- a changed input is refused, never given the old numbers
def _tamper(tmp_path, case):
    doc = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    doc["observed_arm_metrics"][1]["buyers"] += 25                                                   # a changed dataset/result
    p = tmp_path / "changed.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_modified_export_without_its_checksum_is_refused(case, tmp_path):
    p = _tamper(tmp_path, case)
    shutil.copy(CHECKSUM_PATH, p.with_suffix(".sha256"))                                              # the OLD checksum travels with it
    r = load_case(p)
    assert r.status == "REJECTED" and "SHA-256 mismatch" in " ".join(r.reasons)
    assert not r.ok and MV.run_advisor(r, None)["ok"] is False                                        # no run, no figure


def test_modified_export_with_its_own_checksum_cannot_inherit_the_old_trace(case, tmp_path):
    p = _tamper(tmp_path, case)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    r = load_case(p, expected_sha=sha)
    old_trace = VM.latest_trace()
    assert r.sha256 != case.sha256
    assert not VM.trace_is_current(old_trace, r.sha256)                                               # the saved agent run belongs to the old export
    assert SC.freshness(r, old_trace)["stale"] == ["agent_trace_is_for_this_export"] or not r.ok
    if r.ok:                                                                                          # if the contract accepts it, the advisor recomputes from it
        assert MV.run_advisor(r, None)["export_sha256"] == r.sha256


def test_raw_file_check_refuses_a_changed_dataset_and_accepts_the_locked_one(case):
    stub_bytes = b"id,visit\n1,0\n"
    stub = CaseResult("OK", doc={"dataset_provenance": {"sha256": hashlib.sha256(stub_bytes).hexdigest(), "rows": 1, "bytes": len(stub_bytes), "source_id": "S"}}, sha256="f" * 64)
    assert SC.verify_raw_bytes(stub, stub_bytes)["state"] == "VERIFIED"
    bad = SC.verify_raw_bytes(stub, stub_bytes + b"2,1\n")
    assert bad["state"] == "REFUSED" and "NOT attached" in bad["text"] and "recomputation" in bad["text"]
    real = SC.verify_local_raw(case)
    assert real["state"] in ("VERIFIED", "ABSENT")                                                    # never silently attached on a mismatch
    if real["state"] == "ABSENT":
        assert "never committed" in real["text"]


# ---------------------------------------------------------------- the manager screen reconciles to the export
def test_options_reconcile_to_the_export_claims(case):
    v = VM.build(case, None, None)
    rows = {r["option"]: r for r in MV.options_table(v)}
    claims = case.claims()
    assert rows["Mens e-mail to all"]["per1000_contacted"] == pytest.approx(round(claims["CLM_BUYERS_PER_1000_MENS"]["value"], 1), abs=0.051)
    assert rows["Model-targeted top 25%"]["per1000_contacted"] == pytest.approx(claims["CLM_CAP25_MODEL"]["value"], abs=0.01)
    share = case.doc["model_vs_baselines"]["primary_contact_share"]
    assert rows["Model-targeted top 25%"]["per1000_eligible"] == pytest.approx(rows["Model-targeted top 25%"]["per1000_contacted"] * share)
    assert rows["Model-targeted top 25%"]["tag"] == "HELD-OUT MODEL ESTIMATE" and rows["Mens e-mail to all"]["tag"] == "RANDOMIZED OBSERVATION"
    assert rows["No e-mail"]["per1000_contacted"] == 0 and "excludes no one" in rows["Model-targeted top 25%"]["condition"]
    assert v["verdict"]["code"] == "MODEL_AHEAD_NOT_STABLE" and v["verdict"]["stable_vs_random"] is not True


def test_measurement_keeps_future_outcomes_pending(case):
    r = MV.run_advisor(case, OK_INPUTS)
    plan = MV.measurement_plan(r, case.doc)
    text = " ".join(p["status"] for p in plan)
    assert "PENDING: no e-mail has been sent" in text and "UNKNOWN" in text
    assert all(p["status"].startswith("PENDING") for p in plan if "buyers" in p["measure"].lower() or "Unsubscribes" in p["measure"])


def test_manager_page_has_no_send_control_and_names_the_labels():
    src = (SC.DATA.parent / "app" / "manager_home.py").read_text(encoding="utf-8")
    for label in ("RANDOMIZED OBSERVATION", "HELD-OUT MODEL ESTIMATE", "SCENARIO", "UNKNOWN", "PENDING", "Evidence drawer"):
        assert label in src, label
    assert "form_submit_button" not in src and "st.button" not in src                                 # no action control on the manager screen
    assert "send_email" not in src and "record_sandbox_action" not in src
