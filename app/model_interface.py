"""Model interface: look at the grocery purchase-propensity model on its own.  Run:  streamlit run app/model_interface.py --server.port 8502

Reads only saved artifacts (data/processed/scores_latest.parquet, reports/model_report.json). Nothing is retrained or sent.
Run `PYTHONPATH=src python -m mi.model.train` first if scores_latest.parquet is missing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from mi.paths import PROCESSED, REPORTS  # noqa: E402
from mi.model import marketing_metrics as mm  # noqa: E402
from mi.decision import interpret as it  # noqa: E402

st.set_page_config(page_title="Purchase-propensity model", layout="wide")

SCORES = PROCESSED / "scores_latest.parquet"
REPORT = REPORTS / "model_report.json"
if not SCORES.exists() or not REPORT.exists():
    st.error("Model outputs are missing. Run: PYTHONPATH=src python -m mi.model.train")
    st.stop()


@st.cache_data
def load():
    return pd.read_parquet(SCORES), json.loads(REPORT.read_text(encoding="utf-8"))


sc, rep = load()
SEL = rep["selected_model"]
T = rep["test"]["model_" + SEL]
R = rep["test"]["rule_repeat"]
P = rep["test"]["rule_popularity"]
nice = lambda c: c.title().replace("/", " / ")  # noqa: E731


def explain(box, expanded=True):
    """A plain-words reading of the chart above it: what it shows, so what, what to do, what to watch out for."""
    with st.expander("How to read this: " + box["title"], expanded=expanded):
        st.markdown(f"**What it shows.** {box['shows']}")
        st.markdown(f"**So what.** {box['so_what']}")
        st.markdown(f"**What to do.** {box['do']}")
        st.markdown(f"**Watch out.** {box['watch_out']}")
        st.caption(f"Evidence: {box['evidence']}. Written by rules from the numbers on this page, so it changes when they do.")

st.title("Purchase-propensity model")
st.caption("Which household is likely to buy which category in the next 4 weeks? Grocery case (84.51 Complete Journey, 2017).")
st.warning("**Historical propensity, not a coupon effect.** The score says who is likely to buy anyway. It does not say who would respond "
           "to a coupon, because coupon exposure was not randomized. No profit is claimed.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Average precision (test)", f"{T['AP']:.3f}", f"{T['AP'] - R['AP']:+.3f} vs repeat rule")
c2.metric("ROC AUC (test)", f"{T['ROC_AUC']:.3f}", f"{T['ROC_AUC'] - R['ROC_AUC']:+.3f} vs repeat rule")
c3.metric("Households scored", f"{sc.household_id.nunique():,}")
c4.metric("Household x category rows", f"{len(sc):,}")

tab_score, tab_top, tab_perf, tab_how, tab_gain, tab_rfm, tab_card, tab_data, tab_plan = st.tabs(
    ["1 Score a household", "2 Who to rank first", "3 How good is it", "4 How it was built",
     "5 Lift and gains", "6 Customer tiers", "7 Decision card", "8 Another dataset", "9 Strategy and plan"])

# ------------------------------------------------------------------ 1 score a household
with tab_score:
    st.subheader("Look up one household and one category")
    a, b = st.columns(2)
    hh = a.selectbox("Household", sorted(sc.household_id.unique(), key=lambda x: int(x)), index=0)
    cat = b.selectbox("Category", sorted(sc.product_category.unique()), index=sorted(sc.product_category.unique()).index("FROZEN PIZZA"))
    row = sc[(sc.household_id == hh) & (sc.product_category == cat)]
    if row.empty:
        st.info("This household is not scored for this category (it had no basket in the last 12 weeks, so it is not eligible).")
    else:
        r = row.iloc[0]
        cat_rows = sc[sc.product_category == cat]
        rank = int((cat_rows.p_model > r.p_model).sum()) + 1
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Model: chance of buying in 4 weeks", f"{r.p_model:.0%}")
        m2.metric("Repeat-purchase rule", f"{r.p_rule:.0%}")
        m3.metric("Rank in this category", f"{rank:,} of {len(cat_rows):,}")
        m4.metric("Segment", r.segment.replace("_", " ").title())
        st.markdown("**Signals behind the score**")
        st.table(pd.DataFrame({
            "signal": ["Weeks with a purchase of this category (last 12)", "Spend on this category (last 12 weeks, USD)", "Baskets by this household (last 12 weeks)"],
            "value": [f"{r.cat_weeks_active_12w:.0f}", f"{r.cat_spend_12w:,.2f}", f"{r.hh_baskets_12w:,}"]}).set_index("signal"))
        st.altair_chart(alt.Chart(cat_rows).mark_bar(color="#0e5c5c").encode(
            x=alt.X("p_model:Q", bin=alt.Bin(maxbins=25), title="model score (chance of buying)"),
            y=alt.Y("count():Q", title="households"),
            tooltip=["count():Q"]).properties(height=200, title=f"Where this household sits among all {nice(cat)} scores") +
            alt.Chart(pd.DataFrame({"x": [float(r.p_model)]})).mark_rule(color="#c8571f", size=3).encode(x="x:Q"),
            width="stretch")
        st.caption("The orange line is the selected household. A score of 30% means about 3 in 10 such households bought in the test weeks "
                   "(see tab 3, calibration). MODEL ESTIMATE.")

# ------------------------------------------------------------------ 2 who to rank first
with tab_top:
    st.subheader("Rank households in one category")
    a, b = st.columns(2)
    cat2 = a.selectbox("Category", sorted(sc.product_category.unique()), index=sorted(sc.product_category.unique()).index("YOGURT"), key="cat2")
    n = b.slider("How many households to list", 10, 500, 100, 10)
    d = sc[sc.product_category == cat2].sort_values("p_model", ascending=False)
    top = d.head(n)
    exp_top, exp_all = float(top.p_model.sum()), float(d.p_model.sum())
    base = float(d.p_model.mean())
    k1, k2, k3 = st.columns(3)
    k1.metric(f"Expected buyers in the top {n}", f"{exp_top:,.0f}", f"{exp_top / n:.0%} of the list")
    k2.metric("A random list of the same size", f"{base * n:,.0f}", f"{base:.0%} of the list")
    k3.metric("Households in this category", f"{len(d):,}")
    st.caption("Expected buyers = sum of the calibrated scores. These are people likely to buy anyway, **not** extra buyers caused by an offer. MODEL ESTIMATE.")
    out = top[["household_id", "segment", "p_model", "p_rule", "cat_weeks_active_12w", "cat_spend_12w", "hh_baskets_12w"]].rename(columns={
        "household_id": "household", "p_model": "model score", "p_rule": "repeat rule", "cat_weeks_active_12w": "weeks active (12w)",
        "cat_spend_12w": "category spend (12w, USD)", "hh_baskets_12w": "baskets (12w)"})
    st.dataframe(out.style.format({"model score": "{:.0%}", "repeat rule": "{:.0%}", "weeks active (12w)": "{:.0f}", "category spend (12w, USD)": "{:,.2f}"}),
                 width="stretch", hide_index=True, height=380)
    st.download_button("Download this list (CSV)", out.to_csv(index=False).encode("utf-8"), f"top_{cat2.lower().replace(' ', '_').replace('/', '_')}.csv", "text/csv")

# ------------------------------------------------------------------ 3 how good is it
with tab_perf:
    st.subheader("Locked test on weeks 50 to 53 (never used for training or choosing)")
    perf = pd.DataFrame({"scorer": ["Trained model", "Repeat-purchase rule", "Popularity rule"],
                         "Average precision": [T["AP"], R["AP"], P["AP"]], "ROC AUC": [T["ROC_AUC"], R["ROC_AUC"], P["ROC_AUC"]],
                         "Top-10% precision": [T["precision_top10pct"], R["precision_top10pct"], P["precision_top10pct"]],
                         "Brier (lower is better)": [T["Brier"], R["Brier"], P["Brier"]]})
    a, b = st.columns([1, 1])
    a.dataframe(perf.style.format({c: "{:.3f}" for c in perf.columns[1:]}), hide_index=True, width="stretch")
    b.altair_chart(alt.Chart(perf).mark_bar().encode(
        x=alt.X("scorer:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("Average precision:Q", scale=alt.Scale(domain=[0, 0.8])),
        color=alt.Color("scorer:N", legend=None, scale=alt.Scale(range=["#0e5c5c", "#a8a89a", "#d0cabb"])),
        tooltip=["scorer", alt.Tooltip("Average precision:Q", format=".3f")]).properties(height=220), width="stretch")
    bo = rep["bootstrap_model_minus_rule_repeat"]
    st.success(f"Gain over the repeat rule: {bo['AP_diff_mean']:+.3f} average precision (95% interval {bo['AP_diff_95ci'][0]:+.3f} to {bo['AP_diff_95ci'][1]:+.3f}, "
               f"household bootstrap, {bo['n_boot']} resamples). The interval excludes zero.")
    explain(it.interpret_performance(T["AP"], R["AP"], P["AP"], bo["AP_diff_mean"], bo["AP_diff_95ci"][0], bo["AP_diff_95ci"][1], T["ROC_AUC"]))
    st.markdown("**Calibration: does a 30% score mean about 30%?**")
    cal = pd.DataFrame(rep["calibration_deciles_model"])
    cal["decile"] = range(1, len(cal) + 1)
    line = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 4], color="#999").encode(x="x:Q", y="y:Q")
    pts = alt.Chart(cal).mark_line(point=True, color="#0e5c5c").encode(
        x=alt.X("mean_pred:Q", title="predicted chance", scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("observed:Q", title="share who actually bought", scale=alt.Scale(domain=[0, 1])),
        tooltip=["decile", alt.Tooltip("mean_pred:Q", format=".2f"), alt.Tooltip("observed:Q", format=".2f"), "n"])
    st.altair_chart((line + pts).properties(height=280), width="stretch")
    st.caption("Points close to the dashed diagonal mean the scores behave like real probabilities (isotonic calibration, fitted on a separate window).")
    explain(it.interpret_calibration(rep["calibration_deciles_model"]))
    st.markdown("**By category (test): model vs repeat rule, average precision**")
    bc = pd.DataFrame(rep["by_category"])[["category", "n", "prevalence", "AP_model", "AP_rule"]].rename(
        columns={"AP_model": "model", "AP_rule": "repeat rule"})
    st.dataframe(bc.style.format({"prevalence": "{:.1%}", "model": "{:.3f}", "repeat rule": "{:.3f}"}), hide_index=True, width="stretch")
    f = rep["failure_case"]
    st.warning(f"**Documented weakness.** Weakest category versus the rule: {f['weakest_category_vs_rule']['category']}. "
               f"{f['missed_buyers_pred_below_5pct']['n']:,} buyers ({f['missed_buyers_pred_below_5pct']['share_of_positives']:.1%} of all buyers) "
               f"were given under 5%. {f['interpretation']}")

# ------------------------------------------------------------------ 4 how it was built
with tab_how:
    st.subheader("How the model was built")
    st.markdown(
        "1. **Question.** Will this household buy this category in the next 4 weeks? Eight categories, 2,469 households, 1,469,307 purchase lines.\n"
        "2. **Features (20).** Recency, frequency and spend for the category and the household, category popularity and trend, coupon history. "
        "Each is computed only from weeks up to the cutoff, and a check stops the run if any feature looks past it.\n"
        "3. **Time-based split.** Train on cutoffs 13 to 37, choose the model at cutoff 41, calibrate at cutoff 45, test once at cutoff 49 (outcome weeks 50 to 53).\n"
        "4. **Baselines first.** A popularity rule and a repeat-purchase rule, so the model has something real to beat.\n"
        "5. **Candidates.** Logistic regression and two gradient-boosted models. The smaller gradient-boosted one won on validation.\n"
        "6. **Calibration.** Isotonic regression on a separate window, so a score of 30% means about 30%.\n"
        "7. **One locked test and a household bootstrap** for the interval.")
    sp = pd.DataFrame(rep["split_counts"]).T
    sp["cutoffs"] = sp["cutoffs"].map(lambda c: ", ".join(map(str, c)))
    st.dataframe(sp[["cutoffs", "rows", "households", "positives", "prevalence"]].style.format({"prevalence": "{:.1%}"}), width="stretch")
    st.markdown("**Validation average precision (to pick the model)**")
    v = pd.Series(rep["validation_AP"], name="average precision").to_frame()
    st.dataframe(v.style.format("{:.3f}"), width="stretch")
    with st.expander("The 20 features"):
        st.write(", ".join(rep["features"]))
    st.markdown("**Limits.** One anonymous retailer, 2,469 households, 2017. The test weeks are the holiday period. No margin, stock, consent or cost data. "
                "The model cannot predict households with no purchase in the category for 12 weeks who then buy (the cold-start limit).")
    st.caption(f"Run {rep['run_id']} · status: {rep['status']}")

# ------------------------------------------------------------------ 5 lift and gains
with tab_gain:
    st.subheader("Lift and cumulative gains on the locked test (weeks 50 to 53)")
    st.caption("If you can only contact part of the list, how many of the real buyers are in that part? OBSERVED on held-out outcomes; ranking, not a coupon effect.")
    TP = PROCESSED / "test_predictions.parquet"
    if not TP.exists():
        st.info("test_predictions.parquet is missing. Run: PYTHONPATH=src python -m mi.model.train")
    else:
        tp = pd.read_parquet(TP)
        frac = st.slider("Contact the top share of the list", 5, 50, 20, 5, format="%d%%") / 100
        lm, lr_ = mm.lift_at(tp.y, tp.s_model, frac), mm.lift_at(tp.y, tp.s_rule, frac)
        a, b, c = st.columns(3)
        a.metric("Model: buyers captured", f"{lm['buyers_captured_share']:.0%}", f"lift {lm['lift']:.2f}x")
        b.metric("Repeat rule: buyers captured", f"{lr_['buyers_captured_share']:.0%}", f"lift {lr_['lift']:.2f}x")
        c.metric("Random list: buyers captured", f"{frac:.0%}", "lift 1.00x")
        gm, gr = mm.gains_table(tp.y, tp.s_model), mm.gains_table(tp.y, tp.s_rule)
        curve = pd.concat([
            pd.DataFrame({"share of list contacted": [0] + gm.cum_households_share.tolist(), "share of buyers captured": [0] + gm.cum_buyers_share.tolist(), "scorer": "Trained model"}),
            pd.DataFrame({"share of list contacted": [0] + gr.cum_households_share.tolist(), "share of buyers captured": [0] + gr.cum_buyers_share.tolist(), "scorer": "Repeat rule"}),
            pd.DataFrame({"share of list contacted": [0, 1], "share of buyers captured": [0, 1], "scorer": "Random"})])
        st.altair_chart(alt.Chart(curve).mark_line(point=True).encode(
            x=alt.X("share of list contacted:Q", axis=alt.Axis(format="%")), y=alt.Y("share of buyers captured:Q", axis=alt.Axis(format="%")),
            color=alt.Color("scorer:N", scale=alt.Scale(domain=["Trained model", "Repeat rule", "Random"], range=["#0e5c5c", "#a8a89a", "#c8571f"])),
            tooltip=["scorer", alt.Tooltip("share of list contacted:Q", format=".0%"), alt.Tooltip("share of buyers captured:Q", format=".0%")]).properties(height=300),
            width="stretch")
        st.markdown("**Decile table (model).** Decile 1 = the 10% with the highest scores.")
        st.dataframe(gm.rename(columns={"households": "rows", "rate": "buyer rate", "cum_buyers_share": "cumulative buyers captured", "cum_households_share": "cumulative list"})
                     [["decile", "rows", "buyers", "buyer rate", "lift", "cumulative list", "cumulative buyers captured"]]
                     .style.format({"buyer rate": "{:.0%}", "lift": "{:.2f}", "cumulative list": "{:.0%}", "cumulative buyers captured": "{:.0%}"}), hide_index=True, width="stretch")
        st.caption("Lift is the buyer rate in the group divided by the overall buyer rate. A lift of 2.5x means the group buys 2.5 times as often as an average row.")
        explain(it.interpret_gains(lm["buyers_captured_share"], lr_["buyers_captured_share"], frac, lm["lift"], lr_["lift"]))

# ------------------------------------------------------------------ 6 customer tiers
with tab_rfm:
    st.subheader("Customer tiers by recency, frequency and spend (RFM)")
    st.caption("Computed from purchases up to week 53 (last 12 weeks for frequency and spend). OBSERVED. Ties share a score. The value column is an ASSUMPTION-based proxy, not profit.")
    TX = PROCESSED / "transactions.parquet"
    if not TX.exists():
        st.info("transactions.parquet is missing. Run: python -m mi.ingest.download, then any pipeline step that loads the data.")
    else:
        @st.cache_data
        def _rfm():
            tx = pd.read_parquet(TX, columns=["household_id", "basket_id", "week", "sales_value"])
            return mm.rfm_table(tx, 53), mm.retention_table(tx, 53)

        rf, ret = _rfm()
        a, b = st.columns(2)
        margin = a.slider("Margin (assumed)", 0.10, 0.50, 0.28, 0.01)
        keep = b.slider("Chance a household keeps shopping each 4 weeks (assumed)", 0.50, 1.00, 0.90, 0.01)
        tier = rf.groupby("rfm_segment").agg(households=("R", "size"), weeks_since_last_basket=("recency_weeks", "mean"), baskets_12w=("frequency", "mean"), spend_12w=("monetary", "mean")).reset_index()
        tier["value_next_52_weeks_per_household"] = tier.spend_12w.map(lambda x: mm.value_proxy(x / 3, margin, keep))
        order = ["Champions", "Loyal", "Potential loyalists", "New or light", "Need attention", "At risk", "Hibernating"]
        tier["o"] = tier.rfm_segment.map({k: i for i, k in enumerate(order)})
        tier = tier.sort_values("o").drop(columns="o")
        st.altair_chart(alt.Chart(tier).mark_bar(color="#0e5c5c").encode(x=alt.X("rfm_segment:N", sort=order, title=None, axis=alt.Axis(labelAngle=-20)), y="households:Q",
                        tooltip=["rfm_segment", "households"]).properties(height=240), width="stretch")
        st.dataframe(tier.rename(columns={"rfm_segment": "tier"}).style.format({"weeks_since_last_basket": "{:.1f}", "baskets_12w": "{:.1f}", "spend_12w": "{:,.0f}", "value_next_52_weeks_per_household": "{:,.0f}"}),
                     hide_index=True, width="stretch")
        st.caption("Value = discounted margin over 13 four-week cycles if the household keeps spending at its recent rate and keeps shopping with the chance chosen above. A ranking aid, not a forecast.")
        st.markdown("**Store-level retention: of the households active in a 4-week window, the share active in the next**")
        st.altair_chart(alt.Chart(ret).mark_line(point=True, color="#c8571f").encode(x=alt.X("window:N", sort=None, title=None), y=alt.Y("retention:Q", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                        tooltip=["window", "active", "active_next_window", alt.Tooltip("retention:Q", format=".0%")]).properties(height=220), width="stretch")

        explain(it.interpret_rfm(tier.to_dict("records"), ret.to_dict("records")))

# ------------------------------------------------------------------ 7 decision card
with tab_card:
    from mi.decision import decision_card as dc
    from mi.config import load_config

    st.subheader("Decision card: who, what to do, does it pay, how to test it")
    st.caption("Composed from the model scores, the portfolio economics and the validated cross-sell. Scenario numbers are assumptions. Approval stays PENDING_HUMAN: nothing is sent, spent or published.")

    @st.cache_data
    def _cards():
        cfg = load_config()
        return {c: dc.build_card(c, cfg) for c in cfg["categories"]}

    cards = _cards()
    rk = dc.rank_cards(list(cards.values()))
    st.markdown("**All categories, ranked by how close a paid offer is to paying**")
    st.dataframe(rk.rename(columns={"needed_response_multiple": "response needed vs assumed (x)", "net_base_usd": "net base (USD)", "net_high_usd": "net if all favourable (USD)",
                                    "expected_buyers_4w": "expected buyers (4 wk)"}).style.format({"response needed vs assumed (x)": "{:.1f}", "net base (USD)": "{:,.0f}", "net if all favourable (USD)": "{:,.0f}",
                                                                                             "expected buyers (4 wk)": "{:,.0f}"}), hide_index=True, width="stretch")
    explain(it.interpret_portfolio(rk.to_dict("records")))
    cat_pick = st.selectbox("Open the card for", list(cards), index=list(cards).index("COFFEE"), key="card_cat")
    card = cards[cat_pick]
    (st.success if card["headline"]["decision"].startswith("TEST") else st.warning)(f"**{card['headline']['decision']}** — {card['headline']['one_line']}")
    if card["checker"]:
        st.error("The checker found problems: " + "; ".join(card["checker"]))
    st.markdown(dc.to_markdown(card).split("\n", 4)[-1])
    explain(it.interpret_segments(card["situation"]["segments"], cat_pick))
    d1, d2 = st.columns(2)
    d1.download_button("Download the card (Markdown)", dc.to_markdown(card).encode("utf-8"), f"decision_card_{cat_pick.lower().replace('/', '_').replace(' ', '_')}.md", "text/markdown")
    d2.download_button("Download the card (JSON)", json.dumps(card, indent=1, default=float).encode("utf-8"), f"decision_card_{cat_pick.lower().replace('/', '_').replace(' ', '_')}.json", "application/json")

# ------------------------------------------------------------------ 8 another dataset
with tab_data:
    from mi import data_readiness as dr

    st.subheader("Can this project work on another retail dataset?")
    st.caption("Drop in a transactions file (CSV, Parquet or Excel). Nothing is stored or trained: the page only checks the data against the design this model used.")
    up = st.file_uploader("Transactions file", type=["csv", "parquet", "xlsx"], key="up_tx")
    up2 = st.file_uploader("Products file (only if categories are in a separate table)", type=["csv", "parquet", "xlsx"], key="up_pr")
    colA, colB = st.columns(2)
    run_demo = colB.button("Check the Complete Journey data (reference, expect READY)")

    def _read(f):
        n = f.name.lower()
        return pd.read_parquet(f) if n.endswith(".parquet") else pd.read_excel(f) if n.endswith(".xlsx") else pd.read_csv(f, low_memory=False)

    result = None
    if run_demo:
        with st.spinner("Checking 1.4 million rows..."):
            result = dr.demo_complete_journey()
    elif up is not None:
        txd = _read(up)
        prd = _read(up2) if up2 is not None else None
        auto = dr.map_columns(txd.columns)
        with st.expander("Column mapping (change it if the guess is wrong)", expanded=False):
            cols = ["(none)"] + list(txd.columns)
            ov = {}
            for k in ("household_id", "date", "week", "amount", "category", "product_id", "basket_id"):
                pick = st.selectbox(k, cols, index=cols.index(auto[k]) if k in auto else 0, key=f"map_{k}")
                if pick != "(none)":
                    ov[k] = pick
        result = dr.assess(txd, prd, ov)
    if result:
        (st.success if result["verdict"] == "READY" else st.warning if result["verdict"] == "PARTIAL" else st.error)(f"**{result['verdict']}**")
        explain(it.interpret_readiness(result))
        if result["facts"]:
            f = result["facts"]
            m1, m2, m3 = st.columns(3)
            m1.metric("Rows", f"{f['rows']:,}")
            m2.metric("Customers", f"{f['customers']:,}")
            m3.metric("Weeks of history", f"{f['weeks']}")
        st.dataframe(pd.DataFrame(result["checks"]).drop(columns=["fix"]).astype(str), hide_index=True, width="stretch")
        if result["proposed_temporal"]:
            t = result["proposed_temporal"]
            st.markdown(f"**Time split the data supports ({t['design']} design):** train cut-offs {t['train_cutoffs']}, validation {t['validation_cutoff']}, calibration {t['calibration_cutoff']}, test {t['test_cutoff']}, scoring {t['scoring_cutoff']}.")
        if result["categories"]:
            cdf = pd.DataFrame(result["categories"]).head(20)
            st.markdown("**Categories (top 20 by buyers in the label window)**")
            st.dataframe(cdf[["category", "buyers_in_label_window", "penetration", "excluded_by_guardrail", "qualifies"]].style.format({"penetration": "{:.0%}", "buyers_in_label_window": "{:,.0f}"}), hide_index=True, width="stretch")
        c = result["can_do"]
        st.markdown(f"**What the project can do:** who buys next: {'yes' if c['propensity_model_who_buys_next'] else 'no'} · effect of an offer: "
                    f"{'yes (treatment column found)' if c['uplift_or_coupon_effect'] else 'no (needs a randomized test)'} · profit or ROI: no ({c['profit_or_roi_why']}) · decision card: {'yes' if c['marketing_decision_card'] else 'no'}")
        for fx in result["fixes"]:
            st.info(fx)
        st.download_button("Download the readiness report (JSON)", json.dumps(result, indent=1, default=str).encode("utf-8"), "dataset_readiness.json", "application/json")

# ------------------------------------------------------------------ 9 strategy and plan
with tab_plan:
    from mi.decision import strategy_plan as sp
    from mi.config import load_config as _lc

    st.subheader("Marketing strategy and 13-week plan")
    st.caption("Built on the decision card, so it cannot contradict its economics. Objective, targeting, positioning, strategy by segment, marketing mix, roadmap with owners and approval gates, "
               "budget, KPIs, message drafts, risks and what the client must provide. Nothing is sent, spent or published; approval stays PENDING_HUMAN.")

    @st.cache_data
    def _plans():
        cfg = _lc()
        return {c: sp.build_plan(c, cfg) for c in cfg["categories"]}

    plans = _plans()
    pc = st.selectbox("Plan for", list(plans), index=list(plans).index("COFFEE"), key="plan_cat")
    plan = plans[pc]
    (st.success if plan["decision_from_card"].startswith("TEST") else st.warning)(f"**{plan['decision_from_card']}** — {plan['headline']}")
    if plan["checker"]:
        st.error("The checker found problems: " + "; ".join(plan["checker"]))
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Target segment", (plan["stp"]["targeting"]["primary"] or "none").replace("_", " ").title())
    a2.metric("Test arms", len(plan["budget"]["arms"]))
    a3.metric("Estimated test cost (USD, assumed)", f"{plan['budget']['total_test_usd']:,.0f}")
    a4.metric("Approval", plan["approval"]["state"])
    st.markdown(sp.to_markdown(plan).split("\n", 4)[-1])
    e1, e2 = st.columns(2)
    stem = pc.lower().replace("/", "_").replace(" ", "_")
    e1.download_button("Download the plan (Markdown)", sp.to_markdown(plan).encode("utf-8"), f"marketing_plan_{stem}.md", "text/markdown")
    e2.download_button("Download the plan (JSON)", json.dumps(plan, indent=1, default=float).encode("utf-8"), f"marketing_plan_{stem}.json", "application/json")
