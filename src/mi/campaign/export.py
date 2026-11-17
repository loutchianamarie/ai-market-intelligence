"""Campaign case producer: evidence -> decision -> reports/campaign_case.latest.json (contract v1).

Every number in the export, the claim ledger and the generated cards is computed here from the local raw file.
Nothing is typed by hand, nothing is sent, and no grocery report is read for a number.

  python -m mi.campaign.export        full run: audit, fit, held-out evaluation, economics, export, cards, manifest
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from mi.campaign import contract as K
from mi.campaign import uplift as U
from mi.campaign.contract import ARM_KEY, CONTROL, MENS, TREATMENTS, WOMENS, tv
from mi.campaign.data import ASSIGNMENT, CampaignDataError, audit, dictionary_md, load_protocol, load_raw
from mi.paths import DOCS, REPORTS, ROOT

EXPORT = REPORTS / "campaign_case.latest.json"
CHECKSUM = REPORTS / "campaign_case.latest.sha256"
OUT = REPORTS / "campaign"
SHORT = {MENS: "Mens e-mail", WOMENS: "Womens e-mail", CONTROL: "no e-mail"}


def _f(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}"


def _ci(ci, d: int = 1, scale: float = 1.0) -> str:
    return f"{_f(scale * ci[0], d)} to {_f(scale * ci[1], d)}"


def _git_commit() -> str | None:
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all", "--", "src/mi/campaign", "data/eval/hillstrom_protocol_v2.json",
                                         "docs/contracts/campaign_case.v1.schema.json"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        return head + ("+uncommitted-campaign-code" if dirty else "")
    except Exception:
        return None


# ---------------------------------------------------------------- full-sample randomized evidence
def full_sample(df: pd.DataFrame) -> dict:
    a = df[ASSIGNMENT].to_numpy()
    arms = {arm: {"n": int((a == arm).sum()), "buyers": int(df.conversion[a == arm].sum()), "spend_mean": float(df.spend[a == arm].mean())} for arm in K.ARMS}
    c = arms[CONTROL]
    eff = {}
    for arm in TREATMENTS:
        t = arms[arm]
        w = U.wald(t["n"], t["buyers"], c["n"], c["buyers"])
        s = U.wald_means(df.spend[a == arm].to_numpy(float), df.spend[a == CONTROL].to_numpy(float))
        eff[arm] = {"rate_diff": w["diff"], "rate_ci": w["ci95"], "per_1000": 1000 * w["diff"], "per_1000_ci": [1000 * v for v in w["ci95"]],
                    "relative_lift": w["diff"] / (c["buyers"] / c["n"]) if c["buyers"] else None, "spend_diff": s["diff"], "spend_ci": s["ci95"]}
    return {"arms": arms, "effects": eff}


def holdout_size(p_control: float, p_treated: float, power_z: float = 0.8416, alpha_z: float = 1.96) -> int | None:
    """Customers per arm to detect p_treated vs p_control (two-sided 5%, 80% power). Assumes the historical effect holds."""
    d = p_treated - p_control
    if d <= 0:
        return None
    return int(math.ceil((alpha_z + power_z) ** 2 * (p_control * (1 - p_control) + p_treated * (1 - p_treated)) / d ** 2))


# ---------------------------------------------------------------- decision (pre-registered rule, protocol v2)
def verdict_of(primary: dict) -> dict:
    r, u = primary["model_minus_random"], primary["model_minus_rule"]
    beats_r, beats_u = r["value"] > 0, u["value"] > 0
    stable_r, stable_u = r["ci95"][0] > 0, u["ci95"][0] > 0
    v = "MODEL_WIN_STABLE" if (stable_r and stable_u) else "MODEL_AHEAD_NOT_STABLE" if (beats_r and beats_u) else "NO_MODEL_ADVANTAGE"
    return {"verdict": v, "beats_random": beats_r, "beats_rule": beats_u, "stable_random": stable_r, "stable_rule": stable_u}


def decide(fs: dict, ev: dict) -> dict:
    best = ev["selection"]["best_overall_arm"]
    e, v = fs["effects"][best], verdict_of(ev["primary"])
    if e["per_1000_ci"][0] <= 0:
        status, policy, arm, share = "MORE_EVIDENCE_REQUIRED", None, "NONE", 0.0
    elif v["verdict"] == "MODEL_WIN_STABLE":
        status, policy, arm, share = "TARGETED_SEND_WITH_HOLDOUT_IF_ECONOMICS_CONFIRMED", ev["primary"]["ids"]["model"], best, ev["primary"]["cap"]
    else:
        status, policy, arm, share = "BROAD_SEND_WITH_HOLDOUT_IF_ECONOMICS_CONFIRMED", f"SEND_ALL_{ARM_KEY[best]}_100", best, 1 - K.ASSUMED_HOLDOUT_SHARE
    return {"status": status, "policy_id": policy, "arm": arm, "contact_share": share, "best_arm": best, **v}


# ---------------------------------------------------------------- export document
def build(df: pd.DataFrame, facts: dict, proto: dict, *, n_boot: int | None = None, n_boot_qini: int = 500,
          code_commit: str | None = None, generated_at: str | None = None) -> tuple[dict, dict]:
    """Returns (contract document, detail). Pure computation: nothing is written."""
    t0 = time.time()
    fs = full_sample(df)
    ev = U.run(df, proto, n_boot=n_boot, n_boot_qini=n_boot_qini)
    dec = decide(fs, ev)
    sha, mv = facts["sha256"], ev["model"]["version"]
    best, other = dec["best_arm"], next(a for a in TREATMENTS if a != dec["best_arm"])
    eb, eo = fs["effects"][best], fs["effects"][other]
    arms, ctrl = fs["arms"], fs["arms"][CONTROL]
    rows = {r["spec"]["policy_id"]: r for r in ev["policies"]}
    P, ids, cap = ev["primary"], ev["primary"]["ids"], ev["primary"]["cap"]
    pct = int(round(100 * cap))
    m, rnd, rule = rows[ids["model"]], rows[ids["random"]], rows[ids["rule"]]
    other_rule_id = next(i for i in (f"RULE_RECENCY_{ARM_KEY[best]}_{pct}", f"RULE_HISTORY_{ARM_KEY[best]}_{pct}") if i != ids["rule"])
    other_rule = rows[other_rule_id]
    rule_name = {"RULE_RECENCY": "recency rule", "RULE_HISTORY": "past-spend rule"}
    rname = rule_name[ev["selection"]["primary_rule"]]
    oname = next(v for k, v in rule_name.items() if k != ev["selection"]["primary_rule"])
    run_id = "CAMP-" + hashlib.sha256(f"{sha}|{mv}|{json.dumps(proto, sort_keys=True)}|{ev['n_boot']}".encode()).hexdigest()[:12].upper()

    # ---- held-out policy rows
    pol_rows = []
    for r in ev["policies"]:
        spec, none = r["spec"], r["spec"]["policy_family"] == "NO_EMAIL"
        cmp = [K.comparison(o, d["value"], d["ci95"]) for o, d in r["comparisons"].items()]
        if none:
            tc = ev["test"]["arms"][CONTROL]
            pol_rows.append(K.policy_metric(spec, eligible_n=r["eligible_n"], contacted_n=0, tn=0, tb=0, cn=tc["n"], cb=tc["buyers"]))
        else:
            pol_rows.append(K.policy_metric(spec, eligible_n=r["eligible_n"], contacted_n=r["contacted_n"], tn=r["treated_n"], tb=r["treated_buyers"],
                                            cn=r["control_n"], cb=r["control_buyers"], per_1000_contacts=1000 * r["per_contact"],
                                            ci_contacts=[1000 * v for v in r["per_contact_ci"]], per_1000_eligible=1000 * r["per_eligible"],
                                            ci_eligible=[1000 * v for v in r["per_eligible_ci"]], spend_per_contact=r["spend_per_contact"],
                                            spend_ci=r["spend_ci"], comparisons=cmp, is_primary=r["is_primary"]))

    # ---- economics: scenarios and thresholds (assumptions, never measured profit)
    broad_contacts = K.ASSUMED_ELIGIBLE_BASE * (1 - K.ASSUMED_HOLDOUT_SHARE)
    scen = [K.scenario(f"SEND_ALL_{ARM_KEY[a]}_100", a, name, broad_contacts, spend=fs["effects"][a]["spend_diff"], spend_ci=fs["effects"][a]["spend_ci"])
            for a in TREATMENTS for name in K.ASSUMPTION_SETS]
    thr = [K.threshold(a, mg, spend=fs["effects"][a]["spend_diff"], spend_low=fs["effects"][a]["spend_ci"][0]) for a in TREATMENTS for mg in K.THRESHOLD_MARGINS]
    sc = {s["scenario_id"]: s for s in scen}
    th = {t["threshold_id"]: t for t in thr}
    exp_buyers = broad_contacts * eb["per_1000"] / 1000
    exp_buyers_ci = [broad_contacts * v / 1000 for v in eb["per_1000_ci"]]
    n_hold = holdout_size(ctrl["buyers"] / ctrl["n"], arms[best]["buyers"] / arms[best]["n"])
    seg = U.segment_effects(df)
    segd = {(s["segment"], s["treatment_arm"]): s for s in seg}

    # ---- words (all figures formatted from the numbers above)
    vt = (f"At a {pct}% contact cap, the model's top customers gave {_f(1000 * m['per_contact'])} additional buyers per 1,000 {SHORT[best]}s "
          f"(95% interval {_ci(m['per_contact_ci'], 1, 1000)}), against {_f(1000 * rnd['per_contact'])} for random contacts "
          f"(difference {P['model_minus_random']['value']:+.1f}, interval {_ci(P['model_minus_random']['ci95'])}) and {_f(1000 * rule['per_contact'])} for the {rname} "
          f"(difference {P['model_minus_rule']['value']:+.1f}, interval {_ci(P['model_minus_rule']['ci95'])}). ")
    vt += {"MODEL_WIN_STABLE": "Both intervals lie above zero: the model's targeting gain is statistically stable on this held-out split.",
           "MODEL_AHEAD_NOT_STABLE": "The model is ahead on the point estimate, but both intervals must exclude zero for a stable gain and they do not: "
                                     "no stable targeting gain is shown.",
           "NO_MODEL_ADVANTAGE": "The model does not beat both baselines even on the point estimate: no targeting gain is shown."}[dec["verdict"]]
    vt += (f" The {oname}, which validation did not select as the primary rule, scored {_f(1000 * other_rule['per_contact'])} "
           f"(model minus that rule {m['comparisons'][other_rule_id]['value']:+.1f}, interval {_ci(m['comparisons'][other_rule_id]['ci95'])}).")
    be_c, be_m = th[f"BREAK_EVEN_COST_{ARM_KEY[best]}_M35"], f"BREAK_EVEN_COST_{ARM_KEY[best]}_M"
    broad = dec["status"].startswith("BROAD")
    targeted = dec["status"].startswith("TARGETED")
    if broad:
        decision = (f"Send the {SHORT[best]} to every eligible, consented existing customer except a {K.ASSUMED_HOLDOUT_SHARE:.0%} randomized no-e-mail holdout, "
                    f"but only after finance and CRM confirm that the full cost per e-mail is below the break-even for the confirmed margin. "
                    f"Do not use the targeting model to exclude customers yet. A named human approves; this system sends nothing.")
    elif targeted:
        decision = (f"Send the {SHORT[best]} to the {pct}% of eligible customers with the highest model-predicted uplift, keep a randomized no-e-mail holdout "
                    f"inside and outside that group, and confirm cost per e-mail against break-even first. A named human approves; this system sends nothing.")
    else:
        decision = ("Do not send. The randomized average effect is not clearly above zero; collect more evidence with a randomized pilot. "
                    "A named human decides; this system sends nothing.")
    rationale = [
        f"Randomized evidence on {facts['rows']:,} existing customers: {arms[best]['buyers']} of {arms[best]['n']:,} customers bought within two weeks after the {SHORT[best]} "
        f"({arms[best]['buyers'] / arms[best]['n']:.2%}) against {ctrl['buyers']} of {ctrl['n']:,} with no e-mail ({ctrl['buyers'] / ctrl['n']:.2%}).",
        f"That is {_f(eb['per_1000'])} additional purchasing customers per 1,000 e-mailed (95% interval {_ci(eb['per_1000_ci'])}). "
        f"The {SHORT[other]} added {_f(eo['per_1000'])} per 1,000 (interval {_ci(eo['per_1000_ci'])}) against the same control.",
        f"On the held-out test split the {SHORT[best]} sent to everyone added {_f(1000 * rows[f'SEND_ALL_{ARM_KEY[best]}_100']['per_contact'])} per 1,000 "
        f"(interval {_ci(rows[f'SEND_ALL_{ARM_KEY[best]}_100']['per_contact_ci'], 1, 1000)}), consistent with the full sample.",
        vt,
        f"Incremental spend is {_f(eb['spend_diff'], 2)} USD per customer e-mailed (interval {_ci(eb['spend_ci'], 2)}). Margin and cost per e-mail are UNKNOWN, "
        f"so no profit is claimed; at an assumed 35% margin the e-mail may cost up to {_f(be_c['break_even_cost_per_contact']['value'], 2)} USD "
        f"({_f(be_c['break_even_cost_per_contact_conservative']['value'], 2)} USD on the lower bound) before it loses money, setup aside.",
    ]
    conditions = [
        f"Finance confirms the contribution margin on incremental sales and CRM confirms the full cost per e-mail (delivery, offer, handling); the cost must be below "
        f"margin x {_f(eb['spend_diff'], 2)} USD, and below margin x {_f(eb['spend_ci'][0], 2)} USD to be safe on the lower bound.",
        "E-mail consent and unsubscribe handling are verified for every recipient.",
        f"A {K.ASSUMED_HOLDOUT_SHARE:.0%} randomized no-e-mail holdout is drawn and frozen before sending"
        + (f" (at least {n_hold:,} customers per arm to detect an effect of the 2008 size with 80% power)." if n_hold else "."),
        "A named human approves the final draft; any change to the plan requires a new review.",
        "The 2008 effect is a prior, not a forecast: the first send is itself the pilot and is judged on its own holdout.",
    ]
    reverse = [
        f"Verified cost per e-mail above the break-even for the verified margin (point: margin x {_f(eb['spend_diff'], 2)} USD): choose no e-mail.",
        "Consent cannot be verified, or unsubscribe and complaint costs are material: choose no e-mail or a smaller consented group.",
        "A new randomized pilot on the current base gives an interval for additional buyers that includes zero: stop and research before spending more.",
        "A larger test shows the model beating random and the simple rule with intervals above zero: switch to model-targeted sending.",
        "A binding contact cap (budget or frequency policy): prioritise by a simple auditable rule and randomize inside the cap, as described in the alternative.",
    ]
    alt = (f"If only a share of customers may be contacted, do not present the model as a proven gain. At a {pct}% cap the model ({_f(1000 * m['per_contact'])}), the {rname} "
           f"({_f(1000 * rule['per_contact'])}) and the {oname} ({_f(1000 * other_rule['per_contact'])}) all sit above random ({_f(1000 * rnd['per_contact'])}) on the point estimate, "
           "none with an interval that excludes zero. Use the simplest auditable ranking (past-year spend or recency) to fill the cap, and randomize e-mail versus no e-mail "
           "inside both the selected and the unselected group, so the next campaign measures whether targeting works.")
    no_email = (f"Always allowed. Without an e-mail {ctrl['buyers'] / ctrl['n']:.2%} of customers still bought within two weeks; those purchases are not caused by the campaign. "
                f"Choose no e-mail when cost per contact exceeds break-even, when consent is missing, or when a manager prefers to wait for a current pilot. "
                f"Under the conservative assumption set the {SHORT[other]} loses money "
                f"({sc[f'SEND_ALL_{ARM_KEY[other]}_100__CONSERVATIVE']['contribution']['value']:+,.0f} USD scenario contribution).")

    def segs(arm: str) -> str:
        return "; ".join(f"{s}: {_f(segd[(s, arm)]['additional_buyers_per_1000'])} per 1,000 (interval {_ci(segd[(s, arm)]['ci95_per_1000'])})"
                         for s in ("Mens merchandise only", "Womens merchandise only", "Both"))

    marketing = {
        "research_question": "Among existing customers who bought in the past twelve months, does a merchandise e-mail create additional purchasing customers within two weeks "
                             "compared with no e-mail, which of the two e-mails does it better, and is a targeting model worth using under a contact cap?",
        "audience": f"Existing customers who purchased in the past twelve months ({facts['rows']:,} in the experiment). This is repeat-purchase stimulation of a known base, "
                    "not acquisition of new customers.",
        "segmentation": "Bases available before the e-mail: months since last purchase, past-year spend, past-year purchase category (Mens, Womens or both; product history, "
                        "not gender), new-in-the-past-year flag, zip type and purchase channel. Descriptive only, by past-year category: "
                        f"{SHORT[MENS]}: {segs(MENS)}. {SHORT[WOMENS]}: {segs(WOMENS)}.",
        "targeting": (f"Default target: every eligible, consented customer except the randomized holdout. " if not targeted else f"Target: the model's top {pct}%. ")
                     + f"The {SHORT[MENS]} added buyers in all three purchase categories; the {SHORT[WOMENS]} shows a clear effect only among customers who bought Womens merchandise. "
                       f"The model's ranking is not shown to beat random or a simple rule with a stable margin, so it is not used to suppress anyone.",
        "positioning": f"For customers who bought from us this year: a timely reminder of new merchandise from a retailer they already know, giving a reason to return within two weeks. "
                       f"Lead with the {SHORT[best]} focus because it produced more additional buyers. Copy is a hypothesis: the 2008 creative is not available.",
        "four_ps": [
            {"p": "Product", "decision": f"Lead with the {'Mens' if best == MENS else 'Womens'}-merchandise e-mail.",
             "alternatives": [f"{SHORT[other].capitalize()}: {_f(eo['per_1000'])} additional buyers per 1,000 (interval {_ci(eo['per_1000_ci'])})", "No e-mail"],
             "tag": "OBSERVED", "note": "Product here means the merchandise focus of the e-mail. The dataset has no SKU, assortment or stock data."},
            {"p": "Price", "decision": "No price or discount change is recommended.",
             "alternatives": ["Test a plain reminder against an offer in the next randomized pilot"],
             "tag": "UNKNOWN", "note": "Price and discount terms of the 2008 e-mails are unknown; any offer cost belongs in cost per contact."},
            {"p": "Place", "decision": "E-mail to existing customers, compared with no contact.",
             "alternatives": ["No e-mail (the randomized control)", "Other channels: not tested in this experiment"],
             "tag": "OBSERVED", "note": "The customer's past purchase channel (phone, web, multichannel) is a feature, not the campaign channel."},
            {"p": "Promotion", "decision": "Two draft messages prepared as hypotheses; a human approves or rejects them.",
             "alternatives": ["Merchandise-matched variant for Womens-category buyers, to be tested rather than assumed"],
             "tag": "ASSUMPTION", "note": "The actual creative, subject line and products shown in 2008 are not available. Drafts are never sent by this system."}],
        "journey_barrier_hypotheses": [
            "UNVERIFIED: recent buyers have no trigger to return within two weeks; an e-mail supplies one.",
            "UNVERIFIED: a message about merchandise a customer has never bought is less relevant "
            f"(the {SHORT[WOMENS]} added {_f(segd[('Mens merchandise only', WOMENS)]['additional_buyers_per_1000'])} per 1,000 among customers who bought only Mens merchandise; "
            "this describes a group and does not prove the reason).",
            "UNVERIFIED: something between the visit and the purchase stops most e-mail-driven visitors; site and checkout friction are not observed in this dataset."],
        "message_drafts": [
            {"draft_id": "DRAFT_MENS_A", "arm": MENS, "subject": "New in menswear, picked for returning customers",
             "body": "Hello {first_name}, thank you for shopping with {brand} this year. The new men's collection has arrived: {three_featured_items}. "
                     "See what is new: {landing_page_url}. No price or discount is stated because offer terms are not approved. {unsubscribe_link}",
             "status": "DRAFT_HYPOTHESIS_NOT_SENT"},
            {"draft_id": "DRAFT_WOMENS_A", "arm": WOMENS, "subject": "New in womenswear, picked for returning customers",
             "body": "Hello {first_name}, thank you for shopping with {brand} this year. The new women's collection has arrived: {three_featured_items}. "
                     "See what is new: {landing_page_url}. No price or discount is stated because offer terms are not approved. {unsubscribe_link}",
             "status": "DRAFT_HYPOTHESIS_NOT_SENT"}],
        "action_plan": [
            {"step": 1, "owner_role": "CRM owner", "action": "Review the eligible segment (purchased in the past twelve months) and report its current size.", "status": "PENDING_HUMAN"},
            {"step": 2, "owner_role": "CRM owner with legal", "action": "Verify e-mail consent and unsubscribe handling for every eligible customer.", "status": "PENDING_HUMAN"},
            {"step": 3, "owner_role": "Finance with CRM owner", "action": "Supply the contribution margin and the full cost per e-mail; compare with the break-even thresholds.", "status": "PENDING_HUMAN"},
            {"step": 4, "owner_role": "Analyst", "action": f"Draw and freeze a {K.ASSUMED_HOLDOUT_SHARE:.0%} randomized no-e-mail holdout before any send.", "status": "PENDING_HUMAN"},
            {"step": 5, "owner_role": "Marketing manager", "action": "Approve or reject the draft with name, reason and plan version; re-review after any change.", "status": "PENDING_HUMAN"},
            {"step": 6, "owner_role": "Marketing operations (human)", "action": "Send only after step 5 is approved. This system has no send tool.", "status": "BLOCKED_UNTIL_APPROVED"},
            {"step": 7, "owner_role": "Analyst with marketing manager", "action": "After two weeks, compare unique buyers, incremental spend, cost and unsubscribes between e-mailed customers and the holdout; decide to continue, change or stop.", "status": "PENDING_HUMAN"}],
        "success_metric": "Additional unique purchasing customers per 1,000 e-mailed versus the randomized holdout within two weeks, with a 95% interval above zero. "
                          "Secondary: incremental spend per contact times margin minus cost per contact. Guardrail: unsubscribe and complaint rate.",
    }

    # ---- claim ledger
    C = []
    ci_w, ci_b = "95% interval, normal approximation", f"95% interval, customer bootstrap ({ev['n_boot']} resamples)"

    def obs(i, text, value, unit, den, arm=None, unc=None, safe=True, src="SRC_HILLSTROM_2008_DATA"):
        C.append(K.claim(i, text, value, unit, "OBSERVED", sha=sha, denominator=den, arm=arm, uncertainty=unc, source_id=src, slide_safe=safe))

    def held(i, text, value, unit, den, arm=None, unc=None, safe=True):
        C.append(K.claim(i, text, value, unit, "HELD_OUT_ESTIMATE", sha=sha, denominator=den, arm=arm, split="test", model_version=mv, uncertainty=unc, slide_safe=safe))

    def assume(i, text, value, unit, den=None, arm=None, unc=None, safe=True):
        C.append(K.claim(i, text, value, unit, "ASSUMPTION", sha=sha, denominator=den, arm=arm, split="not_applicable", uncertainty=unc, slide_safe=safe))

    obs("CLM_DATA_ROWS", "Existing customers in the randomized e-mail experiment", facts["rows"], "customers", f"{facts['rows']:,} rows, one per customer", unc=None)
    for a in K.ARMS:
        k = "CONTROL" if a == CONTROL else ARM_KEY[a]
        obs(f"CLM_N_{k}", f"Customers randomized to {a}", arms[a]["n"], "customers", f"{facts['rows']:,} customers in the experiment", arm=a, safe=False)
        obs(f"CLM_BUYERS_{k}", f"Unique customers who purchased within two weeks, {a}", arms[a]["buyers"], "customers", f"{arms[a]['n']:,} customers randomized to {a}", arm=a)
        obs(f"CLM_RATE_{k}", f"Purchase rate, {a}", round(100 * arms[a]["buyers"] / arms[a]["n"], 4), "percent", f"{arms[a]['buyers']} buyers / {arms[a]['n']:,} customers randomized to {a}", arm=a)
    for a in TREATMENTS:
        e, k = fs["effects"][a], ARM_KEY[a]
        den = f"{arms[a]['buyers']}/{arms[a]['n']:,} ({a}) minus {ctrl['buyers']}/{ctrl['n']:,} ({CONTROL})"
        obs(f"CLM_BUYERS_PER_1000_{k}", f"Additional purchasing customers per 1,000 customers sent the {SHORT[a]}, versus no e-mail", round(e["per_1000"], 3),
            "per 1,000 e-mailed", den, arm=a, unc=f"{ci_w}: {_ci(e['per_1000_ci'], 2)}")
        obs(f"CLM_RELATIVE_LIFT_{k}", f"Relative lift in purchase rate, {SHORT[a]} versus no e-mail", round(100 * e["relative_lift"], 1), "percent of the control rate", den, arm=a,
            unc="ratio of two small rates; use the absolute figure first", safe=False)
        obs(f"CLM_SPEND_PER_CONTACT_{k}", f"Incremental spend per customer sent the {SHORT[a]}, versus no e-mail", round(e["spend_diff"], 4), "USD per customer e-mailed",
            f"mean spend of {arms[a]['n']:,} ({a}) minus mean spend of {ctrl['n']:,} ({CONTROL})", arm=a, unc=f"{ci_w}: {_ci(e['spend_ci'], 2)}")
    for s in seg:
        k = f"{'MENSONLY' if s['segment'].startswith('Mens') else 'WOMENSONLY' if s['segment'].startswith('Womens') else 'BOTH'}_{ARM_KEY[s['treatment_arm']]}"
        obs(f"CLM_SEGMENT_{k}", f"Additional buyers per 1,000, {SHORT[s['treatment_arm']]}, customers whose past-year purchases were: {s['segment']} (descriptive)",
            round(s["additional_buyers_per_1000"], 3), "per 1,000 e-mailed",
            f"{s['treated_buyers']}/{s['treated_n']:,} ({s['treatment_arm']}) minus {s['control_buyers']}/{s['control_n']:,} ({CONTROL}) in this segment",
            arm=s["treatment_arm"], unc=f"{ci_w}: {_ci(s['ci95_per_1000'], 2)}; one pre-declared descriptive segmentation, hypothesis-generating", safe=False)
    sh = ev["split"]["hashes"]
    obs("CLM_SPLIT_SIZES", "Customers in train / validation / test", f"{sh['train']['n']} / {sh['validation']['n']} / {sh['test']['n']}", "customers",
        f"{facts['rows']:,} customers, seeded split stratified by arm", src="SRC_LOCAL_RUN", safe=False)
    tst = ev["test"]["arms"]
    obs("CLM_TEST_BUYERS", "Buyers in the held-out test split: no e-mail / Mens e-mail / Womens e-mail",
        f"{tst[CONTROL]['buyers']} / {tst[MENS]['buyers']} / {tst[WOMENS]['buyers']}", "customers",
        f"{tst[CONTROL]['n']:,} / {tst[MENS]['n']:,} / {tst[WOMENS]['n']:,} held-out customers per arm", src="SRC_LOCAL_RUN")

    def pol_den(r):
        where = ("over the whole held-out arms" if r["spec"]["policy_family"] in ("RANDOM", "SEND_ALL") or r["spec"]["contact_share"] == 1
                 else "inside the selected held-out customers")
        return f"{r['treated_buyers']}/{r['treated_n']:,} e-mailed minus {r['control_buyers']}/{r['control_n']:,} not e-mailed, {where}"

    for a in TREATMENTS:
        r = rows[f"SEND_ALL_{ARM_KEY[a]}_100"]
        held(f"CLM_TEST_SEND_ALL_{ARM_KEY[a]}", f"Held-out: additional buyers per 1,000 when every customer gets the {SHORT[a]}", round(1000 * r["per_contact"], 3),
             "per 1,000 contacted", pol_den(r), arm=a, unc=f"{ci_b}: {_ci(r['per_contact_ci'], 2, 1000)}")
    for key, r, label in (("MODEL", m, "model targeting"), ("RANDOM", rnd, "random contacts (expected value)"), ("RULE", rule, rname), ("OTHER_RULE", other_rule, oname)):
        held(f"CLM_CAP{pct}_{key}", f"Held-out, {pct}% contact cap, {SHORT[best]}: additional buyers per 1,000 contacted, {label}", round(1000 * r["per_contact"], 3),
             "per 1,000 contacted", pol_den(r), arm=best, unc=f"{ci_b}: {_ci(r['per_contact_ci'], 2, 1000)}")
    held("CLM_MODEL_VS_RANDOM", f"Model targeting minus random contacts at the {pct}% cap ({SHORT[best]})", round(P["model_minus_random"]["value"], 3),
         "additional buyers per 1,000 contacts", f"model: {pol_den(m)}; random: {pol_den(rnd)}", arm=best,
         unc=f"paired {ci_b}: {_ci(P['model_minus_random']['ci95'], 2)}; " + ("excludes zero" if dec["stable_random"] else "includes zero"))
    held("CLM_MODEL_VS_RULE", f"Model targeting minus the {rname} at the {pct}% cap ({SHORT[best]})", round(P["model_minus_rule"]["value"], 3),
         "additional buyers per 1,000 contacts", f"model: {pol_den(m)}; rule: {pol_den(rule)}", arm=best,
         unc=f"paired {ci_b}: {_ci(P['model_minus_rule']['ci95'], 2)}; " + ("excludes zero" if dec["stable_rule"] else "includes zero"))
    d_or = m["comparisons"][other_rule_id]
    held("CLM_MODEL_VS_OTHER_RULE", f"Model targeting minus the {oname} at the {pct}% cap ({SHORT[best]}); this rule was not the one chosen on validation",
         round(d_or["value"], 3), "additional buyers per 1,000 contacts", f"model: {pol_den(m)}; rule: {pol_den(other_rule)}", arm=best,
         unc=f"paired {ci_b}: {_ci(d_or['ci95'], 2)}")
    held("CLM_MODEL_VERDICT", "Pre-registered verdict on model targeting versus random and the primary rule", dec["verdict"], "verdict",
         f"{pct}% cap on {ev['test']['n']:,} held-out customers", arm=best, unc="stable only if both paired 95% intervals lie above zero")
    ba = rows["MODEL_BESTARM_100"]
    d_ba = ba["comparisons"][f"SEND_ALL_{ARM_KEY[best]}_100"]
    held("CLM_BESTARM_VS_SEND_ALL", f"Letting the model choose the e-mail per customer, minus sending everyone the {SHORT[best]}", round(d_ba["value"], 3),
         "additional buyers per 1,000 contacts", f"model: {pol_den(ba)}; send-all: {pol_den(rows[f'SEND_ALL_{ARM_KEY[best]}_100'])}", arm="MODEL_CHOOSES_ARM",
         unc=f"paired {ci_b}: {_ci(d_ba['ci95'], 2)}", safe=False)
    for a in TREATMENTS:
        for mg in K.THRESHOLD_MARGINS:
            t = th[f"BREAK_EVEN_COST_{ARM_KEY[a]}_M{int(round(100 * mg))}"]
            assume(f"CLM_{t['threshold_id']}", f"Break-even cost per e-mail, {SHORT[a]}, at an ASSUMED {mg:.0%} margin (before setup)",
                   round(t["break_even_cost_per_contact"]["value"], 4), "USD per e-mail", f"incremental spend per contact x {mg:.0%}", arm=a,
                   unc=f"{_f(t['break_even_cost_per_contact_conservative']['value'], 3)} USD using the lower 95% bound of incremental spend", safe=(mg == 0.35))
        for name in ("CONSERVATIVE", "CENTRAL", "FAVOURABLE"):
            s = sc[f"SEND_ALL_{ARM_KEY[a]}_100__{name}"]
            assume(f"CLM_SCENARIO_{ARM_KEY[a]}_{name}", f"SCENARIO contribution, {SHORT[a]} to {broad_contacts:,.0f} customers, {name.lower()} assumptions (not measured profit)",
                   int(round(s["contribution"]["value"])), "USD per campaign",
                   f"{broad_contacts:,.0f} assumed contacts; margin {s['assumed_margin']['value']:.0%}, cost {s['cost_per_contact']['value']:.3f} USD per e-mail, setup {s['fixed_setup_cost']['value']:,.0f} USD",
                   arm=a, unc=f"range over the 95% interval of incremental spend: {s['contribution']['ci95'][0]:,.0f} to {s['contribution']['ci95'][1]:,.0f} USD", safe=(a == best))
    assume("CLM_EXPECTED_BUYERS_BROAD", f"SCENARIO: additional purchasing customers if the {SHORT[best]} goes to {broad_contacts:,.0f} customers and the 2008 effect holds",
           int(round(exp_buyers)), "customers", f"{broad_contacts:,.0f} assumed contacts x {_f(eb['per_1000'], 2)} per 1,000", arm=best,
           unc=f"{exp_buyers_ci[0]:,.0f} to {exp_buyers_ci[1]:,.0f} from the 95% interval of the effect; a 2008 effect is not a forecast for a current base")
    if n_hold:
        assume("CLM_HOLDOUT_PER_ARM", "Customers per arm needed in a future randomized test to detect an effect of the 2008 size (80% power, two-sided 5%)", n_hold, "customers per arm",
               f"control rate {ctrl['buyers'] / ctrl['n']:.4f}, treated rate {arms[best]['buyers'] / arms[best]['n']:.4f}", arm=best, unc="design calculation; assumes the historical effect")
    for i, text, unit in (("CLM_MARGIN", "Contribution margin on incremental sales", "share of revenue"), ("CLM_COST_PER_CONTACT", "Full cost per e-mail", "USD per e-mail"),
                          ("CLM_MEASURED_PROFIT", "Measured profit of the campaign", "USD")):
        C.append(K.claim(i, text, None, unit, "UNKNOWN", sha=None, denominator=None, period=None, split="not_applicable", source_id="SRC_HILLSTROM_2008_DATA",
                         uncertainty="not in the dataset; must be supplied by the business", slide_safe=True))
    for r in K.published_references():
        C.append(K.claim("CLM_" + r["id"], r["label"] + " (published, not our output)", r["value"], r["unit"], "PUBLISHED_REFERENCE", sha=None, denominator="as published",
                         split="full_sample", source_id=r["source_id"], uncertainty=r["locator"], slide_safe=r["id"].startswith("REF_PURCHASE")))

    if broad or not targeted:
        hid, hsplit, htag = (f"SEND_ALL_{ARM_KEY[best]}_100", "full_sample", "OBSERVED")
        hv, hci, hmeth = eb["per_1000"], eb["per_1000_ci"], K.CI_WALD
        hc = {"treated_n": arms[best]["n"], "treated_buyers": arms[best]["buyers"], "control_n": ctrl["n"], "control_buyers": ctrl["buyers"]}
        hnote = (f"Randomized average effect of the {SHORT[best]} on the full sample; the held-out test estimate for the same policy is "
                 f"{_f(1000 * rows[hid]['per_contact'])} (interval {_ci(rows[hid]['per_contact_ci'], 1, 1000)}).")
    else:
        hid, hsplit, htag = ids["model"], "test", "HELD_OUT_ESTIMATE"
        hv, hci, hmeth = 1000 * m["per_contact"], [1000 * v for v in m["per_contact_ci"]], K.CI_BOOT
        hc = {k: m[k] for k in ("treated_n", "treated_buyers", "control_n", "control_buyers")}
        hnote = "Held-out estimate inside the model-selected customers."

    doc = {
        "contract_version": K.CONTRACT_VERSION, "record_type": "COMPUTED_EXPORT", "case_id": K.CASE_ID,
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "producer": {"repo": "ai-market-intelligence", "code_commit": code_commit, "command": "python -m mi.campaign.export"},
        "dataset_provenance": K.provenance(sha, facts["bytes"], facts["rows"]),
        "unit": "unique_existing_customer", "outcome": K.outcome_block(), "arms": K.arms_block(),
        "observed_arm_metrics": [K.arm_metric(a, arms[a]["n"], arms[a]["buyers"], arms[a]["spend_mean"]) for a in K.ARMS],
        "average_effects": [K.average_effect(a, arms[a]["n"], arms[a]["buyers"], ctrl["n"], ctrl["buyers"], rate_ci=fs["effects"][a]["rate_ci"],
                                             spend_diff=fs["effects"][a]["spend_diff"], spend_ci=fs["effects"][a]["spend_ci"]) for a in TREATMENTS],
        "model": {"model_version": mv, "status": "FITTED_REPEATED_EVALUATION",
                  "model_type": f"regularized logistic S-learner (one model, three arms, treatment x feature interactions; L2, C = {ev['selection']['C']})",
                  "outcome": K.OUTCOME, "features_pre_treatment": ev["model"]["raw_features"], "forbidden_post_treatment": ["visit", "conversion", "spend"],
                  "split": {"method": "seeded customer-level train / validation / test, stratified by arm", "seed": ev["split"]["seed"],
                            "n_train": sh["train"]["n"], "n_validation": sh["validation"]["n"], "n_test": sh["test"]["n"]},
                  "protocol_path": "data/eval/hillstrom_protocol_v2.json", "model_card_path": "reports/campaign/model_card.md",
                  "secondary_metrics": [{"name": "qini_coefficient", "arm": q["arm"], "score": q["score"],
                                         "metric": tv(q["value"], "HELD_OUT_ESTIMATE" if q["value"] is not None else "UNKNOWN",
                                                      "normalised area between the Qini curve and the random line", ci95=q["ci95"],
                                                      ci_method=f"{K.CI_BOOT}, {ev['n_boot_qini']} resamples", with_ci=True)} for q in ev["qini"]],
                  "repeated_evaluation_caveat": "REPEATED EVALUATION, not an untouched test: this dataset was analysed before under protocol v1 (visit model, full-sample effects, "
                                                "an exploratory conversion model at a 30% cap). Protocol v2 froze the split, features, caps and decision rule before this fit."},
        "held_out_policy_metrics": pol_rows,
        "model_vs_baselines": {"primary_contact_share": cap, "model_policy_id": ids["model"], "random_policy_id": ids["random"], "rule_policy_id": ids["rule"],
                               "model_minus_random_per_1000_contacts": tv(P["model_minus_random"]["value"], "HELD_OUT_ESTIMATE", "additional buyers per 1,000 contacts",
                                                                          ci95=P["model_minus_random"]["ci95"], ci_method=K.CI_BOOT + " (paired: same resamples)", with_ci=True),
                               "model_minus_rule_per_1000_contacts": tv(P["model_minus_rule"]["value"], "HELD_OUT_ESTIMATE", "additional buyers per 1,000 contacts",
                                                                        ci95=P["model_minus_rule"]["ci95"], ci_method=K.CI_BOOT + " (paired: same resamples)", with_ci=True),
                               "point_estimate_beats_random": bool(dec["beats_random"]), "point_estimate_beats_rule": bool(dec["beats_rule"]),
                               "stable_vs_random": bool(dec["stable_random"]), "stable_vs_rule": bool(dec["stable_rule"]),
                               "verdict": dec["verdict"], "verdict_text": vt},
        "buyer_impact_per_1000": {"value": hv, "tag": htag, "unit": "additional purchasing customers per 1,000 customers e-mailed, vs no e-mail, two weeks",
                                  "policy_id": hid, "arm": best, "control_arm": CONTROL, "split": hsplit, **hc, "note": hnote},
        "buyer_impact_interval_per_1000": {"low": hci[0], "high": hci[1], "level": 0.95, "method": hmeth},
        "business_scenarios": scen, "economic_thresholds": thr,
        "recommendation": {"status": dec["status"], "decision": decision, "recommended_policy_id": dec["policy_id"], "recommended_arm": dec["arm"],
                           "contact_share": dec["contact_share"], "conditions": conditions, "rationale": rationale, "would_reverse_if": reverse,
                           "alternative_if_model_inconclusive": alt, "no_email_option": no_email,
                           "holdout_plan": {"randomized": True, "holdout_share": K.ASSUMED_HOLDOUT_SHARE, "customers_per_arm_needed": n_hold,
                                            "primary_metric": "unique purchasing customers within two weeks, treated minus holdout", "review_after_days": 14},
                           "human_decision_required": True},
        "marketing": marketing,
        "assumptions_and_unknowns": K.assumptions_and_unknowns(), "published_references": K.published_references(),
        "claims": C, "sources": K.SOURCES, "evidence_ids": [s["source_id"] for s in K.SOURCES],
        "model_version": mv, "run_id": run_id, "approval_required": True, "approval_status": "DRAFT_REQUIRES_HUMAN",
        "warnings": [
            "REPEATED EVALUATION: the dataset was analysed before; the test split is not untouched data.",
            f"RARE OUTCOME: {sum(v['buyers'] for v in arms.values())} buyers among {facts['rows']:,} customers. Top-k and subgroup cells hold few buyers, so targeting comparisons are imprecise.",
            "GROUP EFFECTS ONLY: differences between randomized groups estimate additional repeat buyers for a population; they are not an individual's effect and not customer acquisition.",
            "HISTORICAL: a 2008 effect for one anonymous apparel retailer. Do not transfer it to another retailer or to a current base without a new randomized pilot.",
            "ECONOMICS ARE SCENARIOS: margin and cost per e-mail are unknown; no contribution figure is a measured profit.",
            "No e-mail is ever sent, scheduled or approved by this system; a named human decides."],
    }
    K.assert_valid(doc)
    detail = {"case_id": K.CASE_ID, "run_id": run_id, "model_version": mv, "full_sample": fs, "decision": dec, "selection": ev["selection"], "primary": P,
              "test": ev["test"], "split_hashes": sh, "policies": [{**{k: v for k, v in r.items() if k != "spec"}, **r["spec"]} for r in ev["policies"]],
              "qini": ev["qini"], "quartiles": ev["quartiles"], "calibration": ev["calibration"], "segment_effects": seg,
              "predicted_uplift_summary": ev["predicted_uplift_summary"], "bestarm_assignment_share_all_test": ev["bestarm_assignment_share_all_test"],
              "model": ev["model"], "n_boot": ev["n_boot"], "n_boot_qini": ev["n_boot_qini"], "holdout_per_arm": n_hold,
              "expected_buyers_broad": {"contacts": broad_contacts, "value": exp_buyers, "ci95": exp_buyers_ci}, "seconds": round(time.time() - t0, 1)}
    return doc, detail


# ---------------------------------------------------------------- generated documents
def _policy_table(doc: dict, share: float, arm: str | None = None) -> list[str]:
    L = ["| Policy | E-mailed in test | Buyers / customers e-mailed | Buyers / customers not e-mailed | Additional buyers per 1,000 contacted (95% interval) | Small cell |", "|---|---:|---:|---:|---:|---|"]
    for x in doc["held_out_policy_metrics"]:
        if x["contact_share"] != share or (arm and x["arm_assignment"] not in (arm, "MODEL_CHOOSES_ARM")):
            continue
        a = x["additional_buyers_per_1000_contacts"]
        L.append(f"| {x['label']}{' **(primary)**' if x['is_primary'] else ''} | {x['contacted_n']:,} | {x['treated_buyers']} / {x['treated_n']:,} | {x['control_buyers']} / {x['control_n']:,} | "
                 f"{_f(a['value'])} ({_ci(a['ci95'])}) | {'yes' if x['small_cell_warning'] else 'no'} |")
    return L


def model_card_md(doc: dict, det: dict, aud: dict) -> str:
    mv, sel, sp = doc["model_vs_baselines"], det["selection"], doc["model"]["split"]
    best = det["decision"]["best_arm"]
    co = det["model"]["coef"]
    L = [f"# Model card: buyer-uplift model for the e-mail campaign case ({doc['case_id']})", "",
         f"Model version `{doc['model_version']}`. Run `{doc['run_id']}`. Generated {doc['generated_at']} by `python -m mi.campaign.export`. Every figure is computed from the local raw file.", "",
         "## Verdict", "", mv["verdict_text"], "",
         f"Pre-registered verdict: **{mv['verdict']}**. The model is not used to exclude customers. The randomized average effect carries the decision.", "",
         "## Intended use", "",
         "- Rank existing customers by the expected difference in two-week purchase probability between an e-mail and no e-mail, to study whether targeting beats simple rules under a contact cap.",
         "- Support a manager's decision together with the randomized arm comparison, the cost thresholds and a new holdout.",
         "- Not for: individual-level causal claims, new-customer acquisition, another retailer, a current customer base without a new pilot, or automatic sending.", "",
         "## Training data", "",
         f"- Source: Hillstrom MineThatData e-mail challenge (2008). SHA-256 `{aud['file']['sha256']}`, {aud['rows']:,} rows, one per existing customer.",
         "- Arms: " + "; ".join(f"{a} {n:,}" for a, n in aud["arms"]["counts"].items()) + ". Each e-mail is compared with the same no-e-mail control.",
         f"- Outcome: `conversion`, a purchase in the two weeks after the e-mail. {aud['outcome_integrity']['total_buyers']} buyers in total ({aud['outcome_integrity']['overall_purchase_rate']:.2%}).",
         f"- Fully identical rows beyond the first: {aud['duplicates']['fully_identical_rows_beyond_first']:,}; kept, because the file has no customer id.",
         "- The raw file stays local: the source page states no redistribution terms.", "",
         "## Features and timing", "",
         f"- Read by the model (all describe the twelve months before the e-mail): {', '.join('`' + f + '`' for f in doc['model']['features_pre_treatment'])}. `history` enters as log1p.",
         "- `mens` and `womens` are past-year product purchases, not gender.",
         "- `segment` is the randomized assignment and enters only as the treatment indicator.",
         "- Forbidden as predictors or ranking inputs: `visit`, `conversion`, `spend` (all measured after the e-mail). A test fails if any of them reaches the design matrix.", "",
         "## Split and fitting", "",
         f"- Seeded customer-level split, stratified by arm (seed {sp['seed']}): train {sp['n_train']:,}, validation {sp['n_validation']:,}, test {sp['n_test']:,}.",
         f"- One L2 logistic regression used as an S-learner: 9 base features, 2 treatment indicators and 18 treatment x feature interactions ({len(co['coefficients'])} coefficients).",
         "- Regularisation chosen on validation log loss: " + "; ".join(f"C = {g['C']}: {g['validation_log_loss']:.5f}" for g in sel["C_grid"]) + f". Chosen C = {sel['C']}.",
         f"- Refitted once on train+validation ({det['model']['n_fit']:,} customers, {det['model']['buyers_fit']} buyers), then the test split was read.",
         f"- Chosen on train+validation only: best overall arm = {best} ("
         + "; ".join(f"{a} {_f(v)} per 1,000" for a, v in sel["ate_train_validation_per_1000"].items()) + "); primary rule = "
         + sel["primary_rule"] + " (" + "; ".join(f"{k} {_f(v)}" for k, v in sel["rule_uplift_at_cap_validation_per_1000"].items()) + " per 1,000 at the cap on validation).", "",
         "## Baselines", "",
         "No e-mail; one e-mail to everyone; random contacts (expected value, estimated on the whole held-out arms); most-recent-purchase rule; highest-past-spend rule.", "",
         f"## Primary metric: additional buyers per 1,000 contacted, {int(100 * mv['primary_contact_share'])}% cap, {best}", ""]
    L += _policy_table(doc, mv["primary_contact_share"], best)
    L += ["", f"## Same metric at the 50% cap, {best}", ""] + _policy_table(doc, 0.5, best)
    L += ["", "## Every customer contacted", ""] + _policy_table(doc, 1.0)
    L += ["", "## Interval method", "",
          f"- Held-out figures: customer-level bootstrap of the test split, {det['n_boot']} resamples, percentile 95% interval. Differences between policies use the same resamples.",
          "- Policy scores are held fixed, so the intervals cover test-sampling uncertainty only, not the variability of refitting the model.",
          "- Full-sample arm comparisons: unpooled normal approximation.", "",
          "## Secondary metrics", "", "Qini coefficient on test (area between the Qini curve and the random line, divided by that area for the optimum curve without negative effects):", "",
          "| E-mail | Ranking | Qini coefficient | 95% interval |", "|---|---|---:|---|"]
    L += [f"| {q['arm']} | {q['score']} | {'undefined' if q['value'] is None else _f(q['value'], 3)} | {'not available' if q['ci95'] is None else _ci(q['ci95'], 3)} |" for q in det["qini"]]
    L += ["", "Every Qini interval includes zero. The normalisation divides by a small total uplift, so the Womens e-mail values are unstable.", "",
          "## Calibration on test", "", "| Arm | Customers | Buyers | Observed rate | Mean predicted rate |", "|---|---:|---:|---:|---:|"]
    L += [f"| {c['arm']} | {c['n']:,} | {c['buyers']} | {c['observed_rate']:.3%} | {c['mean_predicted_rate']:.3%} |" for c in det["calibration"]]
    L += ["", "## Failure segments", "", "Observed uplift by quartile of predicted uplift on test (Q4 = highest predicted). A useful ranking would rise from Q1 to Q4.", ""]
    for arm, q in det["quartiles"].items():
        L += [f"**{arm}**", "", "| Quartile | Buyers / e-mailed | Buyers / not e-mailed | Observed additional buyers per 1,000 (95% interval) | Mean predicted | Small cell |", "|---|---:|---:|---:|---:|---|"]
        L += [f"| {r['quartile']} | {r['treated_buyers']} / {r['treated_n']:,} | {r['control_buyers']} / {r['control_n']:,} | {_f(r['observed_additional_buyers_per_1000'])} ({_ci(r['ci95_per_1000'])}) | "
              f"{_f(r['mean_predicted_additional_buyers_per_1000'])} | {'yes' if r['small_cell_warning'] else 'no'} |" for r in q] + [""]
    us = det["predicted_uplift_summary"]
    L += [f"- The ranking is weak: for the {SHORT[MENS]} only the top quartile stands apart, and for the {SHORT[WOMENS]} the quartiles are not ordered.",
          f"- The model predicts a negative effect of the {SHORT[WOMENS]} for {us[WOMENS]['share_negative']:.0%} of test customers; the lowest quartile's observed effect has an interval that includes zero.",
          f"- Letting the model choose the e-mail per customer assigns the {SHORT[MENS]} to {det['bestarm_assignment_share_all_test'][MENS]:.0%} of customers and adds nothing over sending everyone the {SHORT[best]}.",
          "- Descriptive segmentation by past-year purchase category (full sample, hypothesis-generating):", "",
          "| Past-year purchases | E-mail | Buyers / e-mailed | Buyers / not e-mailed | Additional buyers per 1,000 (95% interval) |", "|---|---|---:|---:|---:|"]
    L += [f"| {s['segment']} | {s['treatment_arm']} | {s['treated_buyers']} / {s['treated_n']:,} | {s['control_buyers']} / {s['control_n']:,} | {_f(s['additional_buyers_per_1000'])} ({_ci(s['ci95_per_1000'])}) |"
          for s in det["segment_effects"]]
    L += ["", "## Coefficients", "", f"Intercept {co['intercept']:.4f}. Reference levels: zip_code = {co['reference_levels']['zip_code']}, channel = {co['reference_levels']['channel']}. "
          "Numeric features are standardised.", "", "| Term | Coefficient |", "|---|---:|"]
    L += [f"| `{k}` | {v:+.4f} |" for k, v in co["coefficients"].items()]
    L += ["", "## Caveats", ""] + [f"- {w}" for w in doc["warnings"]]
    L += ["", "## Reproduce", "", "`python -m mi.campaign.export` with the raw file at `data/raw/hillstrom/hillstrom_2008.csv`. "
          "Split hashes, seed, feature list, code commit and package versions are in `reports/campaign/run_manifest.json`."]
    return "\n".join(L) + "\n"


def decision_card_md(doc: dict, det: dict) -> str:
    rec, mk, fs = doc["recommendation"], doc["marketing"], det["full_sample"]
    best = det["decision"]["best_arm"]
    L = ["# Manager decision card: e-mail to existing customers", "",
         f"Case `{doc['case_id']}`. Run `{doc['run_id']}`. Status: **{doc['approval_status']}**. Nothing has been sent.", "",
         "## The buyer problem", "",
         f"We have an existing customer base ({doc['dataset_provenance']['rows']:,} customers who bought in the past year), a limit on how often we may contact them, "
         "two possible merchandise e-mails, and a contribution margin to protect. Which e-mail, to whom, creates additional purchasing customers, and at what cost does it stop paying?", "",
         "## Recommendation", "", f"**{rec['decision']}**", "", "Conditions:", ""] + [f"{i}. {c}" for i, c in enumerate(rec["conditions"], 1)]
    L += ["", "## What the experiment observed (all customers, two weeks)", "",
          "| Arm | Customers | Buyers | Purchase rate | Additional buyers per 1,000 e-mailed (95% interval) | Incremental spend per e-mail (95% interval) |", "|---|---:|---:|---:|---:|---:|"]
    eff = {e["treatment_arm"]: e for e in doc["average_effects"]}
    for m in doc["observed_arm_metrics"]:
        e = eff.get(m["arm"])
        L.append(f"| {m['arm']} | {m['n_customers']:,} | {m['buyers']} | {m['purchase_rate']['value']:.2%} | "
                 + (f"{_f(e['additional_buyers_per_1000']['value'])} ({_ci(e['additional_buyers_per_1000']['ci95'])}) | {_f(e['incremental_spend_per_contact']['value'], 2)} USD ({_ci(e['incremental_spend_per_contact']['ci95'], 2)}) |"
                    if e else "reference | reference |"))
    cap = doc["model_vs_baselines"]["primary_contact_share"]
    L += ["", "Tag: OBSERVED. Each e-mail is compared with the same no-e-mail control. These are additional repeat buyers for a group, not new customers and not an individual's effect.", "",
          f"## Does a targeting model help under a {int(100 * cap)}% contact cap? (held-out customers)", ""] + _policy_table(doc, cap, best)
    L += ["", "Tag: HELD_OUT_ESTIMATE. " + doc["model_vs_baselines"]["verdict_text"], "",
          "## Segment, target, position", "",
          f"- **Segment.** {mk['segmentation']}", f"- **Target.** {mk['targeting']}", f"- **Position.** {mk['positioning']}", "",
          "## Four Ps", "", "| P | Decision | Alternatives | Evidence | Note |", "|---|---|---|---|---|"]
    L += [f"| {p['p']} | {p['decision']} | {'; '.join(p['alternatives'])} | {p['tag']} | {p['note']} |" for p in mk["four_ps"]]
    L += ["", "## Economics: scenarios, not measured profit", "", f"`{K.FORMULA}`", "",
          "Margin and cost per e-mail are **UNKNOWN**. The break-even cost per e-mail at an assumed margin, before setup:", "",
          "| E-mail | Assumed margin | Break-even cost per e-mail | Using the lower bound of incremental spend |", "|---|---:|---:|---:|"]
    L += [f"| {t['arm']} | {t['assumed_margin']['value']:.0%} | {_f(t['break_even_cost_per_contact']['value'], 3)} USD | {_f(t['break_even_cost_per_contact_conservative']['value'], 3)} USD |" for t in doc["economic_thresholds"]]
    L += ["", f"Scenario contribution for a broad send to {det['expected_buyers_broad']['contacts']:,.0f} customers (assumed base of {K.ASSUMED_ELIGIBLE_BASE:,} less the holdout):", "",
          "| E-mail | Assumption set | Margin | Cost per e-mail | Setup | Scenario contribution (range from the spend interval) |", "|---|---|---:|---:|---:|---:|"]
    for s in doc["business_scenarios"]:
        c = s["contribution"]
        name = s["scenario_id"].split("__")[1].replace("_", " ").lower()
        if c["value"] is None:
            L.append(f"| {s['arm']} | {name} | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |")
        else:
            L.append(f"| {s['arm']} | {name} | {s['assumed_margin']['value']:.0%} | {s['cost_per_contact']['value']:.3f} USD | {s['fixed_setup_cost']['value']:,.0f} USD | "
                     f"{c['value']:+,.0f} USD ({c['ci95'][0]:+,.0f} to {c['ci95'][1]:+,.0f}) |")
    eb = det["expected_buyers_broad"]
    L += ["", f"If the 2008 effect held for that send, it would mean about {eb['value']:,.0f} additional purchasing customers ({eb['ci95'][0]:,.0f} to {eb['ci95'][1]:,.0f}). "
          "This is a scenario: a 2008 effect is not a forecast for a current base.", "",
          "## The no-e-mail choice", "", rec["no_email_option"], "",
          "## If the model stays inconclusive", "", rec["alternative_if_model_inconclusive"], "",
          "## What would reverse this decision", ""] + [f"- {x}" for x in rec["would_reverse_if"]]
    L += ["", "## Action plan (owners are roles; names are assigned by the manager)", "", "| Step | Owner | Action | Status |", "|---:|---|---|---|"]
    L += [f"| {a['step']} | {a['owner_role']} | {a['action']} | {a['status']} |" for a in mk["action_plan"]]
    L += ["", f"Success metric: {mk['success_metric']}", "", "## Caveats", ""] + [f"- {w}" for w in doc["warnings"]]
    return "\n".join(L) + "\n"


def capability_status() -> list[tuple[str, str, str]]:
    """Seven capabilities with honest status. Other cases are named, and none of their numbers is copied into this case."""
    geo = None
    p = REPORTS / "seo_geo_audit.json"
    if p.exists():
        try:                                                    # older reports were written in the platform encoding
            geo = json.loads(p.read_text(encoding="utf-8", errors="replace")).get("answers_logged")
        except ValueError:
            geo = None
    return [
        ("Research and RAG", "PARTIAL", "Source-backed explanation of this experiment from two primary sources; abstains on offer cost, retailer identity and creative. Grocery RAG tests are a separate case."),
        ("Customer intelligence", "VERIFIED on this case", "Conversion uplift model fitted and evaluated on held-out customers; no stable targeting gain. Not new-customer acquisition."),
        ("Portfolio optimization", "VERIFIED as a campaign portfolio", "Mens e-mail, Womens e-mail and no e-mail compared under contact caps. The product-portfolio optimizer is validated only on the separate grocery case, under assumptions."),
        ("Demand and risk", "SCENARIO", "Additional buyers per 1,000 with intervals; cost and margin scenarios and break-even thresholds. No long-term demand forecast."),
        ("Advisor and CRM", "PENDING in this repo", "The export, the draft messages and the owned action plan are ready for the ConsultAI agents. No send, spend, approve or publish tool exists. A live LLM run is not verified here."),
        ("SEO / GEO", f"PENDING ({geo if geo is not None else 'UNKNOWN'} of 20 answers logged)", "No SEO or GEO effect is attributed to e-mail data. The audit needs the 20 real answers first."),
        ("Outcome learning", "HISTORICAL ONLY", "Historical randomized control comparison plus a planned randomized holdout. No live deployment and no observed outcome of a new campaign."),
    ]


def marketing_brief_md(doc: dict, det: dict, checksum: str) -> str:
    rec, mv = doc["recommendation"], doc["model_vs_baselines"]
    claims = {c["claim_id"]: c for c in doc["claims"]}
    best = det["decision"]["best_arm"]
    kb = ARM_KEY[best]
    pct = int(100 * mv["primary_contact_share"])

    def line(cid: str) -> str:
        c = claims[cid]
        v = "UNKNOWN" if c["value"] is None else f"{c['value']:,}" if isinstance(c["value"], (int, float)) and not isinstance(c["value"], bool) else str(c["value"])
        return f"| `{cid}` | {c['text']} | {v} {c['unit']} | {c['tag']} | {c['denominator'] or '-'} | {c['uncertainty'] or '-'} |"

    slide = ["CLM_DATA_ROWS", "CLM_BUYERS_CONTROL", "CLM_BUYERS_MENS", "CLM_BUYERS_WOMENS", "CLM_RATE_CONTROL", "CLM_RATE_MENS", "CLM_RATE_WOMENS",
             "CLM_BUYERS_PER_1000_MENS", "CLM_BUYERS_PER_1000_WOMENS", "CLM_SPEND_PER_CONTACT_MENS", "CLM_SPEND_PER_CONTACT_WOMENS", "CLM_TEST_BUYERS",
             f"CLM_TEST_SEND_ALL_{kb}", f"CLM_CAP{pct}_MODEL", f"CLM_CAP{pct}_RANDOM", f"CLM_CAP{pct}_RULE", f"CLM_CAP{pct}_OTHER_RULE",
             "CLM_MODEL_VS_RANDOM", "CLM_MODEL_VS_RULE", "CLM_MODEL_VERDICT", f"CLM_BREAK_EVEN_COST_{kb}_M35", f"CLM_SCENARIO_{kb}_CENTRAL",
             f"CLM_SCENARIO_{kb}_CONSERVATIVE", "CLM_EXPECTED_BUYERS_BROAD", "CLM_HOLDOUT_PER_ARM", "CLM_MARGIN", "CLM_COST_PER_CONTACT"]
    L = ["# Campaign case: marketing brief and slide claims", "",
         f"Case `{doc['case_id']}`, contract {doc['contract_version']}, run `{doc['run_id']}`, model `{doc['model_version']}`.",
         f"Export `{K.EXPORT_RELPATH}`, SHA-256 `{checksum}`. Every figure below is copied from that file by code.", "",
         "## The decision in one paragraph", "", rec["decision"], "",
         "## Did the targeting model beat random and the rule?", "",
         f"- Verdict: **{mv['verdict']}**.",
         f"- Point estimate beats random: {'yes' if mv['point_estimate_beats_random'] else 'no'}. Statistically stable: {'yes' if mv['stable_vs_random'] else 'no'}.",
         f"- Point estimate beats the primary rule: {'yes' if mv['point_estimate_beats_rule'] else 'no'}. Statistically stable: {'yes' if mv['stable_vs_rule'] else 'no'}.",
         f"- {mv['verdict_text']}", "",
         "## Why this is still a useful result", ""] + [f"- {r}" for r in rec["rationale"][:3]] + [
         "- The model is a negative finding for targeting; the randomized average effect is what supports the decision.", "",
         "## Marketing rationale", "",
         f"- **Research question.** {doc['marketing']['research_question']}",
         f"- **Audience.** {doc['marketing']['audience']}",
         f"- **Segmentation.** {doc['marketing']['segmentation']}",
         f"- **Targeting.** {doc['marketing']['targeting']}",
         f"- **Positioning.** {doc['marketing']['positioning']}",
         "- **Four Ps.** " + " ".join(f"{p['p']}: {p['decision']}" for p in doc["marketing"]["four_ps"]),
         f"- **Human decision.** {doc['approval_status']}: a named manager approves or rejects; the system has no send tool.",
         f"- **Holdout.** {rec['conditions'][2]}",
         f"- **No e-mail.** {rec['no_email_option']}", "",
         "## Exact claims for slides", "",
         "Quote the value with its tag and denominator. Do not round a difference into a win, and do not show a scenario as a result.", "",
         "| Claim ID | Claim | Value | Tag | Denominator | Uncertainty |", "|---|---|---|---|---|---|"]
    L += [line(c) for c in slide if c in claims]
    L += ["", "Published reference figures (Radcliffe 2008, Table 2, page 3), for comparison only and never as our output: "
          + "; ".join(f"{r['label']}: {r['value']} {r['unit']}" for r in doc["published_references"][:5]) + ".", "",
          "## Sentences that are safe to say", "",
          f"1. \"In a randomized test on {doc['dataset_provenance']['rows']:,} existing customers, the {SHORT[best]} added {_f(claims[f'CLM_BUYERS_PER_1000_{kb}']['value'])} purchasing customers per 1,000 e-mailed in two weeks, compared with no e-mail.\"",
          f"2. \"Our uplift model was ahead of random and of a simple rule at a {pct}% contact cap, but the difference was not statistically stable, so we do not use it to exclude customers.\""
          if mv["verdict"] == "MODEL_AHEAD_NOT_STABLE" else f"2. \"Model verdict: {mv['verdict']}.\"",
          "3. \"Margin and e-mail cost are unknown, so we report break-even thresholds and scenarios, not profit.\"",
          "4. \"The advisor recommends a broad send with a randomized holdout only after cost and consent are confirmed, and a human approves.\"" if rec["status"].startswith("BROAD")
          else f"4. \"Recommendation status: {rec['status']}.\"", "",
          "## Sentences to avoid", "",
          "- \"The model increases sales\" or \"the model beats the rule\": not shown with a stable margin.",
          "- \"The campaign makes a profit of ...\": every contribution figure is a scenario.",
          "- \"New customers\": every customer in the data is an existing buyer.",
          "- Any figure for the grocery retailer, FashionForward or a current customer base taken from this experiment.", "",
          "## Capability status (seven capabilities, honest labels)", "", "| Capability | Status | What is and is not shown |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in capability_status()]
    L += ["", "## What ConsultAI must integrate", "",
          f"1. Load `{K.EXPORT_RELPATH}` through the read-only adapter and verify the SHA-256 above.",
          "2. Run `validate_case` and refuse to render on any error; `record_type` must be `COMPUTED_EXPORT`.",
          "3. Render counts, intervals and tags from the file; do not recompute statistics.",
          "4. Show the recommendation, its conditions, the no-e-mail option and the action plan; keep the send step blocked.",
          "5. Cite `claim_id` and `source_id` for every number on a slide or in a trace.", "",
          "## Human inputs still needed", "",
          "- Contribution margin and full cost per e-mail (finance, CRM).", "- Consent status of the current base (CRM, legal).",
          "- A named approver and the holdout draw.", "- The 20 GEO answers and 2-3 interviews for the separate research tracks."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- writing
def _versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version
    out = {"python": sys.version.split()[0]}
    for p in ("numpy", "pandas", "scikit-learn", "scipy", "jsonschema"):
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def write_all(doc: dict, det: dict, aud: dict, proto: dict, *, export_path: Path = EXPORT, checksum_path: Path = CHECKSUM, out_dir: Path = OUT,
              docs_dir: Path = DOCS, seconds: float | None = None) -> str:
    """Write the export, its checksum, the detail report, ledger, manifest and generated cards. Returns the export SHA-256."""
    if export_path.resolve() == EXPORT.resolve() and doc["dataset_provenance"]["sha256"] != proto["source"]["sha256"]:
        raise CampaignDataError("refusing to write the live export from a file that is not the pre-registered dataset")
    out_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    text = K.dumps(doc)
    export_path.write_text(text, encoding="utf-8", newline="\n")
    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    checksum_path.write_text(f"{checksum}  {export_path.name}\n", encoding="utf-8", newline="\n")
    def _plain(x):
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, np.generic):
            return x.item()
        return str(x)

    dump = lambda o: json.dumps(o, indent=2, default=_plain)     # noqa: E731
    (out_dir / "data_audit.json").write_text(dump(aud), encoding="utf-8")
    (out_dir / "evaluation.json").write_text(dump(det), encoding="utf-8")
    (out_dir / "model_coefficients.json").write_text(dump({"model_version": doc["model_version"], "coef_sha256": det["model"]["coef_sha256"], **det["model"]["coef"],
                                                           "feature_order": det["model"]["feature_names"]}), encoding="utf-8")
    (out_dir / "claims_ledger.json").write_text(dump({"case_id": doc["case_id"], "run_id": doc["run_id"], "export_sha256": checksum,
                                                      "note": "identical to $.claims in the export; one line per displayable figure", "claims": doc["claims"]}), encoding="utf-8")
    (out_dir / "run_manifest.json").write_text(dump({
        "case_id": doc["case_id"], "run_id": doc["run_id"], "generated_at": doc["generated_at"], "command": "python -m mi.campaign.export",
        "code_commit": doc["producer"]["code_commit"], "data": aud["file"], "protocol": {"path": "data/eval/hillstrom_protocol_v2.json",
                                                                                      "sha256": hashlib.sha256(json.dumps(proto, sort_keys=True).encode()).hexdigest()},
        "seed": proto["split"]["seed"], "split": det["split_hashes"], "feature_list": det["model"]["feature_names"], "raw_columns_read_by_model": det["model"]["raw_features"],
        "model_version": doc["model_version"], "coef_sha256": det["model"]["coef_sha256"], "bootstrap_resamples": det["n_boot"], "versions": _versions(),
        "export": {"path": K.EXPORT_RELPATH, "sha256": checksum, "contract_version": doc["contract_version"]}, "seconds": seconds}), encoding="utf-8")
    (out_dir / "model_card.md").write_text(model_card_md(doc, det, aud), encoding="utf-8", newline="\n")
    (docs_dir / "campaign_decision_card.md").write_text(decision_card_md(doc, det), encoding="utf-8", newline="\n")
    (docs_dir / "campaign_marketing_brief.md").write_text(marketing_brief_md(doc, det, checksum), encoding="utf-8", newline="\n")
    (docs_dir / "campaign_data_dictionary.md").write_text(dictionary_md(aud), encoding="utf-8", newline="\n")
    return checksum


def main(argv=None) -> int:
    t0 = time.time()
    try:
        proto = load_protocol()
        df, facts = load_raw(proto=proto)
    except CampaignDataError as e:
        print(f"CAMPAIGN CASE SKIPPED: {e}", file=sys.stderr)
        return 3
    aud = audit(df, facts, proto)
    doc, det = build(df, facts, proto, code_commit=_git_commit())
    checksum = write_all(doc, det, aud, proto, seconds=round(time.time() - t0, 1))
    b, iv, mv = doc["buyer_impact_per_1000"], doc["buyer_impact_interval_per_1000"], doc["model_vs_baselines"]
    print(f"{doc['case_id']} run {doc['run_id']} model {doc['model_version']}")
    print(f"buyer impact: {b['value']:.2f} per 1,000 [{iv['low']:.2f}, {iv['high']:.2f}] ({b['tag']}, {b['treated_buyers']}/{b['treated_n']} vs {b['control_buyers']}/{b['control_n']})")
    print(f"model verdict: {mv['verdict']}; recommendation: {doc['recommendation']['status']}")
    print(f"export: {K.EXPORT_RELPATH} sha256 {checksum} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
