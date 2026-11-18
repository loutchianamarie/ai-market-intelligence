"""A marketing strategy and a 13-week plan per category, built on the decision card (so it can never contradict its economics or verdict).

Contents: objective, segmentation / targeting / positioning, strategy by segment, marketing mix and channels, a phased roadmap with owners,
deliverables and approval gates, a test budget, KPIs and decision rules, message drafts, risks, and what we need from the client.

Rules the plan keeps (the checker enforces them):
  - every activity that contacts households, or spends, is behind two gates: consent and stock verified (G2) and the test launch approved (G4);
  - a paid arm exists only when the card's decision allows a paid test; otherwise the test is reminder versus holdout, with no discount;
  - every number in the text is a registered metric from the card or this plan; targets are minimum worthwhile responses, never forecasts;
  - message drafts contain no price, discount, saving or number; nothing is sent, spent or published; approval is PENDING_HUMAN.

Usage:  python -m mi.decision.strategy_plan --category COFFEE     |     python -m mi.decision.strategy_plan --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

from mi.config import load_config
from mi.decision import decision_card as dc
from mi.decision.scenario import assumptions_from_config
from mi.paths import REPORTS

SCHEMA = "marketing_plan.v1"
PLAN_DIR = REPORTS / "strategy_plans"

GATES = {
    "G1": "Plan approved by a named person",
    "G2": "Consent to contact and stock confirmed (UNKNOWN today)",
    "G3": "Public content approved by a named person",
    "G4": "Test launch approved: arms, holdout and guardrails",
    "G5": "Decision meeting: expand, stop or change",
}
APPROACH = {"REGULAR": "Defend", "RECENT_LIGHT": "Nurture", "LAPSING": "Win back", "ACTIVE_NONBUYER": "Educate", "LOW_ACTIVITY": "Do not spend"}
MESSAGE_ANGLE = {
    "REGULAR": ("recognise loyalty, show what is new", "Thanks for being a regular: what is new in {c}"),
    "RECENT_LIGHT": ("make restocking easy", "Your {c} is easy to restock"),
    "LAPSING": ("a reminder that the habit is easy to pick up again", "Your usual {c}, back on your list"),
    "ACTIVE_NONBUYER": ("help choosing, no offer", "How to choose {c}: a short guide"),
}


def _act(task, owner, deliverable, kind, gates):
    return {"task": task, "owner": owner, "deliverable": deliverable, "kind": kind, "gates": gates}


def build_plan(category: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    card = dc.build_card(category, cfg)
    c = category.title()
    M = dc._Metrics()
    M.items = [dict(m) for m in card["metrics"]]                       # start from the card's registered numbers
    decision = card["headline"]["decision"]
    paid_allowed = decision != "NO PAID OFFER"
    rec = card["recommendation"]
    focus = rec["segment"]
    segs = {s["segment"]: s for s in card["situation"]["segments"]}
    opt = {o["segment"]: o for o in card["options"]}
    a = assumptions_from_config(cfg, "base")

    # ---------------------------------------------------------------- objective
    if focus:
        f = segs[focus]
        o = opt[focus]
        be_points = (o["needed_response_multiple"] or 0) * o["assumed_response_points"][1] * 100
        n_hh = M.add("p_focus_hh", f"{focus} households scored", f["households"], "count", "OBSERVED", "decision card")
        p_base = M.add("p_focus_q", f"Baseline chance of buying in 4 weeks, {focus}", f["mean_chance_of_buying"], "share", "MODEL ESTIMATE", "decision card")
        be = M.add("p_be_points", "Minimum worthwhile response, percentage points (break-even under assumed economics)", be_points, "x", "SCENARIO", "decision card break-even") if be_points else None
        objective = {
            "statement": f"Within 13 weeks, find out whether a reminder{' and a digital coupon' if paid_allowed else ''} brings back {focus.replace('_', ' ').lower()} {c} households, "
                         "measured against a randomized no-message holdout, and decide whether to scale, change or stop.",
            "baseline": f"{n_hh} {focus.replace('_', ' ').lower()} households; model estimate of their chance of buying in the next 4 weeks is {p_base}.",
            "minimum_worthwhile_response": (f"Act on a measured lift of at least {be} percentage points in the 4-week purchase rate (the break-even response under assumed economics)." if be else
                                            "No break-even response could be computed for these inputs."),
            "horizon_weeks": 13,
            "status": "PROPOSED TARGET: a hurdle to test against, not a forecast"}
    else:
        objective = {"statement": f"Within 13 weeks, fix availability and range for {c} and measure whether reminders change buying.", "baseline": "n/a",
                     "minimum_worthwhile_response": "n/a", "horizon_weeks": 13, "status": "PROPOSED TARGET: not a forecast"}

    # ---------------------------------------------------------------- STP
    seg_rows = [{"segment": s, "households": r["households"], "meaning": r["meaning"], "approach": APPROACH.get(s, ""),
                 "chance_of_buying": r["mean_chance_of_buying"], "expected_buyers_4w": r["expected_buyers_4w"]} for s, r in segs.items()]
    primary = focus
    secondary = [s for s in ("RECENT_LIGHT", "LAPSING", "ACTIVE_NONBUYER") if s != focus and s in segs]
    exclude = [{"segment": "REGULAR", "why": "They buy anyway: a discount gives margin away. Defend with recognition and cross-sell, no price offer."},
               {"segment": "LOW_ACTIVITY", "why": "Few baskets: no category action is worth its cost."}]
    base_opp = None
    try:
        base_opp = next(x for x in json.loads((REPORTS / "opportunities.json").read_text(encoding="utf-8")).get("cards", []) if x.get("title", "").lower().startswith(category.lower()))
    except (FileNotFoundError, StopIteration, ValueError):
        pass
    positioning = {"statement": (base_opp["positioning"] if base_opp and base_opp.get("positioning") else f"Your usual {c}, easy to find and easy to pick up again"),
                   "status": "HYPOTHESIS: to test with interviews and the holdout, not to publish",
                   "proof_points": ([f"Often bought together with {card['cross_sell'][0]['then_offer'].title()} (association in baskets, validated on held-out weeks)"] if card["cross_sell"] else [])}
    stp = {"segmentation": seg_rows, "targeting": {"primary": primary, "secondary": secondary, "do_not_target_with_offers": exclude}, "positioning": positioning}

    # ---------------------------------------------------------------- strategy by segment
    strategy = [{"segment": s["segment"], "approach": s["approach"], "households": s["households"], "what_we_do": next(
        (x["do_now_free"] for x in card["next_best_action"] if x["segment"] == s["segment"]), ""),
        "paid_offer_verdict": next((x["paid_offer"] for x in card["next_best_action"] if x["segment"] == s["segment"]), ""),
        "kpi": next((x["kpi"] for x in card["next_best_action"] if x["segment"] == s["segment"]), "")} for s in seg_rows]

    # ---------------------------------------------------------------- mix and channels
    contact = a.contact_cost["digital_coupon"]
    contact_t = M.add("p_contact", "Assumed cost per digital message (USD)", contact, "usd2", "ASSUMPTION", "configs/policy.json")
    channels = [
        {"channel": "In-store availability, range and placement", "role": "fix reasons for lapsing first; place beside related categories", "kind": "free", "cost": "no media cost"},
        {"channel": "Owned digital message (e-mail or app)", "role": "reminder and content, no discount", "kind": "owned", "cost": f"{contact_t} USD per message (ASSUMED)"},
        {"channel": "Content page for the learning questions (SEO/GEO)", "role": "be recommended when shoppers are still choosing", "kind": "free", "cost": "staff time; needs approval G3"}]
    if paid_allowed:
        channels.append({"channel": "Digital coupon", "role": "only in the coupon arm of the test, only for the target segment", "kind": "paid", "cost": "see budget (ASSUMED)"})
    mix = {**card["marketing_mix_4ps"], "channels": channels}

    # ---------------------------------------------------------------- test design and budget
    td = card["test_design"]
    budget = {"free_actions_usd": 0, "status": "SCENARIO: assumed contact cost, redemption, coupon value and setup; panel households stand in for the company"}
    arms = [{"arm": "Holdout (no message)", "kind": "control", "cost_usd": 0.0}]
    n_arm = td["households_per_arm_for_break_even_response"] if td else None
    if td and n_arm:
        n_t = M.add("p_n_arm", "Households per test arm (sample size for the break-even response)", n_arm, "count", "SCENARIO", "decision card test design")
        rem = n_arm * contact
        arms.append({"arm": "Reminder, no discount", "kind": "owned", "cost_usd": round(rem, 2)})
        total = a.fixed_setup + rem
        M.add("p_arm_rem", "Cost of the reminder arm (USD)", rem, "usd", "SCENARIO", "households x message cost")
        if paid_allowed:
            pl = dc._plan(cfg, category, focus)["base"]
            coupon_cost = n_arm * (contact + (pl["mean_q0"] * a.redemption_share + pl["dq"]) * pl["face"])
            arms.append({"arm": "Reminder and digital coupon", "kind": "paid", "cost_usd": round(coupon_cost, 2)})
            total += coupon_cost
            M.add("p_arm_cpn", "Cost of the coupon arm (USD)", coupon_cost, "usd", "SCENARIO", "households x (message + expected coupon cost)")
        M.add("p_setup", "Assumed fixed setup (USD)", a.fixed_setup, "usd", "ASSUMPTION", "configs/policy.json")
        M.add("p_total", "Estimated total cost of the test (USD)", total, "usd", "SCENARIO", "setup + arms")
        budget.update({"households_per_arm": n_arm, "arms": arms, "setup_usd": a.fixed_setup, "total_test_usd": round(total, 2),
                       "note": "Paid items stay blocked until gates G2 and G4 pass; nothing is spent by this plan."})
    else:
        budget.update({"households_per_arm": None, "arms": arms, "total_test_usd": 0.0, "note": "No test is sized for this category's inputs."})

    # ---------------------------------------------------------------- roadmap
    arm_text = "holdout, reminder, and reminder with coupon" if paid_allowed else "holdout and reminder only (no discount)"
    roadmap = [
        {"phase": "0. Approve", "weeks": [0, 0], "goal": "A named person approves the plan", "exit": GATES["G1"], "activities": [
            _act("Review and approve (or change) this plan", "Marketing lead (named approver)", "Signed-off plan", "free", ["G1"])]},
        {"phase": "1. Diagnose", "weeks": [1, 2], "goal": f"Find out why {c} buyers stop, and collect the inputs that are unknown", "exit": GATES["G2"], "activities": [
            _act(f"Check {c} availability, range and price against competitors", "Store operations", "Short findings note", "free", []),
            _act("Run 2 to 3 short interviews with lapsed shoppers: price, habit, stock or switching?", "Marketing analyst", "Coded interview sheet", "free", []),
            _act("Collect margin, message cost, consent pool, coupon funding and stock capacity", "Finance and CRM", "Completed client input form", "free", []),
            _act("Verify consent and stock", "CRM and operations", "Verification record", "free", ["G2"])]},
        {"phase": "2. Prepare", "weeks": [3, 4], "goal": "Design the test and the content", "exit": "Test design and drafts ready for approval", "activities": [
            _act(f"Randomize eligible {focus.replace('_', ' ').lower() if focus else 'target'} households into {arm_text}", "Analytics", "Randomized list with a fixed seed", "free", []),
            _act("Finalize message drafts (no price or discount in reminders)", "Marketing", "Approved drafts", "free", []),
            _act("Draft the factual page for the learning questions", "Content and SEO", "Draft page", "free", ["G3"]),
            _act("Set up daily guardrail monitoring: opt-outs, complaints, stock-outs", "CRM and operations", "Guardrail dashboard", "free", []),
            _act("Approve the test launch", "Marketing lead (named approver)", "Launch decision", "free", ["G4"])]},
        {"phase": "3. Run", "weeks": [5, 8], "goal": "Run the randomized test", "exit": "Four weeks of outcomes collected", "activities": [
            _act("Send reminders to the reminder arm" + (" and the coupon to the coupon arm" if paid_allowed else ""), "CRM", "Send log (outside this tool)", "paid" if paid_allowed else "owned", ["G2", "G4"]),
            _act("Keep the holdout untouched and monitor guardrails weekly", "Analytics", "Weekly guardrail note", "free", [])]},
        {"phase": "4. Read", "weeks": [9, 10], "goal": "Measure the real response", "exit": "Result with an interval", "activities": [
            _act("Analyse purchase rate and contribution per household in the 28-day window with a 95% interval", "Analytics", "Result table and chart", "free", [])]},
        {"phase": "5. Decide", "weeks": [11, 13], "goal": "Expand, change or stop", "exit": GATES["G5"], "activities": [
            _act("Apply the decision rule and update the plan with confirmed margin and cost", "Marketing lead and finance", "Decision memo", "free", ["G5"])]},
    ]

    # ---------------------------------------------------------------- kpis, messages, risks, inputs
    kpis = card["kpis"] | {"decision_rules": td["decision_rules"] if td else None, "minimum_worthwhile_response": objective["minimum_worthwhile_response"]}
    messages = [{"segment": s, "angle": ang, "draft_subject": subj.format(c=c.lower()), "status": "DRAFT: not sent; no price, discount or saving stated; needs approval"}
                for s, (ang, subj) in MESSAGE_ANGLE.items() if s in segs]
    rep = json.loads((REPORTS / "model_report.json").read_text(encoding="utf-8"))["bootstrap_model_minus_rule_repeat"]
    g1 = M.add("p_gain", "Model average-precision gain over the repeat rule", rep["AP_diff_mean"], "x3", "OBSERVED", "reports/model_report.json")
    g0 = M.add("p_gain_lo", "... 95% interval, lower", rep["AP_diff_95ci"][0], "x3", "OBSERVED", "reports/model_report.json")
    g2 = M.add("p_gain_hi", "... 95% interval, upper", rep["AP_diff_95ci"][1], "x3", "OBSERVED", "reports/model_report.json")
    gain = f"on held-out weeks the model beats the simple repeat rule by {g1} average precision (95% interval {g0} to {g2}), history only"
    risks = [
        {"risk": "Discounting people who would buy anyway", "mitigation": "No price offer to regular buyers; the coupon arm is limited to the target segment; the holdout shows the real response", "owner": "Marketing"},
        {"risk": "Promoting a product that is out of stock", "mitigation": "Stock confirmed before launch (gate G2) and a stock-out guardrail during the test", "owner": "Operations"},
        {"risk": "Contacting people without consent", "mitigation": "Only the consented pool is contacted (gate G2); opt-out rate is a stop condition", "owner": "CRM and legal"},
        {"risk": "A misleading result from seasonality or contamination", "mitigation": "Randomize inside the same weeks, keep the holdout clean, and read the interval, not the point estimate", "owner": "Analytics"},
        {"risk": "Over-trusting the model", "mitigation": f"Use it to order lists. Basis: {gain}. Success is judged on the holdout, not on the score", "owner": "Analytics"},
        {"risk": "Assumed margin, cost or response are wrong", "mitigation": "Finance confirms them in phase 1 and the break-even is recomputed before any scale-up", "owner": "Finance"},
        {"risk": "The discovery content has no proven sales effect", "mitigation": "Track visibility in assistant answers only; do not claim sales", "owner": "Content and SEO"}]
    needs = ["Consent: how many households can be contacted, and how (UNKNOWN)", "Margin on the category (ASSUMED)", "Cost per message and per coupon redemption (ASSUMED)",
             "Who funds the coupon: retailer or manufacturer (ASSUMED)", "Stock and capacity for the category (UNKNOWN)", "The campaign calendar, to avoid clashes (UNKNOWN)"]

    plan = {
        "schema_version": SCHEMA, "case_id": cfg["case_id"], "category": category, "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decision_from_card": decision, "headline": card["headline"]["one_line"], "objective": objective, "stp": stp, "strategy_by_segment": strategy,
        "marketing_mix": mix, "roadmap": roadmap, "budget": budget, "kpis": kpis, "message_drafts": messages, "discovery": card["discovery"],
        "cross_sell": card["cross_sell"], "risks": risks, "needed_from_client": needs, "gates": GATES, "metrics": M.items, "confidence": card["confidence"],
        "approval": {"state": "PENDING_HUMAN", "sandbox_only": True, "note": "Nothing is sent, spent or published by this plan."}}
    plan["checker"] = check_plan(plan)
    return plan


# ------------------------------------------------------------------------------------------------ checker
NUM = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")
BAD_COPY = re.compile(r"\d|%|\$|\b(off|free|save|saving|savings|discount|deal|cheap\w*)\b", re.I)


def _plan_texts(p: dict) -> list[str]:
    t = [p["headline"], p["objective"]["statement"], p["objective"]["baseline"], p["objective"]["minimum_worthwhile_response"], p["stp"]["positioning"]["statement"]]
    t += [s["what_we_do"] for s in p["strategy_by_segment"]] + [v for k, v in p["marketing_mix"].items() if isinstance(v, str)]
    t += [c["role"] + " " + c["cost"] for c in p["marketing_mix"]["channels"]]
    t += [r["goal"] + " " + r["exit"] for r in p["roadmap"]] + [a["task"] + " " + a["deliverable"] for r in p["roadmap"] for a in r["activities"]]
    t += [r["risk"] + " " + r["mitigation"] for r in p["risks"]] + p["needed_from_client"] + [p["budget"]["note"]]
    return t


def check_plan(p: dict) -> list[str]:
    out: list[str] = []
    if p["approval"]["state"] != "PENDING_HUMAN" or p["approval"]["sandbox_only"] is not True:
        out.append("approval must stay PENDING_HUMAN and sandbox only")
    ids = [m["id"] for m in p["metrics"]]
    if len(ids) != len(set(ids)):
        out.append("duplicate metric ids")
    paid_allowed = p["decision_from_card"] != "NO PAID OFFER"
    prev_end = -1
    for ph in p["roadmap"]:
        lo, hi = ph["weeks"]
        if lo < prev_end or hi < lo:
            out.append(f"phase {ph['phase']} weeks are out of order")
        prev_end = hi
        for a in ph["activities"]:
            if a["kind"] in ("owned", "paid") and not {"G2", "G4"} <= set(a["gates"]):
                out.append(f"'{a['task'][:50]}' contacts or spends without gates G2 and G4")
            if a["kind"] == "paid" and not paid_allowed:
                out.append("a paid activity exists although the card allows no paid offer")
    if not paid_allowed and any(x["kind"] == "paid" for x in p["budget"]["arms"]):
        out.append("a paid arm exists although the card allows no paid offer")
    if not paid_allowed and any(c["kind"] == "paid" for c in p["marketing_mix"]["channels"]):
        out.append("a paid channel exists although the card allows no paid offer")
    for m in p["message_drafts"]:
        if BAD_COPY.search(m["draft_subject"]):
            out.append(f"message draft for {m['segment']} states a price, discount, saving or number")
    allowed = {m["text"] for m in p["metrics"]} | {m["text"].rstrip("%") for m in p["metrics"]}
    allowed_b = {a.replace(",", "") for a in allowed}
    for s in _plan_texts(p):
        for tok in NUM.findall(s):
            bare = tok.strip("$%").replace(",", "")
            if tok.strip("$") in allowed or bare in allowed_b:
                continue
            if bare.isdigit() and int(bare) <= 60 or bare in ("2017", "95"):
                continue
            out.append(f"number {tok} is not a registered metric: {s[:80]!r}")
        if dc.PROFIT.search(s) and not dc.SCEN.search(s):
            out.append(f"profit is claimed without a scenario label: {s[:80]!r}")
        if dc.CAUSAL.search(s):
            out.append(f"a promise of effect: {s[:80]!r}")
    return out


# ------------------------------------------------------------------------------------------------ output
def to_markdown(p: dict) -> str:
    o, s = p["objective"], p["stp"]
    L = [f"# Marketing strategy and plan: {p['category'].title()}", "", f"**Decision from the card: {p['decision_from_card']}.** {p['headline']}",
         f"**Approval:** {p['approval']['state']} (sandbox only: nothing is sent, spent or published).", "",
         "## 1. Objective", "", o["statement"], "", f"- **Baseline:** {o['baseline']}", f"- **Hurdle:** {o['minimum_worthwhile_response']}", f"- _{o['status']}._", "",
         "## 2. Segmentation, targeting, positioning", "", "| segment | households | what it means | approach |", "|---|---:|---|---|"]
    L += [f"| {r['segment']} | {r['households']:,} | {r['meaning']} | {r['approach']} |" for r in s["segmentation"]]
    t = s["targeting"]
    L += ["", f"**Target first:** {t['primary'] or 'none (fix availability first)'}. **Then:** {', '.join(t['secondary']) or 'none'}.", "**Do not target with offers:** " + "; ".join(f"{x['segment']} ({x['why']})" for x in t["do_not_target_with_offers"]),
          "", f"**Positioning (hypothesis):** {s['positioning']['statement']}. " + " ".join(s["positioning"]["proof_points"]), "", "## 3. Strategy by segment", "", "| segment | approach | what we do | paid offer | KPI |", "|---|---|---|---|---|"]
    L += [f"| {r['segment']} | {r['approach']} | {r['what_we_do']} | {r['paid_offer_verdict']} | {r['kpi']} |" for r in p["strategy_by_segment"]]
    L += ["", "## 4. Marketing mix and channels", ""] + [f"- **{k}:** {v}" for k, v in p["marketing_mix"].items() if k != "channels"]
    L += ["", "| channel | role | type | cost |", "|---|---|---|---|"] + [f"| {c['channel']} | {c['role']} | {c['kind']} | {c['cost']} |" for c in p["marketing_mix"]["channels"]]
    L += ["", "## 5. 13-week roadmap", "", "| phase | weeks | task | owner | deliverable | type | gates |", "|---|---|---|---|---|---|---|"]
    for ph in p["roadmap"]:
        for i, a in enumerate(ph["activities"]):
            wk = f"{ph['weeks'][0]}" if ph["weeks"][0] == ph["weeks"][1] else f"{ph['weeks'][0]}-{ph['weeks'][1]}"
            L.append(f"| {ph['phase'] if i == 0 else ''} | {wk if i == 0 else ''} | {a['task']} | {a['owner']} | {a['deliverable']} | {a['kind']} | {', '.join(a['gates']) or '-'} |")
    L += ["", "**Gates:** " + "; ".join(f"{k} = {v}" for k, v in p["gates"].items())]
    b = p["budget"]
    L += ["", "## 6. Budget (scenario: assumed contact cost, redemption, coupon value and setup)", ""]
    if b.get("households_per_arm"):
        L += [f"Households per arm: {b['households_per_arm']:,}.", "", "| arm | type | cost (USD) |", "|---|---|---:|"] + [f"| {x['arm']} | {x['kind']} | {x['cost_usd']:,.0f} |" for x in b["arms"]]
        L += [f"| Fixed setup (assumed) | | {b['setup_usd']:,.0f} |", f"| **Total** | | **{b['total_test_usd']:,.0f}** |", "", b["note"]]
    else:
        L += [b["note"]]
    k = p["kpis"]
    L += ["", "## 7. KPIs and decision rules", "", f"- **Primary:** {k['primary']}", "- **Secondary:** " + "; ".join(k["secondary"]), f"- **Guardrails:** {k['guardrails']}"]
    if k.get("decision_rules"):
        r = k["decision_rules"]
        L += [f"- **Expand if:** {r['expand']}", f"- **Stop if:** {r['stop']}", f"- **Change if:** {r['change']}"]
    L += ["", "## 8. Message drafts (not sent)", "", "| segment | angle | draft subject |", "|---|---|---|"] + [f"| {m['segment']} | {m['angle']} | {m['draft_subject']} |" for m in p["message_drafts"]]
    if p["discovery"]:
        d = p["discovery"]
        L += ["", "## 9. Discovery (SEO/GEO)", "", f"{d['audited_brand']} (public analogue): recommended in {d['learn']['recommended']} of {d['learn']['of']} Learn answers. {d['action']}."]
    L += ["", "## 10. Risks and how we handle them", "", "| risk | mitigation | owner |", "|---|---|---|"] + [f"| {r['risk']} | {r['mitigation']} | {r['owner']} |" for r in p["risks"]]
    L += ["", "## 11. What we need from the client", ""] + [f"- {x}" for x in p["needed_from_client"]]
    L += ["", f"_Checker: {'PASS' if not p['checker'] else 'PROBLEMS: ' + '; '.join(p['checker'])}._"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config()
    cats = cfg["categories"] if a.all or not a.category else [a.category.upper()]
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    bad = 0
    for cat in cats:
        p = build_plan(cat, cfg)
        stem = cat.replace("/", "_").replace(" ", "_")
        (PLAN_DIR / f"{stem}.json").write_text(json.dumps(p, indent=1, default=float, ensure_ascii=False), encoding="utf-8")
        (PLAN_DIR / f"{stem}.md").write_text(to_markdown(p), encoding="utf-8")
        print(cat, "|", p["decision_from_card"], "| checker:", "PASS" if not p["checker"] else p["checker"])
        bad += bool(p["checker"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
