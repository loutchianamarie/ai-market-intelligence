"""Manager demo: one opportunity dossier from dilemma to decision.  Run:  streamlit run app/streamlit_app.py

Works offline from saved, hashed artifacts. Every number shows its status label. No live send exists.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from mi.config import load_config  # noqa: E402
from mi.paths import PROCESSED, REPORTS  # noqa: E402
from mi.workflow.store import DossierStore, PermissionDenied, WorkflowError, pilot_hash  # noqa: E402

st.set_page_config(page_title="Market Intelligence Dossier", layout="wide")
BLUE, ORANGE, INK2 = "#2a78d6", "#eb6834", "#52514e"
BADGE = {"HISTORICAL OBSERVATION": "#1f6f43", "MODEL ESTIMATE": "#2a5ca8", "ASSUMPTION": "#8a5a00",
         "SIMULATED WORKFLOW": "#6b3fa0", "FUTURE EXPERIMENT": "#555555", "COMPANY SCALE ASSUMED": "#9a3412"}


def badge(label: str) -> str:
    c = BADGE.get(label, "#555")
    return (f"<span style='border:1.5px solid {c};color:{c};border-radius:4px;padding:1px 6px;"
            f"font-size:0.75rem;font-weight:600;letter-spacing:.03em'>{label}</span>")


def rj(name):
    p = REPORTS / name
    return json.loads(p.read_text()) if p.exists() else None


cfg = load_config()
model = rj("model_report.json")
sens = rj("sensitivity.json")
port = rj("portfolio.json")
store = DossierStore()


def latest_dossier_id():
    with store._conn() as c:
        r = c.execute("SELECT opportunity_id FROM dossier_versions WHERE note='pilot drafted' ORDER BY created_at DESC LIMIT 1").fetchone()
    return r[0] if r else None


st.sidebar.title("Dossier")
oid = st.sidebar.text_input("Opportunity ID", value=latest_dossier_id() or "")
if st.sidebar.button("Run agents → new dossier (to human checkpoint)"):
    from mi.agents.coordinator import Run
    with st.spinner("Coordinator running Research → Intelligence → Portfolio → Activation …"):
        oid = Run().run_to_checkpoint()
    st.sidebar.success(f"Created {oid}")
st.sidebar.markdown("**Labels**<br>" + "<br>".join(badge(k) for k in BADGE), unsafe_allow_html=True)
st.sidebar.caption(f"Config {cfg.get('version')} · model {model['run_id'] if model else 'missing'}")

d = None
if oid:
    try:
        d = store.get(oid)
    except WorkflowError:
        st.sidebar.error("Unknown dossier")

# ---------------------------------------------------------------- header
st.title("Where should the next CRM budget go?")
st.markdown("Category & CRM manager, anonymous US grocery retailer (84.51° Complete Journey panel, 2,469 households, 2017). "
            "Choose a **product category × existing-household segment × channel** pilot, a popularity-led broad mailing, "
            "or **NONE — measure first**. A higher purchase score is not automatically a better investment.")
c1, c2, c3, c4 = st.columns(4)
if model:
    sel = "model_" + model["selected_model"]
    c1.metric("Model AP (locked test)", f"{model['test'][sel]['AP']:.3f}", f"{model['test'][sel]['AP'] - model['test']['rule_repeat']['AP']:+.3f} vs repeat rule")
    c1.markdown(badge("HISTORICAL OBSERVATION"), unsafe_allow_html=True)
if port:
    c2.metric("Base-case recommendation", "NONE" if port["recommended_base"].startswith("NONE") else "Pilot")
    c2.markdown(badge("ASSUMPTION"), unsafe_allow_html=True)
    hn = port['heuristic']['base']['net']
    c3.metric("Popularity-led mailing (base)", f"{'−' if hn < 0 else ''}${abs(hn):,.0f}")
    c3.markdown(badge("ASSUMPTION") + " " + badge("COMPANY SCALE ASSUMED") + " infeasible comparator (over budget)", unsafe_allow_html=True)
if d:
    c4.metric("Dossier state", {"REVIEW_REQUESTED": "IN REVIEW", "SANDBOX_RECORDED": "RECORDED"}.get(d["state"], d["state"]), f"v{d['version']}")
    c4.markdown(badge("SIMULATED WORKFLOW"), unsafe_allow_html=True)

tabs = st.tabs(["1 Evidence & segment", "2 Model vs rule", "3 Plans & reversal", "4 Pilot & approval",
                "5 SEO / GEO", "6 Learning", "7 Agent trace", "8 Buyer outcomes", "9 Work queue", "10 E-mail campaign case"])

# ---------------------------------------------------------------- 1 evidence
with tabs[0]:
    st.subheader("What the sources support — and what they do not")
    if d and d.get("research_output"):
        ro = d["research_output"]
        for c in ro["claims"]:
            st.markdown(f"<blockquote style='margin:0 0 4px 0'>{html.escape(c['span'][:260])}</blockquote>"
                        f"<code>{html.escape(c['source_id'])}</code> · {html.escape(c.get('url', ''))} · retrieved "
                        f"{c.get('retrieved_at', '')[:10]} " + badge("HISTORICAL OBSERVATION"), unsafe_allow_html=True)
        st.markdown("**Limits and unknowns**")
        for l in ro["limits"]:
            st.markdown(f"- {l}")
        st.info(ro["proposed_action"])
    q = st.text_input("Ask the source corpus (abstains when unsupported)", "What is the retailer's actual product gross margin on frozen pizza?")
    if q:
        from mi.evidence.rag import answer
        a = answer(q)
        if a["abstained"]:
            st.warning(a["answer"])
        else:
            for c in a["supported_claims"]:
                st.markdown(f"- “{html.escape(c['span'][:240])}” — `{c['source_id']}`", unsafe_allow_html=True)
            if a.get("conflicts"):
                st.error(f"Source conflict: {a['conflicts']}")
    st.subheader("Behavioural segments (pre-cutoff behaviour only)")
    st.table(pd.DataFrame([{"segment": k, "definition": v} for k, v in cfg["segments"].items()]))
    if (PROCESSED / "scores_latest.parquet").exists():
        sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
        cat = st.selectbox("Category", cfg["categories"], index=cfg["categories"].index("FROZEN PIZZA"))
        prof = sc[sc.product_category == cat].groupby("segment").agg(panel_households=("household_id", "size"),
                                                                    mean_calibrated_q0=("p_used", "mean")).round(3)
        st.dataframe(prof, width="stretch")
        st.markdown(badge("HISTORICAL OBSERVATION") + " segment sizes · " + badge("MODEL ESTIMATE") +
                    " q0 = probability of buying in the next 4 weeks under historical conditions (not coupon response)", unsafe_allow_html=True)

# ---------------------------------------------------------------- 2 model
with tabs[1]:
    if model:
        sel = "model_" + model["selected_model"]
        st.subheader(f"Fitted {model['selected_model']} vs simple rules — locked out-of-time test (weeks 50–53)")
        rows = [{"scorer": k.replace("model_", "model: "), **{m: round(model["test"][k][m], 4) for m in ("AP", "ROC_AUC", "Brier", "precision_top10pct", "recall_at_3")}}
                for k in (sel, "rule_repeat", "rule_popularity")]
        mt = pd.DataFrame(rows)
        st.dataframe(mt.set_index("scorer"), width="stretch")
        bars = alt.Chart(mt).mark_bar(color=BLUE, cornerRadiusEnd=4, size=28).encode(
            x=alt.X("AP:Q", scale=alt.Scale(domain=[0, 1]), title="Average precision (prevalence 0.275)"),
            y=alt.Y("scorer:N", sort=None, title=None), tooltip=["scorer", "AP", "Brier"]).properties(height=150)
        prev = alt.Chart(pd.DataFrame({"x": [model["test"][sel]["prevalence"]]})).mark_rule(color=INK2, strokeDash=[4, 3]).encode(x="x:Q")
        st.altair_chart(bars + prev, width="stretch")
        b = model["bootstrap_model_minus_rule_repeat"]
        st.markdown(f"Household-cluster bootstrap: AP gain **{b['AP_diff_mean']:+.3f}** (95% CI {b['AP_diff_95ci'][0]:+.3f} to {b['AP_diff_95ci'][1]:+.3f}). "
                    f"Decision tools use: `{model['decision_score_used']}` " + badge("HISTORICAL OBSERVATION"), unsafe_allow_html=True)
        cal = pd.DataFrame(model["calibration_deciles_model"])
        cal_long = pd.concat([cal.assign(series="observed rate", y=cal.observed), cal.assign(series="perfect calibration", y=cal.mean_pred)])
        ch = alt.Chart(cal_long).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60)).encode(
            x=alt.X("mean_pred:Q", title="Mean predicted probability (decile)"), y=alt.Y("y:Q", title="Rate"),
            color=alt.Color("series:N", scale=alt.Scale(range=[BLUE, ORANGE]), legend=alt.Legend(orient="top", title=None)),
            tooltip=["series", alt.Tooltip("mean_pred:Q", format=".3f"), alt.Tooltip("y:Q", format=".3f")]).properties(height=260)
        st.altair_chart(ch, width="stretch")
        st.markdown("**Documented failure**")
        f = model["failure_case"]
        st.write(f"Weakest category vs rule: {f['weakest_category_vs_rule']['category']}. "
                 f"{f['missed_buyers_pred_below_5pct']['n']} buyers had < 5% predicted probability. {f['interpretation']}")
        st.dataframe(pd.DataFrame(model["by_segment"]).set_index("segment").round(3), width="stretch")

# ---------------------------------------------------------------- 3 plans
with tabs[2]:
    st.subheader("Conditional plan comparison — move an assumption, watch the choice")
    st.markdown(badge("ASSUMPTION") + " inputs and outputs · " + badge("COMPANY SCALE ASSUMED") +
                " The observed sample is 2,469 anonymized, non-contactable households. 'Scale' multiplies it to a HYPOTHETICAL company; "
                "it is not a measured CRM audience and response, margin and cost need not scale linearly. "
                "Use the scale-free column (per 1,000 contacted, before setup) to judge plans without extrapolation.",
                unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    um = s1.slider("Uplift × assumed", 0.5, 5.0, 1.0, 0.5)
    scale = s2.select_slider("Deployment scale (households per panel hh)", [10, 40, 100, 250], 40)
    margin = s3.slider("Contribution margin", 0.15, 0.45, 0.28, 0.01)
    dcost = s4.slider("Digital contact cost ($)", 0.0, 0.10, 0.03, 0.01)

    @st.cache_data(show_spinner="Enumerating feasible portfolios…")
    def plans(um, scale, margin, dcost):
        from mi.decision.optimizer import compact, load_inputs, optimise
        s, e, _ = load_inputs()
        r = compact(optimise(s, e, cfg, {"uplift_multiplier": um, "scale": float(scale), "margin_rate": margin,
                                         "contact_cost": {"digital_coupon": dcost}}))
        return json.loads(json.dumps(r, default=float))

    r = plans(um, scale, margin, dcost)
    rec = r["recommended_base"]
    (st.success if not rec.startswith("NONE") else st.warning)(f"Recommendation (base case): **{rec}** · robust (worst case): {r['recommended_robust']}")
    def per1000(p):
        cs = p["base"]["components"]
        tot = sum(c.get("panel_households", 0) for c in cs)
        return sum((c.get("net_per_1000_contacted_before_fixed") or 0) * c.get("panel_households", 0) for c in cs) / tot if tot else None

    tbl = [{"plan": p["plan_id"], "feasible": "yes", "per 1,000 contacted (before setup)": per1000(p),
            "net low": p["low"]["net"], "net base": p["base"]["net"], "net high": p["high"]["net"],
            "cost": p["base"]["cost"], "reach (assumed scale)": sum(c["reach"] for c in p["base"]["components"])} for p in r["top3"]]
    h = r["heuristic"]
    tbl.append({"plan": h["plan_id"], "feasible": "NO (comparator)" if not h["base"].get("feasible", True) else "yes",
                "per 1,000 contacted (before setup)": per1000(h),
                "net low": (h.get("low") or {}).get("net"), "net base": h["base"]["net"],
                "net high": (h.get("high") or {}).get("net"), "cost": h["base"]["cost"],
                "reach (assumed scale)": sum(c["reach"] for c in h["base"]["components"])})
    tbl.append({"plan": "NONE: research / measure first", "feasible": "yes", "per 1,000 contacted (before setup)": 0,
                "net low": 0, "net base": 0, "net high": 0, "cost": 0, "reach (assumed scale)": 0})
    pt = pd.DataFrame(tbl)
    st.dataframe(pt.style.format({c: "{:,.0f}" for c in ["per 1,000 contacted (before setup)", "net low", "net base", "net high", "cost",
                                                         "reach (assumed scale)"]}, na_rep="—"), width="stretch")
    st.caption("A negative per-1,000 value means the plan loses money on every contacted household before any fixed cost, so no company "
               "scale can rescue it at these assumptions. The 'model-filtered' variant follows from ASSUMPTION A1 (baseline purchase ≈ "
               "historical propensity; uplift constant within segment): it is a pilot stratification hypothesis, not measured targeting.")
    rng = pt.dropna(subset=["net low", "net high"])
    rng = rng[~rng.plan.str.startswith("HEURISTIC")]
    if len(rng):
        base = alt.Chart(rng).encode(y=alt.Y("plan:N", sort=None, title=None))
        st.altair_chart((base.mark_rule(color=BLUE, strokeWidth=2).encode(x=alt.X("net low:Q", title="Net contribution, USD (low → high case)"), x2="net high:Q")
                         + base.mark_point(color=BLUE, filled=True, size=90).encode(x="net base:Q", tooltip=["plan", "net low", "net base", "net high"])
                         + alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=INK2, strokeDash=[4, 3]).encode(x="x:Q")).properties(height=200),
                        width="stretch")
    if sens:
        st.markdown("**Reversal grid** (base assumptions otherwise)")
        g = pd.DataFrame(sens["reversal_grid"])
        g["recommendation"] = g.recommended_base.str.replace("/digital_coupon", "").str.replace("/MODEL_FILTERED", " (model-filtered)")
        st.dataframe(g.pivot(index="uplift_multiplier", columns="scale", values="recommendation"), width="stretch")
        st.markdown("**Break-even uplift** — the incremental purchase rate a cohort must reach (per household, before fixed setup)")
        st.dataframe(pd.DataFrame(sens["break_even"][:8]).round(3), width="stretch")
        dem = pd.DataFrame(sens["demand"]).set_index("category")[["weekly_sales_mean_last8", "next4w_sales_low", "next4w_sales_base",
                                                                  "next4w_sales_high", "trend_last8_vs_prev8", "WAPE_naive_last4"]].round(2)
        st.markdown("**Demand baseline** " + badge("HISTORICAL OBSERVATION") + " panel sales; trailing-8-week baseline, backtested WAPE", unsafe_allow_html=True)
        st.dataframe(dem, width="stretch")

# ---------------------------------------------------------------- 4 pilot & approval
with tabs[3]:
    st.subheader("Advisor decision: a person decides, the sandbox records, nothing is sent")
    if not d or not d.get("pilot"):
        st.info("Run the agents (sidebar) to draft a pilot.")
    else:
        p = d["pilot"]
        rec = d.get("advisor_recommendation")
        if rec:
            st.error(f"**ADVISOR STATUS: {rec['decision']}** · base case: {rec.get('base_case', 'retailer-funded')} · {rec['reason']}")
            if rec.get("funding_contracts"):
                st.dataframe(pd.DataFrame(rec["funding_contracts"]).T.astype(str), width="stretch")
            c1, c2 = st.columns(2)
            c1.markdown("**Evidence that would reopen the decision**\n" + "\n".join(f"- {x}" for x in rec["reopen_if"]))
            c2.markdown("**$0 research checklist for approval** " + badge("PENDING"), unsafe_allow_html=True)
            c2.dataframe(pd.DataFrame(rec["research_plan"])[["id", "task", "owner", "decides"]], width="stretch", hide_index=True)
        elif d.get("decision_record") is None and p["design"].get("launch_preconditions"):
            st.warning("Superseded dossier: created before the advisor's reject/defer recommendation. Use the latest dossier.")
        if d.get("decision_record"):
            dr = d["decision_record"]
            st.success(f"**Decision recorded: {dr['decision']}** by {dr['by']} · {dr['reason']} · research checklist approved: "
                       f"{'yes' if dr.get('follow_up_approved_by') else 'no'} ({len(dr.get('follow_up_research') or [])} tasks, PLANNED, not executed)")
        st.markdown("**Test design under review (shown so it can be rejected; not a funded campaign)**")
        a, b = st.columns([3, 2])
        a.markdown(f"**Plan** `{p['plan_id']}` · channel **{p['channel']}** · offer **${p['offer']['value_usd']:.2f}** ({p['offer']['value_status']})")
        a.markdown(f"**Audience:** {p['audience']['rule']}  \n*Reachability:* {p['audience']['reachability']}")
        a.markdown(f"**Design:** {p['design']['type']}, {p['design']['n_per_arm']} households per arm "
                   f"({p['design'].get('n_basis', 'basis not recorded (older dossier)')}), {p['design']['duration_days']} days; "
                   f"primary metric: {p['design']['primary_metric']}")
        if p["design"].get("launch_preconditions"):
            a.markdown("**Launch preconditions (all UNKNOWN today):** " + "; ".join(p["design"]["launch_preconditions"]))
            a.markdown(badge("FUTURE EXPERIMENT") + " not performed; the approval below covers a SANDBOX record only", unsafe_allow_html=True)
        else:
            a.warning("Older dossier: its 866/arm design only detects uplift at break-even and cannot support EXPAND. Use a newer dossier.")
        act_limits = (d.get("activation_output") or {}).get("limits", [])
        same_plan = [x for x in act_limits if x.startswith("Worth-it check (SIMULATION, same plan")]
        if same_plan:
            a.markdown(badge("ASSUMPTION") + " " + badge("COMPANY SCALE ASSUMED") + " " + same_plan[0], unsafe_allow_html=True)
            a.caption(next((x for x in act_limits if x.startswith("Why ")), ""))
        elif p["design"].get("launch_preconditions"):
            a.warning("Superseded dossier: its worth-it check compared this test's cost with a different plan's (Coffee) favourable "
                      "case. Use a dossier created after the same-plan reconciliation.")
        new_msg = a.text_area("Message (editing it after approval invalidates the approval)", p["message"])
        bud = p["budget"]
        b.markdown(f"**Budget** ${bud['total']:,.2f} of ${bud['cap']:,.0f} cap  \n{bud['treated_households']} treated × ${bud['per_household_expected_cost']:.3f} + ${bud['fixed_setup']:,.0f} setup")
        b.markdown(badge("ASSUMPTION") + " budget inputs", unsafe_allow_html=True)
        b.code(f"plan hash {pilot_hash(p)[:24]}…\nstate     {d['state']}\napproval  {json.dumps(d.get('approval'))[:80]}")
        if new_msg != p["message"] and st.button("Save edited message"):
            try:
                d = store.update(oid, d["version"], {"pilot": {**p, "message": new_msg}}, "manager_ui", "human")
                st.warning(f"Saved. State now {d['state']} — any prior approval was invalidated.")
            except Exception as e:
                st.error(str(e))
        st.divider()
        x, y, z = st.columns(3)
        name = x.text_input("Approver full name (human)")
        reason = x.text_area("Reason (required to reject)", value=(rec or {}).get("reason", ""), height=110)
        with_plan = x.checkbox("Also approve the $0 research checklist", value=bool(rec))
        if x.button("Reject / defer funding (role: approver)", type="primary", disabled=not name or d["state"] != "REVIEW_REQUESTED"):
            try:
                d = store.reject(oid, name, "approver", reason, follow_up=(rec or {}).get("research_plan") if with_plan else None)
                st.success(f"Rejected by {name}; reason and checklist stored in dossier v{d['version']}")
            except Exception as e:
                st.error(str(e))
        if y.button("Try: record a coupon sandbox action now"):
            try:
                from mi.agents.tools import stable_key
                res = store.record_sandbox_action(oid, stable_key(oid, pilot_hash(d["pilot"])), "activation_agent")
                st.success(f"Recorded in SANDBOX: {res}")
            except PermissionDenied as e:
                st.error(f"BLOCKED: {e}")
        if y.button("Approve the test record anyway (role: approver)", disabled=not name or d["state"] != "REVIEW_REQUESTED"):
            d = store.approve(oid, name, "approver", pilot_hash(d["pilot"]), "sandbox record of learn-first pilot; no live send")
            st.warning(f"Approved by {name} against the advisor's recommendation (sandbox record only).")
        if z.button("Agent: record approved research checklist (sandbox)", disabled=d["state"] != "REJECTED"):
            from mi.agents.coordinator import Run
            st.success(f"State: {Run().resume_after_rejection(oid)} · checklist recorded as PLANNED; nothing executed")
        if z.button("Resume agents after approval (sandbox + measurement)", disabled=d["state"] != "APPROVED"):
            from mi.agents.coordinator import Run
            st.success(f"Final state: {Run().resume_after_approval(oid)}")
        ev = pd.DataFrame(store.events(oid))
        if len(ev):
            ev["detail"] = ev["detail"].map(lambda v: json.dumps(v, default=str))
            st.dataframe(ev[["ts", "actor", "role", "event", "detail"]], width="stretch", height=260)

# ---------------------------------------------------------------- 5 SEO
with tabs[4]:
    from mi.seo.geo import analyze, load_panel, read_log
    panel = load_panel()
    res = analyze(read_log(), panel)
    st.subheader(f"GEO audit — {panel['audited_brand']} (public analogue) vs {', '.join(panel['competitors'])}")
    st.markdown(f"**{res['status']}** — {res['answers_logged']}/{res['answers_target']} real answers logged. "
                "The team collects answers; the app never invents them.")
    st.table(pd.DataFrame(panel["prompts"])[["id", "intent", "lang", "text"]].set_index("id"))
    if res["answers_logged"]:
        st.json({k: res[k] for k in ("mention_rate", "recommendation_rate", "primary_pick_rate", "share_of_voice",
                                     "share_of_recommendations", "largest_leak", "source_gap_top3")})
        from mi.seo.geo import geo_state
        gs = geo_state()
        if gs["complete"]:
            bi = res["by_intent"]
            st.markdown(" · ".join(f"**{k}**: mentioned {v['mentioned']}/{v['n']}, recommended {v['recommended']}/{v['n']}" for k, v in bi.items()))
            st.caption(f"{gs['answers_logged']}/{gs['answers_target']} answers from {' and '.join(gs['assistants'])} (not ChatGPT or Gemini); one dated run {', '.join(gs['dates'])}; "
                       f"region not set; {gs['answers_target'] - gs['answers_citing_urls']} answers made without web search. {gs['brand']} is a public analogue, not the dataset retailer. "
                       f"Recommended in {bi['Learn']['recommended']}/{bi['Learn']['n']} Learn answers is not zero visibility (it is mentioned in "
                       f"{bi['Learn']['mentioned']}/{bi['Learn']['n']}) and is not measured lost sales. "
                       "Content actions below are hypotheses: impact and effort are unscored and any publication needs human approval.")
        from mi.seo.geo import LOG as GEO_LOG
        lg = pd.read_csv(GEO_LOG, dtype=str).fillna("")
        lg["prompt_id"] = lg["prompt_id"].astype(int)
        pr = pd.DataFrame(panel["prompts"]).rename(columns={"id": "prompt_id", "text": "question"})
        pr["prompt_id"] = pr["prompt_id"].astype(int)
        ans = lg.merge(pr[["prompt_id", "question"]], on="prompt_id", how="left").sort_values("prompt_id")
        ans["assistant"] = ans["assistant_version"].str.extract(r"(Claude \w+ [\d.]+)", expand=False).fillna(ans["assistant"])
        st.subheader("The 20 answers, one row each")
        st.caption("Each row is one logged answer, coded by the team: was Kroger mentioned, recommended, or the top pick, and which competitors "
                   "the assistant named. The raw answer text is not stored here; its SHA-256 is in the log. Single run per question.")
        view = st.radio("Show", ["All 20", "Learn", "Browse", "Buy"], horizontal=True, key="geo_intent")
        shown = ans if view == "All 20" else ans[ans["intent"] == view]
        tbl = shown[["prompt_id", "intent", "question", "assistant", "brand_mentioned", "brand_recommended", "brand_top_pick",
                     "competitors_named", "competitors_recommended", "cited_urls", "source_quality_notes"]].rename(columns={
            "prompt_id": "id", "brand_mentioned": "mentioned", "brand_recommended": "recommended", "brand_top_pick": "top pick",
            "competitors_named": "competitors named", "competitors_recommended": "competitors recommended",
            "cited_urls": "sources cited", "source_quality_notes": "how it was coded"}).set_index("id")
        st.dataframe(tbl, width="stretch", height=420)

        @st.cache_data
        def _geo_workbook(_sig):
            from mi.seo import qa as geo_qa
            p = geo_qa.export_xlsx(REPORTS / "geo_audit_answers.xlsx")
            return (REPORTS / "geo_audit_answers.xlsx").read_bytes() if p.endswith(".xlsx") else b""

        wb = _geo_workbook(GEO_LOG.stat().st_mtime)
        d1, d2 = st.columns(2)
        if wb:
            d1.download_button("Download all answers + rates + QA (Excel)", wb, "geo_audit_answers.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        d2.download_button("Download the answers shown (CSV)", tbl.to_csv().encode("utf-8"), "geo_answers.csv", "text/csv")
        st.dataframe(pd.DataFrame(res["candidate_actions"]))
    st.caption(panel["audited_brand_rationale"])

# ---------------------------------------------------------------- 6 learning
with tabs[5]:
    from mi.outcome.learning import campaign_history, decide, sample_size, simulated_outcome

    @st.cache_data
    def hist():
        return campaign_history()

    h = hist()
    st.subheader("Why historical campaign results cannot be read as effects")
    st.markdown(badge("HISTORICAL OBSERVATION") + " descriptive only", unsafe_allow_html=True)
    bt = pd.DataFrame(h["by_type"]).set_index("type")
    st.dataframe(bt.round(3), width="stretch")
    st.write(h["reading"])
    st.subheader("Future test design and the prewritten decision rule")
    st.markdown(badge("FUTURE EXPERIMENT"), unsafe_allow_html=True)
    p0 = st.number_input("Baseline purchase rate (control)", 0.05, 0.9, 0.305, 0.005)
    dq = st.number_input("Minimum uplift worth detecting", 0.01, 0.3, 0.064, 0.002)
    st.write(f"Households per arm (α=0.05, power 0.8): **{sample_size(p0, dq):,}**")
    tdq = st.slider("SIMULATED true uplift in the fixture", 0.0, 0.15, 0.05, 0.01)
    o = simulated_outcome(true_dq=tdq)
    dd = decide(o, cfg)
    st.markdown(badge("SIMULATED WORKFLOW") + f" incremental contribution per household **${o['incremental_contribution_per_household']:.3f}** "
                f"(95% CI {o['ci95'][0]:.3f} to {o['ci95'][1]:.3f}) → **{dd['decision']}** — {dd['next_action']}", unsafe_allow_html=True)

# ---------------------------------------------------------------- 7 trace
with tabs[6]:
    if d:
        st.subheader(f"Agent trace for {oid}")
        for t in d.get("agent_trace", []):
            with st.expander(f"{t['role']} · mode={t['mode']} · next → {t['next_agent']} · violations={len(t['violations'])}"):
                st.dataframe(pd.DataFrame(t["tool_calls"]), width="stretch")
                out = d.get(f"{t['role']}_output", {})
                if out.get("numbers"):
                    nums = pd.DataFrame(out["numbers"])
                    nums["value"] = nums["value"].map(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else str(v))
                    st.dataframe(nums, width="stretch")
        if d.get("coordinator_reconciliation"):
            st.info(d["coordinator_reconciliation"]["note"])
        st.dataframe(pd.DataFrame(store.history(oid)), width="stretch")
        from mi.agents.llm import credentials_available
        st.caption("Runtime LLM: " + ("available — roles run as Claude tool-use nodes" if credentials_available()
                                       else "NOT configured — roles ran as typed deterministic nodes through the same allowlisted tools"))


# ---------------------------------------------------------------- 8 buyer outcomes
with tabs[7]:
    bo = rj("buyer_outcomes.json")
    st.subheader("Buyer-outcome panel: forecast vs scenario vs observed (never mixed)")
    if not bo:
        st.info("Run python -m mi.decision.buyer_outcomes")
    else:
        st.caption(f"Objective: {bo['objective']['primary']}. Buyer = {bo['objective']['units']['buyer']}. "
                   f"Horizon {bo['objective']['decision_horizon_weeks']} weeks. Not measurable here: {bo['objective']['not_measurable_here']}.")
        a = bo["actions"]["A_coupon"]
        p, add = a["current_pattern_buyers_panel"], a["additional_buyers_reachable_hypothetical"]
        rows = [("Eligible panel households (contactable)", f"{a['eligible']['panel_households']:,} (0)", "OBSERVED"),
                ("Eligible / reachable / consent unknown (company)", f"{a['eligible']['company_eligible_hypothetical']:,} / {a['eligible']['reachable_hypothetical']:,} / {a['eligible']['consent_unknown_or_suppressed_hypothetical']:,}", "COMPANY SCALE ASSUMED"),
                ("Expected buyers, current patterns (panel, 4 wks)", f"{p['expected_buyers']} of {p['households']} (95% {p['poisson_binomial_95']}; calibration-adjusted {p.get('calibration_adjusted_range')})", "MODEL ESTIMATE, not a no-contact counterfactual"),
                ("Additional buyers from the coupon (low / base / high)", f"{add['low']:,} / {add['base']:,} / {add['high']:,}", "SCENARIO (assumed response)"),
                ("Break-even additional buyers", f"{a['break_even_additional_buyers']:,}", "SCENARIO"),
                ("Incremental contribution, USD (low / base / high)", " / ".join(f"{a['incremental_contribution_usd'][k]:+,.0f}" for k in ("low", "base", "high")), "SCENARIO"),
                ("Observed after action", str(a["observed_after_action"]), "OBSERVED only after a run")]
        st.markdown(f"**{a['action']}**")
        st.dataframe(pd.DataFrame(rows, columns=["row", "value", "label"]), width="stretch", hide_index=True)
        for k in ("B_yogurt_investigation", "C_content", "D_none", "E_extra"):
            x = bo["actions"].get(k)
            if x:
                st.markdown(f"**{x['action']}** — additional buyers: {x.get('additional_buyers')}; budget ${x.get('budget_usd', 0)}")

# ---------------------------------------------------------------- 9 work queue
with tabs[8]:
    from mi.workflow.store import WorkQueue
    st.subheader("Advisor work queue (simulated CRM; nothing is sent, spent or launched)")
    if not d:
        st.info("Run the agents to build the queue.")
    else:
        wq = WorkQueue(store)
        items = wq.list(oid)
        if not items:
            st.info("No work items for this dossier (dossiers created before this pass have none; run the agents).")
        else:
            st.dataframe(pd.DataFrame([{"item": w["item_id"], "status": w["status"], "kind": w["payload"]["kind"], "title": w["payload"]["title"],
                                        "owner": w["payload"]["owner"], "budget_usd": w["payload"]["budget_usd"], "due": w["payload"]["due_date"],
                                        "success_metric": w["payload"]["success_metric"]} for w in items]).astype(str), width="stretch", hide_index=True)
            _ids = [w["item_id"] for w in items]
            _paid = next((i for i, w in enumerate(items) if w["payload"].get("kind") == "paid_contact"), 0)
            pick = st.selectbox("Work item", _ids, index=_paid)
            st.caption("Example values are pre-filled for a rehearsal of the blocked path. Replace the name with a real person's for a real decision.")
            who = st.text_input("Your full name (human)", value="Demo gate check (not a decision)", key="wq_name")
            why = st.text_input("Reason / source (required)", value="rehearsal of the blocked path", key="wq_reason")
            c1, c2, c3, c4 = st.columns(4)
            for col, dec in ((c1, "approve"), (c2, "reject"), (c3, "defer")):
                if col.button(dec.capitalize(), key=f"wq_{dec}", disabled=not who or not why):
                    try:
                        st.success(f"{dec}: {wq.decide(pick, who, 'approver', dec, why)['status']}")
                    except Exception as e:
                        st.error(f"BLOCKED: {e}")
            if c4.button("Verify consent + stock", disabled=not who or not why):
                try:
                    wq.verify_requirement(pick, "consent_verified", True, who, "approver", why)
                    wq.verify_requirement(pick, "stock_confirmed", True, who, "approver", why)
                    st.success("verified (recorded with your name and source)")
                except Exception as e:
                    st.error(str(e))
            outcome = st.text_input("Observed outcome to record on completion (facts only)", key="wq_outcome")
            if st.button("Mark done with observed outcome", disabled=not who or not outcome):
                try:
                    st.success(wq.complete(pick, who, "human", {"note": outcome})["status"])
                except Exception as e:
                    st.error(f"BLOCKED: {e}")

# ---------------------------------------------------------------- 10 e-mail campaign case (separate client case)
with tabs[9]:
    from mi.campaign import view as cv
    st.subheader("E-mail campaign case: Hillstrom 2008 (a separate client case, never grocery evidence)")
    try:
        cdoc, csha = cv.load_export()
    except cv.ExportRefused as e:
        st.error(f"Campaign export not shown: {e}")
        cdoc = None
    if cdoc:
        rec, mvb, bi = cdoc["recommendation"], cdoc["model_vs_baselines"], cdoc["buyer_impact_per_1000"]
        st.caption(f"Run {cdoc['run_id']} · model {cdoc['model_version']} · export SHA-256 {csha[:16]}… (checked) · contract {cdoc['contract_version']} · "
                   f"approval: {cdoc['approval_status']} · nothing is sent")
        st.markdown("**Buyer problem.** Existing customers, a contact cap and a margin to protect: which merchandise e-mail creates "
                    "*additional purchasing customers* within two weeks, for whom, and at what cost? Repeat purchase, not new-customer acquisition.")
        st.markdown("#### 1. What the randomized experiment observed (all customers) " + badge("HISTORICAL OBSERVATION"), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(cv.arm_rows(cdoc)).astype(str), width="stretch", hide_index=True)
        st.markdown(f"#### 2. Does a targeting model help under a {int(100 * mvb['primary_contact_share'])}% contact cap? (held-out customers) "
                    + badge("MODEL ESTIMATE"), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(cv.policy_rows(cdoc)).astype(str), width="stretch", hide_index=True)
        (st.success if mvb["verdict"] == "MODEL_WIN_STABLE" else st.warning)(f"Verdict {mvb['verdict']}: {mvb['verdict_text']}")
        st.markdown("#### 3. Economics: scenarios, not profit " + badge("ASSUMPTION"), unsafe_allow_html=True)
        st.write("Margin and cost per e-mail are **UNKNOWN** in the data. Enter verified values to see a scenario; leave a box empty and the result stays UNKNOWN.")
        c1, c2, c3, c4 = st.columns(4)
        arm = c1.selectbox("E-mail", list(cv.TREATMENTS), key="cc_arm")
        st.caption("EXAMPLE values are pre-filled (35% margin, 0.10 USD per e-mail, 1,000 USD setup). They are assumptions, not verified; "
                   "clear a box and the result returns to UNKNOWN.")
        mg = c2.number_input("Margin on incremental sales (0 to 1)", min_value=0.0, max_value=1.0, value=0.35, step=0.01, key="cc_m")
        co = c3.number_input("Cost per e-mail (USD)", min_value=0.0, value=0.10, step=0.005, format="%.3f", key="cc_c")
        su = c4.number_input("Fixed setup (USD)", min_value=0.0, value=1000.0, step=100.0, key="cc_s")
        sc = cv.human_scenario(cdoc, arm, mg, co, su)
        k1, k2 = st.columns(2)
        k1.metric("Scenario contribution", "UNKNOWN" if sc["contribution"] is None else f"${sc['contribution']:,.0f}",
                  None if not sc["range"] else f"range ${sc['range'][0]:,.0f} to ${sc['range'][1]:,.0f}", delta_color="off")
        k2.metric("Break-even cost per e-mail", "UNKNOWN" if sc["break_even_cost"] is None else f"${sc['break_even_cost']:.3f}")
        st.caption(f"{sc['label']} · contacts {sc['contacts']:,.0f} (assumed base less holdout) · formula: {cv.K.FORMULA}")
        with st.expander("Break-even cost at assumed margins (before setup)"):
            st.dataframe(pd.DataFrame(cv.threshold_rows(cdoc)).astype(str), width="stretch", hide_index=True)
        st.markdown("#### 4. Recommendation (a named human decides)")
        st.info(rec["decision"])
        a1, a2 = st.columns(2)
        a1.markdown("**Conditions**\n" + "\n".join(f"- {x}" for x in rec["conditions"]))
        a2.markdown("**What would reverse it**\n" + "\n".join(f"- {x}" for x in rec["would_reverse_if"]))
        st.markdown("**No e-mail:** " + rec["no_email_option"])
        st.markdown("**If the model stays inconclusive:** " + rec["alternative_if_model_inconclusive"])
        st.markdown("#### 5. Owned action plan and drafts (none is sent)")
        st.dataframe(pd.DataFrame(cdoc["marketing"]["action_plan"]).astype(str), width="stretch", hide_index=True)
        for dft in cdoc["marketing"]["message_drafts"]:
            st.text_area(f"{dft['draft_id']} · {dft['status']}", f"Subject: {dft['subject']}\n\n{dft['body']}", height=110, disabled=True, key=f"cc_{dft['draft_id']}")
        with st.expander("Warnings and unknowns"):
            st.markdown("\n".join(f"- {w}" for w in cdoc["warnings"]))
            st.dataframe(pd.DataFrame([{"unknown": a["name"], "needed from": a["needed_from"]} for a in cdoc["assumptions_and_unknowns"] if a["tag"] == "UNKNOWN"]).astype(str),
                         width="stretch", hide_index=True)
