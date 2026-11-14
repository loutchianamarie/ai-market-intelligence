import pytest

from mi.workflow.store import DossierStore, PermissionDenied, StaleVersion, WorkflowError, pilot_hash

PILOT = {"plan_id": "P1", "audience": {"segment": "LAPSING"}, "channel": "digital_coupon",
         "offer": {"value_usd": 0.9}, "message": "Coupon added. Reply STOP to opt out.", "budget": {"total": 100}}


@pytest.fixture
def store(tmp_path):
    return DossierStore(tmp_path / "t.sqlite")


def _to_review(store):
    d = store.create({"business_case": {}})
    d = store.update(d["opportunity_id"], d["version"], {"pilot": PILOT}, "activation_agent", "agent")
    return store.request_review(d["opportunity_id"], d["version"], "activation_agent")


def test_versions_are_immutable_and_stale_writes_rejected(store):
    d = store.create({"business_case": {}})
    oid = d["opportunity_id"]
    store.update(oid, 1, {"note": "a"}, "x", "agent")
    with pytest.raises(StaleVersion):
        store.update(oid, 1, {"note": "b"}, "y", "agent")
    assert store.get(oid, 1).get("note") is None and store.get(oid)["note"] == "a"


def test_agent_cannot_write_workflow_fields(store):
    d = store.create({})
    with pytest.raises(PermissionDenied):
        store.update(d["opportunity_id"], 1, {"state": "APPROVED"}, "x", "agent")
    with pytest.raises(PermissionDenied):
        store.update(d["opportunity_id"], 1, {"approval": {"plan_hash": "x"}}, "x", "agent")


def test_only_approver_role_can_approve_and_hash_must_match(store):
    d = _to_review(store)
    oid = d["opportunity_id"]
    with pytest.raises(PermissionDenied):
        store.approve(oid, "activation_agent", "agent", pilot_hash(PILOT), "s")
    with pytest.raises(PermissionDenied):
        store.approve(oid, "Jane Approver", "approver", "wrong-hash", "s")
    events = [e["event"] for e in store.events(oid)]
    assert events.count("APPROVAL_BLOCKED") == 2
    assert store.approve(oid, "Jane Approver", "approver", pilot_hash(PILOT), "s")["state"] == "APPROVED"


def test_changed_message_after_approval_invalidates(store):
    d = _to_review(store)
    oid = d["opportunity_id"]
    d = store.approve(oid, "Jane", "approver", pilot_hash(PILOT), "s")
    d = store.update(oid, d["version"], {"pilot": {**PILOT, "message": "New text. Reply STOP."}}, "activation_agent", "agent")
    assert d["state"] == "DRAFT" and d["approval"] is None
    assert "APPROVAL_INVALIDATED" in [e["event"] for e in store.events(oid)]
    with pytest.raises(PermissionDenied):
        store.record_sandbox_action(oid, "k1", "activation_agent")


def test_unapproved_action_blocked_and_logged(store):
    d = _to_review(store)
    with pytest.raises(PermissionDenied):
        store.record_sandbox_action(d["opportunity_id"], "k0", "activation_agent")
    assert "UNAPPROVED_ACTION_BLOCKED" in [e["event"] for e in store.events(d["opportunity_id"])]
    assert store.crm_actions(d["opportunity_id"]) == []


def test_duplicate_crm_submission_is_idempotent(store):
    d = _to_review(store)
    oid = d["opportunity_id"]
    store.approve(oid, "Jane", "approver", pilot_hash(PILOT), "s")
    first = store.record_sandbox_action(oid, "same-key", "activation_agent")
    second = store.record_sandbox_action(oid, "same-key", "activation_agent")
    assert not first["duplicate"] and second["duplicate"]
    assert len(store.crm_actions(oid)) == 1


def test_illegal_transition(store):
    d = store.create({})
    with pytest.raises(WorkflowError):
        store.request_review(d["opportunity_id"], 1, "x")   # no pilot
    with pytest.raises(WorkflowError):
        store.record_outcome(d["opportunity_id"], {"provenance": "x"}, "EXPAND", "m")   # DRAFT -> EVALUATED illegal
