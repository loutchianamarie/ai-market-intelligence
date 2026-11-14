"""Independent re-derivation of every headline claim from raw artifacts (not from the pipeline's own summaries).

Usage: python -m mi.claim_audit   -> reports/claim_audit.json (+ printed summary)
"""
from __future__ import annotations

import hashlib
import json
import math
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss

from mi.config import load_config
from mi.decision.scenario import face_value
from mi.ingest.load import load
from mi.paths import PROCESSED, RAW, REPORTS

Z975, Z80 = 1.959964, 0.841621


def data_checks() -> dict:
    m = json.loads((RAW / "manifest.json").read_text())
    files = {f["name"]: hashlib.sha256(open(RAW / f["name"], "rb").read()).hexdigest() == f["sha256"] for f in m["files"]}
    tx = load("transactions")
    return {"manifest_commit": m["commit"], "checksums_match": files, "transaction_lines": int(len(tx)),
            "households": int(tx.household_id.nunique()), "year": sorted(tx.transaction_timestamp.dt.year.unique().tolist())}


def model_checks(cfg) -> dict:
    p = pd.read_parquet(PROCESSED / "test_predictions.parquet")
    y = p.y.to_numpy()
    ap = {k: float(average_precision_score(y, p[c])) for k, c in [("model", "s_model"), ("rule_repeat", "s_rule"), ("popularity", "s_popularity")]}
    brier = {k: float(brier_score_loss(y, p[c])) for k, c in [("model", "p_model"), ("rule_repeat", "p_rule"), ("popularity", "p_popularity")]}
    # paired household-cluster bootstrap, fresh seed, 1000 resamples
    rng = np.random.default_rng(7)
    hh = p.household_id.to_numpy()
    uniq, inv = np.unique(hh, return_inverse=True)
    groups = pd.Series(np.arange(len(p))).groupby(inv).apply(np.array).to_list()
    sm, sr = p.s_model.to_numpy(), p.s_rule.to_numpy()
    diffs = []
    for _ in range(1000):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(uniq), len(uniq))])
        diffs.append(average_precision_score(y[idx], sm[idx]) - average_precision_score(y[idx], sr[idx]))
    rep = json.loads((REPORTS / "model_report.json").read_text())
    rows_per_hh = p.groupby("household_id").size()
    nohist = p[p.segment.isin(["LOW_ACTIVITY", "ACTIVE_NONBUYER"])]
    return {
        "test_rows": int(len(p)), "test_households": int(p.household_id.nunique()),
        "rows_per_household": sorted(rows_per_hh.unique().tolist()), "prevalence": float(y.mean()),
        "AP_recomputed": ap, "Brier_recomputed": brier,
        "AP_diff_bootstrap_1000_seed7": {"mean": float(np.mean(diffs)), "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]},
        "AP_diff_reported": rep["bootstrap_model_minus_rule_repeat"]["AP_diff_95ci"],
        "window_gaps": {k: round(v["model"] - v["rule"], 4) for k, v in rep["window_gaps_model_vs_rule"].items()},
        "interval_scope": "household sampling within ONE 4-week test window (holiday); temporal variation shown by window_gaps",
        "category_support": p.groupby("product_category").y.agg(["size", "sum"]).rename(columns={"size": "rows", "sum": "positives"}).astype(int).to_dict("index"),
        "no_recent_history_rows": {"rows": int(len(nohist)), "positives": int(nohist.y.sum()),
                                   "AP_model": float(average_precision_score(nohist.y, nohist.s_model)),
                                   "AP_rule": float(average_precision_score(nohist.y, nohist.s_rule)),
                                   "prevalence": float(nohist.y.mean())},
        "test_window_never_used_for_selection_or_calibration": "selection used cutoff 41, calibration cutoff 45; cutoff 49 used only for reporting (ablation numbers on test are reported, never used to choose)",
    }


def campaign_checks() -> dict:
    from mi.outcome.learning import campaign_history
    h = campaign_history()
    df = pd.DataFrame(h["campaigns"])
    # alternative 1: pooled (recipient-weighted) ratio by type
    df["rec_total"] = df.pre_weekly_spend_recipients * df.recipients_active_pre
    pooled = df.groupby("type").apply(lambda g: (g.rec_total.sum() / g.recipients_active_pre.sum()) / g.pre_weekly_spend_others.mean()).round(3).to_dict()
    # alternative 2: ever- vs never-recipient households, weeks 2-9 (before most campaigns start)
    tx, camp = load("transactions"), load("campaigns")
    early = tx[(tx.week >= 2) & (tx.week <= 9)].groupby("household_id").sales_value.sum() / 8
    ever = set(camp.household_id)
    ratio_ever = float(early[early.index.isin(ever)].mean() / early[~early.index.isin(ever)].mean())
    return {"definition": "pre-period = 8 weeks before the campaign's start week; recipients = households listed for that campaign "
                          "and active in the pre-period; others = active households not listed for that campaign (may receive other campaigns); "
                          "type ratio = mean over campaigns of campaign-level mean ratios; campaigns starting before week 10 excluded",
            "campaigns_included": int(len(df)), "campaigns_total": 27,
            "reported_selection_ratio_by_type": {r["type"]: round(r["selection_ratio"], 3) for r in h["by_type"]},
            "pooled_recipient_weighted_ratio_by_type": pooled,
            "ever_vs_never_recipient_weekly_spend_weeks_2_9": round(ratio_ever, 3),
            "households_ever_recipient": len(ever)}


def economics_checks(cfg) -> dict:
    rep = json.loads((REPORTS / "model_report.json").read_text())
    e = rep["economics_inputs_observed"]
    s = cfg["scenario"]
    sc = pd.read_parquet(PROCESSED / "scores_latest.parquet")
    cat, seg = "FROZEN PIZZA", "LAPSING"
    margin, r = s["contribution_margin_rate"]["value"], s["redemption_share_of_buyers"]["value"]
    c = s["channels"]["digital_coupon"]["contact_cost"]["value"]
    w = s["channels"]["digital_coupon"]["reach_share"]["value"]
    scale, fixed = s["deployment_scale"]["value"], s["fixed_setup_per_plan"]["value"]
    dq = s["incremental_purchase_rate"][seg][1]
    share = s.get("coupon_funding", {}).get("retailer_share", {"value": 1.0})["value"]   # who pays the coupon (ASSUMED)
    g, F = e["mean_4w_category_spend_among_buyers_test"][cat] * margin, face_value(cfg, e["mean_coupon_disc_per_couponed_line"], cat) * share
    q0 = sc[(sc.product_category == cat) & (sc.segment == seg)].p_used.to_numpy()
    v = dq * (g - F) - c - q0 * r * F                                   # plain re-implementation
    net_independent = float(v.sum() * w * scale - fixed)
    from mi.decision.optimizer import Universe, load_inputs
    from mi.decision.scenario import assumptions_from_config
    scores, econ, _ = load_inputs()
    U = Universe(scores, econ, cfg, assumptions_from_config(cfg, "base"))
    j = [i for i, cc in enumerate(U.cands) if cc["candidate_id"] == f"{cat}|{seg}|digital_coupon|ALL"][0]
    net_engine = U.evaluate([j])["net"]
    dq_star = (c + q0.mean() * r * F) / (g - F)
    # sample sizes
    p0 = float(q0.mean())
    st = e["test_window_category_segment_stats"][f"{cat}|{seg}"]
    sigma = margin * st["spend_sd"]          # SD of 4-week contribution per household, observed historical window
    def n_prop(p0, d):
        p1, pb = p0 + d, p0 + d / 2
        return math.ceil((Z975 * math.sqrt(2 * pb * (1 - pb)) + Z80 * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2 / d ** 2)
    def n_contrib(delta):
        return math.ceil((Z975 + Z80) ** 2 * 2 * sigma ** 2 / delta ** 2)
    contrib = {f"true_uplift_{k}x_break_even": {"uplift": round(k * dq_star, 4), "delta_contribution_per_hh": round((k - 1) * dq_star * (g - F), 4),
                                                 "n_per_arm": n_contrib((k - 1) * dq_star * (g - F))} for k in (1.5, 2.0, 3.0)}
    mde = {}
    for n in (200, 406, 866, 2000, 5000):
        d_purchase = (Z975 + Z80) * math.sqrt(2 * p0 * (1 - p0) / n)
        d_contrib = (Z975 + Z80) * math.sqrt(2 * sigma ** 2 / n)
        mde[n] = {"min_detectable_purchase_uplift_pp": round(100 * d_purchase, 2),
                  "min_detectable_contribution_per_hh_usd": round(d_contrib, 3),
                  "implied_uplift_for_positive_contribution_pp": round(100 * (dq_star + d_contrib / (g - F)), 2)}
    per_hh_cost = c + (p0 * r + dq) * F
    reach_panel = len(q0)
    return {
        "inputs": {"g_contribution_per_incremental_buyer": round(g, 4), "coupon_face": F, "q0_mean": round(p0, 4),
                   "assumed_dq": dq, "contact_cost": c, "redemption_share": r, "reach_share": w, "scale": scale, "fixed_setup": fixed},
        "frozen_pizza_lapsing_digital_net_base": {"independent": round(net_independent, 2), "engine": round(net_engine, 2)},
        "per_1000_contacted_households_before_fixed": round(1000 * float(v.mean()), 2),
        "break_even_uplift": round(float(dq_star), 4),
        "reach_needed_to_cover_fixed_at_assumed_dq": None if v.mean() <= 0 else math.ceil(fixed / v.mean()),
        "panel_households_in_cohort": reach_panel,
        "panel_reachable_digital_at_scale_1": round(reach_panel * w, 1),
        "sample_size": {
            "reported_866_reproduced": n_prop(p0, round(float(dq_star), 4)),
            "basis_of_866": "binary 4-week purchase, p0 = model mean q0, minimum effect = break-even uplift, two-sided alpha .05, power .8, 1:1. "
                            "It detects uplift > 0 when true uplift equals break-even; at break-even contribution is ZERO, so it cannot support EXPAND.",
            "contribution_sigma_per_hh_observed": round(sigma, 4),
            "contribution_based_n_per_arm": contrib, "minimum_detectable_effects": mde},
        "pilot_cost_reproduced": {"per_household": round(per_hh_cost, 4), "n_treated": 866,
                                  "total": round(866 * per_hh_cost + fixed, 2), "currency": "USD", "status": "ASSUMED inputs (contact, redemption, fixed, dq); OBSERVED face"},
        "same_plan_test_value": _same_plan(q0, g, F, c, r, w, scale, fixed, dq, dq_star, contrib["true_uplift_2.0x_break_even"]["n_per_arm"], sigma),
    }


def _same_plan(q0, g, F, c, r, w, scale, fixed, dq, dq_star, n, sigma) -> dict:
    """Independent re-derivation of the test's worth for the SAME plan (FROZEN PIZZA / LAPSING / digital).
    v = dq*(g-F) - c - q0*r*F is INCREMENTAL contribution per contacted household vs a no-contact control."""
    from mi.outcome.learning import cohort_turnover
    turn = cohort_turnover()
    share_new = float(np.mean([x["share_new"] for x in turn["by_cutoff"] if "share_new" in x]))
    (REPORTS / "cohort_turnover.json").write_text(json.dumps({**turn, "mean_share_new": round(share_new, 3)}, indent=2))
    reach = len(q0) * w * scale
    rem = reach - n
    rows = {}
    for label, u in (("assumed_4pp", dq), ("sizing_2x_break_even", 2 * dq_star), ("3x_break_even", 3 * dq_star)):
        v = float(np.mean(u * (g - F) - c - q0 * r * F))
        test_net, cycle = fixed - n * v, reach * v - fixed
        newc, once = share_new * reach * v - fixed, rem * v - fixed
        rows[label] = {"uplift_pp": round(100 * u, 2), "value_per_contacted_hh": round(v, 4), "test_net_cost_vs_none": round(test_net, 2),
                       "holdout_forgone": round(n * max(v, 0), 2), "rollout_cycle_net_4w": round(cycle, 2),
                       "whole_cycles_to_cover_net_test_cost": math.ceil(test_net / cycle) if cycle > 0 else None,
                       "B_new_entrants_cycle_net_4w": round(newc, 2),
                       "B_whole_cycles_to_cover": math.ceil(test_net / newc) if newc > 0 else None,
                       "C_one_time_remaining_pool_net": round(once, 2), "C_covers_test": bool(once >= test_net)}
    k = float(np.mean(c + q0 * r * F))
    pp = lambda hh, extra=0.0: round(100 * ((fixed + extra) / hh + k) / (g - F), 2)  # noqa: E731
    hurdles = {"unit_break_even_pp": round(100 * k / (g - F), 2), "A_full_pool_cycle_pp": pp(reach),
               "B_new_entrants_cycle_pp": pp(share_new * reach), "C_one_time_covers_own_setup_pp": pp(rem),
               "C_one_time_covers_setup_and_test_pp": round(100 * (2 * fixed / reach + k) / (g - F), 2)}
    hz = hurdles["A_full_pool_cycle_pp"] / 100
    design = []
    for t in (0.18, 0.20, 0.22, 0.25, 0.30):
        m = math.ceil((Z975 + Z80) ** 2 * 2 * sigma ** 2 / ((t - hz) * (g - F)) ** 2)
        design.append({"true_uplift_pp": round(100 * t, 1), "multiple_of_assumed": round(t / dq, 2), "n_per_arm": m,
                       "households_needed": 2 * m, "feasible_in_assumed_pool": 2 * m <= reach})
    return {"plan": "FROZEN PIZZA|LAPSING|digital_coupon", "n_per_arm": n, "test_gross_cost_at_assumed_uplift": round(n * (c + float(np.mean(q0)) * r * F + dq * F) + fixed, 2),
            "assumed_reachable_households": round(reach), "remaining_never_offered_after_test": round(rem),
            "observed_share_new_per_cycle": round(share_new, 3), "scenarios": rows,
            "rollout_break_even_uplift_pp": hurdles["A_full_pool_cycle_pp"], "hurdles_pp": hurdles,
            "hurdle_based_design_vs_A": {"hurdle_pp": hurdles["A_full_pool_cycle_pp"], "rows": design,
                                         "status": "FUTURE option; shows contribution above the A hurdle, not merely above 0"},
            "formula": "v = dq*(g-F) - c - q0*r*F; test_net = fixed - n*v; A = R*v - fixed; B = share_new*R*v - fixed; C = (R-n)*v - fixed",
            "replaces": "overnight/first-pass check that divided the $1,927 FROZEN PIZZA test cost by COFFEE's all-favourable +$875 cycle",
            "status": "SIMULATION; COMPANY SCALE ASSUMED; A is an upper bound (same uplift on repeat offers, setup each cycle)"}


def rag_checks() -> dict:
    r = json.loads((REPORTS / "rag_eval.json").read_text())
    return {"dev_set": {"n": r["n"], "abstention_correct": round(r["abstention_decision_accuracy"] * r["n"]), "recall_at_5": r["passage_recall_at_5"]},
            "held_out_set": {"n": r["held_out"]["n"], "abstention_correct": round(r["held_out"]["abstention_decision_accuracy"] * r["held_out"]["n"])},
            "what_19_of_19_counts": "answer-vs-abstain DECISIONS on 13 development + 6 'held-out' questions (not claims, not tool calls)",
            "provenance_caveat": "the coverage threshold (0.45) was chosen after inspecting development coverage values; the 6 held-out questions were "
                                 "written by the same session after seeing v1 failures, so they are NOT a clean unseen test"}


def main(argv=None) -> int:
    cfg = load_config()
    out = {"data": data_checks(), "model": model_checks(cfg), "campaigns": campaign_checks(), "economics": economics_checks(cfg), "rag": rag_checks()}
    (REPORTS / "claim_audit.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=1, default=str)[:9000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
