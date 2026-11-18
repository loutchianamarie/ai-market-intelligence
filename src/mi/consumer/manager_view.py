"""Logic behind the two-view manager screen (app/manager_home.py). No Streamlit here, so every rule is testable.

  options_table(view)       the alternatives, with extra buyers per 1,000 CONTACTED and per 1,000 ELIGIBLE, tag and condition
  run_advisor(case, inputs) run the real deterministic specialists on a throwaway store (nothing saved, nothing sent)
  measurement_plan(...)     eligible / consented / contacted / holdout / buyers, each UNKNOWN or PENDING until it exists
  STRIP                     the six workflow stages and whether each is done for the run
"""
from __future__ import annotations

import os
import tempfile
import time

from mi.campaign.contract import MENS, WOMENS
from mi.consumer import gate as G
from mi.consumer.adapter import CaseResult
from mi.consumer.advisor import CampaignRun
from mi.consumer.viewmodel import ci, n
from mi.workflow.store import DossierStore, WorkQueue, pilot_hash

DECISION_HEADLINE = {
    "REJECTED_MODEL_EXCLUSION": "Rejected: the model may not be used to exclude customers",
    "NO_EMAIL": "Do not send: cost is above break-even at this margin",
    "HOLD_FOR_INPUTS": "Hold: draft ready, launch blocked until inputs are supplied",
    "PILOT_ONLY": "Randomized pilot only: the experiment's interval includes a loss",
    "READY_FOR_HUMAN_APPROVAL": "Ready for a named human to approve",
}
STRIP_LABELS = ["Evidence checked", "Model interpreted", "Options compared", "Draft prepared", "Checker passed", "Human review"]


def options_table(v: dict) -> list[dict]:
    """Alternatives for the Mens/Womens e-mail case. Every 'per 1,000 contacted' is copied from the export; 'per 1,000 eligible' is our
    arithmetic (contacted value x share of eligible customers contacted) and is labelled as such."""
    share = v["verdict"].get("share", 0.25)
    rows = []
    arm = {a["arm"]: a for a in v["arms"]}
    for name, label in ((MENS, "Mens e-mail to all"), (WOMENS, "Womens e-mail to all")):
        a = arm[name]
        val = float(a["per1000"])
        lo, hi = (float(t) for t in a["per1000_ci"].replace(" to ", "|").split("|"))
        rows.append({"option": label, "tag": "RANDOMIZED OBSERVATION", "contacted_share": 1.0, "per1000_contacted": val, "low": lo, "high": hi,
                     "per1000_eligible": val, "condition": "cost, consent, holdout, approval"})
    pol = {p["policy_id"]: p for p in v["policies"]}
    for pid, label, cond in (("MODEL_MENS_25", "Model-targeted top 25%", "not stable; excludes no one"),
                             ("RULE_HISTORY_MENS_25", "Past-spend rule top 25%", "fallback under a cap"),
                             ("RULE_RECENCY_MENS_25", "Recency rule top 25%", "fallback under a cap"),
                             ("RANDOM_MENS_25", "Random 25%", "the benchmark")):
        p = pol[pid]
        rows.append({"option": label, "tag": "HELD-OUT MODEL ESTIMATE" if pid == "MODEL_MENS_25" else "HELD-OUT ESTIMATE", "contacted_share": share,
                     "per1000_contacted": p["value"], "low": p["low"], "high": p["high"], "per1000_eligible": p["value"] * share, "condition": cond})
    rows.append({"option": "No e-mail", "tag": "RANDOMIZED OBSERVATION", "contacted_share": 0.0, "per1000_contacted": 0.0, "low": 0.0, "high": 0.0,
                 "per1000_eligible": 0.0, "condition": "default if a gate fails"})
    return rows


def run_advisor(case: CaseResult, commercial: dict | None) -> dict:
    """Run the real specialists (analyst -> research -> strategist -> checker) for these inputs on a throwaway SQLite store.
    Not a replay: the plan, the work items, the checker verdict and the gate are recomputed from the export and the inputs."""
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        store = DossierStore(os.path.join(tmp, "advisor_run.sqlite"))
        run = CampaignRun(case, store, persist=False, commercial=commercial)
        out = run.run_to_checkpoint()
        if out.get("status") != "OK":
            return {"ok": False, "reason": out}
        d = store.get(out["opportunity_id"])
        items = [{"item_id": w["item_id"], "status": w["status"], "kind": w["payload"]["kind"], "title": w["payload"]["title"], "owner": w["payload"]["owner"],
                  "budget_usd": w["payload"]["budget_usd"], "due_date": w["payload"]["due_date"]} for w in WorkQueue(store).list(out["opportunity_id"])]
        g = run.gate or G.evaluate(case, None)
    return {"ok": True, "gate": g, "state": d["state"], "pilot": d.get("pilot"), "plan_hash": pilot_hash(d["pilot"]) if d.get("pilot") else None,
            "checker": d.get("checker_verdict") or {}, "steps": [{"role": s["role"], "transition": s["transition"], "ms": s["runtime_ms"],
                                                                "tools": [f"{c['tool']}:{c['status']}" for c in s["tool_calls"]]} for s in d["agent_trace"]],
            "work_items": items, "mode": out["mode"], "runtime_ms": round((time.perf_counter() - t0) * 1000), "export_sha256": case.sha256}


def strip_state(result: dict, fresh_ok: bool) -> list[tuple[str, bool]]:
    """Which of the six stages are done for this run. 'Human review' is never done by the system: it is the stop."""
    if not result.get("ok"):
        return [(s, False) for s in STRIP_LABELS]
    roles = {s["role"] for s in result["steps"]}
    ck = (result["checker"] or {}).get("verdict", "")
    return [("Evidence checked", fresh_ok and "analyst" in roles), ("Model interpreted", "analyst" in roles), ("Options compared", "research" in roles or "analyst" in roles),
            ("Draft prepared", result.get("pilot") is not None or result["gate"]["decision"] == "NO_EMAIL"),
            ("Checker passed", ck.startswith("PASS")), ("Human review", False)]


def measurement_plan(result: dict, export_doc: dict) -> list[dict]:
    """Counts a manager must have to read the result, and their honest status today. Nothing here is an outcome."""
    g = result["gate"]
    contacts = g["contacts"]
    hold = export_doc["recommendation"]["holdout_plan"]
    cons = "verified as entered by the manager (not independently checked)" if g["inputs"]["consent_verified"] else "UNKNOWN until CRM and legal verify"
    return [
        {"measure": "Eligible customers", "status": "UNKNOWN: CRM counts; the experiment's 64,000 is 2008"},
        {"measure": "Consented customers", "status": cons},
        {"measure": "Contacted and holdout", "status": f"SCENARIO: {contacts:,} contacted; holdout at least {hold['customers_per_arm_needed']:,}"},
        {"measure": "Distinct buyers in 14 days", "status": "PENDING: no e-mail has been sent"},
        {"measure": "Additional buyers per 1,000 vs holdout", "status": "PENDING: needs the read-out; 95% interval above zero"},
        {"measure": "Unsubscribes and complaints", "status": "PENDING: guardrail"},
    ]


def money_line(g: dict) -> str:
    sc, be = g["scenario"], g["break_even_cost"]
    if not sc:
        return "UNKNOWN: margin and cost per e-mail have not been provided, so no contribution is shown."
    return (f"SCENARIO, NOT PROFIT: break-even {n(be['point'], 3)} USD per e-mail (low end {n(be['conservative'], 3)}); contribution {sc['contribution']:,.0f} USD "
            f"(range {sc['low']:,.0f} to {sc['high']:,.0f}) on {g['contacts']:,} contacts.")
