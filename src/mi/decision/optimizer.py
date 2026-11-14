"""Constrained portfolio choice over (category x segment x channel x targeting) pilot plans.

Exact enumeration of all portfolios of 1..max_plans candidates among the top-K candidates (by standalone
base-case net), with the one-contact-per-household rule enforced by assigning each household to the
selected candidate where its expected value is highest. Compared against: NONE (learn first / do nothing)
and a popularity-first heuristic (broad mailed promotion of the most popular categories).

Every output number carries a status. Plan money values are CONDITIONAL SCENARIOS, never observed ROI.
Usage: python -m mi.decision.optimizer [--out reports/portfolio.json]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from dataclasses import asdict

import numpy as np
import pandas as pd

from mi.config import config_hash, load_config
from mi.decision.scenario import CASES, Assumptions, assumptions_from_config, break_even_uplift, coupon_cost, household_value
from mi.paths import PROCESSED, REPORTS

SEGMENTS = ["REGULAR", "RECENT_LIGHT", "LAPSING", "ACTIVE_NONBUYER"]
TARGETING = ["ALL", "MODEL_FILTERED"]
TOP_K = 12


def load_inputs():
    scores = pd.read_parquet(PROCESSED / "scores_latest.parquet")
    rep = json.loads((REPORTS / "model_report.json").read_text())
    econ = rep["economics_inputs_observed"]
    return scores, econ, rep


class Universe:
    """Dense household x candidate value matrices for one assumption set."""

    def __init__(self, scores: pd.DataFrame, econ: dict, cfg: dict, a: Assumptions, score_col="p_used"):
        self.cfg, self.a = cfg, a
        self.hh = np.array(sorted(scores.household_id.unique()))
        hh_index = {h: i for i, h in enumerate(self.hh)}
        spend, face = econ["mean_4w_category_spend_among_buyers_test"], econ["mean_coupon_disc_per_couponed_line"]
        cands, cols_v, cols_cost, cols_q0 = [], [], [], []
        n = len(self.hh)
        scores = scores.assign(_i=scores.household_id.map(hh_index))
        for cat in cfg["categories"]:
            g = spend[cat] * a.margin_rate
            F = face.get(cat) or cfg["scenario"]["coupon_face_value"]["fallback"]
            sc_cat = scores[scores.product_category == cat]
            groups = [(seg, sc_cat[sc_cat.segment == seg]) for seg in SEGMENTS] + [("BROAD", sc_cat)]
            for seg, sub in groups:
                dq = a.dq(seg)
                for ch in a.contact_cost:
                    if seg == "BROAD" and ch != "mail_coupon":
                        continue
                    for tg in (TARGETING if seg != "BROAD" else ["ALL"]):
                        v = household_value(sub[score_col], dq, g, F, a.contact_cost[ch], a.redemption_share)
                        keep = np.ones(len(sub), bool) if tg == "ALL" else v > 0
                        if keep.sum() == 0:
                            continue
                        colv = np.full(n, -np.inf)
                        colc = np.zeros(n)
                        colq = np.full(n, np.nan)
                        idx = sub._i.to_numpy()[keep]
                        colv[idx] = v[keep]
                        colc[idx] = a.contact_cost[ch] + coupon_cost(sub[score_col].to_numpy()[keep], dq, F, a.redemption_share)
                        colq[idx] = sub[score_col].to_numpy()[keep]
                        cands.append({"candidate_id": f"{cat}|{seg}|{ch}|{tg}", "category": cat, "segment": seg,
                                      "channel": ch, "targeting": tg, "dq": dq, "g": g, "face": F,
                                      "contact_cost": a.contact_cost[ch], "w": a.reach_share[ch]})
                        cols_v.append(colv); cols_cost.append(colc); cols_q0.append(colq)
        self.cands = cands
        self.V = np.stack(cols_v, axis=1) if cols_v else np.zeros((n, 0))
        self.C = np.stack(cols_cost, axis=1) if cols_cost else np.zeros((n, 0))
        self.Q = np.stack(cols_q0, axis=1) if cols_q0 else np.zeros((n, 0))
        self.W = np.array([c["w"] for c in cands])

    def evaluate(self, cols: list[int]) -> dict:
        """Portfolio totals with one-contact dedup (each household -> its best selected candidate)."""
        a, s = self.a, self.cfg["scenario"]
        sub = self.V[:, cols]
        best = np.argmax(sub, axis=1)
        valid = np.isfinite(sub[np.arange(len(sub)), best])
        comps, total_net, total_cost = [], 0.0, 0.0
        for k, j in enumerate(cols):
            m = valid & (best == k)
            w = self.W[j] * a.scale
            reach = float(m.sum() * w)
            net = float(self.V[m, j].sum() * w) - a.fixed_setup
            cost = float(self.C[m, j].sum() * w) + a.fixed_setup
            c = self.cands[j]
            mean_q0 = float(np.nanmean(self.Q[m, j])) if m.any() else float("nan")
            be = break_even_uplift(mean_q0, c["g"], c["face"], c["contact_cost"], a.redemption_share)
            per1000 = float(1000 * self.V[m, j].mean()) if m.any() else None   # scale-free: per 1,000 contacted, before fixed setup
            comps.append({**c, "reach": reach, "net": net, "cost": cost, "mean_q0": mean_q0,
                          "panel_households": int(m.sum()), "net_per_1000_contacted_before_fixed": per1000,
                          "reach_status": "COMPANY SCALE ASSUMED; not measured" if a.scale != 1 else "panel sample (not contactable)",
                          "break_even_dq": be if isinstance(be, float) else None,
                          "break_even_note": None if isinstance(be, float) else be.reason})
            total_net += net
            total_cost += cost
        by_cat = {}
        for c in comps:
            by_cat[c["category"]] = by_cat.get(c["category"], 0) + c["cost"]
        budget = s["budget_cap"]["value"]
        checks = {
            "within_budget": total_cost <= budget + 1e-9,
            "category_share_ok": all(v <= s["max_category_share_of_spend"]["value"] * budget + 1e-9 for v in by_cat.values()),
            "min_reach_ok": all(c["reach"] >= s["min_reach_per_plan"]["value"] for c in comps),
            "one_contact_per_household": True,
            "stock_capacity": "UNKNOWN — human capacity check required",
        }
        feasible = checks["within_budget"] and checks["category_share_ok"] and checks["min_reach_ok"]
        return {"components": comps, "net": total_net, "cost": total_cost, "checks": checks, "feasible": feasible}


def _plan_id(comps) -> str:
    return " + ".join(f"{c['category']}/{c['segment']}/{c['channel']}/{c['targeting']}" for c in comps)


def optimise(scores, econ, cfg, overrides=None, score_col="p_used") -> dict:
    s = cfg["scenario"]
    U = {case: Universe(scores, econ, cfg, assumptions_from_config(cfg, case, overrides), score_col) for case in CASES}
    base = U["base"]
    ids = [c["candidate_id"] for c in base.cands]
    standalone = [(j, base.evaluate([j])) for j in range(len(ids))]
    ranked = sorted(standalone, key=lambda t: -t[1]["net"])
    top = [j for j, _ in ranked[:TOP_K]]
    portfolios = []
    for r in range(1, s["max_plans_in_portfolio"]["value"] + 1):
        for combo in itertools.combinations(top, r):
            if len({base.cands[j]["category"] + base.cands[j]["segment"] for j in combo}) < r:
                continue  # same cohort twice (e.g. ALL and MODEL_FILTERED) is redundant
            ev = base.evaluate(list(combo))
            if not ev["feasible"]:
                continue
            out = {"plan_id": _plan_id(ev["components"]), "cols": list(combo), "base": ev}
            for case in ("low", "high"):
                Uc = U[case]
                jj = [Uc_index(Uc, ids[j]) for j in combo]
                out[case] = Uc.evaluate(jj) if None not in jj else None
            portfolios.append(out)
    portfolios.sort(key=lambda p: -p["base"]["net"])
    # popularity-first heuristic: broad mailed promotion of most popular categories until budget
    pop = scores.groupby("product_category").cat_weeks_active_12w.apply(lambda x: (x > 0).mean()).sort_values(ascending=False)
    heur_cols = []
    for cat in pop.index:
        j = Uc_index(base, f"{cat}|BROAD|mail_coupon|ALL")
        if j is None:
            continue
        trial = base.evaluate(heur_cols + [j])
        if trial["checks"]["within_budget"] and trial["checks"]["category_share_ok"]:
            heur_cols.append(j)
        if len(heur_cols) >= s["max_plans_in_portfolio"]["value"]:
            break
    heuristic = None
    if heur_cols:
        hb = base.evaluate(heur_cols)
        heuristic = {"plan_id": "HEURISTIC: " + _plan_id(hb["components"]), "base": hb,
                     "low": U["low"].evaluate([Uc_index(U["low"], ids[j]) for j in heur_cols]),
                     "high": U["high"].evaluate([Uc_index(U["high"], ids[j]) for j in heur_cols])}
    else:
        trial = base.evaluate([Uc_index(base, f"{pop.index[0]}|BROAD|mail_coupon|ALL")])
        heuristic = {"plan_id": f"HEURISTIC: {pop.index[0]}/BROAD/mail_coupon/ALL (INFEASIBLE)", "base": trial, "low": None, "high": None}
    none = {"plan_id": "NONE: research / measure first", "base": {"net": 0.0, "cost": 0.0, "feasible": True, "components": []},
            "low": {"net": 0.0}, "high": {"net": 0.0}}
    top3 = portfolios[:3]
    best_base = top3[0] if top3 and top3[0]["base"]["net"] > 0 else none
    robust_pool = [p for p in portfolios if p.get("low")] + [none]
    best_robust = max(robust_pool, key=lambda p: p["low"]["net"])
    return {"config_hash": config_hash(cfg), "n_candidates": len(ids), "n_portfolios_feasible": len(portfolios),
            "top_k_screen": [ids[j] for j in top], "top3": top3, "heuristic": heuristic, "none": none,
            "recommended_base": best_base["plan_id"], "recommended_robust": best_robust["plan_id"],
            "assumptions_base": asdict(assumptions_from_config(cfg, "base", overrides)),
            "status": "SIMULATION — conditional on ASSUMED uplift, margin, redemption, contact cost, reach and scale; q0 is a MODEL ESTIMATE"}


def Uc_index(U: Universe, cid: str):
    for j, c in enumerate(U.cands):
        if c["candidate_id"] == cid:
            return j
    return None


def reversal_scan(scores, econ, cfg, param: str, values, overrides=None) -> list[dict]:
    rows = []
    for v in values:
        o = dict(overrides or {})
        if param in ("contact_cost", "reach_share"):
            o[param] = v  # dict channel->value
        else:
            o[param] = v
        r = optimise(scores, econ, cfg, o)
        top = r["top3"][0] if r["top3"] else None
        rows.append({"param": param, "value": v, "recommended_base": r["recommended_base"],
                     "best_net_base": top["base"]["net"] if top else 0.0})
    return rows


def compact(res: dict) -> dict:
    """Strip numpy-only fields for JSON."""
    def clean(p):
        if p is None:
            return None
        q = {k: v for k, v in p.items() if k != "cols"}
        return q
    out = dict(res)
    out["top3"] = [clean(p) for p in res["top3"]]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPORTS / "portfolio.json"))
    args = ap.parse_args(argv)
    cfg = load_config()
    scores, econ, rep = load_inputs()
    res = optimise(scores, econ, cfg)
    res["model_run_id"] = rep["run_id"]
    open(args.out, "w").write(json.dumps(compact(res), indent=2, default=float))
    print("candidates", res["n_candidates"], "feasible portfolios", res["n_portfolios_feasible"])
    for p in res["top3"]:
        print(f"  base {p['base']['net']:>10.2f} low {p['low']['net']:>10.2f} high {p['high']['net']:>10.2f} cost {p['base']['cost']:>9.2f} | {p['plan_id']}")
    h = res["heuristic"]
    print(f"  heuristic base {h['base']['net']:.2f} cost {h['base']['cost']:.2f} | {h['plan_id']}")
    print("recommended (base):", res["recommended_base"])
    print("recommended (robust/low):", res["recommended_robust"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
