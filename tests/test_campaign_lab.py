"""Model-lab machinery on SYNTHETIC randomized data with a planted effect (never evidence about Hillstrom)."""
import numpy as np
import pandas as pd
import pytest

from mi.campaign import lab as L
from mi.campaign.contract import CONTROL, MENS, WOMENS


def synth(n=9000, seed=1, effect=True):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"customer_id": np.arange(n), "recency": rng.integers(1, 13, n).astype(float),
                       "history": np.round(rng.gamma(2.0, 120.0, n), 2), "mens": rng.integers(0, 2, n), "womens": rng.integers(0, 2, n),
                       "newbie": rng.integers(0, 2, n), "zip_code": rng.choice(["Rural", "Surburban", "Urban"], n),
                       "channel": rng.choice(["Multichannel", "Phone", "Web"], n), "segment": rng.choice([CONTROL, MENS, WOMENS], n)})
    base = 0.03 + 0.01 * (df.recency < 4)
    lm = np.where(df.recency < 4, 0.05, 0.0) if effect else 0.0            # planted: recent customers respond to the Mens e-mail
    lw = np.where(df.womens == 1, 0.04, 0.0) if effect else 0.0            # planted: Womens-merchandise buyers respond to the Womens e-mail
    p = base + np.where(df.segment == MENS, lm, 0.0) + np.where(df.segment == WOMENS, lw, 0.0)
    df["conversion"] = (rng.random(n) < p).astype(int)
    df["visit"] = rng.integers(0, 2, n)
    df["spend"] = df.conversion * 50.0
    return df


def test_qini_auq_good_order_beats_reverse_order():
    rng = np.random.default_rng(0)
    n = 4000
    group = np.arange(n) < n // 2                                        # first half responds (treated 40% vs control 10%), second half does not
    t = rng.integers(0, 2, n).astype(float)
    y = (rng.random(n) < np.where(group & (t == 1), 0.4, 0.1)).astype(float)
    good = L.qini_auq(y, t, np.ones((1, n)))[0]
    bad = L.qini_auq(y[::-1], t[::-1], np.ones((1, n)))[0]
    shuffled = L.qini_auq(*(a[np.random.default_rng(1).permutation(n)] for a in (y, t)), np.ones((1, n)))[0]
    assert good > 20 and bad < -20 and abs(shuffled) < good / 3


def test_planted_effect_is_found_and_null_is_flat():
    df = synth()
    o = L.cv_oof(df, ["S_LOGIT", "T_LOGIT"], repeats=1, n_jobs=1)[0]
    refs = L.rule_scores(df)
    tab = L.auq_table(df, {**o, **refs})
    assert tab["S_LOGIT"]["mean"] > 8 and tab["RULE_RECENCY"][MENS] > 8          # real signal: large positive area
    assert tab["RANDOM_ORDER"]["mean"] < tab["S_LOGIT"]["mean"] / 2
    flat = synth(effect=False)
    o2 = L.cv_oof(flat, ["S_LOGIT"], repeats=1, n_jobs=1)[0]
    t2 = L.auq_table(flat, {**o2})
    assert abs(t2["S_LOGIT"]["mean"]) < tab["S_LOGIT"]["mean"] / 2                # no effect planted: area collapses


def test_permutation_null_is_below_a_real_signal():
    df = synth(n=6000)
    o = L.cv_oof(df, ["S_LOGIT"], repeats=1, n_jobs=1)[0]
    real = L.auq_table(df, {"S_LOGIT": o["S_LOGIT"]})["S_LOGIT"]["mean"]
    pn = L.permutation_null(df, "S_LOGIT", real, n_perm=6, n_jobs=1)
    assert pn["signal_above_null_p95"] and abs(pn["null_mean"]) < real


def test_candidates_never_read_post_treatment_columns():
    df = synth(n=3000)
    a = L.FIT["T_LOGIT"](df.iloc[:2000], df.iloc[2000:])
    d2 = df.copy()
    d2["visit"], d2["spend"] = 99, 12345.0                                       # garbage in the forbidden columns
    b = L.FIT["T_LOGIT"](d2.iloc[:2000], d2.iloc[2000:])
    assert all(np.allclose(a[k], b[k]) for k in a)
    for name in ("S_LOGIT_SPARSE", "TO_RIDGE"):
        x, y = L.FIT[name](df.iloc[:2000], df.iloc[2000:]), L.FIT[name](d2.iloc[:2000], d2.iloc[2000:])
        assert all(np.allclose(x[k], y[k]) for k in x)


def test_every_candidate_runs_and_returns_both_arms():
    df = synth(n=2500)
    for name in L.ALL:
        out = L.predict_named(name, df.iloc[:1800], df.iloc[1800:])
        assert set(out) == {MENS, WOMENS} and all(len(v) == 700 and np.isfinite(v).all() for v in out.values()), name


def test_selection_rule_keeps_baseline_unless_challenger_is_clearly_better():
    df = synth(n=7000, effect=False)                                             # no signal: nobody should be shown better
    s = L.select(df, repeats=1, n_boot=100, n_jobs=1, names=["S_LOGIT", "T_LOGIT", "TO_RIDGE"])
    assert s["selected"] == "S_LOGIT" and not s["challenger_shown_better"]
    assert set(s["paired_diff_vs_baseline_ci90"]) == {"T_LOGIT", "TO_RIDGE", "ENSEMBLE"} or "T_LOGIT" in s["paired_diff_vs_baseline_ci90"]


def test_protocol_v3_declares_the_same_candidates_as_the_code():
    import json
    proto = json.loads(L.PROTOCOL_V3.read_text(encoding="utf-8"))
    assert [c["id"] for c in proto["candidates"]] == L.ALL
    assert proto["selection"]["scheme"].startswith("repeated stratified K-fold: 5 folds x 3 repeats")


def test_scale_gap_recovers_planted_effect_and_rules():
    import numpy as np
    from mi.campaign import scale as S
    rng = np.random.default_rng(3)
    n = 40_000
    X = rng.normal(size=(n, 12)).astype(np.float32)
    t = rng.binomial(1, 0.5, n).astype(np.int8)
    y = rng.binomial(1, 0.02 + 0.08 * t * (X[:, 0] > 0.3)).astype(np.int8)
    sc = {m: S.fit_predict(m, X[:25000], t[:25000].astype(np.float32), y[:25000], X[25000:]) for m in ("S_LOGIT", "T_HGB")}
    r = S.bootstrap_gaps(y[25000:], t[25000:], sc, n_boot=20)
    assert r["T_HGB|0.25"]["gap"] > 10 and r["T_HGB|0.25"]["ci95"][0] > 0
    assert "vs_baseline" in r["T_HGB|0.25"]
    # random scores carry no information: gap is far below the planted-effect gap
    rs = {"S_LOGIT": rng.normal(size=15000), "T_HGB": rng.normal(size=15000)}
    z = S.bootstrap_gaps(y[25000:], t[25000:], rs, n_boot=20)
    assert abs(z["T_HGB|0.25"]["gap"]) < 0.5 * r["T_HGB|0.25"]["gap"]
    # majority rule: 2 of 3 draws with lower bound > 0 -> beats random
    def fake(lo):
        return {f"{m}|0.25": {"gap": 5.0, "ci95": [lo, 9.0], "vs_baseline": {"diff": 1.0, "ci95": [-1.0, 3.0]}} for m in S.MODELS}
    v = S.verdicts([{"size": "n_64k", "results": fake(1.0)}, {"size": "n_64k", "results": fake(1.0)}, {"size": "n_64k", "results": fake(-1.0)}])
    assert v["n_64k"]["T_HGB"]["beats_random"] is True and v["n_64k"]["T_HGB"]["beats_baseline"] is False
