"""One decision card per category: who, what to do for each segment, whether it pays, how to test it, and what is unknown.

The project already computes the pieces (model scores, segment economics in `buyer_outcomes.coupon_action`, validated cross-sell in
`opportunities.json`, the discovery audit, test-size helpers). This module composes them into ONE marketing decision and refuses to
state anything the pieces do not support. Nothing is sent, spent or published: the approval state is always PENDING_HUMAN.

Decision rule (stated on every card, so a reader can disagree with it):
  for each segment, using the assumed response range (low / base / high) and the observed spend per buyer:
    PAYS (assumed, robust)    net is positive even when every assumption is unfavourable at once (portfolio "low")
    PAYS IN THE BASE CASE     positive under base assumptions                          -> run it as a randomized test, then scale
    PAYS ONLY IF OPTIMISTIC   positive only when every assumption is favourable at once -> learn first: a randomized holdout test
    DOES NOT PAY              not positive even then                                    -> no paid offer; free actions only
  recommendation = a randomized test of the paid offer only if some segment is positive in the base case AND consent and stock are confirmed; otherwise the best free action
  plus a learn-first test on the segment that needs the smallest multiple of the assumed response to break even.

Usage:  python -m mi.decision.decision_card --category COFFEE      # one card -> reports/decision_cards/COFFEE.json + .md
        python -m mi.decision.decision_card --all                  # all categories + a ranking table
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import pandas as pd

from mi.config import load_config
from mi.decision import buyer_outcomes as bo
from mi.outcome.learning import sample_size
from mi.paths import PROCESSED, REPORTS

SCHEMA = "decision_card.v1"
CARD_DIR = REPORTS / "decision_cards"
PAID_SEGMENTS = ["REGULAR", "RECENT_LIGHT", "LAPSING", "ACTIVE_NONBUYER"]
TAGS = {"OBSERVED", "MODEL ESTIMATE", "SCENARIO", "ASSUMPTION", "UNKNOWN", "PUBLISHED_REFERENCE"}

# what each segment is, and the free (owned-channel) action a marketer would take first. Cost of a message is the assumed contact cost.
PLAYBOOK = {
    "REGULAR": {"meaning": "buys the category in 3+ of the last 12 weeks", "goal": "protect and grow basket",
                "free_action": "No discount: these households buy anyway, so a coupon mostly gives margin away. Recognise loyalty and cross-sell a partner category.",
                "kpi": "category purchase frequency and basket size; discount cost per buyer stays at zero"},
    "RECENT_LIGHT": {"meaning": "bought 1-2 times in 12 weeks, at least once in the last 4", "goal": "turn light buyers into regulars",
                     "free_action": "Replenishment reminder and recipe or usage content in owned channels before any discount; confirm the product is in stock.",
                     "kpi": "share who buy again within 4 weeks"},
    "LAPSING": {"meaning": "bought earlier in the 12 weeks, nothing in the last 4", "goal": "win back before they switch",
                "free_action": "Check availability, assortment and price versus competitors first (a reason to stop buying is often stock or range), then a reminder message.",
                "kpi": "distinct buyers back within 4 weeks, versus a randomized no-message holdout"},
    "ACTIVE_NONBUYER": {"meaning": "shops often but has not bought the category in 12 weeks", "goal": "awareness and trial",
                        "free_action": "Educational content and placement near related categories; no paid offer until a test shows response.",
                        "kpi": "first-time category buyers in 4 weeks, versus holdout"},
    "LOW_ACTIVITY": {"meaning": "few baskets in 12 weeks", "goal": "do not spend here",
                     "free_action": "General brand communication only; no category action.",
                     "kpi": "none (no action)"},
}


def _fmt(v, unit):
    if v is None:
        return "UNKNOWN"
    if unit == "usd":
        return f"{v:,.0f}"
    if unit == "usd2":
        return f"{v:,.2f}"
    if unit == "share":
        return f"{100 * v:.0f}%"
    if unit == "x":
        return f"{v:.1f}"
    if unit == "x3":
        return f"{v:.3f}"
    return f"{v:,.0f}"


_CACHE: dict = {}


def _universes(cfg: dict) -> dict:
    """The portfolio engine under low / base / high assumptions (all assumptions move together, exactly as in reports/portfolio.json)."""
    if "u" not in _CACHE:
        from mi.decision.optimizer import Universe, load_inputs
        from mi.decision.scenario import assumptions_from_config
        scores, econ, _ = load_inputs()
        _CACHE["u"] = {c: Universe(scores, econ, cfg, assumptions_from_config(cfg, c)) for c in ("low", "base", "high")}
    return _CACHE["u"]


def _plan(cfg: dict, category: str, seg: str, channel: str = "digital_coupon") -> dict | None:
    U = _universes(cfg)
    cid = f"{category}|{seg}|{channel}|ALL"
    out = {}
    for case, u in U.items():
        ids = [c["candidate_id"] for c in u.cands]
        if cid not in ids:
            return None
        out[case] = u.evaluate([ids.index(cid)])["components"][0]
    return out


class _Metrics:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, mid, label, value, unit, tag, source):
        assert tag in TAGS, tag
        self.items.append({"id": mid, "label": label, "value": value, "unit": unit, "text": _fmt(value, unit), "tag": tag, "source": source})
        return self.items[-1]["text"]


def build_card(category: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    if category not in cfg["categories"]:
        raise ValueError(f"{category!r} is not one of the modelled categories {cfg['categories']}")
    sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
    rep = json.loads((REPORTS / "model_report.json").read_text(encoding="utf-8"))
    opp = json.loads((REPORTS / "opportunities.json").read_text(encoding="utf-8")) if (REPORTS / "opportunities.json").exists() else {}
    d = sc[sc.product_category == category]
    M = _Metrics()
    T, R = rep["test"]["model_" + rep["selected_model"]], rep["test"]["rule_repeat"]
    boot = rep["bootstrap_model_minus_rule_repeat"]
    M.add("m_ap", "Model average precision (locked test)", T["AP"], "x3", "OBSERVED", "reports/model_report.json")
    M.add("m_ap_rule", "Repeat-rule average precision", R["AP"], "x3", "OBSERVED", "reports/model_report.json")

    # ---------------------------------------------------------------- 1 who: segments
    seg_rows = []
    for seg, g in d.groupby("segment"):
        seg_rows.append({"segment": seg, "households": int(len(g)), "mean_chance_of_buying": float(g.p_model.mean()),
                         "expected_buyers_4w": float(g.p_model.sum()), "meaning": PLAYBOOK.get(seg, {}).get("meaning", "")})
    segs = pd.DataFrame(seg_rows).set_index("segment")
    total_hh, total_exp = int(len(d)), float(d.p_model.sum())
    M.add("m_hh", f"Households scored for {category}", total_hh, "count", "OBSERVED", "data/processed/scores_latest.parquet")
    M.add("m_exp", "Expected buyers in the next 4 weeks (all scored households)", total_exp, "count", "MODEL ESTIMATE", "calibrated model scores")

    # ---------------------------------------------------------------- 2 options: economics per paid segment
    options, best = [], None
    for seg in PAID_SEGMENTS:
        if seg not in segs.index:
            continue
        pl = _plan(cfg, category, seg)
        if pl is None:
            continue
        nets = {k: float(pl[k]["net"]) for k in ("low", "base", "high")}
        base = pl["base"]
        ca = bo.coupon_action(cfg, category, seg, "digital_coupon")
        add = ca["additional_buyers_reachable_hypothetical"]
        be_dq, base_dq = base["break_even_dq"], base["dq"]
        multiple = (be_dq / base_dq) if (be_dq and base_dq) else None
        verdict = ("PAYS (assumed, robust)" if nets["low"] > 0 else "PAYS IN THE BASE CASE" if nets["base"] > 0
                   else "PAYS ONLY IF OPTIMISTIC" if nets["high"] > 0 else "DOES NOT PAY")
        k = seg.lower()
        M.add(f"net_base_{k}", f"Scenario net per 4-week cycle, {seg} digital coupon (base assumptions)", nets["base"], "usd", "SCENARIO", "optimizer.Universe.evaluate")
        M.add(f"net_low_{k}", "... all assumptions unfavourable", nets["low"], "usd", "SCENARIO", "optimizer.Universe.evaluate")
        M.add(f"net_high_{k}", "... all assumptions favourable", nets["high"], "usd", "SCENARIO", "optimizer.Universe.evaluate")
        if multiple:
            M.add(f"mult_{k}", f"Response needed to break even, as a multiple of the assumed response ({seg})", multiple, "x", "SCENARIO", "break-even / assumed response")
        options.append({
            "option": f"{seg.replace('_', ' ').title()}: digital coupon", "segment": seg, "kind": "paid", "verdict": verdict,
            "households_in_panel": int(segs.loc[seg, "households"]), "contribution_usd": nets,
            "net_per_1000_contacted_before_setup": base["net_per_1000_contacted_before_fixed"], "cost_usd_base": base["cost"],
            "additional_buyers_assumed": {"low": add["low"], "base": add["base"], "high": add["high"]},
            "break_even_additional_buyers": ca["break_even_additional_buyers"], "needed_response_multiple": round(multiple, 2) if multiple else None,
            "assumed_response_points": ca["additional_buyers_reachable_hypothetical"]["dq_range_points"],
            "status": "SCENARIO: assumed response, margin, cost and company scale; low/high move all assumptions together (as in the portfolio); not measured",
            "metric_ids": [f"net_base_{k}", f"net_low_{k}", f"net_high_{k}"] + ([f"mult_{k}"] if multiple else []),
            "mean_chance_of_buying": float(segs.loc[seg, "mean_chance_of_buying"])})
    rank = {"PAYS (assumed, robust)": 0, "PAYS IN THE BASE CASE": 1, "PAYS ONLY IF OPTIMISTIC": 2, "DOES NOT PAY": 3}
    options.sort(key=lambda o: (rank[o["verdict"]], o["needed_response_multiple"] or 1e9))
    best = options[0] if options else None

    # ---------------------------------------------------------------- 3 next best action per segment
    actions = []
    pay = {o["segment"]: o for o in options}
    for seg, pb in PLAYBOOK.items():
        o = pay.get(seg)
        paid = (o["verdict"] if o else "NOT EVALUATED (no paid action for this segment)")
        actions.append({"segment": seg, "households": int(segs.loc[seg, "households"]) if seg in segs.index else 0, "goal": pb["goal"],
                        "do_now_free": pb["free_action"], "paid_offer": paid, "kpi": pb["kpi"]})

    # ---------------------------------------------------------------- 4 recommendation
    pays = [o for o in options if o["verdict"] in ("PAYS (assumed, robust)", "PAYS IN THE BASE CASE")]
    if pays:
        o = pays[0]
        decision, why = "TEST THEN SCALE", (f"The {o['segment'].lower()} digital coupon is positive in the base case under the assumptions, so run it as a "
                                              "randomized test and scale only if the measured result confirms it.")
        action = f"Randomized holdout test of the {o['segment'].lower()} digital coupon"
    elif best and best["verdict"] == "PAYS ONLY IF OPTIMISTIC":
        o = best
        decision, why = "LEARN FIRST (NO PAID SCALE-UP)", (f"No segment pays in the base case. The {o['segment'].lower()} coupon is positive only if every assumption "
                                                           "is favourable at once, so measure the real response before spending.")
        action = f"Free actions now, plus a randomized holdout test design for the {o['segment'].lower()} segment"
    else:
        o = best
        decision, why = "NO PAID OFFER", ("No coupon plan for this category pays under the assumptions, even when every assumption is favourable. "
                                          "Use free actions, check stock and range, and learn more before any paid offer.")
        action = "Free actions only: availability and range check, owned-channel reminders, content"
    focus = o["segment"] if o else None
    cond = ["Consent to contact is verified (UNKNOWN today)", "Stock is confirmed for the category (UNKNOWN today)",
            "Finance confirms margin and cost per message (ASSUMED today)", "A named person approves the exact plan"]
    reverse = ["A randomized test shows a measured response above the break-even response",
               "A manufacturer funds the coupon, or the confirmed margin is higher than assumed", "Stock or range problems are found: fix those first"]

    # ---------------------------------------------------------------- 5 test design
    test = None
    if focus:
        g = d[d.segment == focus]
        p0 = float(g.p_model.mean())
        be = o["needed_response_multiple"]
        dq_base = o["assumed_response_points"][1]
        dq_be = (be * dq_base) if be else None
        n_assumed = sample_size(min(max(p0, 0.02), 0.9), dq_base) if p0 + dq_base < 1 else None
        n_be = sample_size(min(max(p0, 0.02), 0.9), dq_be) if dq_be and p0 + dq_be < 1 else None
        out = cfg["outcome_rule"]
        if n_assumed:
            M.add("n_assumed", "Households per arm to detect the assumed response", n_assumed, "count", "SCENARIO", "learning.sample_size")
        if n_be:
            M.add("n_be", "Households per arm to detect the break-even response", n_be, "count", "SCENARIO", "learning.sample_size")
        test = {"segment": focus, "design": "randomized: eligible households split at random into message and no-message holdout (about 10-20% holdout)",
                "duration": "4 weeks of outcome after the message, plus the 28-day window in the outcome rule",
                "primary_metric": out["primary_metric"], "households_per_arm_for_assumed_response": n_assumed,
                "households_per_arm_for_break_even_response": n_be,
                "baseline_chance_of_buying": p0, "decision_rules": {"expand": out["expand_if"], "stop": out["stop_if"], "change": out["change_if"], "else": out["else"]},
                "guardrails": out["guardrails"], "status": "SCENARIO: sample sizes use the model's baseline chance and assumed response points; panel is not contactable"}

    # ---------------------------------------------------------------- 6 cross-sell (validated on held-out weeks)
    xs = []
    for r in opp.get("cross_sell_validated", []):
        if r.get("A") == category and r.get("survives_held_out"):
            xs.append({"if_buys": r["A"], "then_offer": r["B"], "lift_H1": r["H1"]["lift"], "lift_H2": r["H2"]["lift"], "lift_H2_ci95": r["H2"]["lift_ci95"],
                       "status": "OBSERVED association (basket level); not proof that promoting A causes B"})
    xs = sorted(xs, key=lambda r: -r["lift_H2"])[:3]

    # ---------------------------------------------------------------- 7 discovery link (observed audit of a public analogue)
    from mi.seo import geo
    gs = geo.geo_state()
    res = geo.analyze(geo.read_log(), geo.load_panel())
    disc = None
    if gs["complete"]:
        L = res["by_intent"]["Learn"]
        disc = {"audited_brand": gs["brand"], "status": "OBSERVED answer log of a public analogue, not this retailer", "answers": gs["answers_logged"],
                "learn": {"mentioned": L["mentioned"], "recommended": L["recommended"], "of": L["n"]},
                "reading": ("Shoppers who are still learning are not being recommended a store" if L["recommended"] == 0 and L["n"] else "Learn questions already recommend the brand"),
                "action": "Publish a factual page for the learning questions (how digital coupons work, store brand versus name brand); needs human approval; no sales effect is claimed"}

    # ---------------------------------------------------------------- 8 confidence and unknowns
    confidence = {
        "who_is_likely_to_buy": {"level": "MEDIUM-HIGH", "tag": "MODEL ESTIMATE",
                                 "basis": f"locked test average precision {T['AP']:.3f} versus {R['AP']:.3f} for the repeat rule; gain {boot['AP_diff_mean']:+.3f} "
                                          f"(95% interval {boot['AP_diff_95ci'][0]:+.3f} to {boot['AP_diff_95ci'][1]:+.3f}); history only, 2017"},
        "what_an_offer_would_do": {"level": "LOW", "tag": "UNKNOWN", "basis": "coupon exposure was not randomized; response is an assumed range"},
        "profit": {"level": "NONE", "tag": "UNKNOWN", "basis": "margin, cost, consent and stock are not confirmed; contributions are scenarios"}}
    unknowns = [{"item": "contribution margin", "status": "ASSUMED", "value": cfg["scenario"]["contribution_margin_rate"]["value"], "owner": "finance"},
                {"item": "cost per message", "status": "ASSUMED", "value": None, "owner": "CRM"},
                {"item": "consent to contact", "status": "UNKNOWN", "value": None, "owner": "legal / CRM"},
                {"item": "stock and capacity", "status": "UNKNOWN", "value": None, "owner": "operations"},
                {"item": "who funds the coupon", "status": "ASSUMED", "value": None, "owner": "merchandising"},
                {"item": "real response to an offer", "status": "UNKNOWN", "value": None, "owner": "a randomized test"}]

    # ---------------------------------------------------------------- 9 headline sentences use only registered numbers
    top = segs.sort_values("expected_buyers_4w", ascending=False)
    lead_seg = top.index[0]
    one_line = (f"{category.title()}: {_fmt(total_exp, 'count')} of {_fmt(total_hh, 'count')} scored households are expected to buy in the next 4 weeks "
                f"(model estimate); {decision.lower()}.")
    card = {
        "schema_version": SCHEMA, "case_id": cfg["case_id"], "category": category, "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scoring_cutoff_week": cfg["temporal"]["scoring_cutoff"], "data": "84.51 Complete Journey 2017 panel (anonymous; not contactable)",
        "headline": {"decision": decision, "one_line": one_line, "action": action},
        "situation": {"households_scored": total_hh, "expected_buyers_4w": total_exp, "lead_segment_by_expected_buyers": lead_seg,
                      "segments": [dict(segment=s, **r) for s, r in segs.to_dict("index").items()]},
        "options": options, "next_best_action": actions,
        "recommendation": {"decision": decision, "action": action, "segment": focus, "why": why, "conditions": cond, "would_reverse_if": reverse},
        "test_design": test, "cross_sell": xs, "discovery": disc, "marketing_mix_4ps": _four_ps(category, decision, focus, xs),
        "kpis": {"primary": cfg["outcome_rule"]["primary_metric"], "secondary": ["distinct buyers in the category", "repeat purchase within 4 weeks", "opt-out rate"],
                 "guardrails": cfg["outcome_rule"]["guardrails"]},
        "confidence": confidence, "unknowns": unknowns, "metrics": M.items,
        "decision_rule": "robust: positive even with every assumption unfavourable; base case: positive under base assumptions; only if optimistic: positive only with every assumption favourable; does not pay: never positive",
        "approval": {"state": "PENDING_HUMAN", "sandbox_only": True, "note": "Nothing is sent, spent or published by this card."}}
    card["checker"] = check_card(card)
    return card


def _four_ps(category, decision, focus, xs):
    c = category.title()
    promo = ("Reminder and content in owned channels; a paid coupon only after a randomized test" if decision != "TEST THEN SCALE"
             else "Digital coupon to the test segment with a no-message holdout")
    return {"Product": f"Confirm {c} availability and range first" + (f"; partner offer: {xs[0]['then_offer'].title()}" if xs else ""),
            "Price": "No blanket discount; a coupon only where the test shows response and the margin covers it",
            "Place": "Digital owned channels and in-store placement near related categories",
            "Promotion": promo}


# ------------------------------------------------------------------------------------------------ checker
NUM = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")
PROFIT = re.compile(r"\b(profit|profitable|revenue gained|net gain|free money)\b", re.I)
SCEN = re.compile(r"\b(not|no|never|unknown|scenario|assum\w*|if|without|until|before)\b", re.I)
CAUSAL = re.compile(r"\b(will|would|can|could)\s+(add|bring|win back|recover|lift|raise|increase|drive|generate)\b", re.I)


def _texts(card: dict) -> list[str]:
    t = [card["headline"]["one_line"], card["recommendation"]["why"], card["recommendation"]["action"]]
    t += [a["do_now_free"] for a in card["next_best_action"]] + list(card["marketing_mix_4ps"].values())
    t += card["recommendation"]["conditions"] + card["recommendation"]["would_reverse_if"]
    t += [o["status"] for o in card["options"]]
    return t


def check_card(card: dict) -> list[str]:
    """Plain-words problems; an empty list means the card passes."""
    p: list[str] = []
    if card["approval"]["state"] != "PENDING_HUMAN" or card["approval"]["sandbox_only"] is not True:
        p.append("approval must stay PENDING_HUMAN and sandbox only")
    ids = [m["id"] for m in card["metrics"]]
    if len(ids) != len(set(ids)):
        p.append("duplicate metric ids")
    for m in card["metrics"]:
        if m["tag"] not in TAGS:
            p.append(f"{m['id']}: unknown tag {m['tag']}")
        if m["tag"] == "OBSERVED" and re.search(r"scenario|assum", (m["source"] + m["label"]).lower()):
            p.append(f"{m['id']}: a scenario is tagged OBSERVED")
        if m["tag"] == "UNKNOWN" and m["value"] is not None:
            p.append(f"{m['id']}: an unknown must have no number")
    for u in card["unknowns"]:
        if u["status"] == "UNKNOWN" and u["value"] is not None:
            p.append(f"unknown {u['item']} carries a number")
    for o in card["options"]:
        if o["status"].split(":")[0] != "SCENARIO":
            p.append(f"option {o['option']} is not labelled a scenario")
        for mid in o["metric_ids"]:
            if mid not in ids:
                p.append(f"option {o['option']} refers to missing metric {mid}")
    allowed = {m["text"] for m in card["metrics"]} | {m["text"].rstrip("%") for m in card["metrics"]}
    for s in _texts(card):
        for tok in NUM.findall(s):
            bare = tok.strip("$%").replace(",", "")
            if tok.strip("$") in allowed or bare in {a.replace(",", "") for a in allowed}:
                continue
            if bare.isdigit() and int(bare) <= 60 or bare in ("2017", "10", "20"):   # small counts, weeks, percentages of a holdout
                continue
            p.append(f"number {tok} is not a registered metric: {s[:80]!r}")
        if PROFIT.search(s) and not SCEN.search(s):
            p.append(f"profit is claimed without a scenario label: {s[:80]!r}")
        if CAUSAL.search(s):
            p.append(f"a promise of effect: {s[:80]!r}")
    return p


# ------------------------------------------------------------------------------------------------ outputs
def to_markdown(c: dict) -> str:
    h = c["headline"]
    L = [f"# Decision card: {c['category'].title()}", "", f"**Decision: {h['decision']}.** {h['one_line']}", "",
         f"**Action:** {h['action']}", f"**Approval:** {c['approval']['state']} (sandbox only; nothing is sent, spent or published).", "",
         "## 1. Who (model estimate, history only)", "", "| segment | households | chance of buying | expected buyers | what it means |", "|---|---:|---:|---:|---|"]
    for s in sorted(c["situation"]["segments"], key=lambda r: -r["expected_buyers_4w"]):
        L.append(f"| {s['segment']} | {s['households']:,} | {s['mean_chance_of_buying']:.0%} | {s['expected_buyers_4w']:,.0f} | {s['meaning']} |")
    L += ["", "## 2. Does a paid offer pay? (scenario, not measured)", "", "| segment | verdict | contribution low / base / high (USD per 4 weeks) | response needed vs assumed |", "|---|---|---|---:|"]
    for o in c["options"]:
        x = o["contribution_usd"]
        L.append(f"| {o['segment']} | **{o['verdict']}** | {x['low']:,.0f} / {x['base']:,.0f} / {x['high']:,.0f} | {o['needed_response_multiple'] or 'n/a'}x |")
    L += ["", "## 3. Next best action by segment", "", "| segment | do now (free) | paid offer | KPI |", "|---|---|---|---|"]
    for a in c["next_best_action"]:
        L.append(f"| {a['segment']} | {a['do_now_free']} | {a['paid_offer']} | {a['kpi']} |")
    r = c["recommendation"]
    L += ["", "## 4. Recommendation", "", r["why"], "", "**Conditions:** " + "; ".join(r["conditions"]), "", "**Would reverse if:** " + "; ".join(r["would_reverse_if"])]
    if c["test_design"]:
        t = c["test_design"]
        L += ["", f"## 5. How to learn the real response ({t['segment']})", "", f"- Design: {t['design']}", f"- Primary metric: {t['primary_metric']}",
              (f"- Households per arm: {t['households_per_arm_for_assumed_response']:,} for the assumed response, "
              f"{t['households_per_arm_for_break_even_response']:,} for the break-even response"
              if t['households_per_arm_for_assumed_response'] and t['households_per_arm_for_break_even_response']
              else "- Households per arm: not computable for these inputs"),
              f"- Expand if: {t['decision_rules']['expand']}; stop if: {t['decision_rules']['stop']}", f"- Guardrails: {t['guardrails']}"]
    if c["cross_sell"]:
        L += ["", "## 6. Cross-sell (observed association, validated on held-out weeks)"] + [
            f"- Baskets containing {x['if_buys'].title()} also contain {x['then_offer'].title()} {x['lift_H2']:.2f} times as often as chance (95% interval {x['lift_H2_ci95'][0]:.2f} to {x['lift_H2_ci95'][1]:.2f}); an association, not proof of cause" for x in c["cross_sell"]]
    if c["discovery"]:
        d = c["discovery"]
        L += ["", "## 7. Discovery (observed audit of a public analogue)", "", f"{d['audited_brand']}: mentioned in {d['learn']['mentioned']} of {d['learn']['of']} Learn answers and recommended in "
              f"{d['learn']['recommended']}. {d['reading']}. {d['action']}."]
    L += ["", "## 8. Marketing mix", ""] + [f"- **{k}:** {v}" for k, v in c["marketing_mix_4ps"].items()]
    L += ["", "## 9. What we are sure of, and what we are not", ""] + [f"- **{k.replace('_', ' ')}:** {v['level']} ({v['tag']}). {v['basis']}" for k, v in c["confidence"].items()]
    L += ["", "**Unknown or assumed:** " + "; ".join(f"{u['item']} ({u['status']})" for u in c["unknowns"]), "", f"_Rule: {c['decision_rule']}._",
          f"_Checker: {'PASS' if not c['checker'] else 'PROBLEMS: ' + '; '.join(c['checker'])}._"]
    return "\n".join(L) + "\n"


def rank_cards(cards: list[dict]) -> pd.DataFrame:
    rows = []
    for c in cards:
        b = c["options"][0] if c["options"] else None
        rows.append({"category": c["category"], "decision": c["headline"]["decision"], "best_segment": b["segment"] if b else None,
                     "verdict": b["verdict"] if b else None, "needed_response_multiple": b["needed_response_multiple"] if b else None,
                     "net_base_usd": b["contribution_usd"]["base"] if b else None, "net_high_usd": b["contribution_usd"]["high"] if b else None,
                     "expected_buyers_4w": c["situation"]["expected_buyers_4w"]})
    return pd.DataFrame(rows).sort_values(["needed_response_multiple"], na_position="last").reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config()
    cats = cfg["categories"] if a.all or not a.category else [a.category.upper()]
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    cards = []
    for cat in cats:
        c = build_card(cat, cfg)
        cards.append(c)
        stem = cat.replace("/", "_").replace(" ", "_")
        (CARD_DIR / f"{stem}.json").write_text(json.dumps(c, indent=1, default=float, ensure_ascii=False), encoding="utf-8")
        (CARD_DIR / f"{stem}.md").write_text(to_markdown(c), encoding="utf-8")
        print(cat, "|", c["headline"]["decision"], "| checker:", "PASS" if not c["checker"] else c["checker"])
    if len(cards) > 1:
        r = rank_cards(cards)
        md = ["# Categories ranked by how close a paid offer is to paying", "", "| category | decision | best segment | verdict | response needed vs assumed | net base USD | net high USD | expected buyers (4 wk) |",
              "|---|---|---|---|---:|---:|---:|---:|"]
        for x in r.itertuples():
            md.append(f"| {x.category} | {x.decision} | {x.best_segment} | {x.verdict} | {x.needed_response_multiple:.1f}x | {x.net_base_usd:,.0f} | {x.net_high_usd:,.0f} | {x.expected_buyers_4w:,.0f} |")
        (CARD_DIR / "ranking.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        print(r.to_string(index=False))
    return 1 if any(c["checker"] for c in cards) else 0


if __name__ == "__main__":
    sys.exit(main())
