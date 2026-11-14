"""Ingest and analyse a FUTURE randomized pilot (treatment vs holdout) and apply the prewritten decision rule.

Input: one CSV row per ASSIGNED household (template: data/pilot/pilot_outcomes_template.csv) plus a metadata JSON
(template: data/pilot/pilot_meta_template.json). The analysis is intention-to-treat: every assigned household
stays in its arm; only exclusions flagged as pre-treatment (decided before assignment) are dropped.

  contribution_usd = category_spend_usd * margin - coupon_cost_usd - contact_cost_usd   (per household, 4 weeks)
  effect = mean(contribution | treatment) - mean(contribution | control)   (stratum-weighted if strata exist)
  EXPAND requires the 95% CI lower bound to exceed the COMMERCIAL hurdle per household
  (rollout setup / rollout households), not merely 0, and all guardrails to pass.

Refuses non-randomized data: observational campaign history (recipients spent 2.0-2.6x more before campaigns)
must never become an uplift estimate. Synthetic fixtures are labelled as such in the output.

Usage: python -m mi.outcome.pilot analyze outcomes.csv --meta meta.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from mi.outcome.learning import decide
from mi.paths import REPORTS

REQUIRED = ["household_id", "arm", "excluded_pre_treatment", "category_spend_usd", "coupon_cost_usd", "contact_cost_usd",
            "purchased", "opted_out", "complaint"]
META_REQUIRED = ["source", "randomized", "assignment_method", "margin_rate", "margin_status", "rollout_households",
                 "rollout_fixed_setup_usd", "stockout_flag", "preregistration"]


class PilotDataError(ValueError):
    pass


def _welch(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    d = float(a.mean() - b.mean())
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return d, se


def analyze(df: pd.DataFrame, meta: dict, cfg=None) -> dict:
    miss = [c for c in REQUIRED if c not in df.columns]
    miss_meta = [k for k in META_REQUIRED if k not in meta]
    if miss or miss_meta:
        raise PilotDataError(f"missing columns {miss} / metadata {miss_meta}")
    if meta["randomized"] is not True:
        raise PilotDataError("assignment is not documented as randomized: refusing to estimate uplift from observational data")
    if df.household_id.duplicated().any():
        raise PilotDataError(f"{int(df.household_id.duplicated().sum())} duplicated household rows")
    if not set(df.arm.unique()) <= {"treatment", "control"}:
        raise PilotDataError(f"unknown arms {sorted(set(df.arm.unique()) - {'treatment', 'control'})}")
    n_assigned = len(df)
    d = df[df.excluded_pre_treatment.astype(int) == 0].copy()
    if d[["category_spend_usd", "coupon_cost_usd", "contact_cost_usd"]].isna().any().any():
        raise PilotDataError("missing outcomes for assigned households: ITT needs every assigned household's outcome (impute 0 only if that is the true outcome)")
    d["contribution_usd"] = d.category_spend_usd * meta["margin_rate"] - d.coupon_cost_usd - d.contact_cost_usd
    t, c = d[d.arm == "treatment"], d[d.arm == "control"]
    if len(t) < 30 or len(c) < 30:
        raise PilotDataError("fewer than 30 households in an arm: no estimate")
    # sample-ratio mismatch (assignment check; expected split from metadata, default 50/50)
    share = meta.get("expected_treatment_share", 0.5)
    n = len(t) + len(c)
    z_srm = (len(t) - n * share) / math.sqrt(n * share * (1 - share))
    srm_p = math.erfc(abs(z_srm) / math.sqrt(2))
    # effect: stratum-weighted if strata are present, else simple Welch difference
    if "stratum" in d.columns and d.stratum.notna().all() and d.stratum.nunique() > 1:
        parts, var = [], 0.0
        for s, g in d.groupby("stratum"):
            gt, gc = g[g.arm == "treatment"].contribution_usd.to_numpy(), g[g.arm == "control"].contribution_usd.to_numpy()
            if len(gt) < 2 or len(gc) < 2:
                raise PilotDataError(f"stratum {s} lacks both arms")
            w = len(g) / len(d)
            de, se = _welch(gt, gc)
            parts.append({"stratum": str(s), "n": int(len(g)), "effect": de, "ci95": [de - 1.96 * se, de + 1.96 * se]})
            var += (w * se) ** 2
        effect = float(sum(p["n"] / len(d) * p["effect"] for p in parts))
        se_all = math.sqrt(var)
        method = "stratum-weighted difference in means (Welch SE per stratum)"
    else:
        parts = []
        effect, se_all = _welch(t.contribution_usd.to_numpy(), c.contribution_usd.to_numpy())
        method = "difference in means (Welch SE)"
    pr_d, pr_se = _welch(t.purchased.to_numpy(float), c.purchased.to_numpy(float))
    hurdle = meta["rollout_fixed_setup_usd"] / max(1.0, float(meta["rollout_households"]))
    synthetic = str(meta["source"]).upper().startswith("SYNTHETIC")
    outcome = {"provenance": ("SYNTHETIC FIXTURE: not evidence" if synthetic else f"OBSERVED randomized pilot ({meta['source']})"),
               "incremental_contribution_per_household": effect, "ci95": [effect - 1.96 * se_all, effect + 1.96 * se_all],
               "guardrails": {"opt_out_rate": float(t.opted_out.mean()), "complaint_rate": float(t.complaint.mean()),
                              "stockout_flag": bool(meta["stockout_flag"])}}
    dec = decide(outcome, cfg, hurdle_usd_per_hh=hurdle)
    return {"provenance": outcome["provenance"], "preregistration": meta["preregistration"], "method": method + "; intention-to-treat",
            "assigned": n_assigned, "analysed": int(n), "excluded_pre_treatment": int(n_assigned - n),
            "arms": {"treatment": int(len(t)), "control": int(len(c))}, "sample_ratio_mismatch_p": round(srm_p, 4),
            "srm_warning": srm_p < 0.001, "margin": {"value": meta["margin_rate"], "status": meta["margin_status"]},
            "effect_contribution_per_household": round(effect, 4), "ci95": [round(x, 4) for x in outcome["ci95"]],
            "by_stratum": parts, "purchase_rate_diff": round(pr_d, 4), "purchase_rate_diff_ci95": [round(pr_d - 1.96 * pr_se, 4), round(pr_d + 1.96 * pr_se, 4)],
            "commercial_hurdle_per_household": round(hurdle, 4), "guardrails": outcome["guardrails"],
            "decision": dec["decision"], "guardrail_failures": dec["guardrail_failures"], "next_action": dec["next_action"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["analyze"])
    ap.add_argument("csv")
    ap.add_argument("--meta", required=True)
    a = ap.parse_args(argv)
    try:
        res = analyze(pd.read_csv(a.csv), json.loads(Path(a.meta).read_text()))
    except PilotDataError as e:
        print(f"PILOT DATA REJECTED: {e}", file=sys.stderr)
        return 2
    (REPORTS / "pilot_analysis.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
