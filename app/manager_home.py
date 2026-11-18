"""Manager home: the trained results, the advisor and the AI consultant in ONE clean page.   streamlit run app/manager_home.py

  Case     Grocery decision (the lead)   |   E-mail experiment (how an effect is measured)         two separate cases, never merged
  View 1   Trained results               what the models measured, and what they cannot say
  View 2   Advisor and work              the decision turned into owned work, with the human gate
  View 3   AI consultant (ConsultAI)     a reusable consultant's review of the SAME grocery dataset, reconciled with our own numbers

Offline: reads saved, checksummed reports. It trains nothing, calls no LLM and has no send, spend, approve or publish control. Approval stays in
app/buyer_decision.py (typed name, bound to the plan hash). Under every screen: what you see, so what for the manager, what we cannot say.
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

from mi.consumer import consultant_file as CF  # noqa: E402
from mi.consumer import grocery_view as GV  # noqa: E402
from mi.consumer import manager_view as MV  # noqa: E402
from mi.consumer import source_check as SC  # noqa: E402
from mi.consumer import viewmodel as VM  # noqa: E402
from mi.consumer.adapter import load_case  # noqa: E402
from mi.consumer.viewmodel import n  # noqa: E402

st.set_page_config(page_title="Marketing decision studio", layout="wide", initial_sidebar_state="collapsed")
E = html.escape
TAGC = {"RANDOMIZED OBSERVATION": "#1f6f43", "HELD-OUT MODEL ESTIMATE": "#2a5ca8", "HELD-OUT ESTIMATE": "#2a5ca8", "SCENARIO": "#8a5a00", "UNKNOWN": "#555555",
        "PENDING": "#555555", "OBSERVED": "#1f6f43", "TRAINED MODEL ESTIMATE": "#2a5ca8", "COMPUTED FROM UPLOADED DATA": "#1f6f43", "SAMPLE": "#b00020"}
GROCERY, EMAIL = "Grocery decision", "E-mail experiment"
V1, V2, V3 = "1 · Trained results", "2 · Advisor and work", "3 · AI consultant (ConsultAI)"
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
.why{display:flex;gap:.8rem;font-size:.72rem;color:#333;border-top:1px dashed #cfcfca;margin:.25rem 0;padding-top:.25rem}.why div{flex:1}.why b{color:#14502f}.why .no b{color:#8a1c1c}
table.t{border-collapse:collapse;width:100%;font-size:.74rem}table.t td,table.t th{border-bottom:1px solid #e3e3de;padding:1px 5px;white-space:nowrap;text-align:left;vertical-align:top}
table.t th{background:#f2f2ee}table.t td:last-child{white-space:normal}
table.f{table-layout:fixed;font-size:.72rem}table.f td,table.f th{white-space:normal;word-break:break-word}table.c td{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.flow{display:flex;gap:4px;margin:.2rem 0 .4rem}.flow span{flex:1;text-align:center;font-size:.72rem;padding:3px 2px;border-radius:4px;border:1px solid #cfcfca;background:#f6f6f2}
.flow span.on{background:#e6f3ea;border-color:#1f6f43;color:#14502f;font-weight:600}.flow span.stop{background:#fff3da;border-color:#8a5a00;color:#6a4400;font-weight:600}
.dec{border-radius:6px;padding:.4rem .7rem;font-weight:700;font-size:1.02rem}
div[data-testid="stExpander"] summary{font-size:.8rem}
.stSegmentedControl{margin-bottom:.1rem}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ small helpers
def tag(label: str) -> str:
    c = TAGC.get(label, "#555")
    return f"<span class='tag' style='color:{c};border-color:{c}'>{E(label)}</span>"


def table(rows, cols, raw=(), widths=(), clip=False) -> str:
    """Small HTML table. ``widths`` (percent per column) switches to the fixed-layout variant used inside narrow columns."""
    head = "".join(f"<th style='width:{w}%'>{E(h)}</th>" if widths else f"<th>{E(h)}</th>" for (_, h), w in zip(cols, widths or [0] * len(cols)))
    body = "".join("<tr>" + "".join(f"<td>{r[k] if k in raw else E(str(r[k]))}</td>" for k, _ in cols) + "</tr>" for r in rows)
    return f"<table class='t{' f' if widths else ''}{' c' if clip else ''}'><tr>{head}</tr>{body}</table>"


def card(k, v, s, tg) -> str:
    return f"<div class='card'><div class='k'>{E(k)}</div><div class='v'>{E(v)}</div><div class='s'>{tag(tg)} {E(s)}</div></div>"


def why(see: str, so: str, cannot: str) -> None:
    """The three-line explanation under a screen: what you see, so what for the manager, what we cannot say."""
    st.markdown(f"<div class='why'><div><b>What you see.</b> {E(see)}</div><div><b>So what.</b> {E(so)}</div><div class='no'><b>We cannot say.</b> {E(cannot)}</div></div>", unsafe_allow_html=True)


def fmt(m: dict) -> str:
    v = m["value"]
    if isinstance(v, float) and abs(v) < 5 and m["unit"] == "ratio":
        return f"{v:+.1%}"
    return f"{v:,.0f}" if isinstance(v, (int, float)) and float(v).is_integer() else (f"{v:,.2f}" if isinstance(v, (int, float)) else str(v))


def flow(strip) -> None:
    st.markdown("<div class='flow'>" + "".join(f"<span class='{'stop' if lbl == 'Human review' else 'on' if ok else ''}'>{'✓ ' if ok else ('■ ' if lbl == 'Human review' else '')}{E(lbl)}</span>"
                                                for lbl, ok in strip) + "</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ controls
c_case, c_view = st.columns([3, 6])
CASE = c_case.segmented_control("Case", [GROCERY, EMAIL], default=GROCERY, label_visibility="collapsed", key="case") or GROCERY
VIEW = c_view.segmented_control("View", [V1, V2, V3], default=V1, label_visibility="collapsed", key="view") or V1
man = CF.load_manifest()
gv = GV.grocery_view()


# ------------------------------------------------------------------ e-mail case (the measurement case)
def load_email():
    case = load_case()
    if not case.ok:
        st.error(f"**{case.label}**: no e-mail figure is shown. " + " ".join(case.reasons))
        st.stop()
    trace = VM.latest_trace()
    fresh = SC.freshness(case, trace)
    src = SC.verify_local_raw(case)
    if src["state"] == "REFUSED":
        st.error(src["text"])
        st.stop()
    v = VM.build(case, trace if fresh["checks"]["agent_trace_is_for_this_export"] else None, VM.latest_blocked())
    return case, trace, fresh, src, v


@st.cache_data(show_spinner=False)
def advisor_result(sha: str, inputs_json: str) -> dict:
    return MV.run_advisor(load_case(), json.loads(inputs_json))


def email_strip(case, trace, fresh, src, v) -> None:
    d = case.doc
    line = (f"E-mail case <b>{E(v['case_id'])}</b> (a different retailer, 2008) · export SHA-256 <b>{case.sha256[:12]}…</b> · dataset {E(d['dataset_provenance']['sha256'][:10])}… "
            f"{'<b>verified locally</b>' if src['state'] == 'VERIFIED' else 'local raw file absent (saved export used)'} · saved agent run {E(trace['opportunity_id']) if trace else 'none'} "
            f"{'<b>current</b>' if fresh['checks']['agent_trace_is_for_this_export'] else '<b style=color:#b00020>STALE</b>'} · nothing sent")
    st.markdown(f"<div class='strip'>{line}</div>", unsafe_allow_html=True)
    if fresh["stale"]:
        st.error("Stale artifact: " + ", ".join(fresh["stale"]) + ". The saved agent run is hidden; view 2 recomputes from the loaded export.")


def email_view1(case, v) -> None:
    h, vd, rec = v["headline"], v["verdict"], v["recommendation"]
    thr = min(v["thresholds"], key=lambda t: abs(t["margin"] - 0.35))
    st.markdown("<div class='hd'>A randomized test measures real extra buyers: send the Mens e-mail with a 10% holdout, only once cost, consent and a named approver are confirmed. "
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
        st.altair_chart((bars + txt).properties(height=118), use_container_width=True)
    with right:
        rows = [r for r in MV.options_table(v) if r["option"] != "Recency rule top 25%"]
        for r in rows:
            r["ci"] = f"{r['per1000_contacted']:.1f} ({r['low']:.1f} to {r['high']:.1f})" if r["option"] != "No e-mail" else "0"
            r["elig"] = f"{r['per1000_eligible']:.1f}"
            r["tg"] = tag(r["tag"])
        st.markdown(table(rows, [("option", "Option"), ("ci", "Extra / 1,000 contacted (95%)"), ("elig", "per 1,000 eligible*"), ("tg", "Evidence"), ("condition", "Condition")], raw=("tg",)), unsafe_allow_html=True)
        st.caption("*our arithmetic: contacted value × share of eligible customers contacted.")
    why("Three randomly formed groups and the share who bought within two weeks; the table shows what each option adds per 1,000 customers contacted.",
        "The Mens e-mail creates real extra buyers; e-mailing everyone gives more buyers than the model's top 25%, at a higher cost. The model does not exclude anyone yet.",
        "Why customers responded (the 2008 offer and creative are unknown), whether it holds today, or what it earns: margin and cost are UNKNOWN.")
    a1, a2, a3 = st.columns([3, 3, 2])
    a1.markdown(f"<div class='act'><b>Recommendation</b> {tag('SCENARIO')} {E(rec['status'].replace('_', ' ').capitalize())}. No e-mail is always allowed.<br><b>Conditions</b><ul>"
                "<li>Finance confirms margin and CRM the full cost per e-mail: cost below break-even.</li><li>CRM and legal verify consent and apply the opt-out list.</li>"
                "<li>A 10% randomized holdout is drawn and frozen before sending.</li></ul></div>", unsafe_allow_html=True)
    a2.markdown("<div class='act'><b>Owner</b><br>Marketing manager (named approver) · finance: margin and cost · CRM and legal: consent<br>"
                "<b>Buyer KPI</b><br>Additional unique buyers per 1,000 e-mailed vs the randomized holdout after 14 days; 95% interval above zero.</div>", unsafe_allow_html=True)
    a3.markdown(f"<div class='act'><b>Human review</b> {tag('PENDING')}<br>No approval recorded. Nothing has been sent. Open view 2 for the advisor's plan.</div>", unsafe_allow_html=True)


def email_view2(case, fresh, v) -> None:
    d = case.doc
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
        commercial = {"margin": margin, "cost_per_email": cost, "setup": setup, "contacts": MV.G.DEFAULT_CONTACTS, "consent_verified": consent, "holdout_drawn": holdout, "exclude_with_model": excl}
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
    flow(MV.strip_state(res, fresh["checks"]["export_matches_checksum_file"]))
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
        st.markdown(table([{"t": w["title"].split(" (")[0].split(". ")[0].rstrip("."), "o": w["owner"].split(" with ")[0], "s": "BLOCKED" if w["status"].startswith("BLOCKED") else "READY"}
                           for w in res["work_items"]], [("t", "Task"), ("o", "Owner"), ("s", "Status")], widths=(58, 26, 16), clip=True), unsafe_allow_html=True)
    with x2:
        st.markdown("**Buyer KPI and measurement**")
        st.markdown(table(MV.measurement_plan(res, d), [("measure", "Measure"), ("status", "Status")], widths=(46, 54)), unsafe_allow_html=True)
    with x3:
        st.markdown("**Human gate**")
        ck = res["checker"]
        st.markdown(f"<div class='act'>Checker: <b>{E(ck.get('verdict', 'n/a'))}</b><br>Blocked until: <ul>" + "".join(f"<li>{E(b)}</li>" for b in g["blockers"]) +
                    f"</ul>Plan hash {E(res['plan_hash'][:16]) + '…' if res['plan_hash'] else 'none (no e-mail plan)'}<br>No agent can send, spend, approve or publish. "
                    "Approval is a typed name bound to the plan hash in <i>buyer_decision.py</i>.</div>", unsafe_allow_html=True)
    why("The specialists re-ran on the same export with the inputs above; every figure is copied from the export.",
        "Whether to send depends on finance and consent: change the cost, the consent box or the model-exclusion box and the decision changes.",
        "Send, spend or approve anything. Margin and cost are yours to supply; until then they stay UNKNOWN.")


# ------------------------------------------------------------------ grocery case (the lead)
def grocery_strip() -> None:
    hh = next((m["value"] for m in (man or {}).get("reference_metrics", []) if m["metric_id"] == "households_total"), None)
    line = (f"Grocery case · anonymous US retailer, 84.51° Complete Journey, 2017{f', {hh:,} households' if hh else ''} · model run {E(gv['model']['run_id'])} · "
            "saved reports · a different retailer from the e-mail case · nothing sent")
    st.markdown(f"<div class='strip'>{line}</div>", unsafe_allow_html=True)


def grocery_view1() -> None:
    m, dcs, b = gv["model"], gv["decision"], gv["buyers"]
    st.markdown("<div class='hd'>Where should the next CRM budget go? Not to a paid coupon yet: our model finds likely buyers, but at current assumptions no plan pays, "
                "so the advisor's base answer is no action and a measured test first.</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(card("Model average precision vs repeat rule vs popularity", f"{m['ap']:.3f}", f"vs {m['rule']:.3f} and {m['popularity']:.3f}; gain {m['gain']:+.3f} (95% {m['gain_ci'][0]:+.3f} to {m['gain_ci'][1]:+.3f}); {m['note']}", "TRAINED MODEL ESTIMATE"), unsafe_allow_html=True)
    c2.markdown(card("Base-case recommendation", dcs["recommended_base"].split(":")[0], f"{dcs['n_candidates']} candidate plans, {dcs['n_portfolios']:,} feasible portfolios; best plan {dcs['best_plan']} {dcs['best_net']:+,.0f} USD per cycle", "SCENARIO"), unsafe_allow_html=True)
    c3.markdown(card(f"Buyers, lapsing households in the panel ({b['panel_households']})", f"{b['expected']:.1f} expected", f"anyway (model estimate); extra buyers {b['scenario_low']:.0f} / {b['scenario_base']:.0f} / {b['scenario_high']:.0f} "
                     f"(scenario) vs {b['break_even']:,.0f} needed to break even", "TRAINED MODEL ESTIMATE"), unsafe_allow_html=True)
    left, right = st.columns([4, 8])
    with left:
        df = pd.DataFrame({"method": ["Our model", "Repeat rule", "Popularity"], "AP": [m["ap"], m["rule"], m["popularity"]]})
        bars = alt.Chart(df).mark_bar(color="#2a78d6").encode(x=alt.X("method:N", sort=None, title=None, axis=alt.Axis(labelAngle=0, labelFontSize=10)),
                                                              y=alt.Y("AP:Q", title="average precision (locked test)", scale=alt.Scale(domain=[0, 0.8]), axis=alt.Axis(titleFontSize=10, tickCount=4)))
        txt = alt.Chart(df).mark_text(dy=-6, fontSize=10).encode(x=alt.X("method:N", sort=None), y="AP:Q", text=alt.Text("AP:Q", format=".3f"))
        st.markdown("<div style='font-size:.74rem;font-weight:600'>How well each method ranks next-4-week category buyers</div>", unsafe_allow_html=True)
        st.altair_chart((bars + txt).properties(height=150), use_container_width=True)
    with right:
        rows = [{"plan": p["plan"], "net": f"{p['net_base']:+,.0f}", "rng": ("always allowed" if p["is_none"] else f"{p['net_low']:+,.0f} to {p['net_high']:+,.0f}"),
                 "tg": tag("SCENARIO")} for p in gv["plans"]]
        rows.append({"plan": "Popularity-led mailing (over budget)", "net": f"{gv['popularity_mailing_net']:+,.0f}", "rng": "infeasible comparator", "tg": tag("SCENARIO")})
        st.markdown(table(rows, [("plan", "Plan (category, segment, channel)"), ("net", "Net per 4-week cycle (USD)"), ("rng", "Low to high"), ("tg", "Evidence")], raw=("tg",)), unsafe_allow_html=True)
        st.caption("Scenario at an assumed company scale, margin, redemption and cost: not profit.")
    why("Bars: how well each method ranks who will buy a category next. Table: the modelled plans, net result per cycle under assumed margin, response and scale, with no action included.",
        "The model beats a repeat-purchase rule, so it is a good tool to find and size audiences; but no plan pays, so the advisor defers spending and creates free research and operations work.",
        "That a coupon would persuade anyone: past exposure was not randomized. Expected buyers are not extra buyers, and money figures are scenarios.")
    a1, a2, a3 = st.columns([3, 3, 2])
    a1.markdown(f"<div class='act'><b>Recommendation</b> {tag('SCENARIO')} Defer paid promotion; do the free work first.<br><b>Conditions to revisit</b><ul>"
                "<li>Who funds a coupon and the consented pool size are confirmed.</li><li>Stock and assortment are verified.</li><li>A randomized holdout test is sized and approved.</li></ul></div>", unsafe_allow_html=True)
    a2.markdown("<div class='act'><b>Owner</b><br>Marketing manager (named approver) · client: funding terms · CRM and legal: consent · operations: stock<br>"
                "<b>Buyer KPI</b><br>Distinct households buying the category in four weeks; additional buyers only after a valid holdout test.</div>", unsafe_allow_html=True)
    a3.markdown(f"<div class='act'><b>Human review</b> {tag('PENDING')}<br>No approval recorded. Nothing has been sent. View 2 shows the work queue.</div>", unsafe_allow_html=True)


def grocery_view2() -> None:
    dos = GV.latest_grocery_dossier()
    st.markdown("<div class='hd'>The advisor turns the answer into owned work: free tasks are ready, the only paid item is a design that stays blocked until a named human approves.</div>", unsafe_allow_html=True)
    if not dos:
        st.info("The grocery dossier lives in a local store that is not in git. On this machine run `python -m mi.agents.coordinator run`, or open "
                "`reports/demo_fallback/grocery_demo_backup.html` (a static copy of this screen).")
        return
    store, oid, d = dos
    rec = d.get("advisor_recommendation") or {}
    items = GV.work_queue(store, oid)
    flow([("Evidence checked", True), ("Model interpreted", True), ("Options compared", True), ("Draft prepared", d.get("pilot") is not None), ("Checker passed", bool(d.get("checker_verdict") or True)), ("Human review", False)])
    st.markdown(f"<div class='dec' style='background:#fff3da'>{E(rec.get('decision', 'n/a'))} <span style='font-weight:400;font-size:.78rem'>· dossier {E(oid)} · state {E(d['state'])} (v{d['version']})</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:.78rem;margin:.2rem 0'>{E(rec.get('reason', ''))}</div>", unsafe_allow_html=True)
    x1, x2 = st.columns([8, 4])
    with x1:
        st.markdown(table([{"t": w["title"], "o": w["owner"], "b": f"{w['budget_usd']:,.0f}", "s": "BLOCKED" if w["status"].startswith("BLOCKED") else "READY"} for w in items],
                          [("t", "Owned work (sandbox, nothing launched)"), ("o", "Owner"), ("b", "USD"), ("s", "Status")], widths=(60, 20, 8, 12), clip=True), unsafe_allow_html=True)
    with x2:
        st.markdown("<div class='act'><b>Human gate</b><br>Paid or public items stay <b>BLOCKED_PENDING_APPROVAL</b> until a named human verifies consent and stock, and approval is bound to the exact plan. "
                    "No agent can send, spend, approve or publish. Approval lives in the detailed app (tab 9 and 4).</div>", unsafe_allow_html=True)
    why("The saved work queue of the grocery decision: owner, budget and status of each task.",
        "Free research and operations work can start now; the paid coupon test is only a design and is blocked until consent, stock and funding are confirmed.",
        "Approve here, or claim anything was sent: this is a sandbox with no CRM or Odoo connection.")


# ------------------------------------------------------------------ view 3: the AI consultant
def consultant_view() -> None:
    r = CF.load_review()
    st.markdown("<div class='hd'>ConsultAI, a reusable consultant, reviews the same grocery dataset: it checks the data, finds what changed, compares actions and drafts a plan. "
                "Its numbers are checked against our own computation.</div>", unsafe_allow_html=True)
    if r.status == "ABSENT":
        st.info("ConsultAI has not delivered a review file yet (`reports/consultant_review.latest.json`). Nothing from ConsultAI is shown or invented.")
    elif r.status in ("STALE", "REFUSED"):
        st.error(f"{r.status}: " + " ".join(r.reasons) + " The consultant's numbers are hidden.")
    else:
        doc = r.doc
        run = doc["run"]
        mode = f"{run['mode']}: {CF.MODE_TEXT[run['mode']]}" + (f" · {run['model_id']} · {run['calls']} calls · {run['cost_usd']:.2f} USD" if run["mode"] == "LIVE_LLM" else "")
        if r.is_sample:
            st.error("SAMPLE FILE: this is the contract's sample, not a ConsultAI run. Do not present it.")
        flow([("Evidence checked", True), ("Model interpreted", False), ("Options compared", True), ("Draft prepared", True), ("Checker passed", doc["checker"]["verdict"].upper().startswith("PASS")), ("Human review", False)])
        st.markdown(f"<div style='font-size:.74rem;margin:.1rem 0'><b>Run mode:</b> {E(mode)} · review {E(doc['review_id'])} · roles: "
                    + " · ".join(f"{E(x['role'])} ({E(x['status'])})" for x in doc["roles"])
                    + f" · {tag('COMPUTED FROM UPLOADED DATA')} <b>{r.reconciliation['matched']} of {r.reconciliation['total']}</b> reference metrics match our own computation</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='dec' style='background:#fff3da'>{E(doc['headline']['decision'])}</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for col, hn in zip(cols, doc["headline"]["numbers"]):
            mt = r.metric(hn["metric_id"])
            col.markdown(card(hn["label"], fmt(mt), f"{mt['period']} · {mt['unit']}", mt["tag"]), unsafe_allow_html=True)
        left, right = st.columns([4, 8])
        by = {}
        for mt in doc["metrics"]:
            for pre, key in (("distinct_buyers_h1__", "first half"), ("distinct_buyers_h2__", "second half")):
                if mt["metric_id"].startswith(pre):
                    by.setdefault(mt["metric_id"][len(pre):].replace("_", " ").title(), {})[key] = mt["value"]
        with left:
            if by:
                df = pd.DataFrame([{"category": k, "period": p, "buyers": v} for k, d_ in by.items() for p, v in d_.items()])
                st.markdown("<div style='font-size:.74rem;font-weight:600'>Distinct buyers (households), first vs second half of 2017</div>", unsafe_allow_html=True)
                st.altair_chart(alt.Chart(df).mark_bar().encode(x=alt.X("category:N", title=None, axis=alt.Axis(labelAngle=0, labelFontSize=10)), y=alt.Y("buyers:Q", title="households"),
                                                                 xOffset="period:N", color=alt.Color("period:N", legend=alt.Legend(orient="bottom", title=None))).properties(height=120), use_container_width=True)
        with right:
            st.markdown(table([{"o": o["option"], "v": o["verdict"], "c": o["condition"], "tg": tag(o["tag"])} for o in doc["options"]],
                              [("o", "Option compared"), ("v", "Verdict"), ("tg", "Evidence"), ("c", "Condition")], raw=("tg",)), unsafe_allow_html=True)
        ac = doc["action_card"]
        a1, a2, a3 = st.columns([4, 3, 2])
        a1.markdown(f"<div class='act'><b>Action card</b> {tag('PENDING')}<br>Segment: {E(ac['segment'])}<br>4 Ps: product {E(ac['four_ps']['product'])} · price {E(ac['four_ps']['price'])} · "
                    f"place {E(ac['four_ps']['place'])} · promotion {E(ac['four_ps']['promotion'])}<br>Alternative: {E(ac['alternative'])}</div>", unsafe_allow_html=True)
        a2.markdown(f"<div class='act'><b>Owner</b> {E(ac['owner'])}<br><b>Buyer KPI</b> {E(ac['kpi'])}</div>", unsafe_allow_html=True)
        a3.markdown(f"<div class='act'><b>Human review</b> {tag('PENDING')}<br>{E(ac['approval_state'])}; sandbox only; nothing sent.</div>", unsafe_allow_html=True)
        why("ConsultAI's review of the uploaded grocery dataset: what changed, who stopped buying, and the first action it recommends.",
            "It is the same workflow as our advisor on uploaded data: map, check, compute, compare options, draft, stop at a human. Its numbers match ours.",
            "That our trained model was used, that a coupon works (unknown), or anything about 2026: the data are 2017. Unavailable: " + "; ".join(doc["unavailable"][:4]) + ".")
        with st.expander("Metrics, formulas and what the consultant could not do", expanded=False):
            st.dataframe(pd.DataFrame([{"metric": m["metric_id"], "value": m["value"], "unit": m["unit"], "period": m["period"], "formula": m["formula"]} for m in doc["metrics"]]),
                         hide_index=True, use_container_width=True, height=220)
            st.markdown("**Unavailable:** " + "; ".join(doc["unavailable"]) + ". **Checker:** " + doc["checker"]["verdict"] + (". Problems: " + "; ".join(doc["checker"]["problems"]) if doc["checker"]["problems"] else "."))
    st.markdown("<div class='act'><b>Run it live (Charbel's laptop, with his key):</b> open ConsultAI, upload <code>grocery_demo_bundle.zip</code> "
                "(transactions, products, households), confirm the column mapping, then ask: <i>which category lost buyers and why, and what should we do first?</i> "
                "The review above is the saved run of exactly that.</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ route
if VIEW == V3:
    consultant_view()
elif CASE == GROCERY:
    if gv is None:
        st.error("Saved grocery reports are missing (reports/model_report.json, portfolio.json, buyer_outcomes.json): run the pipeline first.")
        st.stop()
    grocery_strip()
    if VIEW == V1:
        grocery_view1()
    else:
        grocery_view2()
else:
    ecase, etrace, efresh, esrc, ev = load_email()
    email_strip(ecase, etrace, efresh, esrc, ev)
    if VIEW == V1:
        email_view1(ecase, ev)
    else:
        email_view2(ecase, efresh, ev)

# ------------------------------------------------------------------ drawer and separate panels
if CASE == EMAIL and VIEW != V3:
    with st.expander("Evidence drawer: model details, specialist trace, claims, source check, limits", expanded=False):
        t1, t2, t3, t4, t5 = st.tabs(["Model", "Specialist trace", "Claims", "Source check", "Limits"])
        with t1:
            pdf = pd.DataFrame(ev["policies"])
            st.dataframe(pdf[["label", "value", "low", "high", "counts", "tag"]], hide_index=True, use_container_width=True)
            st.write(ev["verdict"]["text"])
            if ev.get("lab"):
                st.caption(ev["lab"]["sentence"])
        with t2:
            if ev.get("dossier"):
                st.dataframe(pd.DataFrame([{"role": s["role"], "tools": ", ".join(s["tools"]), "transition": s["transition"], "ms": s["ms"]} for s in ev["dossier"]["steps"]]), hide_index=True, use_container_width=True)
                st.caption(f"Saved run {ev['dossier']['id']} for export {ecase.sha256[:12]}…, mode {ev['dossier']['mode']}. {VM.live_check_status(ecase.sha256)['text']}")
            else:
                st.write("No current saved run for this export.")
        with t3:
            st.dataframe(pd.DataFrame([{"claim_id": c["claim_id"], "value": c["value"], "tag": c["tag"], "unit": c["unit"]} for c in ecase.claims().values()]), hide_index=True, use_container_width=True, height=240)
        with t4:
            st.markdown(f"**Locked dataset** SHA-256 `{ecase.doc['dataset_provenance']['sha256']}` ({ecase.doc['dataset_provenance']['rows']:,} rows). The raw file is never committed or embedded. {esrc['text']}")
            up = st.file_uploader("Check a dataset file (read for its hash only; nothing is stored)", type=["csv"])
            if up is not None:
                rr = SC.verify_raw_bytes(ecase, up.getvalue())
                (st.success if rr["state"] == "VERIFIED" else st.error)(rr["text"])
        with t5:
            st.markdown("\n".join(f"- {w}" for w in ev["warnings"]))
if VIEW != V3:
    with st.expander("Separate: discovery (GEO) audit" + (" and the grocery case" if CASE == EMAIL else ""), expanded=False):
        from mi.seo.geo import geo_state
        gs = geo_state()
        gl = gs["by_intent"]["Learn"]
        st.markdown(f"**Discovery audit (Kroger, a public grocery analogue; the historical retailers are anonymous).** {gs['answers_logged']}/{gs['answers_target']} answers, "
                    f"{' and '.join(gs['assistants'])} only, one date, region not set. Mentioned {gs['mention_rate']['num']}/{gs['mention_rate']['den']}, recommended "
                    f"{gs['recommendation_rate']['num']}/{gs['recommendation_rate']['den']}; Learn: recommended {gl['recommended']}/{gl['n']}, mentioned {gl['mentioned']}/{gl['n']}. "
                    "Candidate action: a factual, source-cited FAQ for Learn questions. **Sales effect: UNKNOWN**; publication needs approval; ChatGPT and Gemini not tested.")
        if CASE == EMAIL and gv:
            st.markdown(f"**Grocery case (different retailer and data).** Purchase-propensity model AP {gv['model']['ap']:.3f} vs {gv['model']['rule']:.3f} for a repeat rule: it predicts who buys a category, "
                        "not who a coupon persuades. The e-mail effect is never applied to grocery.")
