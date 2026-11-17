"""Model lab for the Hillstrom case, following data/eval/hillstrom_protocol_v3_lab.json (pre-registered).

Eight fixed candidates are scored by cross-fitted (out-of-fold) Qini area on train+validation; a challenger replaces the
v2 baseline only if its paired-bootstrap 90% interval for the AUQ difference is above zero; the selected model is
permutation-tested against shuffled arm labels and then evaluated ONCE on the test split with the v2 policy machinery.
Nothing here writes to the frozen export. Outputs go to reports/campaign_lab/.

  python -m mi.campaign.lab            run everything (a few minutes)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import StratifiedKFold

from mi.campaign import uplift as U
from mi.campaign.contract import CONTROL, MENS, TREATMENTS, WOMENS
from mi.campaign.data import ASSIGNMENT, load_protocol, load_raw
from mi.paths import REPORTS, ROOT

PROTOCOL_V3 = ROOT / "data" / "eval" / "hillstrom_protocol_v3_lab.json"
OUT = REPORTS / "campaign_lab"
SEED = 20261117
Y = "conversion"
BASE = ["S_LOGIT", "S_LOGIT_SPARSE", "T_LOGIT", "S_HGB", "T_HGB", "TO_RIDGE", "TO_HGB"]
ALL = BASE + ["ENSEMBLE"]
ENSEMBLE_MEMBERS = ["S_LOGIT", "T_LOGIT", "S_HGB"]
HGB_C = dict(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=200, l2_regularization=10.0, random_state=SEED)
HGB_R = dict(max_depth=2, learning_rate=0.05, max_iter=100, min_samples_leaf=400, l2_regularization=10.0, random_state=SEED)


# ---------------------------------------------------------------- features
def base_matrix(d: U.Design, df: pd.DataFrame) -> np.ndarray:
    """Standardized pre-e-mail features (no treatment columns)."""
    b = d._base_frame(df)
    for c in U.BASE_NUM:
        b[c] = (b[c] - d.mean[c]) / d.std[c]
    return b[d.base_names].to_numpy()


def _onehot_arm(a: np.ndarray) -> np.ndarray:
    return np.column_stack([(a == MENS).astype(float), (a == WOMENS).astype(float)])


# ---------------------------------------------------------------- candidates: f(df_fit, df_pred) -> {arm: predicted uplift}
def _fit_s_logit(df_fit, df_pred):
    d, clf = U.fit_slearner(df_fit, 0.1)
    p = U.predict_arms(d, clf, df_pred)
    return {a: p[a] - p[CONTROL] for a in TREATMENTS}


def _sparse_design(d, df, arm):
    B = base_matrix(d, df)
    a = df[ASSIGNMENT].to_numpy() if arm is None else np.full(len(df), arm, dtype=object)
    tm, tw = (a == MENS).astype(float)[:, None], (a == WOMENS).astype(float)[:, None]
    i = [d.base_names.index("mens"), d.base_names.index("womens")]
    P = B[:, i]
    return np.hstack([B, tm, tw, P * tm, P * tw])


def _fit_s_sparse(df_fit, df_pred):
    d = U.Design().fit(df_fit)
    clf = LogisticRegression(C=0.1, max_iter=5000).fit(_sparse_design(d, df_fit, None), df_fit[Y].to_numpy())
    p = {a: clf.predict_proba(_sparse_design(d, df_pred, a))[:, 1] for a in (CONTROL, MENS, WOMENS)}
    return {a: p[a] - p[CONTROL] for a in TREATMENTS}


def _fit_t_logit(df_fit, df_pred):
    d = U.Design().fit(df_fit)
    B, Bp, arm = base_matrix(d, df_fit), base_matrix(d, df_pred), df_fit[ASSIGNMENT].to_numpy()
    p = {a: LogisticRegression(C=0.1, max_iter=5000).fit(B[arm == a], df_fit[Y].to_numpy()[arm == a]).predict_proba(Bp)[:, 1]
         for a in (CONTROL, MENS, WOMENS)}
    return {a: p[a] - p[CONTROL] for a in TREATMENTS}


def _fit_s_hgb(df_fit, df_pred):
    d = U.Design().fit(df_fit)
    B, Bp = base_matrix(d, df_fit), base_matrix(d, df_pred)
    clf = HistGradientBoostingClassifier(**HGB_C).fit(np.hstack([B, _onehot_arm(df_fit[ASSIGNMENT].to_numpy())]), df_fit[Y].to_numpy())
    p = {a: clf.predict_proba(np.hstack([Bp, _onehot_arm(np.full(len(df_pred), a, dtype=object))]))[:, 1] for a in (CONTROL, MENS, WOMENS)}
    return {a: p[a] - p[CONTROL] for a in TREATMENTS}


def _fit_t_hgb(df_fit, df_pred):
    d = U.Design().fit(df_fit)
    B, Bp, arm = base_matrix(d, df_fit), base_matrix(d, df_pred), df_fit[ASSIGNMENT].to_numpy()
    p = {a: HistGradientBoostingClassifier(**HGB_C).fit(B[arm == a], df_fit[Y].to_numpy()[arm == a]).predict_proba(Bp)[:, 1]
         for a in (CONTROL, MENS, WOMENS)}
    return {a: p[a] - p[CONTROL] for a in TREATMENTS}


def _transformed(df_fit, arm_name):
    """Transformed outcome z with E[z|x] = uplift of `arm_name` vs control (propensity from the two groups' sizes)."""
    sub = df_fit[df_fit[ASSIGNMENT].isin([arm_name, CONTROL])]
    t = (sub[ASSIGNMENT] == arm_name).to_numpy().astype(float)
    e = t.mean()
    return sub, (sub[Y].to_numpy(float) * (t - e)) / (e * (1 - e))


def _fit_to_ridge(df_fit, df_pred):
    d = U.Design().fit(df_fit)
    Bp = base_matrix(d, df_pred)
    out = {}
    for a in TREATMENTS:
        sub, z = _transformed(df_fit, a)
        out[a] = Ridge(alpha=1000.0).fit(base_matrix(d, sub), z).predict(Bp)
    return out


def _fit_to_hgb(df_fit, df_pred):
    d = U.Design().fit(df_fit)
    Bp = base_matrix(d, df_pred)
    out = {}
    for a in TREATMENTS:
        sub, z = _transformed(df_fit, a)
        out[a] = HistGradientBoostingRegressor(**HGB_R).fit(base_matrix(d, sub), z).predict(Bp)
    return out


FIT = {"S_LOGIT": _fit_s_logit, "S_LOGIT_SPARSE": _fit_s_sparse, "T_LOGIT": _fit_t_logit, "S_HGB": _fit_s_hgb, "T_HGB": _fit_t_hgb,
       "TO_RIDGE": _fit_to_ridge, "TO_HGB": _fit_to_hgb}


def predict_named(name: str, df_fit: pd.DataFrame, df_pred: pd.DataFrame) -> dict:
    if name == "ENSEMBLE":
        m = [FIT[k](df_fit, df_pred) for k in ENSEMBLE_MEMBERS]
        return {a: np.mean([x[a] for x in m], axis=0) for a in TREATMENTS}
    return FIT[name](df_fit, df_pred)


# ---------------------------------------------------------------- Qini / AUQ (weights = bootstrap multiplicities)
def _cum(y, t, w):
    """Cumulative weighted treated/control sizes and buyers along an already-sorted axis (last axis)."""
    wt, wc = w * t, w * (1.0 - t)
    return np.cumsum(wt, -1), np.cumsum(wc, -1), np.cumsum(wt * y, -1), np.cumsum(wc * y, -1)


def qini_auq(y, t, w) -> np.ndarray:
    """Area between the Qini curve (cumulative incremental buyers) and the random line, in buyers. y, t, w sorted by score."""
    Nt, Nc, Yt, Yc = _cum(y, t, w)
    Q = np.where(Nc > 0, Yt - Yc * Nt / np.where(Nc > 0, Nc, 1.0), 0.0)
    x = np.cumsum(w, -1) / np.sum(w, -1, keepdims=True)
    return np.trapezoid(Q - x * Q[..., -1:], x, axis=-1)


def uplift_at_shares(y, t, w, shares) -> np.ndarray:
    """Incremental buyers per 1,000 contacts among the top `share` of the sorted subset (rows = resamples)."""
    Nt, Nc, Yt, Yc = _cum(y, t, w)
    idx = np.array([max(int(round(s * y.shape[-1])) - 1, 0) for s in shares])
    with np.errstate(divide="ignore", invalid="ignore"):
        return 1000.0 * (Yt[..., idx] / Nt[..., idx] - Yc[..., idx] / Nc[..., idx])


class ArmView:
    """The two-arm subset (e-mail vs control) of the customers, with fixed outcome / treatment arrays."""

    def __init__(self, df: pd.DataFrame, arm: str):
        self.arm = arm
        self.mask = df[ASSIGNMENT].isin([arm, CONTROL]).to_numpy()
        sub = df[self.mask]
        self.ids = sub.customer_id.to_numpy()
        self.y = sub[Y].to_numpy(float)
        self.t = (sub[ASSIGNMENT] == arm).to_numpy().astype(float)
        self.n = len(sub)

    def order(self, score_full: np.ndarray) -> np.ndarray:
        s = np.asarray(score_full, float)[self.mask]
        return np.lexsort((self.ids, -s))

    def auq(self, score_full, W=None) -> np.ndarray:
        o = self.order(score_full)
        w = np.ones((1, self.n)) if W is None else W
        return qini_auq(self.y[o], self.t[o], w[:, o])

    def curve(self, score_full, shares, W=None) -> np.ndarray:
        o = self.order(score_full)
        w = np.ones((1, self.n)) if W is None else W
        return uplift_at_shares(self.y[o], self.t[o], w[:, o], shares)

    def qini_points(self, score_full, n_pts=200):
        o = self.order(score_full)
        y, t = self.y[o], self.t[o]
        Nt, Nc, Yt, Yc = _cum(y, t, np.ones(self.n))
        Q = np.where(Nc > 0, Yt - Yc * Nt / np.where(Nc > 0, Nc, 1.0), 0.0)
        x = np.arange(1, self.n + 1) / self.n
        k = np.linspace(0, self.n - 1, n_pts).astype(int)
        return x[k], Q[k]


def boot_weights(n: int, b: int, rng: np.random.Generator) -> np.ndarray:
    return rng.multinomial(n, np.full(n, 1.0 / n), size=b).astype(float)


# ---------------------------------------------------------------- cross-fitting
def _task(df_fit, df_pred, names):
    try:
        from threadpoolctl import threadpool_limits
        with threadpool_limits(1):
            return {n: FIT[n](df_fit, df_pred) for n in names}
    except ImportError:
        return {n: FIT[n](df_fit, df_pred) for n in names}


def cv_oof(df: pd.DataFrame, names: list[str] | None = None, repeats: int = 1, folds: int = 5, seed: int = SEED, n_jobs: int = 8) -> list[dict]:
    """Out-of-fold predicted uplifts. Returns, per repeat, {candidate: {arm: array over df rows}} incl. ENSEMBLE if its members ran."""
    from joblib import Parallel, delayed
    names = [n for n in dict.fromkeys(names or BASE) if n != "ENSEMBLE"]
    strat = (df[ASSIGNMENT].astype(str) + df[Y].astype(str)).to_numpy()
    jobs, plan = [], []
    for r in range(repeats):
        for tr, te in StratifiedKFold(folds, shuffle=True, random_state=seed + r).split(np.zeros(len(df)), strat):
            plan.append((r, te))
            jobs.append(delayed(_task)(df.iloc[tr], df.iloc[te], names))
    res = Parallel(n_jobs=n_jobs)(jobs) if n_jobs > 1 else [j[0](*j[1], **j[2]) for j in jobs]
    out = [{n: {a: np.zeros(len(df)) for a in TREATMENTS} for n in names} for _ in range(repeats)]
    for (r, te), pred in zip(plan, res):
        for n in names:
            for a in TREATMENTS:
                out[r][n][a][te] = pred[n][a]
    for o in out:
        if all(m in o for m in ENSEMBLE_MEMBERS):
            o["ENSEMBLE"] = {a: np.mean([o[m][a] for m in ENSEMBLE_MEMBERS], axis=0) for a in TREATMENTS}
    return out


def rule_scores(df: pd.DataFrame, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    rnd = rng.random(len(df))
    return {"RULE_RECENCY": {a: -df.recency.to_numpy(float) for a in TREATMENTS},
            "RULE_HISTORY": {a: df.history.to_numpy(float) for a in TREATMENTS},
            "RANDOM_ORDER": {a: rnd for a in TREATMENTS}}


def auq_table(df: pd.DataFrame, scores: dict) -> dict:
    """{name: {'Mens E-Mail': AUQ, 'Womens E-Mail': AUQ, 'mean': ...}} on the pooled predictions."""
    views = {a: ArmView(df, a) for a in TREATMENTS}
    out = {}
    for k, s in scores.items():
        v = {a: float(views[a].auq(s[a])[0]) for a in TREATMENTS}
        out[k] = {**v, "mean": float(np.mean(list(v.values())))}
    return out


# ---------------------------------------------------------------- selection
def select(df_tv: pd.DataFrame, repeats: int = 3, n_boot: int = 500, n_jobs: int = 8, names: list[str] | None = None, seed: int = SEED) -> dict:
    t0 = time.time()
    oofs = cv_oof(df_tv, names, repeats=repeats, n_jobs=n_jobs, seed=seed)
    refs = rule_scores(df_tv, seed)
    per_repeat = [auq_table(df_tv, {**o, **refs}) for o in oofs]
    cands = [k for k in per_repeat[0] if k not in refs]
    mean_auq = {k: float(np.mean([r[k]["mean"] for r in per_repeat])) for k in per_repeat[0]}
    sd_auq = {k: float(np.std([r[k]["mean"] for r in per_repeat])) for k in per_repeat[0]}
    # paired bootstrap of AUQ(challenger) - AUQ(baseline) on repeat 0 (same resamples for every candidate and the baseline)
    rng = np.random.default_rng(seed + 1)
    views = {a: ArmView(df_tv, a) for a in TREATMENTS}
    diffs = {k: [] for k in cands if k != "S_LOGIT"}
    done = 0
    while done < n_boot:
        b = min(100, n_boot - done)
        W = {a: boot_weights(views[a].n, b, rng) for a in TREATMENTS}
        base = np.mean([views[a].auq(oofs[0]["S_LOGIT"][a], W[a]) for a in TREATMENTS], axis=0)
        for k in diffs:
            diffs[k].append(np.mean([views[a].auq(oofs[0][k][a], W[a]) for a in TREATMENTS], axis=0) - base)
        done += b
    ci90 = {k: [float(np.percentile(np.concatenate(v), 5)), float(np.percentile(np.concatenate(v), 95))] for k, v in diffs.items()}
    challengers = {k: mean_auq[k] for k in cands if k != "S_LOGIT"}
    best = max(challengers, key=challengers.get)
    replaced = ci90[best][0] > 0
    return {"mean_auq": mean_auq, "sd_auq_over_repeats": sd_auq, "per_repeat": per_repeat, "paired_diff_vs_baseline_ci90": ci90,
            "best_challenger": best, "selected": best if replaced else "S_LOGIT", "challenger_shown_better": bool(replaced),
            "rule": "challenger replaces S_LOGIT only if its paired 90% bootstrap interval for AUQ difference is above zero",
            "n_customers": int(len(df_tv)), "oof_repeat0": oofs[0], "seconds": round(time.time() - t0, 1)}


def _perm_task(df_tv, name, seed):
    rng = np.random.default_rng(seed)
    d = df_tv.copy()
    d[ASSIGNMENT] = rng.permutation(d[ASSIGNMENT].to_numpy())
    o = cv_oof(d, [m for m in (ENSEMBLE_MEMBERS if name == "ENSEMBLE" else [name])], repeats=1, n_jobs=1)[0]
    s = o[name] if name in o else o["ENSEMBLE"]
    return auq_table(d, {name: s})[name]["mean"]


def permutation_null(df_tv: pd.DataFrame, name: str, real_auq: float, n_perm: int = 40, n_jobs: int = 8, seed: int = 77) -> dict:
    from joblib import Parallel, delayed
    null = Parallel(n_jobs=n_jobs)(delayed(_perm_task)(df_tv, name, seed + i) for i in range(n_perm))
    null = np.asarray(null)
    return {"model": name, "real_auq_repeat0": real_auq, "null_mean": float(null.mean()), "null_sd": float(null.std()),
            "null_p95": float(np.percentile(null, 95)), "p_value": float((1 + (null >= real_auq).sum()) / (1 + n_perm)),
            "signal_above_null_p95": bool(real_auq > np.percentile(null, 95)), "null": [float(x) for x in null], "n_perm": n_perm}


# ---------------------------------------------------------------- confirmation on the test split (once)
def confirm(df: pd.DataFrame, lab: np.ndarray, name: str, n_boot: int = 2000, seed: int = SEED) -> dict:
    trva, te = df[lab != "test"], df[lab == "test"].reset_index(drop=True)
    res = {}
    uplifts = {n: predict_named(n, trva, te) for n in sorted({name, "S_LOGIT"})}
    # Policies are built once per model; all share the same test customers, so bootstraps are paired through the same seed.
    arms_boot = {}
    for n, up in uplifts.items():
        pol = U.build_policies(te, up)
        ev = U.Evaluator(te, pol)
        arms_boot[n] = (ev.point(), ev.bootstrap(n_boot, seed), ev, pol)
    pt0, bt0, ev0, _ = arms_boot[name]

    def d(a_model, pid_a, b_model, pid_b):
        pa, ba = arms_boot[a_model][0], arms_boot[a_model][1]
        pb, bb = arms_boot[b_model][0], arms_boot[b_model][1]
        x = 1000 * (ba[pid_a]["buyers"] - bb[pid_b]["buyers"])
        return {"value": 1000 * (pa[pid_a]["buyers"] - pb[pid_b]["buyers"]), "ci95": U.pct_ci(x)}

    rows = {}
    for pct in (25, 50):
        for fam in ("MODEL", "RANDOM", "RULE_RECENCY", "RULE_HISTORY"):
            for arm in ("MENS", "WOMENS"):
                pid = f"{fam}_{arm}_{pct}"
                p, b, ev = arms_boot[name][0], arms_boot[name][1], arms_boot[name][2]
                rows[pid] = {**ev.counts(pid), "per_1000_contacts": 1000 * p[pid]["buyers"], "ci95": U.pct_ci(1000 * b[pid]["buyers"])}
    out = {"model": name, "n_test": int(len(te)), "test_buyers": int(te[Y].sum()), "policies": rows, "comparisons": {}}
    for pct in (25, 50):
        for arm in ("MENS", "WOMENS"):
            m = f"MODEL_{arm}_{pct}"
            for other in (f"RANDOM_{arm}_{pct}", f"RULE_RECENCY_{arm}_{pct}", f"RULE_HISTORY_{arm}_{pct}"):
                out["comparisons"][f"{m} minus {other}"] = d(name, m, name, other)
            if name != "S_LOGIT":
                out["comparisons"][f"{m}: {name} minus S_LOGIT baseline"] = d(name, m, "S_LOGIT", m)
    out["baseline_S_LOGIT_per_1000_MENS_25"] = 1000 * arms_boot["S_LOGIT"][0]["MODEL_MENS_25"]["buyers"]
    out["stable_vs_random_mens_25"] = bool(out["comparisons"]["MODEL_MENS_25 minus RANDOM_MENS_25"]["ci95"][0] > 0)
    out["stable_vs_recency_mens_25"] = bool(out["comparisons"]["MODEL_MENS_25 minus RULE_RECENCY_MENS_25"]["ci95"][0] > 0)
    return out


# ---------------------------------------------------------------- full-sample cross-fitted descriptive curves
def descriptive_curves(df: pd.DataFrame, names: list[str], shares=None, n_boot: int = 200, n_jobs: int = 8, seed: int = SEED) -> dict:
    shares = list(shares or np.round(np.arange(0.05, 1.0001, 0.05), 2))
    names = list(dict.fromkeys(names))
    oof = cv_oof(df, [n for n in names if n != "ENSEMBLE"] + (ENSEMBLE_MEMBERS if "ENSEMBLE" in names else []), repeats=1, n_jobs=n_jobs, seed=seed + 50)[0]
    refs = rule_scores(df, seed)
    scores = {**{n: oof[n] for n in names if n in oof}, **refs}
    rng = np.random.default_rng(seed + 2)
    out = {"shares": shares, "curves": {}, "auq": auq_table(df, scores)}
    for a in TREATMENTS:
        v = ArmView(df, a)
        W = boot_weights(v.n, n_boot, rng)
        for k, s in scores.items():
            pt = v.curve(s[a], shares)[0]
            bs = v.curve(s[a], shares, W)
            out["curves"].setdefault(a, {})[k] = {"value": pt.tolist(), "lo": np.nanpercentile(bs, 2.5, axis=0).tolist(), "hi": np.nanpercentile(bs, 97.5, axis=0).tolist()}
    out["oof"] = oof
    return out


def decile_calibration(df: pd.DataFrame, score: dict, n_bins: int = 5) -> dict:
    """Observed uplift per 1,000 inside quantile bins of the predicted uplift (cross-fitted)."""
    res = {}
    for a in TREATMENTS:
        v = ArmView(df, a)
        s = np.asarray(score[a], float)[v.mask]
        bins = pd.qcut(pd.Series(s).rank(method="first"), n_bins, labels=False).to_numpy()
        rows = []
        for b in range(n_bins):
            m = bins == b
            t, y = v.t[m], v.y[m]
            nt, nc = t.sum(), (1 - t).sum()
            obs = 1000 * (y[t == 1].mean() - y[t == 0].mean()) if nt and nc else float("nan")
            se = 1000 * np.sqrt(y[t == 1].var() / nt + y[t == 0].var() / nc) if nt > 1 and nc > 1 else float("nan")
            rows.append({"bin": b + 1, "pred_per_1000": float(1000 * s[m].mean()), "obs_per_1000": float(obs), "se": float(se), "n": int(m.sum())})
        res[a] = rows
    return res


# ---------------------------------------------------------------- figures
def figures(R: dict, out: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=True)
    files = []
    col = {"S_LOGIT": "#222222", "S_LOGIT_SPARSE": "#2a78d6", "T_LOGIT": "#8a5a00", "S_HGB": "#1f6f43", "T_HGB": "#6b3fa0", "TO_RIDGE": "#c2185b",
           "TO_HGB": "#00838f", "ENSEMBLE": "#eb6834", "RULE_RECENCY": "#999999", "RULE_HISTORY": "#bbbb55", "RANDOM_ORDER": "#cccccc"}
    sel = R["selection"]
    # 1. Qini curves on train+validation (out-of-fold, repeat 0)
    df_tv, oof0 = R["_df_tv"], sel["oof_repeat0"]
    refs = rule_scores(df_tv)
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    for i, a in enumerate(TREATMENTS):
        v = ArmView(df_tv, a)
        for k, s in {**oof0, **refs}.items():
            x, q = v.qini_points(s[a])
            ax[i].plot(x, q, label=k, color=col.get(k), lw=2.4 if k == sel["selected"] else 1.3, ls="--" if k.startswith(("RULE", "RANDOM")) else "-")
        ax[i].plot([0, 1], [0, v.qini_points(oof0["S_LOGIT"][a])[1][-1]], color="k", lw=0.8, ls=":")
        ax[i].set_title(f"{a}: cumulative incremental buyers\n(out-of-fold, train+validation)", fontsize=10)
        ax[i].set_xlabel("share of customers contacted (ranked by score)")
        ax[i].set_ylabel("incremental buyers")
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig1_qini_curves_oof.png", dpi=130)
    plt.close(fig)
    files.append("fig1_qini_curves_oof.png")
    # 2. selection forest: mean AUQ and paired diff vs baseline
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    names = [k for k in sel["mean_auq"]]
    ax[0].barh(names, [sel["mean_auq"][k] for k in names], xerr=[sel["sd_auq_over_repeats"][k] for k in names], color=[col.get(k, "#888") for k in names])
    ax[0].set_title("Mean cross-fitted AUQ (buyers; bars = sd over 3 repeats)")
    ds = sel["paired_diff_vs_baseline_ci90"]
    for j, k in enumerate(ds):
        ax[1].plot(ds[k], [j, j], color=col.get(k), lw=3)
        ax[1].plot([np.mean(ds[k])], [j], "o", color=col.get(k))
    ax[1].axvline(0, color="k", lw=1)
    ax[1].set_yticks(range(len(ds)))
    ax[1].set_yticklabels(list(ds))
    ax[1].set_title("AUQ difference vs baseline S_LOGIT (paired 90% bootstrap)")
    fig.tight_layout()
    fig.savefig(out / "fig2_selection.png", dpi=130)
    plt.close(fig)
    files.append("fig2_selection.png")
    # 3. descriptive full-sample curves
    dc = R["descriptive"]
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    for i, a in enumerate(TREATMENTS):
        for k in dict.fromkeys(("S_LOGIT", sel["selected"], sel["best_challenger"], "ENSEMBLE", "RULE_RECENCY", "RULE_HISTORY")):
            if k in dc["curves"][a]:
                c = dc["curves"][a][k]
                ax[i].plot(dc["shares"], c["value"], label=k, color=col.get(k))
                if k in (sel["selected"], "S_LOGIT"):
                    ax[i].fill_between(dc["shares"], c["lo"], c["hi"], color=col.get(k), alpha=0.12)
        ax[i].axhline(dc["curves"][a]["RANDOM_ORDER"]["value"][-1], color="k", ls=":", lw=1, label="send to all")
        ax[i].set_title(f"{a}: uplift per 1,000 contacts by contact share\n(all 64,000 customers, cross-fitted)", fontsize=10)
        ax[i].set_xlabel("contact share")
        ax[i].set_ylabel("per 1,000 contacts")
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig3_uplift_by_cap_fullsample.png", dpi=130)
    plt.close(fig)
    files.append("fig3_uplift_by_cap_fullsample.png")
    # 4. test confirmation
    cf = R["confirmation"]
    ids = [("MODEL_MENS_25", f"{cf['model']} 25%"), ("RANDOM_MENS_25", "Random 25%"), ("RULE_RECENCY_MENS_25", "Recency rule 25%"), ("RULE_HISTORY_MENS_25", "Past-spend rule 25%"),
           ("MODEL_MENS_50", f"{cf['model']} 50%"), ("RANDOM_MENS_50", "Random 50%")]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for j, (pid, lab) in enumerate(ids):
        r = cf["policies"][pid]
        ax.plot(r["ci95"], [j, j], color="#555", lw=3)
        ax.plot([r["per_1000_contacts"]], [j], "o", color="#eb6834")
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels([l for _, l in ids])
    ax.invert_yaxis()
    ax.set_xlabel("additional buyers per 1,000 contacts (Mens e-mail, test split, 95% interval)")
    fig.tight_layout()
    fig.savefig(out / "fig4_test_confirmation.png", dpi=130)
    plt.close(fig)
    files.append("fig4_test_confirmation.png")
    # 5. permutation null
    pn = R["permutation"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(pn["null"], bins=15, color="#bbb")
    ax.axvline(pn["real_auq_repeat0"], color="#eb6834", lw=2.5, label=f"real AUQ ({pn['model']})")
    ax.axvline(pn["null_p95"], color="k", ls="--", label="null 95th percentile")
    ax.set_xlabel("mean AUQ with shuffled arm labels")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fig5_permutation_null.png", dpi=130)
    plt.close(fig)
    files.append("fig5_permutation_null.png")
    # 6. calibration of predicted uplift
    cal = R["calibration"]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    for i, a in enumerate(TREATMENTS):
        rows = cal[a]
        ax[i].errorbar([r["pred_per_1000"] for r in rows], [r["obs_per_1000"] for r in rows], yerr=[1.96 * r["se"] for r in rows], fmt="o", color="#2a78d6")
        lim = [min(r["pred_per_1000"] for r in rows) - 2, max(r["pred_per_1000"] for r in rows) + 2]
        ax[i].plot(lim, lim, "k:", lw=1)
        ax[i].set_title(f"{a}: predicted vs observed uplift by quintile\n({R['selection']['selected']}, cross-fitted)", fontsize=10)
        ax[i].set_xlabel("mean predicted uplift per 1,000")
        ax[i].set_ylabel("observed uplift per 1,000 (95%)")
    fig.tight_layout()
    fig.savefig(out / "fig6_uplift_calibration.png", dpi=130)
    plt.close(fig)
    files.append("fig6_uplift_calibration.png")
    return files


# ---------------------------------------------------------------- orchestration
def run(n_jobs: int = 8, repeats: int = 3, n_boot_sel: int = 500, n_perm: int = 40, n_boot_test: int = 2000, write: bool = True) -> dict:
    t0 = time.time()
    proto2 = load_protocol()
    df, facts = load_raw(proto=proto2)
    lab = U.make_split(df, proto2)
    df_tv = df[lab != "test"].reset_index(drop=True)
    print(f"[lab] selection on {len(df_tv):,} customers, {repeats} repeats x 5 folds, {len(ALL)} candidates", flush=True)
    sel = select(df_tv, repeats=repeats, n_boot=n_boot_sel, n_jobs=n_jobs)
    name = sel["selected"]
    print(f"[lab] mean AUQ: " + ", ".join(f"{k}={v:.2f}" for k, v in sel["mean_auq"].items()), flush=True)
    print(f"[lab] best challenger {sel['best_challenger']}; paired 90% CI {sel['paired_diff_vs_baseline_ci90'][sel['best_challenger']]}; selected {name}", flush=True)
    real = sel["per_repeat"][0][name]["mean"]
    pn = permutation_null(df_tv, name, real, n_perm=n_perm, n_jobs=n_jobs)
    print(f"[lab] permutation: real {real:.2f} vs null p95 {pn['null_p95']:.2f} (p={pn['p_value']:.3f})", flush=True)
    cf = confirm(df, lab, name, n_boot=n_boot_test)
    desc = descriptive_curves(df, ["S_LOGIT", name, sel["best_challenger"], "ENSEMBLE"], n_jobs=n_jobs)
    sel_scores = desc["oof"][name] if name in desc["oof"] else desc["oof"]["ENSEMBLE"]
    cal = decile_calibration(df, sel_scores)
    R = {"protocol": "hillstrom_protocol_v3_lab.json", "selection": sel, "permutation": pn, "confirmation": cf, "descriptive": desc, "calibration": cal,
         "_df_tv": df_tv, "seconds": round(time.time() - t0, 1)}
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        R["figures"] = figures(R, OUT)
        slim = {k: v for k, v in R.items() if not k.startswith("_")}
        slim["selection"] = {k: v for k, v in sel.items() if k != "oof_repeat0"}
        slim["descriptive"] = {k: v for k, v in desc.items() if k != "oof"}
        (OUT / "results.json").write_text(json.dumps(slim, indent=1, default=float), encoding="utf-8")
    return R


if __name__ == "__main__":
    r = run()
    print(f"[lab] done in {r['seconds']} s; figures: {r.get('figures')}")
    sys.exit(0)
