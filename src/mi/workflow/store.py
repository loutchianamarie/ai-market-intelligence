"""Versioned OpportunityDossier + CRM sandbox state machine on SQLite.

Guarantees (tested):
  * every write creates a new immutable dossier version; writers must pass the version they read
    (optimistic concurrency) or get StaleVersion,
  * approval binds the SHA-256 of the exact pilot (audience, channel, offer, message, budget);
    changing any of those after approval invalidates it (state -> DRAFT, event logged),
  * only role "approver" can approve; agents can never approve,
  * a sandbox action requires state APPROVED and a matching hash; the idempotency key makes
    duplicate submissions return the original record,
  * no live send, spend or publication exists anywhere in this module.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from mi.paths import DB_PATH

STATES = ["DRAFT", "REVIEW_REQUESTED", "APPROVED", "REJECTED", "SANDBOX_RECORDED", "EVALUATED",
          "EXPAND", "CHANGE", "STOP", "INCONCLUSIVE", "CANCELLED"]
TRANSITIONS = {
    "DRAFT": {"REVIEW_REQUESTED", "CANCELLED"},
    "REVIEW_REQUESTED": {"APPROVED", "REJECTED", "DRAFT", "CANCELLED"},
    "APPROVED": {"SANDBOX_RECORDED", "DRAFT", "CANCELLED"},
    "REJECTED": {"DRAFT"},
    "SANDBOX_RECORDED": {"EVALUATED"},
    "EVALUATED": {"EXPAND", "CHANGE", "STOP", "INCONCLUSIVE"},
    "EXPAND": set(), "CHANGE": {"DRAFT"}, "STOP": set(), "INCONCLUSIVE": {"DRAFT"}, "CANCELLED": set(),
}
PILOT_BOUND_FIELDS = ("audience", "channel", "offer", "message", "budget", "plan_id")


class WorkflowError(RuntimeError):
    pass


class StaleVersion(WorkflowError):
    pass


class PermissionDenied(WorkflowError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def pilot_hash(pilot: dict | None) -> str | None:
    if not pilot:
        return None
    return canonical_hash({k: pilot.get(k) for k in PILOT_BOUND_FIELDS})


SCHEMA = """
CREATE TABLE IF NOT EXISTS dossier_versions(
  opportunity_id TEXT, version INTEGER, created_at TEXT, actor TEXT, role TEXT, note TEXT,
  payload TEXT, payload_hash TEXT, PRIMARY KEY(opportunity_id, version));
CREATE TABLE IF NOT EXISTS audit_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id TEXT, version INTEGER, ts TEXT,
  actor TEXT, role TEXT, event TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS crm_actions(
  action_id TEXT PRIMARY KEY, opportunity_id TEXT, version INTEGER, idempotency_key TEXT UNIQUE,
  plan_hash TEXT, kind TEXT, payload TEXT, ts TEXT, sandbox INTEGER DEFAULT 1);
"""


class DossierStore:
    def __init__(self, path=None):
        self.path = str(path or DB_PATH)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ---------------- events
    def _event(self, c, oid, version, actor, role, event, detail=None):
        c.execute("INSERT INTO audit_events(opportunity_id,version,ts,actor,role,event,detail) VALUES(?,?,?,?,?,?,?)",
                  (oid, version, now(), actor, role, event, json.dumps(detail or {}, default=str)))

    def events(self, oid) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM audit_events WHERE opportunity_id=? ORDER BY id", (oid,)).fetchall()
        return [dict(r) | {"detail": json.loads(r["detail"])} for r in rows]

    # ---------------- dossier
    def create(self, payload: dict, actor="coordinator", role="agent") -> dict:
        oid = payload.get("opportunity_id") or f"OPP-{uuid.uuid4().hex[:8].upper()}"
        payload = {**payload, "opportunity_id": oid, "state": payload.get("state", "DRAFT"),
                   "approval": None, "crm_action_ids": [], "audit": "see audit_events"}
        with self._conn() as c:
            if c.execute("SELECT 1 FROM dossier_versions WHERE opportunity_id=?", (oid,)).fetchone():
                raise WorkflowError(f"{oid} exists")
            self._insert(c, oid, 1, actor, role, "created", payload)
            self._event(c, oid, 1, actor, role, "DOSSIER_CREATED")
        return self.get(oid)

    def _insert(self, c, oid, version, actor, role, note, payload):
        payload = {**payload, "version": version}
        c.execute("INSERT INTO dossier_versions VALUES(?,?,?,?,?,?,?,?)",
                  (oid, version, now(), actor, role, note, json.dumps(payload, default=str), canonical_hash(payload)))

    def get(self, oid, version=None) -> dict:
        with self._conn() as c:
            q = ("SELECT * FROM dossier_versions WHERE opportunity_id=? ORDER BY version DESC LIMIT 1", (oid,)) if version is None \
                else ("SELECT * FROM dossier_versions WHERE opportunity_id=? AND version=?", (oid, version))
            r = c.execute(*q).fetchone()
        if not r:
            raise WorkflowError(f"unknown dossier {oid} v{version}")
        d = json.loads(r["payload"])
        d["_payload_hash"] = r["payload_hash"]
        return d

    def history(self, oid) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT version, created_at, actor, role, note, payload_hash FROM dossier_versions "
                             "WHERE opportunity_id=? ORDER BY version", (oid,)).fetchall()
        return [dict(r) for r in rows]

    def update(self, oid, expected_version: int, patch: dict, actor: str, role: str, note: str = "update") -> dict:
        forbidden = {"approval", "state", "crm_action_ids", "version", "opportunity_id"} & set(patch)
        if forbidden:
            raise PermissionDenied(f"fields {sorted(forbidden)} change only through workflow transitions")
        with self._conn() as c:
            cur = self._latest(c, oid)
            if cur["version"] != expected_version:
                raise StaleVersion(f"{oid}: expected v{expected_version}, current v{cur['version']}")
            new = {**cur, **patch}
            new.pop("_payload_hash", None)
            invalidated = False
            if cur.get("approval") and pilot_hash(new.get("pilot")) != cur["approval"]["plan_hash"]:
                new["approval"] = None
                if new["state"] in ("APPROVED", "REVIEW_REQUESTED"):
                    new["state"] = "DRAFT"
                invalidated = True
            v = cur["version"] + 1
            self._insert(c, oid, v, actor, role, note, new)
            self._event(c, oid, v, actor, role, "DOSSIER_UPDATED", {"fields": sorted(patch)})
            if invalidated:
                self._event(c, oid, v, actor, role, "APPROVAL_INVALIDATED", {"reason": "pilot changed after approval"})
        return self.get(oid)

    def _latest(self, c, oid):
        r = c.execute("SELECT payload FROM dossier_versions WHERE opportunity_id=? ORDER BY version DESC LIMIT 1", (oid,)).fetchone()
        if not r:
            raise WorkflowError(f"unknown dossier {oid}")
        return json.loads(r["payload"])

    def _transition(self, c, cur, to, actor, role, detail=None, extra=None):
        if to not in TRANSITIONS[cur["state"]]:
            raise WorkflowError(f"illegal transition {cur['state']} -> {to}")
        new = {**cur, **(extra or {}), "state": to}
        v = cur["version"] + 1
        self._insert(c, cur["opportunity_id"], v, actor, role, f"-> {to}", new)
        self._event(c, cur["opportunity_id"], v, actor, role, f"STATE_{to}", detail)
        return v

    # ---------------- workflow
    def request_review(self, oid, expected_version, actor, role="agent") -> dict:
        with self._conn() as c:
            cur = self._latest(c, oid)
            if cur["version"] != expected_version:
                raise StaleVersion(f"{oid}: expected v{expected_version}, current v{cur['version']}")
            if not cur.get("pilot"):
                raise WorkflowError("no pilot draft to review")
            self._transition(c, cur, "REVIEW_REQUESTED", actor, role, {"plan_hash": pilot_hash(cur["pilot"])})
        return self.get(oid)

    def approve(self, oid, approver: str, role: str, plan_hash: str, scope: str) -> dict:
        if role != "approver":
            self._log(oid, None, approver, role, "APPROVAL_BLOCKED", {"reason": f"role {role} cannot approve"})
            raise PermissionDenied(f"role '{role}' cannot approve money, offers or customer messages")
        with self._conn() as c:
            cur = self._latest(c, oid)
            if cur["state"] != "REVIEW_REQUESTED":
                raise WorkflowError(f"cannot approve in state {cur['state']}")
            mismatch = plan_hash != pilot_hash(cur["pilot"])
            if not mismatch:
                self._approve_tx(c, cur, approver, role, plan_hash, scope)
        if mismatch:
            self._log(oid, cur["version"], approver, role, "APPROVAL_BLOCKED", {"reason": "hash mismatch"})
            raise PermissionDenied("plan hash does not match the pilot under review")
        return self.get(oid)

    def _approve_tx(self, c, cur, approver, role, plan_hash, scope):
            self._transition(c, cur, "APPROVED", approver, role, {"plan_hash": plan_hash, "scope": scope},
                             extra={"approval": {"approver": approver, "role": role, "ts": now(),
                                                 "plan_hash": plan_hash, "scope": scope}})

    def reject(self, oid, approver, role, reason) -> dict:
        if role != "approver":
            raise PermissionDenied("only an approver can reject")
        with self._conn() as c:
            cur = self._latest(c, oid)
            self._transition(c, cur, "REJECTED", approver, role, {"reason": reason})
        return self.get(oid)

    def record_sandbox_action(self, oid, idempotency_key: str, actor: str, role: str = "agent") -> dict:
        with self._conn() as c:
            dup = c.execute("SELECT * FROM crm_actions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if dup:
                self._event(c, oid, None, actor, role, "SANDBOX_DUPLICATE_IGNORED", {"idempotency_key": idempotency_key})
                return {"duplicate": True, **dict(dup)}
            cur = self._latest(c, oid)
            appr = cur.get("approval")
            blocked = cur["state"] != "APPROVED" or not appr or appr["plan_hash"] != pilot_hash(cur.get("pilot"))
            if not blocked:
                aid = self._record(c, cur, appr, idempotency_key, actor, role)
        if blocked:  # logged in its own committed transaction, then raised
            self._log(oid, cur["version"], actor, role, "UNAPPROVED_ACTION_BLOCKED",
                      {"state": cur["state"], "idempotency_key": idempotency_key})
            raise PermissionDenied(f"sandbox action blocked: dossier state {cur['state']} has no valid approval")
        return {"duplicate": False, "action_id": aid, "sandbox": 1}

    def _log(self, oid, version, actor, role, event, detail=None):
        with self._conn() as c:
            self._event(c, oid, version, actor, role, event, detail)

    def _record(self, c, cur, appr, idempotency_key, actor, role):
            oid = cur["opportunity_id"]
            aid = f"SBX-{uuid.uuid4().hex[:10]}"
            c.execute("INSERT INTO crm_actions VALUES(?,?,?,?,?,?,?,?,1)",
                      (aid, oid, cur["version"], idempotency_key, appr["plan_hash"], "coupon_pilot_record",
                       json.dumps(cur["pilot"], default=str), now()))
            self._transition(c, cur, "SANDBOX_RECORDED", actor, role, {"action_id": aid, "live_send": False},
                             extra={"crm_action_ids": cur.get("crm_action_ids", []) + [aid]})
            return aid

    def record_outcome(self, oid, outcome: dict, decision: str, actor: str, role="agent") -> dict:
        with self._conn() as c:
            cur = self._latest(c, oid)
            self._transition(c, cur, "EVALUATED", actor, role, {"provenance": outcome.get("provenance")},
                             extra={"outcome": outcome})
            cur = self._latest(c, oid)
            self._transition(c, cur, decision, actor, role, {"decision": decision})
        return self.get(oid)

    def crm_actions(self, oid) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM crm_actions WHERE opportunity_id=?", (oid,)).fetchall()]
