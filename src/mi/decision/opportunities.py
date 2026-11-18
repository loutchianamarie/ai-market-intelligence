"""Customer and product opportunity analysis from REAL transactions -> evidence-to-action cards + strategy comparison.

Observed (2017 panel): penetration by half-year, return-to-category, lapsing cohort size and turnover,
basket cross-sell lift validated on a later time window against a popularity benchmark, private-label mix,
promotion context. Nothing here infers unmet need, competitor share, stock-outs, margin, satisfaction or
individual persuasion; those stay HYPOTHESES with a named research step.

Usage: python -m mi.decision.opportunities -> reports/opportunities.json, docs/opportunity_cards.md
"""
from __future__ import annotations

import json
import math
import sys

import numpy as np
import pandas as pd

from mi.config import load_config
from mi.ingest.load import load
from mi.paths import REPORTS, ROOT
from mi.seo.geo import geo_pending_phrase


def _geo_n() -> int:
    """GEO answers actually logged (read from the generated audit; never a typed number)."""
    p = REPORTS / "seo_geo_audit.json"
    try:
        return int(json.loads(p.read_text(encoding="utf-8", errors="replace")).get("answers_logged", 0)) if p.exists() else 0
    except ValueError:
        return 0

H1, H2 = (1, 26), (27, 53)


def _ci_prop(k, n):
    p = k / n if n else float("nan")
    se = math.sqrt(p * (1 - p) / n) if n else float("nan")
    return p, [p - 1.96 * se, p + 1.96 * se]


def category_facts(t: pd.DataFrame, cats) -> list[dict]:
    rows = []
    hh_all = t.household_id.nunique()
    for c in cats:
        g = t[t.product_category == c]
        a = set(g[g.week.between(*H1)].household_id)
        b = set(g[g.week.between(*H2)].household_id)
        ret, ret_ci = _ci_prop(len(a & b), len(a))
        wk = g.groupby("household_id").week.apply(lambda w: np.diff(np.sort(w.unique())))
        gaps = np.concatenate([x for x in wk if len(x)]) if len(wk) else np.array([])
        priv = lambda d: float(d.sales_value[d.brand == "Private"].sum() / d.sales_value.sum())  # noqa: E731
        rows.append({"category": c, "households_year": int(g.household_id.nunique()), "penetration_year": round(g.household_id.nunique() / hh_all, 4),
                     "buyers_H1": len(a), "buyers_H2": len(b), "buyer_change_H2_vs_H1": round(len(b) / max(1, len(a)) - 1, 4),
                     "return_to_category_H1_to_H2": round(ret, 4), "return_ci95": [round(x, 4) for x in ret_ci],
                     "median_weeks_between_purchase_weeks": float(np.median(gaps)) if len(gaps) else None,
                     "private_label_sales_share_H1": round(priv(g[g.week.between(*H1)]), 4), "private_label_sales_share_H2": round(priv(g[g.week.between(*H2)]), 4),
                     "sales_value_year": round(float(g.sales_value.sum()), 2)})
    return rows


def cross_sell(t: pd.DataFrame, cats, min_support=300) -> list[dict]:
    """Lift of B given A at basket level; fit on H1, validated on H2; benchmark = attaching the most popular other category."""
    b = t[t.product_category.isin(cats)][["basket_id", "week", "product_category"]].drop_duplicates()
    out = []
    halves = {}
    for name, (lo, hi) in {"H1": H1, "H2": H2}.items():
        x = b[b.week.between(lo, hi)]
        m = pd.crosstab(x.basket_id, x.product_category).clip(upper=1)
        n_all = t[t.week.between(lo, hi)].basket_id.nunique()        # all baskets, incl. those with none of the 8
        halves[name] = (m, n_all)
    for A in cats:
        for B in cats:
            if A == B:
                continue
            r = {"A": A, "B": B}
            ok = True
            for name, (m, n_all) in halves.items():
                if A not in m or B not in m:
                    ok = False
                    break
                nA = int(m[A].sum())
                nAB = int((m[A] & m[B]).sum())
                pB = m[B].sum() / n_all
                pBA, ci = _ci_prop(nAB, nA)
                pop = m.drop(columns=[A]).sum().idxmax()
                r[name] = {"baskets_with_A": nA, "baskets_A_and_B": nAB, "P(B|A)": round(pBA, 4), "P(B)": round(float(pB), 4),
                           "lift": float(round(pBA / pB, 3)) if pB else None, "lift_ci95": [float(round(ci[0] / pB, 3)), float(round(ci[1] / pB, 3))] if pB else None,
                           "popularity_benchmark": pop, "P(pop|A)": round(float((m[A] & m[pop]).sum() / nA), 4) if nA else None}
            if not ok or r["H1"]["baskets_A_and_B"] < min_support:
                continue
            h2 = r["H2"]
            r["survives_held_out"] = bool(h2["lift_ci95"][0] > 1)
            r["beats_popularity_benchmark_H2"] = bool(h2["P(B|A)"] > h2["P(pop|A)"]) if r["H1"]["popularity_benchmark"] != B else None
            out.append(r)
    return sorted(out, key=lambda r: -r["H1"]["lift"])


def cohort_by_category(cats) -> dict:
    from mi.model.features import build_cutoff, prepare
    cfg = load_config()
    t = cfg["temporal"]
    prep = prepare(load("transactions"), load("products"), cats)
    red, camp, cd = load("coupon_redemptions"), load("campaigns"), load("campaign_descriptions")
    a = build_cutoff(prep, 49, t["lookback_weeks"], t["horizon_weeks"], red, camp, cd, with_label=False)
    b = build_cutoff(prep, 53, t["lookback_weeks"], t["horizon_weeks"], red, camp, cd, with_label=False)
    out = {}
    for c in cats:
        s49 = set(a[(a.product_category == c) & (a.segment == "LAPSING")].household_id)
        s53 = set(b[(b.product_category == c) & (b.segment == "LAPSING")].household_id)
        seg = b[b.product_category == c].segment.value_counts().to_dict()
        out[c] = {"segments_at_53": {k: int(v) for k, v in seg.items()}, "lapsing_53": len(s53),
                  "lapsing_new_vs_49": round(len(s53 - s49) / max(1, len(s53)), 3)}
    return out


def cards(facts, xs, coh, promo, port, dev) -> list[dict]:
    f = {r["category"]: r for r in facts}
    fp = f["FROZEN PIZZA"]
    survivors = [r for r in xs if r["survives_held_out"] and r.get("beats_popularity_benchmark_H2")]
    top_x = survivors[0] if survivors else None
    declining = min(facts, key=lambda r: r["buyer_change_H2_vs_H1"])
    plan = {p["plan_id"]: p for p in port.get("ranked_actions", [])}
    fp_net = next((v["net_base"] for k, v in plan.items() if k.startswith("FROZEN PIZZA/LAPSING/digital")), None)
    C = []
    C.append({"id": "C1", "title": "Frozen Pizza / lapsing / digital coupon (REJECTED for funding)", "strategy_class": "coupon / paid contact",
              "segment": {"panel_households_lapsing_at_53": coh["FROZEN PIZZA"]["lapsing_53"], "reachability": "UNKNOWN (consent, offer mechanics)",
                          "substantial": "UNKNOWN at a real company (7,308 is ASSUMED)"},
              "observed": [f"return to category H1→H2 {fp['return_to_category_H1_to_H2']:.0%} of H1 buyers",
                           f"{coh['FROZEN PIZZA']['lapsing_new_vs_49']:.0%} of the lapsing cohort is new each 4 weeks",
                           f"{promo.get('FROZEN PIZZA', {}).get('sales_share_on_display_or_mailer_covered', float('nan')):.0%} of category sales occur while on display or in the mailer (association)",
                           f"model ranks lapsing buyers better than recency (AP 0.42 vs 0.35), but ranking ≠ persuasion"],
              "counterevidence": ["every modelled coupon plan loses at base (best Frozen Pizza plan " + (f"{fp_net:+,.0f}" if fp_net is not None else "n/a") + " per 4-week cycle, assumed scale)",
                                  "flips only under joint changes (e.g., manufacturer-funded coupon + larger reachable pool), none confirmed"],
              "hypothesized_need": "an easy dinner restarted after a lapse (HYPOTHESIS)",
              "positioning": "the easy dinner you already like, back on your list (to test, not to publish)",
              "four_ps": {"Product": "as is", "Price": "coupon only if price is the barrier", "Place": "check stock/pickup first", "Promotion": "reminder before discount"},
              "discriminating_evidence": ["interviews: price vs habit vs stock vs switching", "who funds the coupon", "consented pool size", "randomized response"],
              "success_metric": "incremental contribution per randomized household above the rollout hurdle (pilot analyzer)",
              "evidence_level": "OBSERVED behaviour + ASSUMED economics", "recommendation": "do not fund now; research first"})
    if top_x:
        h2 = top_x["H2"]
        C.append({"id": "C2", "title": f"Basket attachment: {top_x['A']} → {top_x['B']}", "strategy_class": "place / merchandising (non-discount)",
                  "segment": {"baskets_with_A_H2": h2["baskets_with_A"], "reachability": "in-store placement or app 'goes well with' module; no individual contact needed"},
                  "observed": [f"lift {top_x['H1']['lift']} (H1) and {h2['lift']} (H2, CI {h2['lift_ci95']}) — survives the held-out half",
                               f"P({top_x['B']}|{top_x['A']}) {h2['P(B|A)']:.1%} vs popularity benchmark {h2['popularity_benchmark']} {h2['P(pop|A)']:.1%} in H2"],
                  "counterevidence": ["co-purchase can reflect shared shopping missions (association, not causation)",
                                      f"only {len(survivors)} of {len(xs)} tested pairs both survive the held-out half and beat simply suggesting the most "
                                      f"popular category; here the margin is {100 * (h2['P(B|A)'] - h2['P(pop|A)']):.2f} pp, i.e. negligible",
                                      "most basket 'lift' among these categories reflects large shopping trips, not specific affinity",
                                      "no data on whether adjacency or a bundle would add incremental baskets"],
                  "hypothesized_need": "convenience: complete a meal/occasion in one trip (HYPOTHESIS)",
                  "positioning": f"{top_x['B'].lower()} that goes with your {top_x['A'].lower()}",
                  "four_ps": {"Product": "none", "Price": "no discount needed", "Place": "adjacency / secondary display / app pairing", "Promotion": "in-store or in-app suggestion"},
                  "discriminating_evidence": ["store placement test with a holdout of stores (operations validation)", "interviews on shopping missions"],
                  "success_metric": f"incremental share of {top_x['A']} baskets that also contain {top_x['B']} vs control stores",
                  "evidence_level": "OBSERVED association, WEAK (negligible margin over a popularity suggestion); effect UNKNOWN",
                  "recommendation": "low priority: weak evidence; consider only as a zero-cost app 'goes well with' default after operations sign-off"})
    C.append({"id": "C3", "title": f"{declining['category']}: shrinking buyer base", "strategy_class": "product / place investigation (non-discount)",
              "segment": {"buyers_H1": declining["buyers_H1"], "buyers_H2": declining["buyers_H2"], "reachability": "assortment/stock review; no contact needed"},
              "observed": [f"buyers {declining['buyer_change_H2_vs_H1']:+.1%} H2 vs H1 while most categories grew",
                           f"return to category {declining['return_to_category_H1_to_H2']:.0%}; private label {declining['private_label_sales_share_H1']:.0%}→{declining['private_label_sales_share_H2']:.0%} (stable)"],
              "counterevidence": ["seasonality cannot be separated with one year of data", "no stock, price-list or competitor data"]
                                 + _trend_checks(declining["category"]),
              "hypothesized_need": "availability / assortment fit (HYPOTHESIS: could equally be seasonal)",
              "positioning": "n/a until the barrier is known",
              "four_ps": {"Product": "assortment review", "Price": "check price moves (no price list in data)", "Place": "stock-out / shelf check", "Promotion": "none until diagnosed"},
              "discriminating_evidence": ["operations: stock-out and assortment changes in H2", "interviews with lapsed buyers", "second year of data for seasonality"],
              "success_metric": "buyers per 4 weeks returns to H1 level after the fix (vs same weeks last year when available)",
              "evidence_level": "OBSERVED trend; cause UNKNOWN", "recommendation": "operational investigation; no spend"})
    C.append({"id": "C4", "title": "Discovery content for the public analogue (SEO/GEO)", "strategy_class": "content / discovery",
              "segment": {"reachability": "public web and AI assistants; not linkable to the anonymous panel"},
              "observed": [f"{_geo_n()}/20 assistant answers collected" + (" (two Claude models, not ChatGPT or Gemini)" if _geo_n() else "") + "; no Search Console data"],
              "counterevidence": ["a mention in a small prompt panel does not show reach, traffic or conversion"],
              "hypothesized_need": "shoppers asking how to save on frozen pizza/coffee may not find the retailer's offers (HYPOTHESIS)",
              "positioning": "clear, factual answers to buyer questions",
              "four_ps": {"Product": "none", "Price": "none", "Place": "owned pages / listings", "Promotion": "content where cited sources are"},
              "discriminating_evidence": ["the GEO audit (20 answers when complete)", "Search Console impressions/clicks for owned pages (if a real site owner)"],
              "success_metric": "mention/recommendation rate in a re-run panel AND owned-page search clicks (separately)",
              "evidence_level": "PENDING" if not _geo_n() else "OBSERVED answers (Claude models only); no traffic or conversion evidence",
              "recommendation": "collect evidence first; zero cost to collect" if not _geo_n() else "low-cost content action only where the audit shows a gap; repeat the panel in ChatGPT and Gemini before claiming anything about them"})
    C.append({"id": "C0", "title": "Do nothing now / research first", "strategy_class": "no action",
              "observed": ["no modelled coupon plan beats doing nothing at base assumptions"], "evidence_level": "decision rule",
              "recommendation": "default until a card's discriminating evidence arrives"})
    return C


def _trend_checks(category) -> list[str]:
    """Robustness facts from mi.decision.trend_check (equal windows, attrition, coverage, promotions)."""
    p = REPORTS / f"trend_check_{category.lower().replace('/', '_').replace(' ', '_')}.json"
    if not p.exists():
        return ["robustness check not run (python -m mi.decision.trend_check)"]
    t = json.loads(p.read_text())
    me = next(r for r in t["equal_windows_all_categories"] if r["category"] == category)
    c, cp = t["composition"], t.get("coverage_and_promotions", {})
    out = [f"robustness: on equal 25-week windows buyers change {me['change']:+.1%} (buyer rate {me['buyer_rate_A']:.1%} -> {me['buyer_rate_B']:.1%} of active households)",
           f"not panel attrition: {c['lost_still_shopping_in_B']} of {c['lost']} lost buyers still shop in the later window; active households {c['active_households_A']:,} -> {c['active_households_B']:,}"]
    if isinstance(cp, dict):
        out.append(f"not a promotion or coverage change: promoted product-store rows/week {cp['promoted_product_store_rows_per_week_A']:,} -> {cp['promoted_product_store_rows_per_week_B']:,}; "
                   f"sales share on promotion {cp['A']['sales_share_on_promotion_covered']:.1%} -> {cp['B']['sales_share_on_promotion_covered']:.1%}; "
                   f"lines in covered stores {cp['A']['lines_in_covered_stores']:.1%} -> {cp['B']['lines_in_covered_stores']:.1%}")
    out.append("verdict: a SIGNAL for an operations check, not a diagnosed cause")
    return out


def strategy_comparison(cards_) -> list[dict]:
    rank = {"no action": (1, "n/a", "$0"), "place / merchandising (non-discount)": (3, "LOW-MEDIUM: association barely beats a popularity suggestion", "not modelled (no causal data)"),
            "product / place investigation (non-discount)": (2, "HIGH: an operations check is cheap", "not modelled"),
            "content / discovery": (3, "MEDIUM: GEO audit + analytics", "not modelled"),
            "coupon / paid contact": (4, "LOW at current cost: decision-grade test infeasible in the assumed pool", "negative at base; positive only under unconfirmed joint changes")}
    return [{"card": c["id"], "strategy_class": c["strategy_class"], "feasibility_rank_now": rank[c["strategy_class"]][0],
             "information_value": rank[c["strategy_class"]][1], "assumed_financial_upside": rank[c["strategy_class"]][2],
             "evidence_level": c["evidence_level"]} for c in cards_]


def run(write=True) -> dict:
    cfg = load_config()
    cats = cfg["categories"]
    tx, pr = load("transactions"), load("products")
    t = tx.merge(pr[["product_id", "product_category", "brand"]], on="product_id", how="left")
    facts = category_facts(t, cats)
    xs = cross_sell(t, cats)
    coh = cohort_by_category(cats)
    pa = REPORTS / "promotions_audit.json"
    promo = json.loads(pa.read_text())["join"]["by_category"] if pa.exists() else {}
    port = json.loads((REPORTS / "portfolio.json").read_text())
    C = cards(facts, xs, coh, promo, port, None)
    res = {"status": "OBSERVED behaviour (2017 panel) + labelled hypotheses; no ROI is claimed for non-coupon actions",
           "category_facts": facts, "cross_sell_validated": [r for r in xs if r["survives_held_out"]][:10],
           "cross_sell_all_pairs_tested": len(xs), "cohorts": coh, "cards": C, "strategy_comparison": strategy_comparison(C),
           "what_to_learn_next": ["who funds a coupon and the consented pool size (flip the coupon economics or not)",
                                  "interviews: barrier for lapsed frozen-pizza buyers",
                                  "operations: stock/assortment for the shrinking category; feasibility of an adjacency test",
                                  geo_pending_phrase() + " before any content work"],
           "unavailable_metrics": "market size, LTV, CAC, ROAS: numerator/denominator/attribution/costs not in the data"}
    if write:
        (REPORTS / "opportunities.json").write_text(json.dumps(res, indent=2, default=float))
        (ROOT / "docs" / "opportunity_cards.md").write_text(to_md(res), encoding="utf-8")
    return res


def to_md(r) -> str:
    L = ["# Opportunity cards (evidence → action)", "", r["status"], "", "## Category facts (2017 panel)", "",
         "| category | buyers H1 → H2 | change | return to category (95% CI) | median weeks between purchase weeks | private label H1 → H2 |", "|---|---|---:|---|---:|---|"]
    for f in r["category_facts"]:
        L.append(f"| {f['category']} | {f['buyers_H1']:,} → {f['buyers_H2']:,} | {f['buyer_change_H2_vs_H1']:+.1%} | {f['return_to_category_H1_to_H2']:.1%} "
                 f"({f['return_ci95'][0]:.1%}–{f['return_ci95'][1]:.1%}) | {f['median_weeks_between_purchase_weeks']} | {f['private_label_sales_share_H1']:.1%} → {f['private_label_sales_share_H2']:.1%} |")
    L += ["", f"## Cross-sell pairs surviving the held-out half (of {r['cross_sell_all_pairs_tested']} tested with ≥300 H1 co-baskets)", "",
          "| A → B | lift H1 | lift H2 (95% CI) | P(B|A) H2 | popularity benchmark P(pop|A) H2 |", "|---|---:|---|---:|---|"]
    for x in r["cross_sell_validated"][:8]:
        L.append(f"| {x['A']} → {x['B']} | {x['H1']['lift']} | {x['H2']['lift']} ({x['H2']['lift_ci95'][0]}–{x['H2']['lift_ci95'][1]}) | {x['H2']['P(B|A)']:.1%} | "
                 f"{x['H2']['popularity_benchmark']} {x['H2']['P(pop|A)']:.1%} |")
    for c in r["cards"]:
        L += ["", f"## {c['id']}. {c['title']}", f"- **Strategy class:** {c['strategy_class']} · **Evidence level:** {c['evidence_level']}"]
        if c.get("segment"):
            L.append(f"- **Segment / reach:** {c['segment']}")
        L += [f"- **Observed:** " + "; ".join(c["observed"])]
        for k, lab in (("counterevidence", "Counterevidence"), ("discriminating_evidence", "Evidence that would decide")):
            if c.get(k):
                L.append(f"- **{lab}:** " + "; ".join(c[k]))
        for k, lab in (("hypothesized_need", "Hypothesized need"), ("positioning", "Positioning (to test)"), ("success_metric", "Success metric")):
            if c.get(k):
                L.append(f"- **{lab}:** {c[k]}")
        if c.get("four_ps"):
            L.append("- **4 Ps:** " + "; ".join(f"{k}: {v}" for k, v in c["four_ps"].items()))
        L.append(f"- **Recommendation:** {c['recommendation']}")
    L += ["", "## Strategy classes compared (feasibility and information value ranked separately from assumed upside)", "",
          "| card | class | feasibility rank now | information value | assumed financial upside | evidence |", "|---|---|---:|---|---|---|"]
    L += [f"| {s['card']} | {s['strategy_class']} | {s['feasibility_rank_now']} | {s['information_value']} | {s['assumed_financial_upside']} | {s['evidence_level']} |" for s in r["strategy_comparison"]]
    L += ["", "## What to learn next", ""] + [f"{i + 1}. {x}" for i, x in enumerate(r["what_to_learn_next"])]
    L += ["", f"Unavailable: {r['unavailable_metrics']}."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    r = run()
    for f in r["category_facts"]:
        print(f["category"], f["buyers_H1"], f["buyers_H2"], f["buyer_change_H2_vs_H1"], f["return_to_category_H1_to_H2"])
    for x in r["cross_sell_validated"][:5]:
        print(x["A"], "->", x["B"], x["H1"]["lift"], x["H2"]["lift"], x["H2"]["lift_ci95"], x.get("beats_popularity_benchmark_H2"))
    print([c["id"] for c in r["cards"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
