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
with st.expander("Limits"):
    st.markdown("\n".join(f"- {w}" for w in v["warnings"]))
