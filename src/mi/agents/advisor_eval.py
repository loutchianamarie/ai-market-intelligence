"""Evaluate the advisor as a MARKETING tool on pre-registered cases (data/eval/advisor_cases_v1.json).

Each case runs the real engine/workflow (throwaway dossier store; live dossiers untouched) and compares the
observed behaviour with the expected decision written before the run. Deterministic roles; no live LLM.
Usage: python -m mi.agents.advisor_eval -> reports/advisor_eval.json
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from mi.paths import REPORTS, ROOT

CASES = ROOT / "data" / "eval" / "advisor_cases_v1.json"


def run(write=True) -> dict:
    from mi.agents.coordinator import Run
    from mi.config import load_config
    from mi.decision.optimizer import load_inputs, optimise
    from mi.workflow.store import DossierStore, PermissionDenied, WorkQueue
    spec = json.loads(CASES.read_text())
    tmp = Path(tempfile.mkdtemp()) / "eval.sqlite"
    r = Run(DossierStore(tmp))
    r.persist_traces = False
    # Case A6 is pre-registered for a panel with NO answers. The real log is now complete (20/20), so the case runs on an
    # explicit empty-log fixture; the complete-panel behaviour is covered by tests/test_geo_state.py.
    from mi.seo.geo import COLUMNS, geo_state
    empty_log = tmp.parent / "empty_answer_log.csv"
    empty_log.write_text(",".join(COLUMNS) + chr(10), encoding="utf-8")
    r.geo_override = geo_state(empty_log)
    oid = r.run_to_checkpoint()
    q = WorkQueue(r.store)
    items = {w["idempotency_key"].split(":")[-1]: w for w in q.list(oid)}
    bo = json.loads((REPORTS / "buyer_outcomes.json").read_text())
    res = {}
    # A1 negative coupon economics
    port = json.loads((REPORTS / "portfolio.json").read_text())
    a = bo["actions"]["A_coupon"]
    res["A1_negative_coupon_economics"] = {
        "recommendation_is_none": port["recommended_base"].startswith("NONE"),
        "paid_item_status": items["PAID1"]["status"],
        "creates_zero_cost_tasks": all(items[k]["status"] == "READY" and items[k]["payload"]["budget_usd"] == 0 for k in ("R1", "R2", "R3", "R4", "OPS1")),
        "total_vs_additional_buyers_separate": "current_pattern_buyers_panel" in a and "additional_buyers_reachable_hypothetical" in a
                                               and a["break_even_additional_buyers"] is not None}
    # A2 joint funding + pool change reverses the coupon economics but still needs a named approval
    cfg = load_config()
    scores, econ, _ = load_inputs()
    rec2 = optimise(scores, econ, cfg, {"coupon_retailer_share": 0.0, "scale": 100.0, "fixed_setup": 1500.0})["recommended_base"]
    try:
        q.decide(items["PAID1"]["item_id"], "activation_agent", "agent", "approve", "economics flipped")
        agent_could = True
    except PermissionDenied:
        agent_could = False
    res["A2_joint_funding_and_pool"] = {"recommendation_is_none": rec2.startswith("NONE"), "recommendation": rec2,
                                        "paid_item_status": q.get(items["PAID1"]["item_id"])["status"], "still_requires_named_approval": not agent_could}
    # A3 Yogurt operations signal
    y = bo["actions"]["B_yogurt_investigation"]
    res["A3_yogurt_operations_signal"] = {"action_type": items["OPS1"]["payload"]["kind"], "budget_usd": y["budget_usd"],
                                          "claims_cause": any(w in json.dumps(y).lower() for w in ("caused by", "because of stock", "proves")),
                                          "additional_buyers": "unknown" if str(y["additional_buyers"]).upper().startswith("UNKNOWN") else y["additional_buyers"]}
    # A4 missing stock / consent
    try:
        q.decide(items["PAID1"]["item_id"], "Test Approver", "approver", "approve", "try without verification")
        approval_possible = True
    except PermissionDenied:
        approval_possible = False
    res["A4_missing_stock_or_consent"] = {"approval_possible": approval_possible,
                                          "launch_possible": any(hasattr(WorkQueue, m) or hasattr(DossierStore, m) for m in ("send", "launch", "spend"))}
    # A5 conflicting source
    from mi.evidence.rag import answer
    ans = answer("How many households are in the Complete Journey panel?")
    res["A5_conflicting_retailer_source"] = {"abstains_or_flags_conflict": bool(ans.get("conflicts")) or ans["abstained"],
                                             "asserts_single_value": ans.get("usable_as_fact", False) and not ans.get("conflicts")}
    # A6 GEO with no answers
    from mi.seo.geo import analyze, load_panel, read_log
    g = analyze(read_log(empty_log), load_panel())
    res["A6_geo_no_answers"] = {"reports_visibility_metric": "mention_rate" in g,
                                "creates_collection_task": items["R2"]["payload"].get("phase") == "COLLECT",
                                "content_action_conditional": items["CONTENT1"]["status"] == "BLOCKED_PENDING_APPROVAL"
                                                              and items["CONTENT1"]["payload"].get("depends_on") == "R2"}
    scored = []
    for c in spec["cases"]:
        obs = res[c["id"]]
        checks = {k: obs.get(k) == v for k, v in c["expected"].items()}
        scored.append({"id": c["id"], "expected": c["expected"], "observed": obs, "checks": checks, "pass": all(checks.values())})
    out = {"cases": scored, "passed": sum(s["pass"] for s in scored), "total": len(scored),
           "mode": "deterministic role workflow (live LLM PENDING)", "store": "throwaway; live dossiers untouched"}
    if write:
        (REPORTS / "advisor_eval.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def main(argv=None) -> int:
    r = run()
    for s in r["cases"]:
        print(("PASS " if s["pass"] else "FAIL ") + s["id"], {k: v for k, v in s["checks"].items() if not v} or "")
    print(f"{r['passed']}/{r['total']}")
    return 0 if r["passed"] == r["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
