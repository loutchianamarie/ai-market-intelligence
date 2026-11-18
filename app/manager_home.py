"""Manager home: ONE verified case (Hillstrom randomized e-mail experiment), two views.   streamlit run app/manager_home.py

  1. Trained model & measured effect   what the randomized test measured, and what the held-out targeting model did and did not prove
  2. Marketing advisor                 the deterministic specialists run on the SAME validated export, with the manager's commercial inputs

Offline: reads the checksummed export and runs the specialists on a throwaway store in about a quarter of a second. It trains nothing,
calls no LLM and has no send, spend, approve or publish control. Approval stays in app/buyer_decision.py (typed name, plan-hash bound).
The grocery case and the Kroger GEO audit are separate, collapsed panels: neither is evidence about the e-mail effect.
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

from mi.consumer import manager_view as MV  # noqa: E402
from mi.consumer import source_check as SC  # noqa: E402
from mi.consumer import viewmodel as VM  # noqa: E402
from mi.consumer.adapter import load_case  # noqa: E402
from mi.consumer.viewmodel import n  # noqa: E402

st.set_page_config(page_title="Hillstrom e-mail decision", layout="wide", initial_sidebar_state="collapsed")
E = html.escape
TAGC = {"RANDOMIZED OBSERVATION": "#1f6f43", "HELD-OUT MODEL ESTIMATE": "#2a5ca8", "HELD-OUT ESTIMATE": "#2a5ca8", "SCENARIO": "#8a5a00",
        "UNKNOWN": "#555555", "PENDING": "#555555"}
st.markdown("""<style>
[data-testid=stHeader]{display:none}
.block-container{padding-top:.7rem;padding-bottom:.4rem;max-width:1340px}
h1,h2,h3{margin:0;padding:0}
.hd{font-size:1.12rem;font-weight:700;line-height:1.25;margin:.05rem 0 .15rem}
.strip{font-size:.74rem;color:#444;border-bottom:1px solid #dcdcd6;padding-bottom:.35rem;margin-bottom:.4rem}
.tag{display:inline-block;border:1.5px solid;border-radius:4px;padding:0 5px;font-size:.66rem;font-weight:700;margin-right:4px;white-space:nowrap}
.card{border:1px solid #cfcfca;border-radius:6px;padding:.4rem .7rem;background:#fff;min-height:5.2rem}
.card .k{font-size:.72rem;color:#555}.card .v{font-size:1.3rem;font-weight:700;line-height:1.15}.card .s{font-size:.72rem;color:#444}
.act{border:1.5px solid #2a78d6;border-radius:6px;padding:.45rem .7rem;background:#f5f9ff;font-size:.8rem}
.act b{font-size:.78rem}.act ul{margin:.1rem 0 0 1rem;padding:0}
table.t{border-collapse:collapse;width:100%;font-size:.74rem}table.t td,table.t th{border-bottom:1px solid #e3e3de;padding:1px 5px;white-space:nowrap;text-align:left;vertical-align:top}
table.t th{background:#f2f2ee}table.t td:last-child{white-space:normal}
table.f{table-layout:fixed;font-size:.72rem}table.f td,table.f th{white-space:normal;word-break:break-word}table.c td{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.flow{display:flex;gap:4px;margin:.2rem 0 .4rem}.flow span{flex:1;text-align:center;font-size:.72rem;padding:3px 2px;border-radius:4px;border:1px solid #cfcfca;background:#f6f6f2}
.flow span.on{background:#e6f3ea;border-color:#1f6f43;color:#14502f;font-weight:600}.flow span.stop{background:#fff3da;border-color:#8a5a00;color:#6a4400;font-weight:600}
.dec{border-radius:6px;padding:.4rem .7rem;font-weight:700;font-size:1.02rem}
div[data-testid="stExpander"] summary{font-size:.8rem}
.stSegmentedControl{margin-bottom:.2rem}
</style>""", unsafe_allow_html=True)


def tag(label: str) -> str:
    c = TAGC.get(label, "#555")
    return f"<span class='tag' style='color:{c};border-color:{c}'>{E(label)}</span>"


def table(rows: list[dict], cols: list[tuple[str, str]], raw: tuple = (), widths: tuple = (), clip: bool = False) -> str:
    """Small HTML table. ``widths`` (percent per column) switches to the fixed-layout variant used inside narrow columns."""
    head = "".join(f"<th style='width:{w}%'>{E(h)}</th>" if widths else f"<th>{E(h)}</th>" for (_, h), w in zip(cols, widths or [0] * len(cols)))
    body = "".join("<tr>" + "".join(f"<td>{r[k] if k in raw else E(str(r[k]))}</td>" for k, _ in cols) + "</tr>" for r in rows)
    return f"<table class='t{' f' if widths else ''}{' c' if clip else ''}'><tr>{head}</tr>{body}</table>"


def card(k: str, v: str, s: str, tg: str) -> str:
    return f"<div class='card'><div class='k'>{E(k)}</div><div class='v'>{E(v)}</div><div class='s'>{tag(tg)} {E(s)}</div></div>"


# ------------------------------------------------------------------ load, verify, refuse
case = load_case()
if not case.ok:
    st.error(f"**{case.label}**: no empirical figure is shown. " + " ".join(case.reasons))
    st.info("Place the validated reports/campaign_case.latest.json and its .sha256, then reload. Nothing is substituted.")
    st.stop()
trace = VM.latest_trace()
fresh = SC.freshness(case, trace)


@st.cache_data(show_spinner=False)
def local_source(sha: str) -> dict:
    return SC.verify_local_raw(load_case())


@st.cache_data(show_spinner=False)
def advisor_result(sha: str, inputs_json: str) -> dict:
    return MV.run_advisor(load_case(), json.loads(inputs_json))


src = local_source(case.sha256)
if src["state"] == "REFUSED":
    st.error(src["text"])
    st.stop()
v = VM.build(case, trace if fresh["checks"]["agent_trace_is_for_this_export"] else None, VM.latest_blocked())
d = case.doc
case_line = (f"Case <b>{E(v['case_id'])}</b> · run {E(v['run_id'])} · export SHA-256 <b>{case.sha256[:12]}…</b> · contract v{E(v['contract_version'])} · "
             f"dataset {E(d['dataset_provenance']['sha256'][:10])}… {'<b>verified locally</b>' if src['state'] == 'VERIFIED' else 'local raw file absent (saved export used)'} · "
             f"saved agent run {E(trace['opportunity_id']) if trace else 'none'} {'<b>current</b>' if fresh['checks']['agent_trace_is_for_this_export'] else '<b style=color:#b00020>STALE</b>'} · "
             "deterministic specialists, no live LLM · nothing sent")
st.markdown(f"<div class='strip'>{case_line}</div>", unsafe_allow_html=True)
if fresh["stale"]:
    st.error("Stale artifact: " + ", ".join(fresh["stale"]) + ". The saved agent run is hidden; the advisor view below recomputes from the loaded export. "
             "Run `python -m mi.consumer.advisor run` to refresh the saved trace.")

view = st.segmented_control("View", ["1 · Trained model & measured effect", "2 · Marketing advisor (same export)"], default="1 · Trained model & measured effect",
                            label_visibility="collapsed", key="view")
view = view or "1 · Trained model & measured effect"

h, vd, rec = v["headline"], v["verdict"], v["recommendation"]
thr = min(v["thresholds"], key=lambda t: abs(t["margin"] - 0.35))

# ================================================================== view 1
if view.startswith("1"):
    st.markdown("<div class='hd'>Send the Mens e-mail to consented customers with a 10% randomized holdout, only once cost, consent and a named approver are confirmed. "
                "The targeting model is not proven better than random.</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(card("Mens e-mail vs no e-mail: additional buyers per 1,000 e-mailed", f"+{n(h['value'])}", f"95% interval {n(h['low'])} to {n(h['high'])} · {h['counts']}", "RANDOMIZED OBSERVATION"), unsafe_allow_html=True)
    c2.markdown(card("Targeting model minus random, 25% cap (held-out)", f"{vd['vs_random']['value']:+.1f}", f"per 1,000 contacted; interval {n(vd['vs_random']['ci95'][0])} to {n(vd['vs_random']['ci95'][1])} includes zero: not stable", "HELD-OUT MODEL ESTIMATE"), unsafe_allow_html=True)
    c3.markdown(card("Break-even cost per Mens e-mail at an assumed 35% margin", f"{n(thr['point'], 3)} USD", "margin, cost and consent are UNKNOWN; scenario, not profit", "SCENARIO"), unsafe_allow_html=True)
    left, right = st.columns([4, 8])
    with left:
        df = pd.DataFrame(v["arms"])
        df["label"] = df.buyers.astype(str) + "/" + df.customers.map("{:,}".format)
        bars = alt.Chart(df).mark_bar(color="#2a78d6").encode(x=alt.X("arm:N", sort=None, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=10)),
                                                              y=alt.Y("rate_pct:Q", title="bought in 2 weeks (%)", scale=alt.Scale(domain=[0, 1.6]), axis=alt.Axis(titleFontSize=10, tickCount=4)))
        txt = alt.Chart(df).mark_text(dy=-6, fontSize=10).encode(x=alt.X("arm:N", sort=None), y="rate_pct:Q", text="label:N")
        st.markdown("<div style='font-size:.74rem;font-weight:600'>Randomized buyer outcomes: distinct buyers / customers per arm</div>", unsafe_allow_html=True)
        st.altair_chart((bars + txt).properties(height=165), use_container_width=True)
    with right:
        rows = [r for r in MV.options_table(v) if r["option"] != "Recency rule top 25%"]      # recency rule: see the drawer
        for r in rows:
            r["ci"] = f"{r['per1000_contacted']:.1f} ({r['low']:.1f} to {r['high']:.1f})" if r["option"] != "No e-mail" else "0"
            r["elig"] = f"{r['per1000_eligible']:.1f}"
            r["tg"] = tag(r["tag"])
        st.markdown(table(rows, [("option", "Option"), ("ci", "Extra / 1,000 contacted (95%)"), ("elig", "per 1,000 eligible*"), ("tg", "Evidence"), ("condition", "Condition")], raw=("tg",)), unsafe_allow_html=True)
        st.caption("*our arithmetic: contacted value × share of eligible customers contacted.")
    a1, a2, a3 = st.columns([3, 3, 2])
    a1.markdown(f"<div class='act'><b>Recommendation</b> {tag('SCENARIO')} {E(rec['status'].replace('_', ' ').capitalize())}. No e-mail is always allowed.<br><b>Conditions</b><ul>"
                "<li>Finance confirms margin and CRM the full cost per e-mail: cost below break-even.</li>"
                "<li>CRM and legal verify consent and apply the opt-out list.</li>"
                "<li>A 10% randomized holdout is drawn and frozen before sending.</li></ul></div>", unsafe_allow_html=True)
    a2.markdown("<div class='act'><b>Owner</b><br>Marketing manager (named approver) · finance: margin and cost · CRM and legal: consent<br>"
                f"<b>Buyer KPI</b><br>Additional unique buyers per 1,000 e-mailed vs the randomized holdout after 14 days; 95% interval above zero.</div>", unsafe_allow_html=True)
    a3.markdown(f"<div class='act'><b>Human review</b> {tag('PENDING')}<br>No approval recorded. Nothing has been sent. Open view 2 for the advisor's plan.</div>", unsafe_allow_html=True)

# ================================================================== view 2
else:
    with st.container():
        i1, i2, i3, i4, i5 = st.columns([2.0, 1.0, 1.0, 1.0, 1.6])
        mode = i1.radio("Commercial inputs", ["Not provided (UNKNOWN)", "Enter scenario"], horizontal=True, label_visibility="collapsed")
        commercial = None
        if mode == "Enter scenario":
            margin = i2.slider("Margin", 0.05, 0.90, 0.35, 0.05)
            cost = i3.number_input("Cost per e-mail (USD)", 0.0, 5.0, 0.03, 0.01, format="%.3f")
            setup = i4.number_input("Setup (USD)", 0, 100000, 1000, 500)
            consent = i5.checkbox("Consent verified (CRM/legal)", value=True)
            holdout = i5.checkbox("10% holdout drawn", value=True)
            excl = i5.checkbox("Use the model to exclude customers", value=False)
            commercial = {"margin": margin, "cost_per_email": cost, "setup": setup, "contacts": MV.G.DEFAULT_CONTACTS, "consent_verified": consent,
                          "holdout_drawn": holdout, "exclude_with_model": excl}
        else:
            i2.caption("Margin: UNKNOWN")
            i3.caption("Cost per e-mail: UNKNOWN")
            i4.caption("Consent: not verified")
            i5.caption("Never guessed; a draft is still prepared.")
    res = advisor_result(case.sha256, json.dumps(commercial, sort_keys=True))
    if not res["ok"]:
        st.error(f"The specialists did not run: {res['reason']}")
        st.stop()
    g, pilot = res["gate"], res["pilot"]
    strip = MV.strip_state(res, fresh["checks"]["export_matches_checksum_file"])
    st.markdown("<div class='flow'>" + "".join(f"<span class='{'stop' if lbl == 'Human review' else 'on' if ok else ''}'>{'✓ ' if ok else ('■ ' if lbl == 'Human review' else '')}{E(lbl)}</span>" for lbl, ok in strip) + "</div>", unsafe_allow_html=True)
    colour = {"READY_FOR_HUMAN_APPROVAL": "#e6f3ea", "PILOT_ONLY": "#fff3da", "HOLD_FOR_INPUTS": "#fff3da", "NO_EMAIL": "#fdeaea", "REJECTED_MODEL_EXCLUSION": "#fdeaea"}[g["decision"]]
    st.markdown(f"<div class='dec' style='background:{colour}'>{E(MV.DECISION_HEADLINE[g['decision']])} <span style='font-weight:400;font-size:.78rem'>· {res['runtime_ms']} ms · "
                f"export {case.sha256[:8]}… · {E(res['mode'].replace('_', ' ').lower())}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:.78rem;margin:.2rem 0'>{E(' '.join(g['reasons']))} {tag('SCENARIO' if g['scenario'] else 'UNKNOWN')} {E(MV.money_line(g))}</div>", unsafe_allow_html=True)
    x1, x2, x3 = st.columns([4, 4, 3.5])
    with x1:
        st.markdown("**Audience and CRM draft**")
        if pilot:
            aud, des = pilot["audience"], pilot["design"]
            st.markdown(f"<div style='font-size:.76rem'>Segment rule: {E(aud['segment'])}. No customer IDs exist in this file, so no contact list is generated.<br>"
                        f"Consent: {E(aud.get('consent', 'UNKNOWN: CRM owner with legal'))} · holdout {des['randomized_holdout_share']:.0%} randomized, ≥ {des['customers_per_arm_needed']:,} per arm · "
                        f"model excludes anyone: <b>{'YES (rejected)' if des['model_used_to_exclude_anyone'] else 'no'}</b><br>"
                        f"Drafts are hypotheses (2008 creative and offer unknown), not sent: <i>{E(pilot['message'].splitlines()[0][:90])}</i> …</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size:.76rem'><b>No e-mail draft.</b> The strategist queued the $0 no-send work instead: obtain margin, cost and consent, then re-run.</div>", unsafe_allow_html=True)
        st.markdown("**Owned work** (sandbox, nothing launched)")
        st.markdown(table([{"t": w["title"].split(" (")[0].split(". ")[0].rstrip("."), "o": w["owner"].split(" with ")[0],
                           "s": "BLOCKED" if w["status"].startswith("BLOCKED") else "READY"} for w in res["work_items"]],
                          [("t", "Task"), ("o", "Owner"), ("s", "Status")], widths=(58, 26, 16), clip=True), unsafe_allow_html=True)
    with x2:
        st.markdown("**Buyer KPI and measurement**")
        st.markdown(table(MV.measurement_plan(res, d), [("measure", "Measure"), ("status", "Status")], widths=(46, 54)), unsafe_allow_html=True)
    with x3:
        st.markdown("**Human gate**")
        ck = res["checker"]
        st.markdown(f"<div class='act'>Checker: <b>{E(ck.get('verdict', 'n/a'))}</b><br>Blocked until: <ul>" + "".join(f"<li>{E(b)}</li>" for b in g["blockers"]) +
                    f"</ul>Plan hash {E(res['plan_hash'][:16]) + '…' if res['plan_hash'] else 'none (no e-mail plan)'}<br>No agent can send, spend, approve or publish. "
                    "Approval is a typed name bound to the plan hash in <i>buyer_decision.py</i>.</div>", unsafe_allow_html=True)

# ================================================================== drawer and separate cases
with st.expander("Evidence drawer: model details, specialist trace, claims, source check, limits", expanded=False):
    t1, t2, t3, t4, t5 = st.tabs(["Model", "Specialist trace", "Claims", "Source check", "Limits"])
    with t1:
        pdf = pd.DataFrame(v["policies"])
        st.dataframe(pdf[["label", "value", "low", "high", "counts", "tag"]], hide_index=True, use_container_width=True)
        st.write(vd["text"])
        if v.get("lab"):
            st.caption(v["lab"]["sentence"])
    with t2:
        if v.get("dossier"):
            st.dataframe(pd.DataFrame([{"role": s["role"], "tools": ", ".join(s["tools"]), "transition": s["transition"], "ms": s["ms"]} for s in v["dossier"]["steps"]]), hide_index=True, use_container_width=True)
            st.caption(f"Saved run {v['dossier']['id']} for export {case.sha256[:12]}…, mode {v['dossier']['mode']}. {VM.live_check_status(case.sha256)['text']}")
        else:
            st.write("No current saved run for this export.")
    with t3:
        st.dataframe(pd.DataFrame([{"claim_id": c["claim_id"], "value": c["value"], "tag": c["tag"], "unit": c["unit"]} for c in case.claims().values()]), hide_index=True, use_container_width=True, height=240)
    with t4:
        st.markdown(f"**Locked dataset** SHA-256 `{d['dataset_provenance']['sha256']}` ({d['dataset_provenance']['rows']:,} rows). The raw file is never committed or embedded. {src['text']}")
        up = st.file_uploader("Check a dataset file (read for its hash only; nothing is stored)", type=["csv"])
        if up is not None:
            r = SC.verify_raw_bytes(case, up.getvalue())
            (st.success if r["state"] == "VERIFIED" else st.error)(r["text"])
    with t5:
        st.markdown("\n".join(f"- {w}" for w in v["warnings"]))
with st.expander("Separate cases, not evidence for the e-mail effect: discovery (GEO) audit and grocery", expanded=False):
    from mi.seo.geo import geo_state
    gs = geo_state()
    gl = gs["by_intent"]["Learn"]
    st.markdown(f"**Discovery audit (Kroger, a public grocery analogue; the historical retailers are anonymous).** {gs['answers_logged']}/{gs['answers_target']} answers, "
                f"{' and '.join(gs['assistants'])} only, one date, region not set. Mentioned {gs['mention_rate']['num']}/{gs['mention_rate']['den']}, recommended "
                f"{gs['recommendation_rate']['num']}/{gs['recommendation_rate']['den']}; Learn: recommended {gl['recommended']}/{gl['n']}, mentioned {gl['mentioned']}/{gl['n']}. "
                "Candidate action: a factual, source-cited FAQ for Learn questions. **Sales effect: UNKNOWN**; publication needs approval; ChatGPT and Gemini not tested.")
    mr = json.loads((ROOT / "reports" / "model_report.json").read_text(encoding="utf-8")) if (ROOT / "reports" / "model_report.json").exists() else None
    if mr:
        sel = "model_" + mr["selected_model"]
        st.markdown(f"**Grocery case (different retailer and data; `python -m mi.cli demo`).** Purchase-propensity model AP {mr['test'][sel]['AP']:.3f} vs {mr['test']['rule_repeat']['AP']:.3f} for a repeat rule: "
                    "it predicts who buys a category, not who a coupon persuades. Base recommendation: no paid promotion yet. The e-mail effect is never applied to grocery.")
