"""Buyer (conversion) uplift model and held-out policy evaluation for the campaign case.

Follows data/eval/hillstrom_protocol_v2.json (pre-registered): one L2 logistic S-learner for the three arms,
a frozen seeded customer-level split, fixed contact caps, and randomized-policy estimators on the test split.
Predicted uplift is a conditional expected difference for customers like x; it is never an observed individual effect.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from mi.campaign.contract import ARM_KEY, CONTROL, MENS, SMALL_CELL_BUYERS, TREATMENTS, WOMENS, policy_catalog
from mi.campaign.data import ASSIGNMENT, MODEL_FEATURES, POST

Y = "conversion"
BASE_NUM = ["recency", "log_history"]
BASE_BIN = ["mens", "womens", "newbie"]
CAT = {"zip_code": ["Rural", "Surburban", "Urban"], "channel": ["Multichannel", "Phone", "Web"]}     # first level = reference


# ---------------------------------------------------------------- split
def make_split(df: pd.DataFrame, proto: dict) -> np.ndarray:
    """Seeded customer-level split, stratified by arm. Returns an array of 'train' / 'validation' / 'test' per row."""
    fr, rng = proto["split"]["fractions"], np.random.default_rng(proto["split"]["seed"])
    lab = np.empty(len(df), dtype=object)
    arm = df[ASSIGNMENT].to_numpy()
    for a in proto["arms"]:                                   # fixed order from the protocol keeps the split reproducible
        idx = np.flatnonzero(arm == a)
        rng.shuffle(idx)
        n_tr, n_va = int(len(idx) * fr["train"]), int(len(idx) * fr["validation"])
        lab[idx[:n_tr]], lab[idx[n_tr:n_tr + n_va]], lab[idx[n_tr + n_va:]] = "train", "validation", "test"
    return lab


def split_hashes(df: pd.DataFrame, lab: np.ndarray) -> dict:
    """SHA-256 of the sorted customer ids in each split: lets anyone confirm they evaluate on the same customers."""
    out = {}
    for s in ("train", "validation", "test"):
        ids = np.sort(df.customer_id.to_numpy()[lab == s])
        out[s] = {"n": int(len(ids)), "sha256_of_customer_ids": hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest()}
    return out


# ---------------------------------------------------------------- design matrix and model
@dataclass
class Design:
    """Pre-e-mail features only. Scaling statistics come from the fitting rows, never from outcomes."""
    mean: dict = field(default_factory=dict)
    std: dict = field(default_factory=dict)

    @staticmethod
    def _base_frame(df: pd.DataFrame) -> pd.DataFrame:
        leaked = [c for c in MODEL_FEATURES if c in POST or c == ASSIGNMENT]
        if leaked:
            raise ValueError(f"post-treatment or assignment column used as a feature: {leaked}")
        x = df[MODEL_FEATURES]                                 # nothing outside this list can reach the model
        return pd.DataFrame({"recency": x.recency.astype(float), "log_history": np.log1p(x.history.astype(float)),
                             "mens": x.mens.astype(float), "womens": x.womens.astype(float), "newbie": x.newbie.astype(float),
                             **{f"{c}={lv}": (x[c] == lv).astype(float) for c, lvs in CAT.items() for lv in lvs[1:]}}, index=df.index)

    def fit(self, df: pd.DataFrame) -> "Design":
        b = self._base_frame(df)
        self.mean = {c: float(b[c].mean()) for c in BASE_NUM}
        self.std = {c: float(b[c].std(ddof=0)) or 1.0 for c in BASE_NUM}
        return self

    @property
    def base_names(self) -> list[str]:
        return BASE_NUM + BASE_BIN + [f"{c}={lv}" for c, lvs in CAT.items() for lv in lvs[1:]]

    @property
    def names(self) -> list[str]:
        b = self.base_names
        return b + ["T_mens", "T_womens"] + [f"T_mens x {n}" for n in b] + [f"T_womens x {n}" for n in b]

    def transform(self, df: pd.DataFrame, arm: str | np.ndarray | None = None) -> np.ndarray:
        """Design matrix for each row's own randomized arm, or for a hypothetical arm when `arm` is a name."""
        b = self._base_frame(df)
        for c in BASE_NUM:
            b[c] = (b[c] - self.mean[c]) / self.std[c]
        B = b[self.base_names].to_numpy()
        a = df[ASSIGNMENT].to_numpy() if arm is None else (np.full(len(df), arm, dtype=object) if isinstance(arm, str) else arm)
        tm, tw = (a == MENS).astype(float)[:, None], (a == WOMENS).astype(float)[:, None]
        return np.hstack([B, tm, tw, B * tm, B * tw])


def fit_slearner(df_fit: pd.DataFrame, C: float) -> tuple[Design, LogisticRegression]:
    d = Design().fit(df_fit)
    clf = LogisticRegression(C=C, max_iter=5000, solver="lbfgs").fit(d.transform(df_fit), df_fit[Y].to_numpy())
    return d, clf


def predict_arms(d: Design, clf: LogisticRegression, df: pd.DataFrame) -> dict[str, np.ndarray]:
    """p(purchase | x, arm) for the three arms, for every row regardless of the arm it was randomized to."""
    return {a: clf.predict_proba(d.transform(df, arm=a))[:, 1] for a in (CONTROL, MENS, WOMENS)}


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


# ---------------------------------------------------------------- policies (rankings from pre-e-mail information only)
def order_recency(df: pd.DataFrame) -> np.ndarray:
    """Most recent purchasers first; ties by higher past-year spend, then customer id."""
    return np.lexsort((df.customer_id.to_numpy(), -df.history.to_numpy(float), df.recency.to_numpy(float)))


def order_history(df: pd.DataFrame) -> np.ndarray:
    """Highest past-year spend first; ties by lower recency, then customer id."""
    return np.lexsort((df.customer_id.to_numpy(), df.recency.to_numpy(float), -df.history.to_numpy(float)))


def order_score(df: pd.DataFrame, score: np.ndarray) -> np.ndarray:
    """Highest score first; ties by customer id."""
    return np.lexsort((df.customer_id.to_numpy(), -np.asarray(score, float)))


def top_mask(order: np.ndarray, k: int) -> np.ndarray:
    m = np.zeros(len(order), bool)
    m[order[:k]] = True
    return m


def cap_size(n: int, share: float) -> int:
    return int(round(share * n))


@dataclass
class Policy:
    """A contact policy on the evaluation customers: who is selected and which e-mail each selected customer gets."""
    spec: dict
    selected: np.ndarray                      # bool per customer
    assigned: np.ndarray                      # arm name per customer (meaningful where selected)
    expectation_of_random: bool = False       # RANDOM: evaluated as the average effect over the whole arms


def build_policies(df: pd.DataFrame, uplift: dict[str, np.ndarray], shares=None) -> list[Policy]:
    """Every policy of the catalog for the customers in `df` (all three arms). Uses no outcome column."""
    n, P = len(df), []
    best_arm = np.where(uplift[MENS] >= uplift[WOMENS], MENS, WOMENS).astype(object)
    best_up = np.maximum(uplift[MENS], uplift[WOMENS])
    everyone = np.ones(n, bool)
    for spec in policy_catalog(*(() if shares is None else (shares,))):
        fam, arm, k = spec["policy_family"], spec["arm_assignment"], cap_size(n, spec["contact_share"])
        pid = spec["policy_id"]
        if fam == "NO_EMAIL":
            P.append(Policy(spec, np.zeros(n, bool), np.full(n, "NONE", dtype=object)))
        elif fam in ("SEND_ALL", "RANDOM"):
            P.append(Policy(spec, everyone, np.full(n, arm, dtype=object), expectation_of_random=(fam == "RANDOM")))
        elif fam == "RULE":
            order = order_recency(df) if "RECENCY" in pid else order_history(df)
            P.append(Policy(spec, top_mask(order, k), np.full(n, arm, dtype=object)))
        elif arm == "MODEL_CHOOSES_ARM":
            P.append(Policy(spec, top_mask(order_score(df, best_up), k), best_arm))
        else:
            P.append(Policy(spec, top_mask(order_score(df, uplift[arm]), k), np.full(n, arm, dtype=object)))
    return P


# ---------------------------------------------------------------- randomized-policy estimators + bootstrap
class Evaluator:
    """Evaluates policies on randomized customers. Every estimate is a ratio of weighted sums, so one matrix product
    per bootstrap chunk evaluates all policies on the same resamples (paired differences come for free)."""

    def __init__(self, df: pd.DataFrame, policies: list[Policy]):
        self.df, self.policies, self.n = df, policies, len(df)
        self.arm = df[ASSIGNMENT].to_numpy()
        self.out = {"buyers": df[Y].to_numpy(float), "spend": df["spend"].to_numpy(float)}
        self.cols: list[np.ndarray] = []
        self.plan = {}
        for p in policies:
            strata = []
            for a in TREATMENTS:
                sa = p.selected & (p.assigned == a)
                if sa.any():
                    matched = sa & (self.arm == a)
                    strata.append({"arm": a, "size": self._col(sa), "n": self._col(matched),
                                   "buyers": self._col(matched * self.out["buyers"]), "spend": self._col(matched * self.out["spend"]),
                                   "matched": matched})
            c = p.selected & (self.arm == CONTROL)
            self.plan[p.spec["policy_id"]] = {"strata": strata, "sel": self._col(p.selected), "c_mask": c, "c_n": self._col(c),
                                              "c_buyers": self._col(c * self.out["buyers"]), "c_spend": self._col(c * self.out["spend"])}
        self.V = np.column_stack(self.cols).astype(float)

    def _col(self, v: np.ndarray) -> int:
        self.cols.append(np.asarray(v, float))
        return len(self.cols) - 1

    def _value(self, M: np.ndarray, pid: str, outcome: str) -> np.ndarray:
        """Policy estimate per resample (rows of M): treated mean (stratified by assigned e-mail) minus control mean."""
        pl = self.plan[pid]
        if not pl["strata"]:
            return np.zeros(M.shape[0])
        with np.errstate(divide="ignore", invalid="ignore"):
            treated = sum((M[:, s["size"]] / M[:, pl["sel"]]) * (M[:, s[outcome]] / M[:, s["n"]]) for s in pl["strata"])
            return treated - M[:, pl["c_" + outcome]] / M[:, pl["c_n"]]

    def point(self) -> dict:
        M = self.V.sum(axis=0, keepdims=True)
        return {pid: {o: float(self._value(M, pid, o)[0]) for o in self.out} for pid in self.plan}

    def counts(self, pid: str) -> dict:
        pl, p = self.plan[pid], next(x for x in self.policies if x.spec["policy_id"] == pid)
        t = np.zeros(self.n, bool)
        for s in pl["strata"]:
            t |= s["matched"]
        y = self.out["buyers"]
        return {"eligible_n": self.n, "contacted_n": cap_size(self.n, p.spec["contact_share"]) if p.expectation_of_random else int(p.selected.sum()),
                "treated_n": int(t.sum()), "treated_buyers": int(y[t].sum()), "control_n": int(pl["c_mask"].sum()), "control_buyers": int(y[pl["c_mask"]].sum()),
                "assigned_split": {s["arm"]: int((p.selected & (p.assigned == s["arm"])).sum()) for s in pl["strata"]}}

    def bootstrap(self, n_boot: int, seed: int, chunk: int = 200) -> dict:
        """Customer-level bootstrap. Returns {policy_id: {outcome: array of n_boot estimates}} on shared resamples."""
        rng, prob = np.random.default_rng(seed), np.full(self.n, 1.0 / self.n)
        acc = {pid: {o: [] for o in self.out} for pid in self.plan}
        done = 0
        while done < n_boot:
            b = min(chunk, n_boot - done)
            M = rng.multinomial(self.n, prob, size=b).astype(float) @ self.V
            for pid in self.plan:
                for o in self.out:
                    acc[pid][o].append(self._value(M, pid, o))
            done += b
        return {pid: {o: np.concatenate(v) for o, v in d.items()} for pid, d in acc.items()}


def pct_ci(x: np.ndarray) -> list[float] | None:
    x = x[np.isfinite(x)]
    return None if len(x) == 0 else [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def wald(tn: int, tb: float, cn: int, cb: float) -> dict:
    """Difference of two proportions with an unpooled normal-approximation 95% interval."""
    pt, pc = tb / tn, cb / cn
    se = float(np.sqrt(pt * (1 - pt) / tn + pc * (1 - pc) / cn))
    return {"diff": pt - pc, "ci95": [pt - pc - 1.96 * se, pt - pc + 1.96 * se]}


def wald_means(a: np.ndarray, b: np.ndarray) -> dict:
    d = float(a.mean() - b.mean())
    se = float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
    return {"diff": d, "ci95": [d - 1.96 * se, d + 1.96 * se]}


def uplift_at_cap(df: pd.DataFrame, order: np.ndarray, arm: str, share: float) -> float:
    """Uplift at k ('overall' strategy over all arms): treated minus control purchase rate inside the top share."""
    sel = top_mask(order, cap_size(len(df), share))
    a, y = df[ASSIGNMENT].to_numpy(), df[Y].to_numpy(float)
    return float(y[sel & (a == arm)].mean() - y[sel & (a == CONTROL)].mean())


# ---------------------------------------------------------------- secondary metrics
def qini_coefficient(y: np.ndarray, treated: np.ndarray, score_order: np.ndarray, w: np.ndarray | None = None) -> float | None:
    """Qini coefficient for one e-mail versus control. `score_order` ranks the pair sample best-first.
    Q(t) = treated buyers - control buyers x treated/control among the first t customers. The coefficient is the area between
    the Qini curve and the random line, divided by the same area for the optimum curve without negative effects."""
    w = np.ones(len(y)) if w is None else w
    w, y, t = w[score_order], y[score_order], treated[score_order].astype(float)
    nt, nc = np.cumsum(w * t), np.cumsum(w * (1 - t))
    yt, yc = np.cumsum(w * t * y), np.cumsum(w * (1 - t) * y)
    q = yt - np.divide(yc * nt, nc, out=np.zeros_like(yc), where=nc > 0)
    N, q_end = float(w.sum()), float(q[-1])
    if q_end <= 0 or N <= 0:
        return None
    x = np.concatenate([[0.0], np.cumsum(w) / N])
    qq = np.concatenate([[0.0], q])
    area = float(np.sum((x[1:] - x[:-1]) * (qq[1:] + qq[:-1]) / 2)) - 0.5 * q_end
    perfect = q_end * (1 - q_end / N) / 2
    return area / perfect if perfect > 0 else None


def qini_with_ci(pair: pd.DataFrame, arm: str, order: np.ndarray, n_boot: int, seed: int) -> dict:
    y, t = pair[Y].to_numpy(float), (pair[ASSIGNMENT] == arm).to_numpy()
    rng, n = np.random.default_rng(seed), len(pair)
    boots = [qini_coefficient(y, t, order, rng.multinomial(n, np.full(n, 1.0 / n)).astype(float)) for _ in range(n_boot)]
    ok = np.array([b for b in boots if b is not None])
    return {"value": qini_coefficient(y, t, order), "ci95": pct_ci(ok) if len(ok) >= 0.9 * n_boot else None,
            "undefined_resamples": int(n_boot - len(ok))}


def quartiles(df: pd.DataFrame, pred_uplift: np.ndarray, arm: str) -> list[dict]:
    """Observed uplift by quartile of predicted uplift (Q4 = highest predicted): does the ranking hold on held-out customers?"""
    q = pd.qcut(pd.Series(pred_uplift).rank(method="first"), 4, labels=False).to_numpy()
    a, y, rows = df[ASSIGNMENT].to_numpy(), df[Y].to_numpy(float), []
    for k in range(4):
        t, c = (q == k) & (a == arm), (q == k) & (a == CONTROL)
        tn, tb, cn, cb = int(t.sum()), int(y[t].sum()), int(c.sum()), int(y[c].sum())
        w = wald(tn, tb, cn, cb)
        rows.append({"quartile": f"Q{k + 1}", "treated_n": tn, "treated_buyers": tb, "control_n": cn, "control_buyers": cb,
                     "observed_additional_buyers_per_1000": 1000 * w["diff"], "ci95_per_1000": [1000 * v for v in w["ci95"]],
                     "mean_predicted_additional_buyers_per_1000": float(1000 * pred_uplift[q == k].mean()),
                     "small_cell_warning": bool(min(tb, cb) < SMALL_CELL_BUYERS)})
    return rows


def segment_effects(df: pd.DataFrame) -> list[dict]:
    """The one pre-declared descriptive segmentation: past-year purchase category (product history, not gender)."""
    cat = np.where((df.mens == 1) & (df.womens == 1), "Both", np.where(df.mens == 1, "Mens merchandise only", "Womens merchandise only"))
    a, y, rows = df[ASSIGNMENT].to_numpy(), df[Y].to_numpy(float), []
    for seg in ("Mens merchandise only", "Womens merchandise only", "Both"):
        for arm in TREATMENTS:
            t, c = (cat == seg) & (a == arm), (cat == seg) & (a == CONTROL)
            tn, tb, cn, cb = int(t.sum()), int(y[t].sum()), int(c.sum()), int(y[c].sum())
            w = wald(tn, tb, cn, cb)
            rows.append({"segment": seg, "treatment_arm": arm, "control_arm": CONTROL, "treated_n": tn, "treated_buyers": tb, "control_n": cn,
                         "control_buyers": cb, "additional_buyers_per_1000": 1000 * w["diff"], "ci95_per_1000": [1000 * v for v in w["ci95"]],
                         "ci_excludes_zero": bool(w["ci95"][0] > 0 or w["ci95"][1] < 0), "small_cell_warning": bool(min(tb, cb) < SMALL_CELL_BUYERS)})
    return rows


# ---------------------------------------------------------------- the pre-registered run
def run(df: pd.DataFrame, proto: dict, n_boot: int | None = None, n_boot_qini: int = 500) -> dict:
    """Fit on train(+validation), evaluate once on test. Returns plain numbers; nothing is written here."""
    seed = proto["split"]["seed"]
    n_boot = n_boot or 2000
    lab = make_split(df, proto)
    tr, va, te = df[lab == "train"], df[lab == "validation"], df[lab == "test"].reset_index(drop=True)
    trva = df[lab != "test"]

    # 1. regularisation chosen by validation log loss (train-only fits)
    grid = []
    for C in proto["model"]["C_grid"]:
        d, clf = fit_slearner(tr, C)
        grid.append({"C": C, "validation_log_loss": _log_loss(va[Y].to_numpy(float), clf.predict_proba(d.transform(va))[:, 1]),
                     "train_log_loss": _log_loss(tr[Y].to_numpy(float), clf.predict_proba(d.transform(tr))[:, 1])})
    best_C = min(grid, key=lambda g: (round(g["validation_log_loss"], 9), g["C"]))["C"]
    d_tr, clf_tr = fit_slearner(tr, best_C)

    # 2. choices made on train+validation only: best overall arm, primary rule
    y_tv, a_tv = trva[Y].to_numpy(float), trva[ASSIGNMENT].to_numpy()
    ate_tv = {arm: float(y_tv[a_tv == arm].mean() - y_tv[a_tv == CONTROL].mean()) for arm in TREATMENTS}
    best_arm = max(TREATMENTS, key=lambda arm: ate_tv[arm])
    va_r = va.reset_index(drop=True)
    cap = proto["primary_cap"]
    rule_val = {"RULE_RECENCY": uplift_at_cap(va_r, order_recency(va_r), best_arm, cap), "RULE_HISTORY": uplift_at_cap(va_r, order_history(va_r), best_arm, cap)}
    primary_rule = max(rule_val, key=lambda k: rule_val[k])
    up_va = predict_arms(d_tr, clf_tr, va_r)
    model_val = uplift_at_cap(va_r, order_score(va_r, up_va[best_arm] - up_va[CONTROL]), best_arm, cap)

    # 3. final fit on train+validation, then the test split is read once
    d, clf = fit_slearner(trva, best_C)
    p = predict_arms(d, clf, te)
    uplift = {arm: p[arm] - p[CONTROL] for arm in TREATMENTS}
    policies = build_policies(te, uplift)
    ev = Evaluator(te, policies)
    point, boots = ev.point(), ev.bootstrap(n_boot, seed)
    pct = int(round(100 * cap))
    k = ARM_KEY[best_arm]
    ids = {"model": f"MODEL_{k}_{pct}", "random": f"RANDOM_{k}_{pct}", "rule": f"{primary_rule}_{k}_{pct}"}

    def diff(a: str, b: str) -> dict:
        x = boots[a]["buyers"] - boots[b]["buyers"]
        ci = pct_ci(1000 * x)
        return {"value": 1000 * (point[a]["buyers"] - point[b]["buyers"]), "ci95": ci}

    rows = []
    for pol in policies:
        pid, spec = pol.spec["policy_id"], pol.spec
        share = spec["contact_share"]
        r = {"spec": spec, **ev.counts(pid), "per_contact": point[pid]["buyers"], "per_contact_ci": pct_ci(boots[pid]["buyers"]),
             "spend_per_contact": point[pid]["spend"], "spend_ci": pct_ci(boots[pid]["spend"]), "comparisons": {}}
        r["per_eligible"], r["per_eligible_ci"] = share * r["per_contact"], [share * v for v in r["per_contact_ci"]]
        if spec["policy_family"] == "MODEL" and share < 1:
            s_pct = int(round(100 * share))
            arms_cmp = [spec["arm_assignment"]] if spec["arm_assignment"] in ARM_KEY else [best_arm]
            for arm in arms_cmp:
                for other in (f"RANDOM_{ARM_KEY[arm]}_{s_pct}", f"RULE_RECENCY_{ARM_KEY[arm]}_{s_pct}", f"RULE_HISTORY_{ARM_KEY[arm]}_{s_pct}"):
                    r["comparisons"][other] = diff(pid, other)
        elif spec["policy_family"] == "RULE":
            other = f"RANDOM_{ARM_KEY[spec['arm_assignment']]}_{int(round(100 * share))}"
            r["comparisons"][other] = diff(pid, other)
        elif pid == "MODEL_BESTARM_100":
            r["comparisons"][f"SEND_ALL_{k}_100"] = diff(pid, f"SEND_ALL_{k}_100")
        r["is_primary"] = pid in ids.values()
        rows.append(r)

    # 4. secondary: Qini, quartiles, calibration, coefficients
    qini, quart = [], {}
    for arm in TREATMENTS:
        pair_mask = te[ASSIGNMENT].isin([arm, CONTROL]).to_numpy()
        pair = te[pair_mask].reset_index(drop=True)
        for name, order in (("model predicted uplift", order_score(pair, uplift[arm][pair_mask])),
                            ("recency rule", order_recency(pair)), ("history rule", order_history(pair))):
            qini.append({"arm": arm, "score": name, **qini_with_ci(pair, arm, order, n_boot_qini, seed + 1)})
        quart[arm] = quartiles(te, uplift[arm], arm)
    a_te, y_te = te[ASSIGNMENT].to_numpy(), te[Y].to_numpy(float)
    calib = [{"arm": a, "n": int((a_te == a).sum()), "buyers": int(y_te[a_te == a].sum()), "observed_rate": float(y_te[a_te == a].mean()),
              "mean_predicted_rate": float(p[a][a_te == a].mean())} for a in (CONTROL, MENS, WOMENS)]
    coef = {"intercept": float(clf.intercept_[0]), "coefficients": {n: float(c) for n, c in zip(d.names, clf.coef_[0])},
            "scaling": {"mean": d.mean, "std": d.std}, "C": best_C, "reference_levels": {c: lv[0] for c, lv in CAT.items()}}
    coef_hash = hashlib.sha256(json.dumps(coef, sort_keys=True).encode()).hexdigest()
    return {
        "split": {"labels": lab, "hashes": split_hashes(df, lab), "seed": seed, "fractions": proto["split"]["fractions"]},
        "selection": {"C_grid": grid, "C": best_C, "ate_train_validation_per_1000": {a: 1000 * v for a, v in ate_tv.items()}, "best_overall_arm": best_arm,
                      "rule_uplift_at_cap_validation_per_1000": {r_: 1000 * v for r_, v in rule_val.items()}, "primary_rule": primary_rule,
                      "model_uplift_at_cap_validation_per_1000": 1000 * model_val},
        "model": {"coef": coef, "coef_sha256": coef_hash, "version": f"hillstrom-conv-slearner-p2-{coef_hash[:10]}", "feature_names": d.names,
                  "raw_features": list(MODEL_FEATURES), "n_fit": int(len(trva)), "buyers_fit": int(trva[Y].sum())},
        "test": {"n": int(len(te)), "arms": {a: {"n": int((a_te == a).sum()), "buyers": int(y_te[a_te == a].sum())} for a in (CONTROL, MENS, WOMENS)}},
        "policies": rows, "primary": {"cap": cap, "ids": ids, "model_minus_random": diff(ids["model"], ids["random"]),
                                      "model_minus_rule": diff(ids["model"], ids["rule"])},
        "predicted_uplift_summary": {arm: {"mean_per_1000": float(1000 * uplift[arm].mean()), "min_per_1000": float(1000 * uplift[arm].min()),
                                           "max_per_1000": float(1000 * uplift[arm].max()), "share_negative": float((uplift[arm] < 0).mean())} for arm in TREATMENTS},
        "bestarm_assignment_share_all_test": {a: float(np.mean(np.where(uplift[MENS] >= uplift[WOMENS], MENS, WOMENS) == a)) for a in TREATMENTS},
        "qini": qini, "quartiles": quart, "calibration": calib, "n_boot": n_boot, "n_boot_qini": n_boot_qini,
    }
