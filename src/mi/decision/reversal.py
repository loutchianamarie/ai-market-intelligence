"""Decision inputs (machine-readable, measured vs assumed) and a one-at-a-time decision-reversal view.

For each assumed input, holding all others at base, find the value at which the optimizer's recommendation
stops being NONE (bisection over the full constrained optimizer, not a shortcut formula). "No flip" within the
searched range is a result too. This is a SCENARIO analysis, not a forecast; the purchase model does not identify
persuadable buyers.

Usage: python -m mi.decision.reversal -> reports/decision_inputs.json, reports/decision_reversal.json
"""
from __future__ import annotations

import json
import sys
import time

from mi.config import load_config
from mi.decision.optimizer import load_inputs, optimise
from mi.paths import REPORTS

NONE_ID = "NONE: research / measure first"

# param -> (override builder, base value, search end value, unit, plain-language name)
SEARCH = {
    "uplift_multiplier": (lambda v: {"uplift_multiplier": v}, 1.0, 10.0, "x assumed uplift", "true response to the coupon"),
    "margin_rate": (lambda v: {"margin_rate": v}, 0.28, 0.80, "share of sales", "contribution margin"),
    "scale": (lambda v: {"scale": v}, 40.0, 1000.0, "x panel", "company size (reachable households)"),
    "reach_share_digital": (lambda v: {"reach_share": {"digital_coupon": v}}, 0.45, 1.0, "share", "consented digital reach"),
    "fixed_setup": (lambda v: {"fixed_setup": v}, 1500.0, 0.0, "USD per plan", "setup cost"),
    "contact_cost_digital": (lambda v: {"contact_cost": {"digital_coupon": v}}, 0.03, 0.0, "USD per contact", "digital contact cost"),
    "redemption_share": (lambda v: {"redemption_share": v}, 0.35, 0.0, "share of baseline buyers", "coupons used by people who buy anyway"),
    "coupon_retailer_share": (lambda v: {"coupon_retailer_share": v}, 1.0, 0.0, "share of coupon face paid by retailer", "who funds the coupon"),
}
# combination grid: plausible joint changes (each level is a value a manager could plausibly confirm or negotiate)
GRID = {"uplift_multiplier": [1.0, 1.5, 2.0, 3.0], "funding": ["retailer", "manufacturer+observed match"],
        "scale": [40.0, 100.0, 250.0], "fixed_setup": [1500.0, 750.0], "margin_rate": [0.28, 0.35]}


def decision_inputs(cfg=None) -> dict:
    cfg = cfg or load_config()
    s = cfg["scenario"]
    rep = json.loads((REPORTS / "model_report.json").read_text())
    turn = REPORTS / "cohort_turnover.json"
    rows = [
        {"input": "contribution_margin_rate", "value": s["contribution_margin_rate"]["value"], "range": s["contribution_margin_rate"].get("range"), "status": "ASSUMED", "source": "configs/policy.json (finance to confirm)"},
        {"input": "redemption_share_of_buyers", "value": s["redemption_share_of_buyers"]["value"], "range": s["redemption_share_of_buyers"].get("range"), "status": "ASSUMED", "source": "configs/policy.json"},
        {"input": "incremental_purchase_rate (uplift) by segment", "value": {k: v for k, v in s["incremental_purchase_rate"].items() if isinstance(v, list)}, "status": "ASSUMED [low, base, high]", "source": "configs/policy.json; no randomized grocery evidence"},
        {"input": "contact_cost by channel", "value": {k: v["contact_cost"]["value"] for k, v in s["channels"].items()}, "status": "ASSUMED", "source": "configs/policy.json"},
        {"input": "reach_share (consented, reachable) by channel", "value": {k: v["reach_share"]["value"] for k, v in s["channels"].items()}, "status": "ASSUMED", "source": "configs/policy.json; real consented pool UNKNOWN"},
        {"input": "fixed_setup_per_plan", "value": s["fixed_setup_per_plan"]["value"], "range": s["fixed_setup_per_plan"].get("range"), "status": "ASSUMED", "source": "configs/policy.json"},
        {"input": "deployment_scale", "value": s["deployment_scale"]["value"], "status": "ASSUMED (COMPANY SCALE)", "source": "configs/policy.json; the panel is not contactable"},
        {"input": "budget_cap", "value": s["budget_cap"]["value"], "status": "ASSUMED", "source": "configs/policy.json"},
        {"input": "stock_capacity", "value": None, "status": "UNKNOWN", "source": "no inventory data"},
        {"input": "mean 4-week category spend among buyers", "value": rep["economics_inputs_observed"]["mean_4w_category_spend_among_buyers_test"], "status": "OBSERVED (panel, weeks 50-53 2017)", "source": "reports/model_report.json"},
        {"input": "coupon face value per couponed line", "value": rep["economics_inputs_observed"]["mean_coupon_disc_per_couponed_line"], "status": "OBSERVED (panel, 2017)", "source": "reports/model_report.json"},
        {"input": "q0 (probability of buying in 4 weeks, by household x category)", "value": "data/processed/scores_latest.parquet", "status": "MODEL ESTIMATE (historical conditions; NOT a no-coupon counterfactual)", "source": rep["run_id"]},
        {"input": "lapsing-cohort turnover per 4-week cycle", "value": json.loads(turn.read_text()).get("mean_share_new") if turn.exists() else None, "status": "OBSERVED (panel, 2017)", "source": "reports/cohort_turnover.json"},
    ]
    return {"model_run_id": rep["run_id"], "inputs": rows,
            "rule": "Money outputs are SIMULATIONS whenever any ASSUMED or UNKNOWN input enters them."}


def _rec(scores, econ, cfg, ov) -> tuple[str, float]:
    r = optimise(scores, econ, cfg, ov)
    top = r["top3"][0]["base"]["net"] if r["top3"] else 0.0
    return r["recommended_base"], top


def reversal(cfg=None, iters=10) -> dict:
    cfg = cfg or load_config()
    scores, econ, rep = load_inputs()
    base_rec, base_net = _rec(scores, econ, cfg, {})
    rows = []
    for name, (build, base, end, unit, label) in SEARCH.items():
        rec_end, net_end = _rec(scores, econ, cfg, build(end))
        row = {"input": name, "meaning": label, "base": base, "searched_to": end, "unit": unit}
        if rec_end == NONE_ID:
            row.update({"flips": False, "result": f"recommendation stays NONE across {base}..{end} (others at base)",
                        "best_plan_net_at_end": round(net_end, 2)})
        else:
            lo, hi = base, end                         # lo: NONE, hi: a plan
            for _ in range(iters):
                mid = (lo + hi) / 2
                if _rec(scores, econ, cfg, build(mid))[0] == NONE_ID:
                    lo = mid
                else:
                    hi = mid
            rec_hi, net_hi = _rec(scores, econ, cfg, build(hi))
            row.update({"flips": True, "flip_value": round(hi, 4), "first_plan_after_flip": rec_hi,
                        "multiple_of_base": round(hi / base, 2) if base else None,
                        "best_plan_net_at_flip": round(net_hi, 2)})
        rows.append(row)
    return {"model_run_id": rep["run_id"], "base_recommendation": base_rec, "base_best_plan_net": round(base_net, 2),
            "one_at_a_time": rows,
            "status": "SCENARIO (one input varied, others at ASSUMED base values); not a forecast"}


def combinations(cfg=None) -> dict:
    """Full factorial over GRID (others at base). A combination 'flips' if the optimizer stops recommending NONE.
    Minimal flips: no other flipping combination is at least as close to base on every dimension."""
    import itertools
    cfg = cfg or load_config()
    scores, econ, rep = load_inputs()
    acc = REPORTS / "accounting_audit.json"
    match = {c: v["retailer_match_share_of_coupon_value"] for c, v in json.loads(acc.read_text())["by_candidate_category"].items()} if acc.exists() else None
    keys = list(GRID)
    rows = []
    for combo in itertools.product(*[GRID[k] for k in keys]):
        d = dict(zip(keys, combo))
        if d["funding"] != "retailer" and match is None:
            continue
        ov = {"uplift_multiplier": d["uplift_multiplier"], "scale": d["scale"], "fixed_setup": d["fixed_setup"], "margin_rate": d["margin_rate"],
              "coupon_retailer_share": 1.0 if d["funding"] == "retailer" else match}
        rec, net = _rec(scores, econ, cfg, ov)
        rows.append({**d, "recommendation": rec, "best_plan_net": round(net, 2), "flips": rec != NONE_ID})
    level = {k: {v: i for i, v in enumerate(GRID[k])} for k in keys}
    flips = [r for r in rows if r["flips"]]
    def dominated(a, b):  # b at least as close to base everywhere and strictly closer somewhere
        return all(level[k][b[k]] <= level[k][a[k]] for k in keys) and any(level[k][b[k]] < level[k][a[k]] for k in keys)
    minimal = [r for r in flips if not any(dominated(r, o) for o in flips if o is not r)]
    return {"model_run_id": rep["run_id"], "grid": GRID, "n_combinations": len(rows), "n_flip": len(flips),
            "minimal_flipping_combinations": minimal, "all": rows,
            "status": "SCENARIO; each grid value is an ASSUMED alternative, not an observed input",
            "reading": "A flip shows which JOINT changes would have to be confirmed before any coupon plan beats doing nothing."}


def main(argv=None) -> int:
    t = time.time()
    di = decision_inputs()
    (REPORTS / "decision_inputs.json").write_text(json.dumps(di, indent=2, default=str))
    rv = reversal()
    rv["seconds"] = round(time.time() - t, 1)
    rv["combinations"] = combinations()
    rv["seconds"] = round(time.time() - t, 1)
    (REPORTS / "decision_reversal.json").write_text(json.dumps(rv, indent=2, default=str))
    print("combinations:", rv["combinations"]["n_flip"], "of", rv["combinations"]["n_combinations"], "flip; minimal:")
    for m in rv["combinations"]["minimal_flipping_combinations"]:
        print("  ", {k: m[k] for k in GRID}, "->", m["recommendation"], m["best_plan_net"])
    print("base:", rv["base_recommendation"])
    for r in rv["one_at_a_time"]:
        print(" ", r["input"], "->", r.get("flip_value", "no flip"), r.get("first_plan_after_flip", r.get("result")))
    print(f"{rv['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
