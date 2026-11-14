"""Measurement & learning.

1. campaign_history(): DESCRIPTIVE analysis of real Complete Journey campaigns — recipients vs other
   active households BEFORE each campaign starts, plus redemption rates. Shows selection bias; it is
   not an effect estimate (assignment is not documented as randomized).
2. sample_size(): households per arm to detect the break-even uplift (two proportions).
3. simulated_outcome(): a clearly SIMULATED pilot result (seeded) for exercising the rule. Never real.
4. decide(): the prewritten STOP / CHANGE / EXPAND / INCONCLUSIVE rule from configs/policy.json.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from mi.config import load_config
from mi.ingest.load import load


def campaign_history() -> dict:
    tx, camp, cd, red = load("transactions"), load("campaigns"), load("campaign_descriptions"), load("coupon_redemptions")
    wk_end = tx.groupby("week").transaction_timestamp.max().dt.normalize()
    hh_week = tx.groupby(["household_id", "week"]).sales_value.sum().reset_index()
    rows = []
    for _, c in cd.iterrows():
        start = c.start_date
        start_week = int((wk_end >= start).idxmax()) if (wk_end >= start).any() else None
        if start_week is None or start_week < 10:
            continue  # need 8 pre-weeks inside the data
        pre = hh_week[(hh_week.week >= start_week - 8) & (hh_week.week < start_week)]
        spend = pre.groupby("household_id").sales_value.sum() / 8
        recips = set(camp[camp.campaign_id == c.campaign_id].household_id)
        active = spend.index
        r_sp = spend[spend.index.isin(recips)]
        o_sp = spend[~spend.index.isin(recips)]
        n_red = red[red.campaign_id == c.campaign_id].household_id.nunique()
        rows.append({"campaign_id": c.campaign_id, "type": c.campaign_type, "start": str(start.date()),
                     "recipients": len(recips), "recipients_active_pre": int(len(r_sp)),
                     "pre_weekly_spend_recipients": float(r_sp.mean()) if len(r_sp) else None,
                     "pre_weekly_spend_others": float(o_sp.mean()) if len(o_sp) else None,
                     "redeeming_households": int(n_red), "redemption_rate": n_red / max(1, len(recips))})
    df = pd.DataFrame(rows)
    by_type = df.groupby("type").agg(campaigns=("campaign_id", "count"), recipients=("recipients", "sum"),
                                     pre_spend_recipients=("pre_weekly_spend_recipients", "mean"),
                                     pre_spend_others=("pre_weekly_spend_others", "mean"),
                                     redemption_rate=("redemption_rate", "mean")).reset_index()
    by_type["selection_ratio"] = by_type.pre_spend_recipients / by_type.pre_spend_others
    return {"status": "OBSERVED, DESCRIPTIVE ONLY — recipients were selected, not randomized; differences are not campaign effects",
            "by_type": by_type.round(4).to_dict("records"), "campaigns": df.round(4).to_dict("records"),
            "reading": "If recipients already spent more BEFORE the campaign, comparing their later spend with "
                       "non-recipients would credit the campaign with pre-existing differences (selection bias)."}


def sample_size(p0: float, dq: float, alpha=0.05, power=0.80) -> int:
    """Households per arm, two-sided two-proportion z-test (normal approximation)."""
    if dq <= 0 or not 0 < p0 < 1 or p0 + dq >= 1:
        raise ValueError("need 0 < p0 < p0+dq < 1")
    z = {0.05: 1.959964, 0.10: 1.644854}[alpha]
    zb = {0.80: 0.841621, 0.90: 1.281552}[power]
    p1 = p0 + dq
    pbar = (p0 + p1) / 2
    n = (z * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2 / dq ** 2
    return int(math.ceil(n))


def simulated_outcome(n_per_arm=6000, p0=0.30, true_dq=0.05, spend=10.33, margin=0.28, face=0.90,
                      redemption=0.35, contact=0.03, opt_out=0.004, seed=7) -> dict:
    """SIMULATED pilot (synthetic numbers). Exists only to exercise the decision rule end to end."""
    rng = np.random.default_rng(seed)
    ctl = rng.random(n_per_arm) < p0
    trt_base = rng.random(n_per_arm) < p0
    trt_incr = (~trt_base) & (rng.random(n_per_arm) < true_dq / (1 - p0))
    trt = trt_base | trt_incr
    g = spend * margin
    # contribution per household: buyers contribute g; treated pay contact cost and coupon on redeemers
    ctl_val = ctl * g
    redeem = (trt_base & (rng.random(n_per_arm) < redemption)) | trt_incr
    trt_val = trt * g - contact - redeem * face
    diff = trt_val.mean() - ctl_val.mean()
    se = math.sqrt(trt_val.var(ddof=1) / n_per_arm + ctl_val.var(ddof=1) / n_per_arm)
    return {"provenance": "SIMULATED fixture (seeded synthetic data) — not a real pilot",
            "n_per_arm": n_per_arm, "purchase_rate_treatment": float(trt.mean()), "purchase_rate_control": float(ctl.mean()),
            "incremental_contribution_per_household": float(diff), "ci95": [float(diff - 1.96 * se), float(diff + 1.96 * se)],
            "guardrails": {"opt_out_rate": opt_out, "complaint_rate": 0.0005, "stockout_flag": False},
            "inputs": {"p0": p0, "true_dq": true_dq, "spend": spend, "margin": margin, "face": face,
                       "redemption": redemption, "contact": contact, "seed": seed}}


def decide(outcome: dict, cfg=None) -> dict:
    cfg = cfg or load_config()
    g = cfg["outcome_rule"]["guardrails"]
    gr = outcome["guardrails"]
    fails = [k for k, ok in {"opt_out": gr["opt_out_rate"] <= g["opt_out_rate_max"],
                             "complaints": gr["complaint_rate"] <= g["complaint_rate_max"],
                             "stockout": gr["stockout_flag"] == g["stockout_flag"]}.items() if not ok]
    lo, hi = outcome["ci95"]
    point = outcome["incremental_contribution_per_household"]
    if fails or hi < 0:
        d = "STOP"
    elif lo > 0:
        d = "EXPAND"
    elif point > 0:
        d = "CHANGE"
    else:
        d = "INCONCLUSIVE"
    nxt = {"STOP": "Stop the offer; research why (offer value, category fit) before any new test.",
           "EXPAND": "Expand to the next cohort with the same holdout design; re-check stock with operations.",
           "CHANGE": "Keep the holdout; change one lever (offer value or audience score band) and rerun.",
           "INCONCLUSIVE": "Extend the test or enlarge the sample; do not roll out."}[d]
    return {"decision": d, "guardrail_failures": fails, "rule": cfg["outcome_rule"], "next_action": nxt,
            "provenance": outcome["provenance"]}


Z975, Z80 = 1.959964, 0.841621


def contribution_sample_size(sigma: float, delta: float) -> int:
    """Households per arm so the 95% CI lower bound of the contribution difference is > 0 with 80% power,
    if the true effect is `delta` USD/household and the per-household SD is `sigma` (equal arms)."""
    if delta <= 0 or sigma <= 0:
        raise ValueError("need delta > 0 and sigma > 0")
    return int(math.ceil((Z975 + Z80) ** 2 * 2 * sigma ** 2 / delta ** 2))


def pilot_design(q0: float, g: float, face: float, contact: float, redemption: float, sigma: float,
                 assumed_dq: float, multiples=(1.5, 2.0, 3.0), arms_n=(200, 406, 866, 2000, 5000)) -> dict:
    """Deterministic design table for a learn-first holdout. Every input is labelled by the caller."""
    dq_star = (contact + q0 * redemption * face) / (g - face)
    n_proxy = sample_size(q0, round(dq_star, 4))
    contrib = {}
    for k in multiples:
        delta = (k - 1) * dq_star * (g - face)
        contrib[str(k)] = {"true_uplift": round(k * dq_star, 4), "delta_usd_per_hh": round(delta, 4),
                           "n_per_arm": contribution_sample_size(sigma, delta)}
    mde = {}
    for n in arms_n:
        d_c = (Z975 + Z80) * math.sqrt(2 * sigma ** 2 / n)
        mde[str(n)] = {"min_detectable_purchase_uplift": round((Z975 + Z80) * math.sqrt(2 * q0 * (1 - q0) / n), 4),
                       "uplift_needed_for_expand": round(dq_star + d_c / (g - face), 4)}
    return {"break_even_uplift": round(dq_star, 4), "assumed_uplift": assumed_dq,
            "n_purchase_proxy": n_proxy,
            "n_purchase_proxy_note": "detects uplift > 0 when true uplift = break-even; contribution is then 0, so it cannot support EXPAND",
            "n_contribution": contrib, "mde_by_n_per_arm": mde,
            "per_treated_household_cost": round(contact + (q0 * redemption + assumed_dq) * face, 4)}
