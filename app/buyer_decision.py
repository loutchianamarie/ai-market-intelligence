"""Buyer decision: ONE screen from buyers to decision to guarded action.   streamlit run app/buyer_decision.py

Reads only the validated campaign export (via the adapter) and the saved agent trace. Nothing is recomputed here.
No send, spend or publish control exists on this page; approval is a typed-name human act bound to the plan hash.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from mi.consumer import advisor as A  # noqa: E402
from mi.consumer.adapter import load_case  # noqa: E402
from mi.consumer import viewmodel as VM  # noqa: E402
from mi.consumer.viewmodel import TAG_KEY, build, latest_blocked, latest_trace, n  # noqa: E402
from mi.workflow.store import DossierStore, PermissionDenied, WorkflowError, pilot_hash  # noqa: E402

st.set_page_config(page_title="Buyer decision", layout="wide")
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#8a8a86"
COLORS = {"OBSERVED": "#1f6f43", "ESTIMATE": "#2a5ca8", "ASSUMPTION": "#8a5a00", "UNKNOWN": "#555555", "PENDING": "#555555"}


def badge(label: str) -> str:
    c = COLORS.get(label, "#555")
    return f"<span style='border:1.5px solid {c};color:{c};border-radius:4px;padding:1px 6px;font-size:.75rem;font-weight:600'>{label}</span>"


case = load_case()
st.title("Which e-mail creates additional buyers, and what should a manager approve?")
if not case.ok:
    st.error(f"**{case.label}**: no empirical figure is shown. " + " ".join(case.reasons))
    st.info("Place the validated `reports/campaign_case.latest.json` and its `.sha256` from the marketing repo, then reload.")
    st.stop()

store = DossierStore(A.CAMPAIGN_DB)
trace = latest_trace()
blocked = latest_blocked()
if trace and trace.get("export_sha256") != case.sha256:
    st.warning("The saved agent trace was produced from a different export; run the agents again.")
    trace = None
v = build(case, trace, blocked)

with st.sidebar:
    st.header("Case")
    st.caption(f"{v['case_id']} | contract {v['contract_version']}")
    st.caption(f"Run {v['run_id']}")
    st.caption(f"Export SHA-256 {v['sha256'][:16]}...")
    st.markdown(" ".join(badge(k) for k in ("OBSERVED", "ESTIMATE", "ASSUMPTION", "PENDING")), unsafe_allow_html=True)
    st.caption(TAG_KEY)
    if st.button("Run agents (to the human checkpoint)"):
        with st.spinner("Analyst, Research, Strategist, Checker ..."):
            out = A.CampaignRun(case, store).run_to_checkpoint()
            A.blocked_demo(case, DossierStore(A.CAMPAIGN_DB))
        st.success(f"{out.get('opportunity_id')}: {out.get('state')}")
        st.rerun()

h, vd, r = v["headline"], v["verdict"], v["recommendation"]
st.markdown(f"**Objective.** {v['objective']}  \n**Audience.** {v['audience']}  \n**Unit and window.** {v['unit'].replace('_', ' ')}, {v['period']}.")

c1, c2, c3 = st.columns(3)
c1.metric("Additional buyers per 1,000 e-mailed (Mens vs no e-mail)", n(h["value"]), f"95% interval {n(h['low'])} to {n(h['high'])}", delta_color="off")
c1.markdown(badge("OBSERVED") + f" {h['counts']}", unsafe_allow_html=True)
c2.metric("Targeting model vs random and rule", "Ahead, not stable" if vd["code"] == "MODEL_AHEAD_NOT_STABLE" else vd["code"],
          f"vs random {vd['vs_random']['value']:+.1f} ({n(vd['vs_random']['ci95'][0])} to {n(vd['vs_random']['ci95'][1])})", delta_color="off")
c2.markdown(badge("ESTIMATE") + " 25% cap, held-out", unsafe_allow_html=True)
c3.metric("Recommendation", "Broad send + 10% holdout" if "BROAD_SEND" in r["status"] else r["status"], "if economics confirmed; human approves", delta_color="off")
c3.markdown(badge("PENDING") + " approval DRAFT_REQUIRES_HUMAN", unsafe_allow_html=True)
st.warning(vd["headline"])

left, right = st.columns(2)
with left:
    st.subheader("1. Three arms, randomized")
    df = pd.DataFrame(v["arms"])
    show = pd.DataFrame({"arm": df.arm, "buyers / customers": df.buyers.astype(str) + " / " + df.customers.map("{:,}".format),
                         "rate": df.rate_pct.map("{:.2f}%".format), "extra per 1,000": df.per1000, "95% interval": df.per1000_ci})
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.altair_chart(alt.Chart(df).mark_bar(color=BLUE).encode(
        x=alt.X("arm:N", sort=None, title=None), y=alt.Y("rate_pct:Q", title="purchase rate within two weeks (%)"),
        tooltip=["arm", "buyers", "customers"]).properties(height=200), use_container_width=True)
with right:
    st.subheader("2. Model vs random vs rules (held-out, 25% cap, Mens e-mail)")
    pdf = pd.DataFrame(v["policies"])
    base = alt.Chart(pdf).encode(y=alt.Y("label:N", sort=None, title=None))
    st.altair_chart((base.mark_rule(color=GREY).encode(x=alt.X("low:Q", title="additional buyers per 1,000 contacts"), x2="high:Q") +
                     base.mark_point(filled=True, size=90, color=ORANGE).encode(x="value:Q", tooltip=["label", "value", "low", "high", "counts"])
                     ).properties(height=200), use_container_width=True)
    st.caption("Dot = estimate, line = 95% interval. Overlapping intervals: no stable targeting gain.")
    st.write(f"Model minus random: {vd['vs_random']['value']:+.1f} (interval {n(vd['vs_random']['ci95'][0])} to {n(vd['vs_random']['ci95'][1])}). "
             f"Model minus recency rule: {vd['vs_rule']['value']:+.1f} (interval {n(vd['vs_rule']['ci95'][0])} to {n(vd['vs_rule']['ci95'][1])}).")

st.subheader("3. Decision, reason and what would reverse it")
st.success(r["decision"])
a, b = st.columns(2)
a.markdown("**Conditions**\n\n" + "\n".join(f"- {x}" for x in r["conditions"]))
b.markdown("**Would reverse it**\n\n" + "\n".join(f"- {x}" for x in r["reverse_if"]) + f"\n\n**No e-mail is always allowed.** {r['no_email']}")

st.subheader("4. Economics: experiment-estimated spend vs assumed margin (scenarios, not profit)")
e1, e2 = st.columns(2)
e1.markdown(badge("OBSERVED") + " incremental spend per customer e-mailed: " +
            ", ".join(f"{x['arm']} {x['spend']} USD ({x['spend_ci']})" for x in v["arms"] if x["role"] != "control"), unsafe_allow_html=True)
thr = pd.DataFrame(v["thresholds"])
e1.dataframe(pd.DataFrame({"assumed margin": thr.margin.map("{:.0%}".format), "break-even cost per e-mail (USD)": thr.point.map("{:.3f}".format),
                           "conservative (USD)": thr.conservative.map("{:.3f}".format)}), hide_index=True, use_container_width=True)
sc = pd.DataFrame(v["scenarios"])
e2.markdown(badge("ASSUMPTION") + " **SCENARIO, NOT MEASURED PROFIT.** Margin, cost per e-mail and setup are UNKNOWN until finance and CRM supply them.",
            unsafe_allow_html=True)
e2.dataframe(pd.DataFrame({"scenario": sc.label, "contribution": sc.contribution.map(lambda x: "unknown" if pd.isna(x) else f"{x:,.0f} USD"),
                           "range": sc.range.replace("", "unknown")}), hide_index=True, use_container_width=True)

with st.expander("What-if: enter your own margin and cost (scenario arithmetic, not profit)"):
    mens = next(x for x in v["arms"] if x["role"] != "control" and x["spend_num"] is not None)
    w1, w2, w3, w4 = st.columns(4)
    m_in = w1.slider("Margin on incremental revenue", 0.05, 0.90, 0.30, 0.05)
    c_in = w2.number_input("Cost per e-mail (USD)", 0.0, 5.0, 0.02, 0.005, format="%.3f")
    n_in = w3.number_input("Customers e-mailed", 1000, 1000000, 57600, 1000)
    s_in = w4.number_input("Fixed setup (USD)", 0, 1000000, 0, 500)
    out = VM.what_if(mens["spend_num"], mens["spend_ci_num"], m_in, c_in, int(n_in), float(s_in))
    st.markdown(badge("ASSUMPTION") + f" **{out['kind']}**: contribution {out['contribution']:,.0f} USD "
                f"(range {out['low']:,.0f} to {out['high']:,.0f} from the experiment's spend interval). "
                f"Break-even cost per e-mail at this margin: {out['break_even_cost_per_email']:.3f} USD. Verdict: `{out['verdict']}`.", unsafe_allow_html=True)
    st.caption("Spend per e-mailed customer is OBSERVED in the randomized test; every number you type is an assumption. Nothing is saved or sent.")
    cv = v.get("curve")
    if cv:
        sc2 = VM.share_curve(cv["shares"], cv["per1000"], cv["lo"], cv["hi"], cv["random_per1000"], cv["spend_per_buyer"], m_in, c_in)
        cdf = pd.DataFrame({"share of customers e-mailed": sc2["shares"], "model order": sc2["model"], "random order": sc2["random"],
                            "model low": sc2["low"], "model high": sc2["high"]})
        base = alt.Chart(cdf).encode(x=alt.X("share of customers e-mailed:Q", axis=alt.Axis(format="%")))
        band = base.mark_area(opacity=0.15).encode(y="model low:Q", y2="model high:Q")
        ln = base.transform_fold(["model order", "random order"], as_=["policy", "USD"]).mark_line().encode(y=alt.Y("USD:Q", title="scenario contribution per 1,000 customers (USD)"), color="policy:N")
        st.altair_chart(band + ln, use_container_width=True)
        st.caption(f"{sc2['kind']}. Uses the cross-fitted uplift curve of the baseline model (wide intervals: the model's ordering is NOT proven better than random) and about "
                   f"{cv['spend_per_buyer']:.0f} USD of observed incremental spend per additional buyer. At your inputs the model-order curve peaks at {sc2['best_share']:.0%} "
                   f"({sc2['best_contribution']:,.0f} USD per 1,000) versus {sc2['all_in_contribution']:,.0f} USD for e-mailing everyone; treat that difference as within noise.")

st.subheader("5. Research, unknowns and SEO/GEO status")
dz = v.get("dossier")
g1, g2 = st.columns(2)
g1.markdown("**Abstains on (UNKNOWN, never estimated):** " + "; ".join(u["name"] for u in v["unknowns"]) + "; retailer identity; 2008 creative; consent status.")
g1.markdown("**Sources:** " + "; ".join(f"`{s['source_id']}`" for s in v["sources"]) + ". 2008 published figures are PUBLISHED REFERENCE only.")
geo = A.CampaignTools(case, store).t_seo_status()["data"]
g2.markdown(f"**SEO/GEO:** {badge('PENDING' if geo['answers_logged'] < geo['answers_target'] else 'OBSERVED')} {geo['answers_logged']}/{geo['answers_target']} real answers logged. "
            "Separate real-brand workstream; no effect is attributed to e-mail data.", unsafe_allow_html=True)

st.subheader("6. Action draft, CRM sandbox and human checkpoint")
if not dz:
    st.info("No agent run yet: press **Run agents** in the sidebar. Nothing is sent by any control on this page.")
else:
    d = store.get(dz["id"])
    cols = st.columns(2)
    for dr in v["marketing"]["message_drafts"]:
        cols[0 if dr["arm"].startswith("Mens") else 1].markdown(f"**{dr['draft_id']}** `{dr['status']}`  \n*{dr['subject']}*  \n{dr['body']}")
    ck = dz["checker"]
    st.markdown(f"**Checker:** `{ck['verdict']}`. Launch blocked by: {', '.join(ck['launch_blockers'])}.")
    st.dataframe(pd.DataFrame([{"item": w["item_id"], "kind": w["kind"], "status": w["status"], "title": w["title"]} for w in dz["work_items"]]),
                 hide_index=True, use_container_width=True)
    ph = pilot_hash(d["pilot"])
    st.markdown(f"**Dossier** `{dz['id']}` state **{d['state']}**; plan hash `{ph[:16]}...`; mode `{dz['mode']}`. {dz['llm_status']}.")
    if d["state"] == "REVIEW_REQUESTED":
        with st.form("human"):
            name = st.text_input("Approver full name (a human decision)")
            why = st.text_input("Reason (required to reject)")
            ok_btn = st.form_submit_button("Approve sandbox draft")
            no_btn = st.form_submit_button("Reject")
        if ok_btn or no_btn:
            try:
                if not name.strip():
                    raise WorkflowError("a named approver is required")
                if no_btn:
                    store.reject(dz["id"], name.strip(), "approver", why)
                else:
                    store.approve(dz["id"], name.strip(), "approver", ph, scope="sandbox draft of the campaign plan; no live send")
                st.rerun()
            except (WorkflowError, PermissionDenied) as ex:
                st.error(str(ex))
    elif d.get("approval"):
        ap = d["approval"]
        st.success(f"Approved by {ap['approver']} for plan {ap['plan_hash'][:16]}... Scope: {ap['scope']}")
    st.caption("Approval records a sandbox draft only. This system has no send tool.")

with st.expander("Agent trace (saved, real tool calls)"):
    if dz:
        st.dataframe(pd.DataFrame([{"role": s["role"], "tools": ", ".join(s["tools"]), "transition": s["transition"], "ms": s["ms"]} for s in dz["steps"]]),
                     hide_index=True, use_container_width=True)
    if blocked:
        st.markdown("**Blocked on purpose** (scripted attempts, not human decisions)")
        st.json({k: blocked[k] for k in ("strategist_calls_send_email", "analyst_calls_draft_action", "crm_records_before_approval",
                                         "agent_self_approval", "outcome_before_any_action")})
if v.get("lab"):
    with st.expander("Model lab: could a better model fix this?"):
        st.markdown(v["lab"]["sentence"])
        st.caption("Pre-registered protocol v3; figures and the full report are in reports/campaign_lab/.")
if v.get("scale"):
    with st.expander("Scale replication: is it just too little data? (Criteo, 14M rows)"):
        st.markdown(v["scale"]["sentence"])
        fig = Path(__file__).resolve().parents[1] / "reports" / "criteo_scale" / "fig_gap_vs_size.png"
        if fig.exists():
            st.image(str(fig))
        st.caption("Pre-registered protocol v4; details in reports/criteo_scale/report.md.")
with st.expander("What changed? Compare with another export"):
    up = st.file_uploader("Upload an older or newer campaign_case JSON (it is validated first; nothing is saved)", type="json")
    if up is not None:
        import json as _json
        from mi.campaign.contract import validate_case
        try:
            other = _json.loads(up.getvalue().decode("utf-8"))
            errs = validate_case(other)
        except Exception as ex:  # unreadable file
            other, errs = None, [f"not readable as JSON: {ex}"]
        if errs:
            st.error("Rejected: this file does not satisfy the contract, so it is not compared. " + "; ".join(errs[:3]))
        else:
            dd = VM.diff_cases(other, case.doc)
            st.markdown("**Identical to the loaded export.**" if dd["identical"] else "**Differences (uploaded file -> loaded export)**")
            if dd["changed_fields"]:
                st.dataframe(pd.DataFrame(dd["changed_fields"]), hide_index=True, use_container_width=True)
            if dd["changed_claims"]:
                st.dataframe(pd.DataFrame(dd["changed_claims"]), hide_index=True, use_container_width=True)
            if dd["added_claims"] or dd["removed_claims"]:
                st.write({"added": dd["added_claims"], "removed": dd["removed_claims"]})
    else:
        st.caption("Use this after the producer re-exports: it shows which claims, verdicts or statuses moved, so nothing changes silently.")
with st.expander("Limits"):
    st.markdown("\n".join(f"- {w}" for w in v["warnings"]))
