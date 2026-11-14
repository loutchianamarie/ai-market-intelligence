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
                "5 SEO / GEO", "6 Learning", "7 Agent trace"])

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
    st.subheader("Drafted learn-first pilot — a human approves, the sandbox records, nothing is sent")
    if not d or not d.get("pilot"):
        st.info("Run the agents (sidebar) to draft a pilot.")
    else:
        p = d["pilot"]
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
        if x.button("Approve (role: approver)", disabled=not name or d["state"] != "REVIEW_REQUESTED"):
            d = store.approve(oid, name, "approver", pilot_hash(d["pilot"]), "sandbox record of learn-first pilot; no live send")
            st.success(f"Approved by {name}")
        if y.button("Try: record sandbox action now"):
            try:
                from mi.agents.tools import stable_key
                res = store.record_sandbox_action(oid, stable_key(oid, pilot_hash(d["pilot"])), "activation_agent")
                st.success(f"Recorded in SANDBOX: {res}")
            except PermissionDenied as e:
                st.error(f"BLOCKED: {e}")
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
