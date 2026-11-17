"""Visit-outcome run of the model lab, as pre-registered in data/eval/hillstrom_protocol_v5_visit.json.

Identical machinery to mi.campaign.lab (same split, candidates, selection rule, permutation test, single test confirmation);
the only change is that the 0/1 outcome column is the website visit instead of the purchase. The visit outcome is placed in
the column the machinery reads, so no model code is duplicated. Results are INTERMEDIATE-OUTCOME evidence, never buyers.

  python -m mi.campaign.lab_visit        writes reports/campaign_lab_visit/results.json
  python -m mi.campaign.lab_visit report writes reports/campaign_lab_visit/report.md
"""
from __future__ import annotations

import json
import sys
import time

from mi.campaign import lab, uplift as U
from mi.campaign.data import load_protocol, load_raw
from mi.paths import REPORTS

OUT = REPORTS / "campaign_lab_visit"


def run(n_jobs: int = 8, repeats: int = 3, n_boot_sel: int = 500, n_perm: int = 40, n_boot_test: int = 2000, write: bool = True) -> dict:
    t0 = time.time()
    proto2 = load_protocol()
    df, _ = load_raw(proto=proto2)
    df = df.copy()
    df["conversion"] = df["visit"].astype(df["conversion"].dtype)       # machinery reads 'conversion'; here it holds the VISIT outcome
    lab_split = U.make_split(df, proto2)
    df_tv = df[lab_split != "test"].reset_index(drop=True)
    print(f"[visit] {len(df_tv):,} customers for selection; visit rate {df['visit'].mean():.3f}", flush=True)
    sel = lab.select(df_tv, repeats=repeats, n_boot=n_boot_sel, n_jobs=n_jobs)
    name = sel["selected"]
    real = sel["per_repeat"][0][name]["mean"]
    pn = lab.permutation_null(df_tv, name, real, n_perm=n_perm, n_jobs=n_jobs)
    cf = lab.confirm(df, lab_split, name, n_boot=n_boot_test)
    R = {"protocol": "hillstrom_protocol_v5_visit.json", "outcome": "visit (intermediate outcome, not purchase)", "visit_rate": float(df["visit"].mean()),
         "selection": {k: v for k, v in sel.items() if k != "oof_repeat0"}, "permutation": pn, "confirmation": cf, "seconds": round(time.time() - t0, 1)}
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "results.json").write_text(json.dumps(R, indent=1, default=float), encoding="utf-8")
    return R


def report(R: dict) -> str:
    sel, pn, cf = R["selection"], R["permutation"], R["confirmation"]
    cand = [k for k in sel["mean_auq"] if k not in ("RULE_RECENCY", "RULE_HISTORY", "RANDOM_ORDER")]
    rows = "\n".join(f"| {k} | {sel['mean_auq'][k]:.1f} | " + (f"{sel['paired_diff_vs_baseline_ci90'][k][0]:+.1f} to {sel['paired_diff_vs_baseline_ci90'][k][1]:+.1f}" if k in sel["paired_diff_vs_baseline_ci90"] else "baseline") + " |" for k in cand)
    c = cf["comparisons"]
    key = "MODEL_MENS_25 minus RANDOM_MENS_25"
    lo, hi = c[key]["ci95"]
    det = lo > 0
    comp = "\n".join(f"| {k} | {v['value']:+.1f} | {v['ci95'][0]:+.1f} to {v['ci95'][1]:+.1f} |" for k, v in c.items() if k.startswith("MODEL_MENS"))
    sk = sel["selected"]
    return f"""# Hillstrom targeting on the VISIT outcome (pre-registered protocol v5)

*Generated from `results.json`.* Protocol: `data/eval/hillstrom_protocol_v5_visit.json`, committed before any fitting. Same data, split, candidates and rules as the purchase lab (v3); only the outcome differs.

**This is an intermediate outcome.** A visit is not a purchase and not revenue. Numbers below are *additional visits*, never buyers or profit. About {R['visit_rate']*100:.1f}% of customers visit (about 15 times more events than purchases), so the test has more power.

## Selection on train + validation (cross-fitted Qini area, visits)

| Candidate | Mean AUQ (visits) | Paired 90% interval vs baseline |
|---|---|---|
{rows}

Selected: **{sk}** ({'a challenger was shown better than the baseline' if sel['challenger_shown_better'] else 'baseline retained'}). Note: `S_LOGIT_SPARSE` was motivated by segment effects seen in the purchase data before this protocol (disclosed in the protocol).

**Permutation test.** Selected model's out-of-fold AUQ {pn['real_auq_repeat0']:.1f} against a shuffled-label 95th percentile of {pn['null_p95']:.1f} (p = {pn['p_value']:.3f}).

## Single confirmation on the untouched test split ({cf['n_test']:,} customers; additional visits per 1,000 contacts, Mens e-mail)

| Comparison | Value | 95% interval |
|---|---|---|
{comp}

## Reading (pre-registered rule)

The pre-registered test is whether MODEL_MENS_25 minus RANDOM_MENS_25 has a 95% interval above zero: here it is {c[key]['value']:+.1f} ({lo:+.1f} to {hi:+.1f}), so targeting is **{'detectable' if det else 'NOT detectable'}** on the test split even on the more frequent outcome. {'' if det else 'There is an in-sample hint (the permutation test on the selection data and the challenger gain), but it does not hold up on the untouched test split, so it stays a hypothesis for a larger test.'} Nothing here changes the purchase conclusions.
"""


def main() -> int:
    R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    (OUT / "report.md").write_text(report(R), encoding="utf-8")
    print("wrote report.md")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        sys.exit(main())
    r = run()
    print(f"[visit] selected {r['selection']['selected']}; best challenger {r['selection']['best_challenger']} "
          f"{r['selection']['paired_diff_vs_baseline_ci90'][r['selection']['best_challenger']]}; permutation p={r['permutation']['p_value']:.3f}; "
          f"MENS25 model-random {r['confirmation']['comparisons']['MODEL_MENS_25 minus RANDOM_MENS_25']}; {r['seconds']} s")
    sys.exit(0)
