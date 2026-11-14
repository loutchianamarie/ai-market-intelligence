"""Hillstrom (MineThatData 2008) randomized e-mail experiment: a SEPARATE methodological learning track.

Follows data/eval/hillstrom_protocol_v1.json (pre-registered). It shows what a randomized marketing test can
identify (average effects, heterogeneity, policy value vs simple rules). It is a different retailer, period,
channel and product mix, so NOTHING here is a grocery coupon effect; results live in their own provenance
namespace (reports/experiments/hillstrom_report.json) and are never read by the grocery optimizer.

The raw CSV is kept local (data/raw/hillstrom/, gitignored): the source page states no terms of use.
Usage: python -m mi.experiments.hillstrom
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mi.paths import RAW, REPORTS, ROOT

PROTOCOL = ROOT / "data" / "eval" / "hillstrom_protocol_v1.json"
CSV = RAW / "hillstrom" / "hillstrom_2008.csv"
NUM, CAT = ["recency", "history", "mens", "womens", "newbie"], ["zip_code", "channel"]
CTRL = "No E-Mail"


class HillstromUnavailable(RuntimeError):
    pass


def load(path: Path = CSV, proto: dict | None = None) -> pd.DataFrame:
    proto = proto or json.loads(PROTOCOL.read_text())
    if not Path(path).exists():
        raise HillstromUnavailable(f"{path} not found. Download (local only) from {proto['source']['file']}")
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if sha != proto["source"]["sha256"]:
        raise HillstromUnavailable(f"checksum {sha[:16]} differs from the pre-registered {proto['source']['sha256'][:16]}")
    df = pd.read_csv(path)
    checks = {"rows_64000": len(df) == 64000, "arms": set(df.segment) == set(proto["arms"]),
              "binary_outcomes": set(df.visit.unique()) <= {0, 1} and set(df.conversion.unique()) <= {0, 1},
              "spend_nonneg": bool((df.spend >= 0).all()), "spend_implies_conversion": bool(((df.spend > 0) <= (df.conversion == 1)).all())}
    if not all(checks.values()):
        raise HillstromUnavailable(f"data checks failed: {checks}")
    return df


def diff_ci(a: np.ndarray, b: np.ndarray) -> dict:
    d = float(a.mean() - b.mean())
    se = float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
    rel = d / float(b.mean()) if b.mean() else None
    return {"diff": d, "ci95": [d - 1.96 * se, d + 1.96 * se], "n_a": int(len(a)), "n_b": int(len(b)),
            "mean_a": float(a.mean()), "mean_b": float(b.mean()),
            "absolute_effect": d, "relative_effect": rel,
            "label": "absolute = difference in means per customer emailed; relative = absolute / control mean"}


def balance(df: pd.DataFrame) -> list[dict]:
    """Standardised mean differences of pre-treatment features vs control (|SMD| < 0.1 is the usual balance bar)."""
    X = pd.get_dummies(df[NUM + CAT], columns=CAT, dtype=float)
    c = X[df.segment == CTRL]
    out = []
    for arm in [a for a in df.segment.unique() if a != CTRL]:
        t = X[df.segment == arm]
        smd = ((t.mean() - c.mean()) / np.sqrt((t.var() + c.var()) / 2)).abs()
        out.append({"arm": arm, "max_abs_smd": round(float(smd.max()), 4), "feature_at_max": str(smd.idxmax())})
    return out


def _model():
    pre = ColumnTransformer([("num", StandardScaler(), NUM), ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])
    return make_pipeline(pre, LogisticRegression(C=1.0, max_iter=2000))


def policy_eval(ho: pd.DataFrame, score: np.ndarray, treat: str, shares, n_boot=500, seed=0) -> list[dict]:
    """Incremental visits per 1,000 targeted when targeting the top share by `score` (held-out, randomized arms)."""
    rng = np.random.default_rng(seed)
    order = np.argsort(-score, kind="stable")
    rows = []
    for s in shares:
        k = int(round(len(ho) * s))
        sel = ho.iloc[order[:k]]
        est = lambda d: d[d.segment == treat].visit.mean() - d[d.segment == CTRL].visit.mean()  # noqa: E731
        point = est(sel)
        boots = [est(sel.iloc[rng.integers(0, len(sel), len(sel))]) for _ in range(n_boot)]
        rows.append({"target_share": s, "n_targeted": k, "incremental_visits_per_1000": round(1000 * point, 1),
                     "ci95_per_1000": [round(1000 * float(np.percentile(boots, 2.5)), 1), round(1000 * float(np.percentile(boots, 97.5)), 1)]})
    return rows


def uplift_by_decile(ho: pd.DataFrame, score: np.ndarray, treat: str) -> list[dict]:
    d = ho.assign(_s=score, _dec=pd.qcut(pd.Series(score).rank(method="first"), 10, labels=False).to_numpy())
    rows = []
    for k, g in d.groupby("_dec"):
        t, c = g[g.segment == treat].visit, g[g.segment == CTRL].visit
        rows.append({"decile_from_low": int(k), "n": int(len(g)), "observed_uplift_visit": round(float(t.mean() - c.mean()), 4),
                     "mean_predicted_uplift": round(float(g._s.mean()), 4)})
    return rows


def run(path: Path = CSV, write=True) -> dict:
    t0 = time.time()
    proto = json.loads(PROTOCOL.read_text())
    df = load(path, proto)
    arms = {a: df[df.segment == a] for a in proto["arms"]}
    ate = {}
    for comp in proto["comparisons"]:
        a, b = comp.split(" vs ")
        ate[comp] = {o: diff_ci(arms[a][o].to_numpy(float), arms[b][o].to_numpy(float)) for o in ["visit", "conversion", "spend"]}
    conv_ctrl = float(arms[CTRL].conversion.mean())
    # frozen split (pre-registered seed), stratified by arm
    rng = np.random.default_rng(proto["split"]["seed"])
    is_train = np.zeros(len(df), bool)
    for a in proto["arms"]:
        idx = np.flatnonzero((df.segment == a).to_numpy())
        rng.shuffle(idx)
        is_train[idx[: len(idx) // 2]] = True
    tr, ho = df[is_train], df[~is_train].reset_index(drop=True)
    models = {}
    for treat in ["Womens E-Mail", "Mens E-Mail"]:
        mt = _model().fit(tr[tr.segment == treat][NUM + CAT], tr[tr.segment == treat].visit)
        mc = _model().fit(tr[tr.segment == CTRL][NUM + CAT], tr[tr.segment == CTRL].visit)
        pair = ho[ho.segment.isin([treat, CTRL])].reset_index(drop=True)
        upl = mt.predict_proba(pair[NUM + CAT])[:, 1] - mc.predict_proba(pair[NUM + CAT])[:, 1]
        rec = -pair.recency.to_numpy(float)                      # recency rule: most recent buyers first
        rand = np.random.default_rng(1).random(len(pair))        # random targeting
        models[treat] = {
            "heldout_pair_n": int(len(pair)),
            "policy_value": {"uplift_model": policy_eval(pair, upl, treat, proto["policy_evaluation"]["target_shares"]),
                             "recency_rule": policy_eval(pair, rec, treat, proto["policy_evaluation"]["target_shares"]),
                             "random": policy_eval(pair, rand, treat, proto["policy_evaluation"]["target_shares"])},
            "uplift_by_decile": uplift_by_decile(pair, upl, treat)}
    # ---- EXPLORATORY additions (not in protocol v1; added in a later pass and labelled as such) ----
    explore = {"label": "EXPLORATORY: added after protocol v1; treat as hypothesis-generating"}
    explore["break_even_email_cost"] = {
        arm: {f"margin_{m}": round(m * ate[f"{arm} vs No E-Mail"]["spend"]["diff"], 4) for m in (0.2, 0.3, 0.4, 0.5)}
        for arm in ("Mens E-Mail", "Womens E-Mail")}
    explore["break_even_note"] = ("max cost per e-mail sent that the incremental 2-week spend could cover at each ASSUMED margin; "
                                  "email cost and margin are unknown, so no profit is claimed")
    pv = {}
    for treat in ["Womens E-Mail", "Mens E-Mail"]:
        pair = ho[ho.segment.isin([treat, CTRL])].reset_index(drop=True)
        trp = tr[tr.segment.isin([treat, CTRL])]
        rows = {}
        for outcome in ("conversion", "spend"):
            mt = _model().fit(trp[trp.segment == treat][NUM + CAT], (trp[trp.segment == treat][outcome] > 0).astype(int))
            mc = _model().fit(trp[trp.segment == CTRL][NUM + CAT], (trp[trp.segment == CTRL][outcome] > 0).astype(int))
            upl = mt.predict_proba(pair[NUM + CAT])[:, 1] - mc.predict_proba(pair[NUM + CAT])[:, 1]
            p2 = pair.assign(visit=pair[outcome])        # reuse the estimator on another outcome
            rows[outcome] = {"uplift_model": policy_eval(p2, upl, treat, [0.3]), "history_rule": policy_eval(p2, pair.history.to_numpy(float), treat, [0.3]),
                             "random": policy_eval(p2, np.random.default_rng(1).random(len(pair)), treat, [0.3])}
        rows["visit_history_rule"] = policy_eval(pair, pair.history.to_numpy(float), treat, proto["policy_evaluation"]["target_shares"])
        pv[treat] = rows
    explore["policy_values_other_outcomes_and_history_rule"] = pv
    explore["note"] = "spend policy values are 'incremental dollars per 1,000 targeted' (estimator reused on spend); conversion is rare: wide CIs expected"
    res = {"provenance": {"namespace": "experiments/hillstrom (NOT grocery evidence)", **proto["source"],
                          "rows": int(len(df)), "protocol": str(PROTOCOL.relative_to(ROOT))},
           "arm_sizes": {a: int(len(v)) for a, v in arms.items()}, "balance_vs_control": balance(df),
           "average_effects": ate,
           "rare_outcome_warning": f"Control conversion is {conv_ctrl:.4f}; conversion and spend effects are imprecise at this n and "
                                   "should not drive targeting on their own; visit is the pre-registered primary outcome.",
           "uplift_models_visit": models,
           "exploratory": explore,
           "use_restriction": proto["purpose"], "seconds": round(time.time() - t0, 1)}
    if write:
        out = REPORTS / "experiments"
        out.mkdir(parents=True, exist_ok=True)
        (out / "hillstrom_report.json").write_text(json.dumps(res, indent=2))
    return res


def main(argv=None) -> int:
    try:
        r = run()
    except HillstromUnavailable as e:
        print(f"HILLSTROM TRACK SKIPPED: {e}", file=sys.stderr)
        return 3
    for comp, o in r["average_effects"].items():
        print(comp, {k: (round(v["diff"], 4), [round(x, 4) for x in v["ci95"]]) for k, v in o.items()})
    for t, m in r["uplift_models_visit"].items():
        print(t, {k: [(x["target_share"], x["incremental_visits_per_1000"], x["ci95_per_1000"]) for x in v] for k, v in m["policy_value"].items()})
    print(r["balance_vs_control"], f"{r['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
