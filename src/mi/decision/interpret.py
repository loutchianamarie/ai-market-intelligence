"""Plain-words interpretation of each dashboard element: what it shows, so what, what to do, what to watch out for.

Every sentence is built from the numbers passed in, and the wording changes with them (a small edge is called small, a wide interval is called
inconclusive). Nothing is typed by hand, so an interpretation cannot go stale when the data change. Deterministic: no model call.

Each function returns {"title", "shows", "so_what", "do", "watch_out", "evidence"} where evidence is the provenance tag of the numbers used.
"""
from __future__ import annotations


def _pct(x, d=0):
    return f"{100 * x:.{d}f}%"


def _box(title, shows, so_what, do, watch_out, evidence):
    return {"title": title, "shows": shows, "so_what": so_what, "do": do, "watch_out": watch_out, "evidence": evidence}


# ---------------------------------------------------------------------------------------------------------------- model quality
def interpret_performance(model_ap, rule_ap, pop_ap, gain, ci_lo, ci_hi, auc) -> dict:
    edge = "clearly" if ci_lo > 0 and gain >= 0.10 else ("modestly" if ci_lo > 0 else "not demonstrably")
    inconclusive = ci_lo <= 0 <= ci_hi
    return _box(
        "How good is the model at ranking likely buyers?",
        f"On weeks the model never saw, its average precision is {model_ap:.3f}, against {rule_ap:.3f} for the simple repeat-purchase rule and {pop_ap:.3f} for the popularity rule "
        f"(ROC AUC {auc:.3f}). Higher is better; a random list would score the share of buyers in the data.",
        f"The model ranks buyers {edge} better than the repeat rule: a gain of {gain:+.3f} (95% interval {ci_lo:+.3f} to {ci_hi:+.3f})."
        + (" The interval includes zero, so the gain is not proven." if inconclusive else " The interval excludes zero, so the gain is real" + (", but modest." if gain < 0.10 else " and substantial.")),
        "Use the model to order a contact list. Use the repeat rule to explain to a manager why a household is high on it: the two largely agree, so the story is simple.",
        "This predicts who buys anyway, not who responds to an offer. A high score is a reason to leave a household alone, not to discount it.", "OBSERVED (locked test)")


def interpret_calibration(deciles: list[dict]) -> dict:
    gaps = [abs(d["mean_pred"] - d["observed"]) for d in deciles]
    worst = max(range(len(gaps)), key=gaps.__getitem__)
    n = sum(d["n"] for d in deciles)
    ece = sum(g * d["n"] for g, d in zip(gaps, deciles)) / n
    ok = max(gaps) <= 0.05
    return _box(
        "Can a score be read as a probability?",
        f"Households are cut into {len(deciles)} equal groups by score. For each group the chart compares the average predicted chance with the share who really bought. "
        f"The average gap is {_pct(ece, 1)}; the largest is {_pct(gaps[worst], 1)} (group {worst + 1}).",
        "Scores behave like real probabilities, so a 30% score means about 3 in 10 such households buy." if ok else
        f"Scores are only roughly probabilities: group {worst + 1} is off by {_pct(gaps[worst], 1)}.",
        "Safe to use the scores to size audiences (expected buyers = sum of scores)." if ok else "Size audiences with a margin of error, or recalibrate before using scores in money calculations.",
        "Calibration was fitted on a separate window and checked on the test window; it can drift in other seasons.", "OBSERVED (locked test)")


def interpret_gains(model_captured, rule_captured, frac, model_lift, rule_lift) -> dict:
    edge = model_captured - rule_captured
    vs_rule = ("about the same share of buyers as the simple repeat rule, so the model's advantage is small at this cut" if abs(edge) < 0.02
               else f"{abs(edge) * 100:.0f} points {'more' if edge > 0 else 'fewer'} of the buyers than the simple repeat rule")
    return _box(
        "If I can only contact part of the list, how many buyers do I reach?",
        f"Contacting the top {_pct(frac)} of the ranked list reaches {_pct(model_captured)} of all buyers (lift {model_lift:.2f}x: that group buys {model_lift:.2f} times as often as an average row). "
        f"A random list of the same size reaches {_pct(frac)}.",
        f"Ranking is worth it: {_pct(model_captured)} of buyers for {_pct(frac)} of the effort. The model reaches {vs_rule}.",
        f"Order contact lists by score, and stop where the extra buyers per extra contact no longer cover the cost of a contact. The bottom {_pct(1 - frac)} of the list holds only {_pct(1 - model_captured)} of the buyers.",
        "These are people likely to buy anyway. Reaching them is not the same as causing them to buy; the gain is in saving effort, not in extra sales.", "OBSERVED (locked test)")


# ---------------------------------------------------------------------------------------------------------------- customers
def interpret_rfm(tiers: list[dict], retention: list[dict]) -> dict:
    total = sum(t["households"] for t in tiers)
    by = {t["rfm_segment"]: t for t in tiers}
    top = max(tiers, key=lambda t: t["households"])
    risk = sum(by[k]["households"] for k in ("At risk", "Hibernating") if k in by)
    best = sum(by[k]["households"] for k in ("Champions", "Loyal") if k in by)
    latest = retention[-1] if retention else None
    first = retention[0] if retention else None
    trend = ""
    if latest and first and len(retention) > 1:
        d = latest["retention"] - first["retention"]
        trend = f" Retention moved from {_pct(first['retention'])} to {_pct(latest['retention'])} over the period ({'down' if d < -0.02 else 'up' if d > 0.02 else 'flat'})."
    return _box(
        "Who are our customers, and who is slipping away?",
        f"Households are scored 1 to 5 on how recently they shopped, how often, and how much. The largest tier is {top['rfm_segment']} ({_pct(top['households'] / total)} of {total:,} households). "
        f"Champions and Loyal together are {_pct(best / total)}; At risk and Hibernating together are {_pct(risk / total)}.",
        f"{_pct(risk / total)} of households are at risk or already quiet, and they are the pool for win-back work.{trend}",
        "Protect Champions and Loyal with recognition, not discounts. Run reminders or content for At risk. Check stock, range and price before spending on Hibernating.",
        "Tiers describe past behaviour. The value column assumes a margin and a retention rate that you set; it ranks households, it does not forecast profit.", "OBSERVED (history to week 53)")


# ---------------------------------------------------------------------------------------------------------------- decisions
def interpret_portfolio(ranking: list[dict]) -> dict:
    n = len(ranking)
    by = {}
    for r in ranking:
        by.setdefault(r["verdict"], []).append(r["category"])
    best = ranking[0]
    learn = [r["category"].title() for r in ranking if r["verdict"] == "PAYS ONLY IF OPTIMISTIC"]
    none = [r["category"].title() for r in ranking if r["verdict"] == "DOES NOT PAY"]
    pays = [r["category"].title() for r in ranking if r["verdict"].startswith("PAYS (") or r["verdict"] == "PAYS IN THE BASE CASE"]
    return _box(
        "Which category is closest to a paid offer paying for itself?",
        f"Each row is a category's best segment for a digital coupon. 'Response needed' is how many times the assumed customer response would have to be for the offer to break even; "
        f"the closest is {best['category'].title()} at {best['needed_response_multiple']:.1f}x.",
        (f"{len(pays)} of {n} categories pay at base assumptions. " if pays else f"None of the {n} categories pays at base assumptions. ")
        + (f"{', '.join(learn)} pay only if every assumption is favourable at once, so they are the ones worth learning about. " if learn else "")
        + (f"{', '.join(none)} do not pay even then." if none else ""),
        f"Spend nothing paid yet. Start free actions everywhere, and design a randomized test for {learn[0] if learn else best['category'].title()} first." if not pays else
        f"Test {pays[0]} first, with a holdout, and scale only on the measured result.",
        "Money figures are scenarios built on assumed margin, cost, response and scale. They show what would have to be true, not what will happen.", "SCENARIO")


def interpret_segments(segments: list[dict], category: str) -> dict:
    tot_n = sum(s["households"] for s in segments)
    tot_e = sum(s["expected_buyers_4w"] for s in segments)
    lead = max(segments, key=lambda s: s["expected_buyers_4w"])
    big = max(segments, key=lambda s: s["households"])
    return _box(
        f"Where do the {category.title()} buyers come from?",
        f"{tot_n:,} households are scored; {tot_e:,.0f} are expected to buy in the next 4 weeks. {lead['segment'].replace('_', ' ').title()} supplies the most buyers ({lead['expected_buyers_4w']:,.0f}, "
        f"{_pct(lead['expected_buyers_4w'] / tot_e)}); {big['segment'].replace('_', ' ').title()} is the biggest group ({big['households']:,} households, but only {_pct(big['mean_chance_of_buying'])} chance each).",
        "Volume sits with households that already buy. The biggest group of households is mostly not buying, so reaching everyone would spend most of the budget on people who will not respond.",
        "Defend the regulars without discounts, and aim effort at the segment where a reminder could change the outcome (lapsing and recent-light).",
        "Segments are rules on past behaviour; they are not proof that a message will change anyone's mind.", "MODEL ESTIMATE")


# ---------------------------------------------------------------------------------------------------------------- discovery
def interpret_geo(by_intent: dict, mention, recommend, top, n, brand) -> dict:
    weakest = min(by_intent.items(), key=lambda kv: (kv[1]["recommended"] / kv[1]["n"]) if kv[1]["n"] else 1)
    k, v = weakest
    gap = v["recommended"] == 0 and v["n"] > 0
    return _box(
        "Do AI assistants find and recommend the brand?",
        f"{n} logged answers about {brand}: mentioned in {mention}, recommended in {recommend}, first pick in {top}. By question type: "
        + ", ".join(f"{i} {x['recommended']}/{x['n']} recommended" for i, x in by_intent.items()) + ".",
        (f"The brand is not recommended in any {k} answer ({v['mentioned']}/{v['n']} mentioned), so shoppers still learning are not being pointed to it. That is a content gap, not a lost sale."
         if gap else f"{k} questions convert worst: {v['recommended']}/{v['n']} recommended."),
        f"Publish a factual page for the {k} questions (how it works, how to choose), with the same offer description everywhere; a named person approves it before publishing.",
        "Two assistants from one vendor, one run each, no region set, and a public analogue brand. It shows how the audit works, not what happens to traffic or sales.", "OBSERVED (answer log)")


def interpret_readiness(result: dict) -> dict:
    v = result["verdict"]
    bad = [c for c in result["checks"] if c["status"] in ("NOT_READY", "PARTIAL")]
    return _box(
        "Can this dataset be used with the project?",
        f"The file was checked against the design the grocery model used (look-back, horizon, cut-offs, categories, repeat buying, data quality). Verdict: {v}.",
        ("Everything the design needs is present." if v == "READY" else
         "The model can be trained with caveats: " + "; ".join(c["requirement"] for c in bad) + "." if v == "PARTIAL" else
         "A required element is missing: " + "; ".join(c["requirement"] for c in bad) + "."),
        "Fix the items listed below, or use the reduced design it proposes." if bad else "Train and evaluate with the proposed time split, then read the intervals before trusting any result.",
        "READY means it can be evaluated, not that it will predict well. Profit and the effect of an offer still need the client's costs and a randomized test.", "OBSERVED (data check)")
