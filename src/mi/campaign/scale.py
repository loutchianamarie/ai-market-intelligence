"""Criteo scale replication, run exactly as pre-registered in data/eval/criteo_protocol_v4_scale.json.

Question: does an uplift model beat random targeting once there is enough randomized data, and how does the
answer change with training-set size (including a Hillstrom-sized training set)?

  python -m mi.campaign.scale            full run (about 30-60 min on 16 cores), writes reports/criteo_scale/
  python -m mi.campaign.scale --smoke    tiny synthetic self-check (no download needed)

Pure functions (`gap`, `bootstrap_gaps`, `verdicts`) are unit-tested on synthetic data with a planted effect.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from mi.paths import DATA, REPORTS

SEED = 20261117
RAW = DATA / "raw" / "criteo" / "criteo-research-uplift-v2.1.csv.gz"
PROTOCOL = DATA / "eval" / "criteo_protocol_v4_scale.json"
OUT = REPORTS / "criteo_scale"
FEATS = [f"f{i}" for i in range(12)]
MODELS = ["S_LOGIT", "T_LOGIT", "S_HGB", "T_HGB"]
SIZES = [("n_64k", 64_000, 5), ("n_256k", 256_000, 3), ("n_1m", 1_000_000, 2), ("n_4m", 4_000_000, 1)]
SHARES = (0.25, 0.10)
HGB = dict(max_depth=4, learning_rate=0.1, max_iter=200, min_samples_leaf=200, l2_regularization=10.0)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


# ---------- models (fixed hyper-parameters, nothing tuned) ----------
def _s_design(sc, X, t):
    Z = sc.transform(X)
    return np.hstack([Z, t[:, None], Z * t[:, None]]).astype(np.float32)


def fit_predict(name: str, X: np.ndarray, t: np.ndarray, y: np.ndarray, Xp: np.ndarray, seed: int = SEED) -> np.ndarray:
    """Return uplift scores (P(y|treated) - P(y|control)) for rows Xp."""
    if name == "S_LOGIT":
        sc = StandardScaler().fit(X)
        m = LogisticRegression(C=1.0, max_iter=300).fit(_s_design(sc, X, t), y)
        one, zero = np.ones(len(Xp), np.float32), np.zeros(len(Xp), np.float32)
        return m.predict_proba(_s_design(sc, Xp, one))[:, 1] - m.predict_proba(_s_design(sc, Xp, zero))[:, 1]
    if name == "S_HGB":
        m = HistGradientBoostingClassifier(random_state=seed, **HGB).fit(np.hstack([X, t[:, None]]), y)
        one, zero = np.ones((len(Xp), 1), np.float32), np.zeros((len(Xp), 1), np.float32)
        return m.predict_proba(np.hstack([Xp, one]))[:, 1] - m.predict_proba(np.hstack([Xp, zero]))[:, 1]
    mk = (lambda: LogisticRegression(C=1.0, max_iter=300)) if name == "T_LOGIT" else (lambda: HistGradientBoostingClassifier(random_state=seed, **HGB))
    if name not in ("T_LOGIT", "T_HGB"):
        raise ValueError(name)
    sc = StandardScaler().fit(X) if name == "T_LOGIT" else None
    prep = (lambda A: sc.transform(A)) if sc is not None else (lambda A: A)
    a, b = t == 1, t == 0
    m1, m0 = mk().fit(prep(X[a]), y[a]), mk().fit(prep(X[b]), y[b])
    return m1.predict_proba(prep(Xp))[:, 1] - m0.predict_proba(prep(Xp))[:, 1]


# ---------- estimands ----------
def _arm_rates(y, t, w, mask):
    wt, wc = w * (mask & (t == 1)), w * (mask & (t == 0))
    return (wt * y).sum() / max(wt.sum(), 1e-12), (wc * y).sum() / max(wc.sum(), 1e-12)


def uplift_per_1000(y, t, w, mask) -> float:
    rt, rc = _arm_rates(y, t, w, mask)
    return 1000.0 * (rt - rc)


def top_mask(score: np.ndarray, share: float) -> np.ndarray:
    k = int(round(share * len(score)))
    m = np.zeros(len(score), bool)
    m[np.argsort(-score, kind="stable")[:k]] = True
    return m


def gap(y, t, score, share, w=None) -> float:
    """Selected-top-share uplift per 1,000 minus whole-sample uplift per 1,000 (random reference)."""
    w = np.ones(len(y)) if w is None else w
    return uplift_per_1000(y, t, w, top_mask(score, share)) - uplift_per_1000(y, t, w, np.ones(len(y), bool))


def bootstrap_gaps(y, t, scores: dict, shares=SHARES, n_boot: int = 100, seed: int = SEED, chunk: int = 20) -> dict:
    """Paired customer bootstrap (Poisson weights, same weights for every model). Returns per model/share the point gap,
    its percentile 95% interval, and the paired difference versus S_LOGIT."""
    rng = np.random.default_rng(seed)
    masks = {(m, s): top_mask(sc, s) for m, sc in scores.items() for s in shares}
    whole = np.ones(len(y), bool)
    pt = {k: uplift_per_1000(y, t, np.ones(len(y)), mk) - uplift_per_1000(y, t, np.ones(len(y)), whole) for k, mk in masks.items()}
    draws = {k: [] for k in masks}
    for _ in range(n_boot):
        w = rng.poisson(1.0, len(y)).astype(np.float64)
        base = uplift_per_1000(y, t, w, whole)
        for k, mk in masks.items():
            draws[k].append(uplift_per_1000(y, t, w, mk) - base)
    out = {}
    for (m, s), d in draws.items():
        d = np.asarray(d)
        row = {"gap": pt[(m, s)], "ci95": [float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))]}
        if m != "S_LOGIT" and ("S_LOGIT", s) in draws:
            dd = d - np.asarray(draws[("S_LOGIT", s)])
            row["vs_baseline"] = {"diff": pt[(m, s)] - pt[("S_LOGIT", s)], "ci95": [float(np.nanpercentile(dd, 2.5)), float(np.nanpercentile(dd, 97.5))]}
        out[f"{m}|{s}"] = row
    out["_whole_test_uplift_per_1000"] = uplift_per_1000(y, t, np.ones(len(y)), whole)
    return out


def verdicts(fits: list[dict], primary_share: float = 0.25) -> dict:
    """Apply the pre-registered majority rules per size and model. `fits` = [{'size': key, 'results': bootstrap_gaps(...)}]."""
    sizes = sorted({f["size"] for f in fits}, key=lambda s: [x[0] for x in SIZES].index(s))
    out = {}
    for sz in sizes:
        rows = [f["results"] for f in fits if f["size"] == sz]
        out[sz] = {}
        for m in MODELS:
            key = f"{m}|{primary_share}"
            beats_random = sum(1 for r in rows if r[key]["ci95"][0] > 0)
            if m == "S_LOGIT":
                beats_base = None
            else:
                beats_base = sum(1 for r in rows if r[key]["vs_baseline"]["ci95"][0] > 0)
            out[sz][m] = {"draws": len(rows), "beats_random_draws": beats_random, "beats_random": beats_random > len(rows) / 2,
                          "mean_gap": float(np.mean([r[key]["gap"] for r in rows])),
                          "beats_baseline_draws": beats_base, "beats_baseline": None if beats_base is None else beats_base > len(rows) / 2}
    return out


# ---------- data ----------
def load(path: Path = RAW) -> pd.DataFrame:
    with gzip.open(path, "rt") as f:
        df = pd.read_csv(f, usecols=FEATS + ["treatment", "conversion"], dtype={**{c: np.float32 for c in FEATS}, "treatment": np.int8, "conversion": np.int8})
    return df


def split(n: int, seed: int = SEED):
    perm = np.random.default_rng(seed).permutation(n)
    k = int(0.2 * n)
    return perm[:k], perm[k:]


def run(n_boot: int = 100, write: bool = True) -> dict:
    prot = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    got = sha256(RAW)
    if got != prot["data"]["sha256"]:
        raise SystemExit(f"data hash mismatch: {got}")
    t0 = time.time()
    df = load()
    test_i, pool_i = split(len(df))
    X, T, Y = df[FEATS].to_numpy(np.float32), df["treatment"].to_numpy(np.int8), df["conversion"].to_numpy(np.int8)
    Xte, Tte, Yte = X[test_i], T[test_i], Y[test_i]
    print(f"rows {len(df):,} test {len(test_i):,} pool {len(pool_i):,} treated share {T.mean():.3f} conv {Y.mean()*100:.3f}% ({time.time()-t0:.0f}s)", flush=True)
    fits = []
    for key, n, draws in SIZES:
        for d in range(draws):
            rng = np.random.default_rng(SEED + 1000 * n + d)
            idx = pool_i[rng.choice(len(pool_i), n, replace=False)]
            scores = {}
            for m in MODELS:
                ts = time.time()
                scores[m] = fit_predict(m, X[idx], T[idx].astype(np.float32), Y[idx], Xte, seed=SEED + d)
                print(f"  {key} draw {d} {m} fit {time.time()-ts:.0f}s", flush=True)
            res = bootstrap_gaps(Yte, Tte, scores, n_boot=n_boot, seed=SEED + d)
            fits.append({"size": key, "n_train": n, "draw": d, "train_buyers": int(Y[idx].sum()), "results": res})
            g = {m: round(res[f"{m}|0.25"]["gap"], 2) for m in MODELS}
            print(f"{key} draw {d}: gap top25 {g}", flush=True)
    R = {"protocol": PROTOCOL.name, "data_sha256": got, "rows": int(len(df)), "test_rows": int(len(test_i)), "test_conv": int(Yte.sum()),
         "overall_conv_pct": float(Y.mean() * 100), "treated_share": float(T.mean()),
         "test_overall_uplift_per_1000": fits[0]["results"]["_whole_test_uplift_per_1000"], "fits": fits, "verdicts": verdicts(fits),
         "elapsed_s": round(time.time() - t0)}
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "results.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    return R


# ---------- smoke ----------
def smoke() -> None:
    rng = np.random.default_rng(1)
    n = 60_000
    X = rng.normal(size=(n, 12)).astype(np.float32)
    t = rng.binomial(1, 0.5, n).astype(np.int8)
    p = 0.02 + 0.06 * t * (X[:, 0] > 0.5)
    y = rng.binomial(1, p).astype(np.int8)
    sc = {m: fit_predict(m, X[:40000], t[:40000].astype(np.float32), y[:40000], X[40000:]) for m in MODELS}
    r = bootstrap_gaps(y[40000:], t[40000:], sc, n_boot=30)
    print({k: round(v["gap"], 2) for k, v in r.items() if k.endswith("|0.25")})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--boot", type=int, default=100)
    a = ap.parse_args()
    smoke() if a.smoke else run(a.boot)
    sys.exit(0)
