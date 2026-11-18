"""Display-ready view of the GROCERY case for the manager home (app/manager_home.py). Read-only: it formats saved reports, recomputes nothing,
and never touches the e-mail case. Every figure is copied from reports/model_report.json, portfolio.json, buyer_outcomes.json, opportunities.json
and (when the local store has it) the latest grocery dossier.

Tags: OBSERVED (counted), TRAINED MODEL ESTIMATE, SCENARIO (assumed inputs, never profit), UNKNOWN.
"""
from __future__ import annotations

import json
from pathlib import Path

from mi.paths import REPORTS

RULE_NOTE = "purchase propensity, not coupon response"


def _j(name: str, reports: Path = REPORTS):
    p = reports / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def short_plan(plan_id: str) -> str:
    """COFFEE/LAPSING/digital_coupon/ALL -> Coffee, lapsing, digital coupon;  NONE: ... -> No action"""
    if plan_id.upper().startswith("NONE"):
        return "No action (research first)"
    parts = plan_id.replace("|", "/").split("/")
    cat, seg, ch = parts[0].title(), parts[1].lower().replace("_", " "), parts[2].replace("_", " ")
    return f"{cat}, {seg}, {ch}"


def grocery_view(reports: Path = REPORTS) -> dict | None:
    """None if the saved reports are missing. Otherwise everything the grocery screens show."""
    model, port, outc, opp = _j("model_report.json", reports), _j("portfolio.json", reports), _j("buyer_outcomes.json", reports), _j("opportunities.json", reports)
    if not (model and port and outc):
        return None
    sel = "model_" + model["selected_model"]
    ap, rule, pop = model["test"][sel]["AP"], model["test"]["rule_repeat"]["AP"], model["test"]["rule_popularity"]["AP"]
    gain_ci = model["bootstrap_model_minus_rule_repeat"]["AP_diff_95ci"]
    ranked = port["ranked_actions"]
    plans = [{"plan": short_plan(r["plan_id"]), "net_base": r["net_base"], "net_low": r["net_low"], "net_high": r["net_high"], "is_none": r["plan_id"].upper().startswith("NONE")}
             for r in ranked[:6]]
    best = next(r for r in ranked if not r["plan_id"].upper().startswith("NONE"))
    a = outc["actions"]["A_coupon"]
    scen = a["additional_buyers_reachable_hypothetical"]
    cur = a["current_pattern_buyers_panel"]
    yogurt = next((f for f in (opp or {}).get("category_facts", []) if f["category"] == "YOGURT"), None)
    return {
        "model": {"ap": ap, "rule": rule, "popularity": pop, "gain": ap - rule, "gain_ci": gain_ci, "note": RULE_NOTE, "run_id": model["run_id"]},
        "decision": {"recommended_base": port["recommended_base"], "n_candidates": port["n_candidates"], "n_portfolios": port["n_portfolios_feasible"],
                     "best_plan": short_plan(best["plan_id"]), "best_net": best["net_base"], "status": port["status"]},
        "plans": plans,
        "popularity_mailing_net": port["heuristic"]["base"]["net"],
        "buyers": {"panel_households": a["eligible"]["panel_households"], "expected": cur["expected_buyers"], "expected_ci": cur["poisson_binomial_95"],
                   "scenario_low": scen["low"], "scenario_base": scen["base"], "scenario_high": scen["high"], "break_even": a["break_even_additional_buyers"],
                   "reachable_hypothetical": a["eligible"]["reachable_hypothetical"], "scale_note": a["eligible"]["status"]},
        "yogurt": ({"h1": yogurt["buyers_H1"], "h2": yogurt["buyers_H2"], "change": yogurt["buyer_change_H2_vs_H1"]} if yogurt else None),
    }


def latest_grocery_dossier():
    """(store, oid, dossier) of the newest drafted grocery dossier from the LOCAL store, or None (the store is not in git)."""
    try:
        from mi.decision.demo_backup import latest_dossier_id
        from mi.workflow.store import DB_PATH, DossierStore
        if not Path(DB_PATH).exists():
            return None
        store = DossierStore()
        oid = latest_dossier_id(store)
        return (store, oid, store.get(oid)) if oid else None
    except Exception:
        return None


def work_queue(store, oid) -> list[dict]:
    from mi.workflow.store import WorkQueue
    out = []
    for w in WorkQueue(store).list(oid):
        p = w["payload"]
        out.append({"item_id": w["item_id"], "status": w["status"], "title": p["title"], "owner": str(p["owner"]), "budget_usd": p["budget_usd"], "kind": p["kind"]})
    return out
