"""Typed tools with JSON schemas, provenance and least-privilege role allowlists.

Every tool returns {"tool", "status": ok|error|blocked, "data", "provenance"}. Money, metrics and state
transitions are computed here in code, never by an LLM. No tool can approve, spend, publish or send:
approval exists only in the human path (DossierStore.approve with role "approver").
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pandas as pd

from mi.config import config_hash, load_config
from mi.decision import metrics as M
from mi.paths import PROCESSED, REPORTS
from mi.workflow.store import DossierStore, PermissionDenied, WorkflowError, pilot_hash

ROLE_ALLOWLIST = {
    "coordinator": {"get_dossier"},
    "research": {"get_dossier", "retrieve_sources", "seo_audit_summary"},
    "intelligence": {"get_dossier", "get_data_audit", "run_model_pipeline", "get_model_run", "segment_profile"},
    "portfolio": {"get_dossier", "compare_plans", "sensitivity_summary", "break_even", "demand_baseline", "calculate_metric"},
    "activation": {"get_dossier", "retrieve_sources", "pilot_sample_size", "pilot_design", "draft_pilot", "request_approval", "record_sandbox_action"},
    "measurement": {"get_dossier", "campaign_history", "pilot_sample_size", "pilot_design", "evaluate_outcome", "record_outcome"},
}


def _ok(tool, data, **prov):
    return {"tool": tool, "status": "ok", "data": data,
            "provenance": {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **prov}}


def _read_json(name):
    p = REPORTS / name
    return json.loads(p.read_text()) if p.exists() else None


class Toolbox:
    def __init__(self, store: DossierStore | None = None):
        self.store = store or DossierStore()
        self.cfg = load_config()
        self._scores = None

    @property
    def scores(self) -> pd.DataFrame:
        if self._scores is None:
            self._scores = pd.read_parquet(PROCESSED / "scores_latest.parquet")
        return self._scores

    # ---------------- schemas (for the LLM path) ----------------
    SCHEMAS = {
        "get_dossier": ("Read the current dossier version.", {"opportunity_id": {"type": "string"}}, ["opportunity_id"]),
        "retrieve_sources": ("Search the dated source corpus; returns span-verified claims or an abstention.", {"query": {"type": "string"}}, ["query"]),
        "seo_audit_summary": ("Summarise the GEO answer log (real answers only).", {}, []),
        "get_data_audit": ("Read the data audit (counts, joins, gaps).", {}, []),
        "run_model_pipeline": ("Run (or reuse) the deterministic train/evaluate pipeline.", {"force": {"type": "boolean"}}, ["force"]),
        "get_model_run": ("Read locked-test metrics of the current model run.", {}, []),
        "segment_profile": ("Segment sizes and mean calibrated propensity for one category.", {"category": {"type": "string"}}, ["category"]),
        "compare_plans": ("Enumerate feasible plans under constraints; returns top-3, heuristic, NONE.", {"uplift_multiplier": {"type": "number"}, "scale": {"type": "number"}}, []),
        "sensitivity_summary": ("Reversal thresholds and break-even table.", {}, []),
        "break_even": ("Break-even uplift for a cohort.", {"category": {"type": "string"}, "segment": {"type": "string"}, "channel": {"type": "string"}}, ["category", "segment", "channel"]),
        "demand_baseline": ("Historical weekly demand baseline for a category.", {"category": {"type": "string"}}, ["category"]),
        "calculate_metric": ("Deterministic metric (cpa, roas, break_even_roas, roi, aov).", {"name": {"type": "string"}, "args": {"type": "object"}}, ["name", "args"]),
        "pilot_sample_size": ("Households per arm to detect an uplift.", {"p0": {"type": "number"}, "dq": {"type": "number"}}, ["p0", "dq"]),
        "pilot_design": ("Learn-first test design: break-even, purchase-proxy vs contribution-based n per arm, MDE table, feasibility and cost.",
                         {"category": {"type": "string"}, "segment": {"type": "string"}, "channel": {"type": "string"}, "uplift_multiple_for_sizing": {"type": "number"}},
                         ["category", "segment", "channel"]),
        "draft_pilot": ("Write a DRAFT pilot (audience, channel, offer, message, budget) to the dossier.", {"opportunity_id": {"type": "string"}, "expected_version": {"type": "integer"}, "pilot": {"type": "object"}}, ["opportunity_id", "expected_version", "pilot"]),
        "request_approval": ("Move the dossier to REVIEW_REQUESTED for a named human approver.", {"opportunity_id": {"type": "string"}, "expected_version": {"type": "integer"}}, ["opportunity_id", "expected_version"]),
        "record_sandbox_action": ("Record an APPROVED pilot in the local CRM sandbox (never sends).", {"opportunity_id": {"type": "string"}, "idempotency_key": {"type": "string"}}, ["opportunity_id", "idempotency_key"]),
        "campaign_history": ("Descriptive history of real campaigns (selection-biased).", {}, []),
        "evaluate_outcome": ("Apply the prewritten decision rule to an outcome record.", {"outcome": {"type": "object"}}, ["outcome"]),
        "record_outcome": ("Attach an outcome + decision to the dossier.", {"opportunity_id": {"type": "string"}, "outcome": {"type": "object"}, "decision": {"type": "string"}}, ["opportunity_id", "outcome", "decision"]),
    }

    def schemas_for(self, role: str) -> list[dict]:
        out = []
        for name in sorted(ROLE_ALLOWLIST[role]):
            desc, props, req = self.SCHEMAS[name]
            out.append({"name": name, "description": desc,
                        "input_schema": {"type": "object", "properties": props, "required": req}})
        return out

    # ---------------- dispatcher ----------------
    def dispatch(self, role: str, name: str, args: dict, opportunity_id: str | None = None) -> dict:
        if name not in ROLE_ALLOWLIST.get(role, set()):
            if opportunity_id:
                with self.store._conn() as c:
                    self.store._event(c, opportunity_id, None, f"{role}_agent", "agent", "TOOL_BLOCKED",
                                      {"tool": name, "reason": "not in role allowlist"})
            return {"tool": name, "status": "blocked", "data": None,
                    "provenance": {"reason": f"role '{role}' is not allowed to call '{name}'"}}
        try:
            return getattr(self, "t_" + name)(**args)
        except (PermissionDenied, WorkflowError) as e:
            if opportunity_id is None:
                pass
            return {"tool": name, "status": "blocked", "data": None, "provenance": {"reason": str(e)}}
        except Exception as e:  # tool errors are returned, not raised, so agents can report them
            return {"tool": name, "status": "error", "data": None, "provenance": {"reason": f"{type(e).__name__}: {e}"}}

    # ---------------- tools ----------------
    def t_get_dossier(self, opportunity_id):
        d = self.store.get(opportunity_id)
        return _ok("get_dossier", d, version=d["version"], payload_hash=d["_payload_hash"][:16])

    def t_retrieve_sources(self, query):
        from mi.evidence.rag import answer
        r = answer(query)
        if r.get("conflicts"):
            # a contradicted value can never be promoted to a claim by any role (deterministic or LLM)
            r = {**r, "conflicting_spans": r.get("supported_claims", []), "supported_claims": []}
            return _ok("retrieve_sources", r, method=r["method"], status="CONFLICT: sources disagree; not usable as a fact")
        return _ok("retrieve_sources", r, method=r["method"], status="OBSERVED source spans" if not r["abstained"] else "ABSTAINED")

    def t_seo_audit_summary(self):
        from mi.seo.geo import analyze, load_panel, read_log
        r = analyze(read_log(), load_panel())
        return _ok("seo_audit_summary", r, status=r["status"])

    def t_get_data_audit(self):
        a = _read_json("data_audit.json")
        if a is None:
            raise WorkflowError("run python -m mi.ingest.audit first")
        keep = {k: a[k] for k in ("transactions", "joins", "campaigns", "missing_for_business_case")}
        return _ok("get_data_audit", keep, status="OBSERVED", manifest_commit=a.get("manifest", {}).get("commit"))

    def t_run_model_pipeline(self, force=False):
        rep = _read_json("model_report.json")
        if rep and not force:
            return _ok("run_model_pipeline", {"run_id": rep["run_id"], "reused": True}, run_id=rep["run_id"])
        from mi.model.train import run
        rep = run()
        return _ok("run_model_pipeline", {"run_id": rep["run_id"], "reused": False}, run_id=rep["run_id"])

    def t_get_model_run(self):
        r = _read_json("model_report.json")
        sel = "model_" + r["selected_model"]
        data = {"run_id": r["run_id"], "target": r["target"], "selected_model": r["selected_model"],
                "test": {k: {m: round(v, 4) for m, v in r["test"][k].items() if isinstance(v, float)} for k in (sel, "rule_repeat", "rule_popularity")},
                "bootstrap_model_minus_rule": r["bootstrap_model_minus_rule_repeat"], "decision_score_used": r["decision_score_used"],
                "failure_case": r["failure_case"], "status": r["status"]}
        return _ok("get_model_run", data, run_id=r["run_id"], status="OBSERVED backtest")

    def t_segment_profile(self, category):
        s = self.scores[self.scores.product_category == category]
        if s.empty:
            raise WorkflowError(f"unknown category {category}")
        g = s.groupby("segment").agg(panel_households=("household_id", "size"), mean_q0=("p_used", "mean"),
                                    median_q0=("p_used", "median")).round(4).reset_index().to_dict("records")
        return _ok("segment_profile", {"category": category, "segments": g}, status="MODEL ESTIMATE (q0) on OBSERVED segments",
                   as_of_week=self.cfg["temporal"]["scoring_cutoff"])

    def t_compare_plans(self, uplift_multiplier=None, scale=None):
        from mi.decision.optimizer import compact, load_inputs, optimise
        o = {}
        if uplift_multiplier is not None:
            o["uplift_multiplier"] = float(uplift_multiplier)
        if scale is not None:
            o["scale"] = float(scale)
        scores, econ, rep = load_inputs()
        r = compact(optimise(scores, econ, self.cfg, o or None))
        slim = {"recommended_base": r["recommended_base"], "recommended_robust": r["recommended_robust"],
                "n_feasible": r["n_portfolios_feasible"], "overrides": o,
                "top3": [{"plan_id": p["plan_id"], "net_low": p["low"]["net"], "net_base": p["base"]["net"],
                          "net_high": p["high"]["net"], "cost_base": p["base"]["cost"]} for p in r["top3"]],
                "heuristic": {"plan_id": r["heuristic"]["plan_id"], "net_base": r["heuristic"]["base"]["net"],
                              "cost_base": r["heuristic"]["base"]["cost"]}}
        return _ok("compare_plans", slim, status="SIMULATION", config_hash=r["config_hash"], model_run_id=rep["run_id"])

    def t_sensitivity_summary(self):
        s = _read_json("sensitivity.json")
        if s is None:
            raise WorkflowError("run python -m mi.decision.report first")
        return _ok("sensitivity_summary", {"reversal_grid": s["reversal_grid"], "break_even_top5": s["break_even"][:5],
                                           "break_even_with_fixed_top": [x for x in s["break_even_with_fixed"] if x["uplift_multiple_needed"]][:6]},
                   status="SIMULATION")

    def t_break_even(self, category, segment, channel):
        s = _read_json("sensitivity.json")
        rows = [r for r in s["break_even"] if r["category"] == category and r["segment"] == segment and r["channel"] == channel]
        if not rows:
            raise WorkflowError("cohort not found")
        return _ok("break_even", rows[0], status="SIMULATION (ASSUMED margin/redemption/contact; OBSERVED spend/face; MODEL q0)")

    def t_demand_baseline(self, category):
        s = _read_json("sensitivity.json")
        rows = [d for d in s["demand"] if d["category"] == category]
        if not rows:
            raise WorkflowError("unknown category")
        return _ok("demand_baseline", rows[0], status="OBSERVED history; trailing baseline")

    def t_calculate_metric(self, name, args):
        fn = {"cpa": M.cpa, "roas": M.roas, "break_even_roas": M.break_even_roas, "roi": M.roi, "aov": M.aov, "cac": M.cac}[name]
        v = fn(**args)
        return _ok("calculate_metric", {"name": name, "value": None if isinstance(v, M.Undefined) else v,
                                        "undefined_reason": v.reason if isinstance(v, M.Undefined) else None})

    def t_pilot_sample_size(self, p0, dq):
        from mi.outcome.learning import sample_size
        return _ok("pilot_sample_size", {"p0": p0, "dq": dq, "n_per_arm": sample_size(float(p0), float(dq)),
                                         "alpha": 0.05, "power": 0.8})

    def t_pilot_design(self, category, segment, channel, uplift_multiple_for_sizing=2.0):
        from mi.decision.scenario import assumptions_from_config
        from mi.outcome.learning import pilot_design
        a = assumptions_from_config(self.cfg, "base")
        rep = _read_json("model_report.json")
        e = rep["economics_inputs_observed"]
        st = e["test_window_category_segment_stats"][f"{category}|{segment}"]
        q0 = float(self.scores[(self.scores.product_category == category) & (self.scores.segment == segment)].p_used.mean())
        g, F = e["mean_4w_category_spend_among_buyers_test"][category] * a.margin_rate, e["mean_coupon_disc_per_couponed_line"][category]
        sigma = a.margin_rate * st["spend_sd"]
        d = pilot_design(q0, g, F, a.contact_cost[channel], a.redemption_share, sigma, a.dq(segment))
        key = str(float(uplift_multiple_for_sizing))
        n = d["n_contribution"][key]["n_per_arm"] if key in d["n_contribution"] else d["n_purchase_proxy"]
        panel = int(((self.scores.product_category == category) & (self.scores.segment == segment)).sum())
        s = self.cfg["scenario"]
        assumed_reach = panel * a.reach_share[channel] * s["deployment_scale"]["value"]
        d.update({
            "inputs": {"q0_mean": round(q0, 4), "q0_status": "MODEL ESTIMATE (historical conditions, NOT a no-coupon counterfactual)",
                       "contribution_sd_per_hh": round(sigma, 4), "sd_status": "OBSERVED spend SD (test window) x ASSUMED margin",
                       "g": round(g, 4), "face": F, "contact": a.contact_cost[channel], "redemption": a.redemption_share},
            "sizing_choice": {"uplift_multiple_for_sizing": float(uplift_multiple_for_sizing), "n_per_arm": n,
                              "status": "ASSUMPTION — sized for a true uplift of this multiple of break-even"},
            "feasibility": {"eligible_consented_households_needed": 2 * n, "panel_households_in_segment": panel,
                            "panel_contactable": False,
                            "assumed_company_reachable": round(assumed_reach),
                            "assumed_company_reachable_status": "COMPANY SCALE ASSUMED; not measured",
                            "feasible_under_assumed_scale": assumed_reach >= 2 * n},
            "test_cost": {"n_treated": n, "variable": round(n * d["per_treated_household_cost"], 2), "fixed_setup": a.fixed_setup,
                          "total": round(n * d["per_treated_household_cost"] + a.fixed_setup, 2), "currency": self.cfg["currency"],
                          "status": "ASSUMED (contact, redemption, fixed, uplift); OBSERVED face value"}})
        from mi.outcome.learning import decision_value
        be = d["break_even_uplift"]
        dv = decision_value(q0, g, F, a.contact_cost[channel], a.redemption_share, n, assumed_reach, a.fixed_setup,
                            {"assumed": a.dq(segment), "sizing (x break-even)": float(uplift_multiple_for_sizing) * be,
                             "3x break-even": 3 * be})
        dv.update({"plan": f"{category}|{segment}|{channel}", "status": "SIMULATION; COMPANY SCALE ASSUMED; same plan as the test"})
        d["decision_value"] = dv
        d["candidate_choice"] = self._candidate_choice(category, segment, channel)
        return _ok("pilot_design", d, status="DESIGN under labelled assumptions; FUTURE EXPERIMENT")

    @staticmethod
    def _candidate_choice(category, segment, channel) -> dict | None:
        """Why test this cohort rather than the best base plan: rank by the uplift multiple needed to break even."""
        sens, port = _read_json("sensitivity.json"), _read_json("portfolio.json")
        if not sens or not port:
            return None
        key = lambda r: (r["category"], r["segment"], r["channel"])  # noqa: E731
        hh = {key(r): r["ratio_needed_to_assumed"] for r in sens["break_even"]}
        scale = load_config()["scenario"]["deployment_scale"]["value"]
        fx = {key(r): r["uplift_multiple_needed"] for r in sens["break_even_with_fixed"] if r.get("scale") == scale}
        best = port["top3"][0]["base"]["components"][0]
        bk = (best["category"], best["segment"], best["channel"])
        me = (category, segment, channel)
        nan = float("nan")
        return {"best_base_plan": "|".join(bk), "best_base_per_1000": round(best["net_per_1000_contacted_before_fixed"], 1),
                "candidate": "|".join(me),
                "uplift_multiple_to_break_even_per_hh": {"candidate": round(hh.get(me, nan), 2), "best_base": round(hh.get(bk, nan), 2)},
                "uplift_multiple_to_break_even_after_setup": {"candidate": round(fx.get(me, nan), 2), "best_base": round(fx.get(bk, nan), 2)},
                "candidate_rank_closest_to_break_even": (sorted(hh, key=hh.get).index(me) + 1) if me in hh else None,
                "reason": "Both lose at base; the test goes where the smallest change in true uplift would flip the decision.",
                "status": "SIMULATION (ASSUMED uplift, margin, redemption, contact, scale)"}

    def t_draft_pilot(self, opportunity_id, expected_version, pilot):
        required = {"plan_id", "audience", "channel", "offer", "message", "design"}
        missing = required - set(pilot)
        if missing:
            raise WorkflowError(f"pilot missing {sorted(missing)}")
        msg = pilot["message"].lower()
        if not any(k in msg for k in ("unsubscribe", "opt out", "reply stop")):
            raise WorkflowError("guardrail: customer message must include an opt-out instruction")
        if any(k in msg for k in ("guaranteed", "best price", "lowest price", "cheapest")):
            raise WorkflowError("guardrail: unverifiable price/superlative claim in message")
        pilot = {**pilot, "budget": self._pilot_budget(pilot)}
        d = self.store.update(opportunity_id, expected_version, {"pilot": {**pilot, "status": "DRAFT — not sent"}},
                              actor="activation_agent", role="agent", note="pilot drafted")
        return _ok("draft_pilot", {"version": d["version"], "plan_hash": pilot_hash(d["pilot"])})

    def _pilot_budget(self, pilot) -> dict:
        """Deterministic budget for the TREATED arm of a learn-first test (SIMULATION inputs labelled)."""
        from mi.decision.scenario import assumptions_from_config, coupon_cost
        a = assumptions_from_config(self.cfg, "base")
        rep = _read_json("model_report.json")["economics_inputs_observed"]
        cat, seg, ch = pilot["audience"]["category"], pilot["audience"]["segment"], pilot["channel"]
        face = rep["mean_coupon_disc_per_couponed_line"][cat]
        q0 = float(self.scores[(self.scores.product_category == cat) & (self.scores.segment == seg)].p_used.mean())
        n_t = int(pilot["design"]["n_per_arm"])
        per_hh = a.contact_cost[ch] + float(coupon_cost(q0, a.dq(seg), face, a.redemption_share))
        variable = n_t * per_hh
        total = round(variable + a.fixed_setup, 2)
        cap = self.cfg["scenario"]["budget_cap"]["value"]
        if total > cap:
            raise WorkflowError(f"pilot budget {total} exceeds cap {cap}")
        return {"currency": self.cfg["currency"], "treated_households": n_t, "per_household_expected_cost": round(per_hh, 4),
                "variable": round(variable, 2), "fixed_setup": a.fixed_setup, "total": total, "cap": cap,
                "status": "SIMULATION (ASSUMED contact/redemption/fixed; OBSERVED face value; MODEL q0)"}

    def t_request_approval(self, opportunity_id, expected_version):
        d = self.store.request_review(opportunity_id, expected_version, actor="activation_agent")
        return _ok("request_approval", {"state": d["state"], "version": d["version"], "plan_hash": pilot_hash(d["pilot"]),
                                        "human_task": "A named approver must review audience, offer, message and budget."})

    def t_record_sandbox_action(self, opportunity_id, idempotency_key):
        r = self.store.record_sandbox_action(opportunity_id, idempotency_key, actor="activation_agent")
        return _ok("record_sandbox_action", r, live_send=False)

    def t_campaign_history(self):
        from mi.outcome.learning import campaign_history
        h = campaign_history()
        return _ok("campaign_history", {"by_type": h["by_type"], "status": h["status"], "reading": h["reading"]}, status="OBSERVED descriptive")

    def t_evaluate_outcome(self, outcome):
        from mi.outcome.learning import decide
        return _ok("evaluate_outcome", decide(outcome, self.cfg), provenance_of_outcome=outcome.get("provenance"))

    def t_record_outcome(self, opportunity_id, outcome, decision):
        d = self.store.record_outcome(opportunity_id, outcome, decision, actor="measurement_agent")
        return _ok("record_outcome", {"state": d["state"], "version": d["version"]})


def stable_key(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:20]
