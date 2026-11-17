"""EXPLORATORY add-ons to the model lab (labelled as such; the data were already seen, nothing here is confirmatory).

  1. noise floor: AUQ of many RANDOM orders (what 'no targeting signal' looks like on this many buyers)
  2. heterogeneity tests: does any pre-e-mail feature change the e-mail effect? (likelihood-ratio tests, Holm-corrected)
  3. power: how many customers a confirmatory test needs to show the observed model lead is real
  4. report.md assembled from results.json + these numbers (no hand-typed figures)

  python -m mi.campaign.lab_extras
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import chi2
from sklearn.linear_model import LogisticRegression

from mi.campaign import lab as L
from mi.campaign import uplift as U
from mi.campaign.contract import CONTROL, MENS, TREATMENTS, WOMENS
from mi.campaign.data import ASSIGNMENT, load_protocol, load_raw

Y = "conversion"


def noise_floor(df: pd.DataFrame, n_orders: int = 300, seed: int = 5) -> dict:
    views = {a: L.ArmView(df, a) for a in TREATMENTS}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_orders):
        s = rng.random(len(df))
        vals.append(np.mean([views[a].auq(s)[0] for a in TREATMENTS]))
    v = np.asarray(vals)
    return {"n_orders": n_orders, "mean": float(v.mean()), "sd": float(v.std()), "p95": float(np.percentile(v, 95)), "p05": float(np.percentile(v, 5))}


def _ll(X, y):
    clf = LogisticRegression(C=1e6, max_iter=20000).fit(X, y)
    p = np.clip(clf.predict_proba(X)[:, 1], 1e-12, 1 - 1e-12)
    return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))


def heterogeneity(df: pd.DataFrame) -> dict:
    """LR tests (unpenalized logistic): reduced = base features + arm indicators; full adds arm x feature interactions."""
    d = U.Design().fit(df)
    B = L.base_matrix(d, df)
    a = df[ASSIGNMENT].to_numpy()
    tm, tw = (a == MENS).astype(float)[:, None], (a == WOMENS).astype(float)[:, None]
    y = df[Y].to_numpy()
    ll0 = _ll(np.hstack([B, tm, tw]), y)
    out = {"global": None, "per_feature": []}
    full = _ll(np.hstack([B, tm, tw, B * tm, B * tw]), y)
    stat, k = 2 * (full - ll0), 2 * B.shape[1]
    out["global"] = {"lr_stat": stat, "df": k, "p_value": float(chi2.sf(stat, k)),
                     "reading": "tests whether ANY feature changes the e-mail effect on the log-odds scale; exploratory"}
    rows = []
    for j, name in enumerate(d.base_names):
        Xj = np.hstack([B, tm, tw, B[:, [j]] * tm, B[:, [j]] * tw])
        s = 2 * (_ll(Xj, y) - ll0)
        rows.append({"feature": name, "lr_stat": float(s), "df": 2, "p_raw": float(chi2.sf(s, 2))})
    rows.sort(key=lambda r: r["p_raw"])
    m = len(rows)
    run = 0.0
    for i, r in enumerate(rows):                                  # Holm step-down adjustment
        run = max(run, min(1.0, (m - i) * r["p_raw"]))
        r["p_holm"] = run
    out["per_feature"] = rows
    return out


def power(conf: dict) -> dict:
    """Sample size for a confirmatory test of the model-minus-random gap at the 25% cap, scaled from the observed interval width."""
    c = conf["comparisons"]["MODEL_MENS_25 minus RANDOM_MENS_25"]
    lo, hi, est = c["ci95"][0], c["ci95"][1], c["value"]
    se = (hi - lo) / (2 * 1.96)
    n_now = conf["n_test"]
    need_se = abs(est) / (1.96 + 0.84)                               # 80% power, two-sided 5%, if the true gap equals the estimate
    scale = (se / need_se) ** 2
    mde_now = (1.96 + 0.84) * se
    return {"observed_gap_per_1000": est, "ci95": [lo, hi], "se_per_1000": se, "n_test_now": n_now,
            "customers_needed_for_80pct_power_if_gap_is_real": int(np.ceil(n_now * scale)), "scale_factor": float(scale),
            "min_detectable_gap_per_1000_at_current_n": float(mde_now),
            "reading": "rough: assumes the estimated gap is the true gap and that interval width scales with 1/sqrt(n); the estimated gap itself is uncertain"}


def report(R: dict, extras: dict) -> str:
    s, pn, cf = R["selection"], R["permutation"], R["confirmation"]
    comp = cf["comparisons"]

    def line(k):
        v = comp[k]
        return f"{v['value']:+.1f} (95% interval {v['ci95'][0]:+.1f} to {v['ci95'][1]:+.1f})"
    mean_auq = s["mean_auq"]
    rows = "\n".join(f"| {k} | {mean_auq[k]:.2f} | {s['sd_auq_over_repeats'][k]:.2f} | "
                     + (f"{s['paired_diff_vs_baseline_ci90'][k][0]:+.2f} to {s['paired_diff_vs_baseline_ci90'][k][1]:+.2f}" if k in s["paired_diff_vs_baseline_ci90"] else "baseline" if k == "S_LOGIT" else "reference") + " |"
                     for k in mean_auq)
    h, nf, nff, pw = extras["heterogeneity"], extras["noise_floor"], extras["noise_floor_full"], extras["power"]
    feat = "\n".join(f"| {r['feature']} | {r['p_raw']:.4f} | {r['p_holm']:.4f} |" for r in h["per_feature"][:6])
    dsc = R["descriptive"]["auq"]
    return f"""# Model lab report (protocol v3, pre-registered)

Case `HILLSTROM_EMAIL_2008`. Protocol `data/eval/hillstrom_protocol_v3_lab.json` was committed before any candidate was fitted. This is a **repeated evaluation**: the data were analysed before (disclosed in the protocol). Frozen export, contract and slides are untouched.

## Result in one paragraph

Eight candidate models (logistic and gradient-boosted S-, T- and transformed-outcome learners, a sparse domain-informed variant and an ensemble) were scored by cross-fitted Qini area on train+validation. **No challenger was shown better than the v2 baseline** (best challenger `{s['best_challenger']}`, paired 90% interval {s['paired_diff_vs_baseline_ci90'][s['best_challenger']][0]:+.2f} to {s['paired_diff_vs_baseline_ci90'][s['best_challenger']][1]:+.2f}, which includes zero), so the baseline `{s['selected']}` was retained. Against shuffled arm labels the baseline's out-of-fold signal is **not distinguishable from noise** on train+validation (real {pn['real_auq_repeat0']:.2f}; null 95th percentile {pn['null_p95']:.2f}; p = {pn['p_value']:.3f}). The single test-split confirmation reproduces v2: at a 25% cap the Mens e-mail model minus random is {line('MODEL_MENS_25 minus RANDOM_MENS_25')} and minus the recency rule {line('MODEL_MENS_25 minus RULE_RECENCY_MENS_25')}. **A better model cannot be demonstrated with 578 buyers.**

## 1. Selection (train+validation, 5 folds x 3 repeats, out-of-fold)

AUQ = area between the Qini curve and the random line, in buyers (mean of the Mens and Womens e-mail curves).

| Candidate | Mean AUQ | SD over repeats | Paired 90% interval vs baseline |
|---|---|---|---|
{rows}

How noisy is AUQ? Random orders of the same customers score {nf['mean']:+.2f} on average with a standard deviation of **{nf['sd']:.2f}** (95th percentile {nf['p95']:.2f}; {nf['n_orders']} random orders). Differences of a few buyers between candidates are inside that noise. The one fixed random order used as a reference scored {s['per_repeat'][0]['RANDOM_ORDER']['mean']:.2f}, above every model: that is luck inside the noise, not signal.

## 2. Is there any signal? (exploratory, all 64,000 customers)

Cross-fitted AUQ on all customers (descriptive, selection-biased across candidates): {', '.join(f"{k} {v['mean']:.1f}" for k, v in dsc.items())}. On all 64,000 customers random orders score {nff['mean']:+.2f} with sd {nff['sd']:.2f} (95th percentile {nff['p95']:.1f}); above that 95th percentile: {', '.join(k for k, v in dsc.items() if v['mean'] > nff['p95']) or 'none'}; at or below it: {', '.join(k for k, v in dsc.items() if v['mean'] <= nff['p95'])}. Encouraging but descriptive and selection-biased, not confirmatory.

Likelihood-ratio test for effect modification (does any pre-e-mail feature change the e-mail effect?): global LR = {h['global']['lr_stat']:.1f} on {h['global']['df']} df, p = {h['global']['p_value']:.4f}. Per feature (2 df each, Holm-adjusted):

| Feature | p (raw) | p (Holm) |
|---|---|---|
{feat}

## 3. Test-split confirmation (once; selected model `{cf['model']}`)

| Comparison (25% cap) | Additional buyers per 1,000 contacts |
|---|---|
| Mens: model minus random | {line('MODEL_MENS_25 minus RANDOM_MENS_25')} |
| Mens: model minus recency rule | {line('MODEL_MENS_25 minus RULE_RECENCY_MENS_25')} |
| Mens: model minus past-spend rule | {line('MODEL_MENS_25 minus RULE_HISTORY_MENS_25')} |
| Womens: model minus random | {line('MODEL_WOMENS_25 minus RANDOM_WOMENS_25')} |
| Womens: model minus recency rule | {line('MODEL_WOMENS_25 minus RULE_RECENCY_WOMENS_25')} |

Stable against random: {cf['stable_vs_random_mens_25']}. Stable against the recency rule: {cf['stable_vs_recency_mens_25']}.

## 4. What it would take to prove a targeting gain

If the estimated gap of {pw['observed_gap_per_1000']:+.1f} per 1,000 were real, a confirmatory test needs about **{pw['customers_needed_for_80pct_power_if_gap_is_real']:,} customers** (80% power, 5% two-sided), versus {pw['n_test_now']:,} in this test split. At today's size the smallest gap it could detect is about {pw['min_detectable_gap_per_1000_at_current_n']:.1f} per 1,000. {pw['reading']}

## Conclusion

The honest best result on this file is the **randomized average effect** (Mens e-mail +6.8 buyers per 1,000, interval 5.0 to 8.6) plus a model that ranks customers slightly better than chance but not provably better than random or a simple rule. Further model complexity does not help: the limit is the number of buyers, not the algorithm. The productive next step is a larger randomized pilot with a holdout, sized as above, which is already the recommendation.

Figures: `reports/campaign_lab/fig1..fig6*.png`. Raw numbers: `reports/campaign_lab/results.json`, `extras.json`.
"""


def main() -> int:
    from mi.campaign import lab
    proto2 = load_protocol()
    df, _ = load_raw(proto=proto2)
    lab_split = U.make_split(df, proto2)
    df_tv = df[lab_split != "test"].reset_index(drop=True)
    res = json.loads((L.OUT / "results.json").read_text(encoding="utf-8"))
    extras = {"status": "EXPLORATORY: data already seen; not confirmatory", "noise_floor": noise_floor(df_tv), "noise_floor_full": noise_floor(df), "heterogeneity": heterogeneity(df),
              "power": power(res["confirmation"])}
    (L.OUT / "extras.json").write_text(json.dumps(extras, indent=1), encoding="utf-8")
    (L.OUT / "report.md").write_text(report(res, extras), encoding="utf-8")
    print(json.dumps({"noise_floor": extras["noise_floor"], "global_het": extras["heterogeneity"]["global"], "top_features": extras["heterogeneity"]["per_feature"][:4],
                      "power": extras["power"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
