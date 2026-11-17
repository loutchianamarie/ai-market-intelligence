"""Display-ready view of the campaign case. ONE place formats numbers, so the app, the offline HTML backup, the
decision brief and the five-slide deck show identical figures. Values are copied from the validated export
(never recomputed); formatting only rounds for display.

  python -m mi.consumer.viewmodel brief     write docs/marketing_decision_brief.md  (from export + latest trace)
  python -m mi.consumer.viewmodel backup    write reports/buyer_decision_backup.html (no network, no JS needed)
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from mi.consumer.adapter import CaseResult, load_case
from mi.paths import DOCS, REPORTS

TAG_KEY = "OBSERVED = measured in the randomized experiment | ESTIMATE = held-out model/policy estimate | ASSUMPTION = illustrative input | PENDING/UNKNOWN = not provided"
SHORT_TAG = {"OBSERVED": "OBSERVED", "HELD_OUT_ESTIMATE": "ESTIMATE", "ASSUMPTION": "ASSUMPTION", "UNKNOWN": "UNKNOWN",
             "PUBLISHED_REFERENCE": "PUBLISHED REF"}
POLICY_LABEL = {"RANDOM_MENS_25": "Random 25%", "RULE_RECENCY_MENS_25": "Recency rule 25%", "RULE_HISTORY_MENS_25": "Past-spend rule 25%",
                "MODEL_MENS_25": "Model 25%", "SEND_ALL_MENS_100": "Send to all (held-out)"}


def n(v, d=1):
    return "unknown" if v is None else f"{v:,.{d}f}"


def ci(c, d=1):
    return "" if not c else f"{c[0]:,.{d}f} to {c[1]:,.{d}f}"


def _counts(p) -> str:
    return f"{p['treated_buyers']}/{p['treated_n']:,} e-mailed vs {p['control_buyers']}/{p['control_n']:,} not"


def what_if(spend: float, spend_ci: list[float], margin: float, cost_per_email: float, contacts: int, setup: float = 0.0) -> dict:
    """Interactive scenario arithmetic for a reader-chosen margin/cost. NOT measured profit.

    spend / spend_ci come from the randomized experiment (OBSERVED incremental spend per customer e-mailed);
    margin, cost, contacts and setup are the reader's ASSUMPTIONS. Contribution = contacts * (spend*margin - cost) - setup.
    The range uses the experiment's 95% interval for spend only (assumptions are taken as given)."""
    if not 0 <= margin <= 1 or cost_per_email < 0 or contacts < 0 or setup < 0:
        raise ValueError("margin must be in [0,1]; cost, contacts and setup must be >= 0")
    f = lambda sp: contacts * (sp * margin - cost_per_email) - setup
    lo, hi = f(spend_ci[0]), f(spend_ci[1])
    be = (spend * margin) if margin else 0.0
    verdict = "PAYS_EVEN_AT_LOW_END" if lo > 0 else ("DOES_NOT_PAY_EVEN_AT_HIGH_END" if hi <= 0 else "UNCERTAIN_INTERVAL_INCLUDES_ZERO")
    return {"contribution": f(spend), "low": lo, "high": hi, "break_even_cost_per_email": be, "verdict": verdict,
            "kind": "SCENARIO, NOT MEASURED PROFIT"}


def build(case: CaseResult, trace: dict | None = None, blocked: dict | None = None) -> dict:
    """Return the view model. Raises if the case is not a validated COMPUTED_EXPORT (caller shows DATA_PENDING instead)."""
    if not case.ok:
        raise ValueError(f"case not displayable: {case.status} {case.reasons}")
    d, cl = case.doc, case.claims()
    arms = []
    eff = {e["treatment_arm"]: e for e in d["average_effects"]}
    for a in d["observed_arm_metrics"]:
        e = eff.get(a["arm"])
        arms.append({"arm": a["arm"], "role": a["role"], "buyers": a["buyers"], "customers": a["n_customers"],
                     "rate_pct": a["purchase_rate"]["value"] * 100,
                     "per1000": n(e["additional_buyers_per_1000"]["value"]) if e else "reference",
                     "per1000_ci": ci(e["additional_buyers_per_1000"]["ci95"]) if e else "",
                     "spend": n(e["incremental_spend_per_contact"]["value"], 2) if e else "reference",
                     "spend_ci": ci(e["incremental_spend_per_contact"]["ci95"], 2) if e else "",
                     "spend_num": e["incremental_spend_per_contact"]["value"] if e else None,
                     "spend_ci_num": e["incremental_spend_per_contact"]["ci95"] if e else None})
    pol = {p["policy_id"]: p for p in d["held_out_policy_metrics"]}
    policies = []
    for pid, lab in POLICY_LABEL.items():
        p = pol[pid]
        v = p["additional_buyers_per_1000_contacts"]
        policies.append({"policy_id": pid, "label": lab, "value": v["value"], "low": v["ci95"][0], "high": v["ci95"][1], "tag": v["tag"],
                         "counts": _counts(p), "primary": bool(p.get("is_primary"))})
    mvb = d["model_vs_baselines"]
    rec = d["recommendation"]
    scen = [{"label": s["label"], "margin": s["assumed_margin"]["value"], "cost": s["cost_per_contact"]["value"],
             "setup": s["fixed_setup_cost"]["value"], "contribution": s["contribution"]["value"],
             "range": ci(s["contribution"].get("ci95"), 0), "tag": s["contribution"]["tag"], "kind": "SCENARIO, NOT MEASURED PROFIT"}
            for s in d["business_scenarios"] if s["arm"] == "Mens E-Mail"]
    thr = [{"label": t["label"], "margin": t["assumed_margin"]["value"], "point": t["break_even_cost_per_contact"]["value"],
            "conservative": t["break_even_cost_per_contact_conservative"]["value"]} for t in d["economic_thresholds"] if t["arm"] == "Mens E-Mail"]
    hi = d["buyer_impact_per_1000"]
    v = {
        "label": case.label, "sha256": case.sha256, "run_id": d["run_id"], "model_version": d["model_version"], "case_id": d["case_id"],
        "contract_version": d["contract_version"], "generated_at": d["generated_at"],
        "objective": d["marketing"]["research_question"], "audience": d["marketing"]["audience"], "unit": d["unit"],
        "period": d["dataset_provenance"].get("period", "two weeks after the e-mail"), "tag_key": TAG_KEY,
        "headline": {"value": hi["value"], "low": d["buyer_impact_interval_per_1000"]["low"], "high": d["buyer_impact_interval_per_1000"]["high"],
                     "tag": hi["tag"], "counts": f"{hi['treated_buyers']}/{hi['treated_n']:,} bought (Mens e-mail) vs {hi['control_buyers']}/{hi['control_n']:,} (no e-mail)",
                     "claim_id": "CLM_BUYERS_PER_1000_MENS"},
        "arms": arms, "policies": policies,
        "verdict": {"code": mvb["verdict"], "text": mvb["verdict_text"], "vs_random": mvb["model_minus_random_per_1000_contacts"],
                    "vs_rule": mvb["model_minus_rule_per_1000_contacts"], "stable_vs_random": mvb["stable_vs_random"], "stable_vs_rule": mvb["stable_vs_rule"],
                    "headline": ("Model ahead on the point estimate, NOT statistically stable: both intervals include zero. "
                                 "We do not use it to exclude customers.") if mvb["verdict"] == "MODEL_AHEAD_NOT_STABLE" else mvb["verdict"]},
        "recommendation": {"status": rec["status"], "decision": rec["decision"], "conditions": rec["conditions"], "reverse_if": rec["would_reverse_if"],
                           "no_email": rec["no_email_option"], "alternative": rec["alternative_if_model_inconclusive"], "holdout": rec["holdout_plan"]},
        "scenarios": scen, "thresholds": thr,
        "unknowns": [{"id": a["id"], "name": a["name"], "needed_from": a.get("needed_from")} for a in d["assumptions_and_unknowns"] if a["tag"] == "UNKNOWN"],
        "marketing": {k: d["marketing"][k] for k in ("positioning", "four_ps", "message_drafts", "action_plan", "success_metric", "targeting")},
        "warnings": d["warnings"], "sources": d["sources"], "published_refs": d["published_references"],
        "claims": {k: cl[k] for k in cl}, "approval_status": d["approval_status"],
        "trace": trace, "blocked": blocked, "lab": lab_summary(),
    }
    if trace:
        v["dossier"] = {"id": trace["opportunity_id"], "state": trace["state"], "mode": trace["mode"], "llm_status": trace["llm_status"],
                        "steps": [{"role": s["role"], "transition": s["transition"], "ms": s["runtime_ms"],
                                   "tools": [f"{c['tool']}:{c['status']}" for c in s["tool_calls"]]} for s in trace["agent_trace"]],
                        "checker": trace.get("checker_verdict"), "work_items": trace.get("work_items", []), "approval": trace.get("approval")}
    return v


def lab_summary(path: Path = REPORTS / "campaign_lab" / "results.json") -> dict | None:
    """Headline of the model lab (protocol v3), read from its generated files; None if the lab has not been run."""
    ex = path.with_name("extras.json")
    if not (path.exists() and ex.exists()):
        return None
    r, e = json.loads(path.read_text(encoding="utf-8")), json.loads(ex.read_text(encoding="utf-8"))
    s, pn = r["selection"], r["permutation"]
    best = s["best_challenger"]
    return {"n_candidates": len(s["mean_auq"]) - 3, "selected": s["selected"], "best_challenger": best,
            "best_challenger_ci90": s["paired_diff_vs_baseline_ci90"][best], "challenger_shown_better": s["challenger_shown_better"],
            "perm_p": pn["p_value"], "real_auq": pn["real_auq_repeat0"], "null_p95": pn["null_p95"],
            "heterogeneity_p": e["heterogeneity"]["global"]["p_value"], "customers_needed": e["power"]["customers_needed_for_80pct_power_if_gap_is_real"],
            "n_test": e["power"]["n_test_now"], "mde_per_1000": e["power"]["min_detectable_gap_per_1000_at_current_n"],
            "sentence": (f"{len(s['mean_auq']) - 3} model candidates were tested under a pre-registered protocol; none was shown better than the baseline "
                         f"(best challenger {best}: paired 90% interval {s['paired_diff_vs_baseline_ci90'][best][0]:+.1f} to {s['paired_diff_vs_baseline_ci90'][best][1]:+.1f} buyers of Qini area). "
                         f"The baseline's out-of-fold signal is not distinguishable from shuffled arm labels (p = {pn['p_value']:.2f}). "
                         f"Proving a targeting gain would need roughly {e['power']['customers_needed_for_80pct_power_if_gap_is_real']:,} customers, against {e['power']['n_test_now']:,} in the test split.")}


def latest_trace(path: Path = REPORTS / "marketing_agent_trace.json") -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def latest_blocked(path: Path = REPORTS / "marketing_blocked_demo.json") -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# ----------------------------------------------------------------------------------------------- markdown brief
def brief_markdown(v: dict) -> str:
    h, r, vd = v["headline"], v["recommendation"], v["verdict"]
    L = [f"# Marketing decision brief: Hillstrom e-mail case (agent dossier)", "",
         f"Case `{v['case_id']}`, contract {v['contract_version']}, run `{v['run_id']}`, model `{v['model_version']}`. Export SHA-256 `{v['sha256']}`.",
         "Generated by `python -m mi.consumer.viewmodel brief` from the validated export and the saved agent trace; no figure is typed by hand.", "",
         "## Decision", "", f"**Status:** `{r['status']}`; approval `{v['approval_status']}`. {r['decision']}", "",
         f"**Headline (tag {SHORT_TAG[h['tag']]}):** {n(h['value'])} additional purchasing customers per 1,000 e-mailed with the Mens e-mail "
         f"(95% interval {n(h['low'])} to {n(h['high'])}); {h['counts']}. Claim `{h['claim_id']}`.", "",
         "## Did the targeting model beat random and the rule?", "", f"Verdict `{vd['code']}`. {vd['headline']}", "", vd["text"], "",
         "| Held-out policy (Mens e-mail) | Additional buyers per 1,000 contacts | 95% interval | Counts | Tag |", "|---|---|---|---|---|"]
    L += [f"| {p['label']} | {n(p['value'])} | {n(p['low'])} to {n(p['high'])} | {p['counts']} | {SHORT_TAG[p['tag']]} |" for p in v["policies"]]
    L += ["", "## Observed arms (full randomized sample)", "", "| Arm | Buyers / customers | Rate | Additional per 1,000 vs no e-mail | Incremental spend per contact (USD) |", "|---|---|---|---|---|"]
    L += [f"| {a['arm']} | {a['buyers']} / {a['customers']:,} | {a['rate_pct']:.2f}% | {a['per1000']} ({a['per1000_ci']}) | {a['spend']} ({a['spend_ci']}) |"
          if a["role"] != "control" else f"| {a['arm']} (control) | {a['buyers']} / {a['customers']:,} | {a['rate_pct']:.2f}% | reference | reference |" for a in v["arms"]]
    L += ["", "## Economics are scenarios, not profit", "", "Margin and cost per e-mail are UNKNOWN. Break-even cost per e-mail by assumed margin (Mens e-mail, before setup):", "",
          "| Assumed margin | Break-even cost (point) | Conservative (lower bound) |", "|---|---|---|"]
    L += [f"| {t['margin']:.0%} | {t['point']:.3f} USD | {t['conservative']:.3f} USD |" for t in v["thresholds"]]
    L += ["", "| Scenario (assumption set) | Margin | Cost per e-mail | Setup | Contribution (SCENARIO) | Range |", "|---|---|---|---|---|---|"]
    L += [f"| {s['label']} | {'unknown' if s['margin'] is None else format(s['margin'], '.0%')} | {n(s['cost'], 3)} | {n(s['setup'], 0)} | "
          f"{n(s['contribution'], 0)} USD | {s['range'] or 'unknown'} |" for s in v["scenarios"]]
    if v.get("lab"):
        L += ["", "## Model lab: could a better model fix this?", "", v["lab"]["sentence"], "",
              "Exploratory test of whether any feature changes the e-mail effect: global p = " + f"{v['lab']['heterogeneity_p']:.3f}" + ". Details: `reports/campaign_lab/report.md`."]
    L += ["", "## Conditions, reversal and no-send", ""] + [f"- {c}" for c in r["conditions"]]
    L += ["", "Would reverse the decision:"] + [f"- {x}" for x in r["reverse_if"]]
    L += ["", f"**No e-mail.** {r['no_email']}", "", f"**If only a share can be contacted.** {r['alternative']}"]
    if v.get("dossier"):
        dz = v["dossier"]
        L += ["", "## Agent path (what actually ran)", "", f"Dossier `{dz['id']}`, state `{dz['state']}`, mode `{dz['mode']}`. {dz['llm_status']}.", "",
              "| Role | Tools called (status) | Transition | ms |", "|---|---|---|---|"]
        from collections import Counter
        L += [f"| {s['role']} | {', '.join(f'{t} x{k}' if k > 1 else t for t, k in Counter(u.split(':')[0] for u in s['tools']).items())} | {s['transition']} | {s['ms']} |" for s in dz["steps"]]
        if dz["checker"]:
            L += ["", f"Checker: `{dz['checker']['verdict']}`; launch blocked by: {', '.join(dz['checker']['launch_blockers'])}."]
        L += ["", f"Work items drafted: {len(dz['work_items'])}; the only send-type item is `BLOCKED_PENDING_APPROVAL`. No agent has a send, spend, approve or publish tool."]
    L += ["", "## Capability status (seven capabilities)", "",
          "| Capability | Status |", "|---|---|",
          "| Research and RAG | PARTIAL: sources and abstentions listed by the Research role; no live retrieval over a retailer corpus |",
          "| Customer intelligence | VERIFIED on this case (producer repo): conversion uplift model, held-out, not stable |",
          "| Portfolio optimization | VERIFIED as a campaign portfolio: Mens, Womens, no e-mail under contact caps |",
          "| Demand and risk | SCENARIO: intervals and break-even thresholds; no demand forecast |",
          "| Advisor and CRM | IMPLEMENTED as DETERMINISTIC_SPECIALISTS with a sandbox record; LIVE LLM RUN PENDING |",
          "| SEO / GEO | PENDING: 0 of 20 real answers logged; separate from the e-mail data |",
          "| Outcome learning | HISTORICAL ONLY: outcome log works only after a recorded action; no live outcome exists |", "",
          "## Limits", ""] + [f"- {w}" for w in v["warnings"]]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------------------------- offline html
def backup_html(v: dict) -> str:
    e = html.escape
    h, vd, r = v["headline"], v["verdict"], v["recommendation"]
    rows = "".join(f"<tr><td>{e(a['arm'])}</td><td>{a['buyers']} / {a['customers']:,}</td><td>{a['rate_pct']:.2f}%</td><td>{e(str(a['per1000']))} {e(a['per1000_ci'])}</td></tr>" for a in v["arms"])
    pol = "".join(f"<tr><td>{e(p['label'])}</td><td>{n(p['value'])}</td><td>{n(p['low'])} to {n(p['high'])}</td><td>{e(p['counts'])}</td><td>{SHORT_TAG[p['tag']]}</td></tr>" for p in v["policies"])
    thr = "".join(f"<tr><td>{t['margin']:.0%}</td><td>{t['point']:.3f}</td><td>{t['conservative']:.3f}</td></tr>" for t in v["thresholds"])
    scn = "".join(f"<tr><td>{e(s['label'])}</td><td>{n(s['contribution'], 0)}</td><td>{e(s['range'] or 'unknown')}</td><td>{e(s['kind'])}</td></tr>" for s in v["scenarios"])
    steps = ""
    if v.get("dossier"):
        steps = "<h2>Agent trace (saved)</h2><table><tr><th>Role</th><th>Tools</th><th>Transition</th></tr>" + "".join(
            f"<tr><td>{e(s['role'])}</td><td>{e(', '.join(s['tools']))}</td><td>{e(s['transition'])}</td></tr>" for s in v["dossier"]["steps"]) + "</table>"
        steps += f"<p>Mode <b>{e(v['dossier']['mode'])}</b>. {e(v['dossier']['llm_status'])}. State <b>{e(v['dossier']['state'])}</b>: awaiting a named human.</p>"
    if v.get("blocked"):
        b = v["blocked"]
        steps += ("<h2>Blocked on purpose</h2><ul>"
                  f"<li>Strategist calls send_email: <b>{e(str(b['strategist_calls_send_email']))}</b></li>"
                  f"<li>Agent self-approval: <b>{e(str(b['agent_self_approval']))}</b></li>"
                  f"<li>CRM record before approval: <b>{e(str(b['crm_records_before_approval']['status']))}</b></li></ul>")
    lab_html = f"<h2>Model lab</h2><p>{e(v['lab']['sentence'])}</p>" if v.get("lab") else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Buyer decision (offline backup)</title><style>
body{{font:16px/1.5 system-ui,Segoe UI,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1d1d1b;background:#fff}}
table{{border-collapse:collapse;width:100%;margin:8px 0 20px}}td,th{{border:1px solid #ccc;padding:6px 8px;text-align:left;font-size:14px}}th{{background:#f2f2f0}}
.big{{font-size:2.2rem;font-weight:700}}.warn{{background:#fff4e0;border-left:4px solid #eb6834;padding:8px 12px}}.key{{font-size:13px;color:#52514e}}
@media(prefers-color-scheme:dark){{body{{background:#161616;color:#eee}}td,th{{border-color:#444}}th{{background:#262626}}.warn{{background:#33261a}}}}
</style></head><body>
<h1>Buyer decision: Mens e-mail, existing customers</h1>
<p class="key">{e(v['label'])} | case {e(v['case_id'])} | run {e(v['run_id'])} | export SHA-256 {e(v['sha256'][:16])}... | static offline copy, no network</p>
<p class="key">{e(v['tag_key'])}</p>
<p><span class="big">{n(h['value'])}</span> additional purchasing customers per 1,000 e-mailed (95% interval {n(h['low'])} to {n(h['high'])}) <b>[{SHORT_TAG[h['tag']]}]</b><br>{e(h['counts'])}. Two weeks, unique existing customers, versus the randomized no-e-mail control.</p>
<div class="warn"><b>{e(vd['headline'])}</b></div>
<h2>Three arms (full randomized sample)</h2><table><tr><th>Arm</th><th>Buyers / customers</th><th>Rate</th><th>Additional per 1,000 vs no e-mail</th></tr>{rows}</table>
<h2>Model versus baselines, 25% contact cap (held-out)</h2><table><tr><th>Policy</th><th>Additional per 1,000 contacts</th><th>95% interval</th><th>Counts</th><th>Tag</th></tr>{pol}</table>
{lab_html}<h2>Decision</h2><p><b>{e(r['status'])}</b> (approval {e(v['approval_status'])})<br>{e(r['decision'])}</p>
<h2>Economics are scenarios, not profit</h2><p>Margin and cost per e-mail are UNKNOWN.</p>
<table><tr><th>Assumed margin</th><th>Break-even cost per e-mail, point (USD)</th><th>Conservative (USD)</th></tr>{thr}</table>
<table><tr><th>Scenario</th><th>Contribution (USD)</th><th>Range</th><th>Kind</th></tr>{scn}</table>
{steps}
<h2>Limits</h2><ul>{''.join(f'<li>{e(w)}</li>' for w in v['warnings'])}</ul>
</body></html>"""


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["brief"])[0]
    case = load_case()
    if not case.ok:
        print(f"{case.status}: {case.reasons}")
        return 1
    v = build(case, latest_trace(), latest_blocked())
    if cmd == "brief":
        (DOCS / "marketing_decision_brief.md").write_text(brief_markdown(v), encoding="utf-8")
        print("wrote docs/marketing_decision_brief.md")
    elif cmd == "backup":
        (REPORTS / "buyer_decision_backup.html").write_text(backup_html(v), encoding="utf-8")
        print("wrote reports/buyer_decision_backup.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
