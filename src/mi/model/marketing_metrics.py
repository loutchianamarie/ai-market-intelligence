"""Marketing measurements the analytical model did not report: lift and gains, RFM tiers, a customer-value proxy and retention.  Pure functions on DataFrames (no file access), so each one is tested on data with a known answer.

Cross-sell is NOT here: `mi.decision.opportunities.cross_sell` already measures it at basket level and validates it on held-out weeks.

Status labels carried by the callers: gains and lift are OBSERVED on held-out data when `y` is the observed outcome and MODEL ESTIMATE
when computed from predicted scores; the value proxy and its retention input are ASSUMPTION; nothing here is an effect of an offer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def gains_table(y, score, bins: int = 10) -> pd.DataFrame:
    """Decile table, decile 1 = highest scores. rate = buyer share; lift = rate / overall rate; gain = share of ALL buyers captured so far."""
    y = np.asarray(y, dtype=float)
    s = np.asarray(score, dtype=float)
    if len(y) != len(s) or len(y) < bins:
        raise ValueError("need one score per outcome and at least `bins` rows")
    order = np.argsort(-s, kind="stable")
    parts = np.array_split(order, bins)
    total, n = y.sum(), len(y)
    rows, cb, cn = [], 0.0, 0
    for i, idx in enumerate(parts, 1):
        b = float(y[idx].sum())
        cb, cn = cb + b, cn + len(idx)
        rate = b / len(idx)
        rows.append({"decile": i, "households": len(idx), "buyers": int(b), "rate": rate, "lift": rate / (total / n) if total else np.nan,
                     "cum_households_share": cn / n, "cum_buyers_share": cb / total if total else np.nan,
                     "cum_lift": (cb / cn) / (total / n) if total else np.nan})
    return pd.DataFrame(rows)


def lift_at(y, score, frac: float) -> dict:
    """Buyer rate among the top `frac` of scores, the base rate, and their ratio."""
    y = np.asarray(y, dtype=float)
    k = max(1, int(round(len(y) * frac)))
    top = np.argsort(-np.asarray(score, dtype=float), kind="stable")[:k]
    base = float(y.mean())
    rate = float(y[top].mean())
    return {"contacts": k, "rate": rate, "base_rate": base, "lift": rate / base if base else np.nan, "buyers_captured_share": float(y[top].sum() / y.sum()) if y.sum() else np.nan}


def rfm_table(tx: pd.DataFrame, cutoff_week: int, window: int = 12) -> pd.DataFrame:
    """Recency (weeks since the last basket), frequency (distinct baskets) and monetary (spend) per household at `cutoff_week`.
    Needs columns household_id, basket_id, week, sales_value. Uses only weeks <= cutoff (no look-ahead). Scores 1-5, 5 = best."""
    t = tx[tx.week <= cutoff_week]
    last = t.groupby("household_id").week.max()
    w = t[t.week > cutoff_week - window]
    f = w.groupby("household_id").basket_id.nunique()
    m = w.groupby("household_id").sales_value.sum()
    out = pd.DataFrame({"recency_weeks": cutoff_week - last}).join(f.rename("frequency")).join(m.rename("monetary"))
    out["frequency"] = out["frequency"].fillna(0)
    out["monetary"] = out["monetary"].fillna(0.0)

    def quint(s, ascending):
        # tied households must share a score (most grocery households shop every week), so rank by the average position, not by row order
        pct = (s if ascending else -s).rank(method="average", pct=True)
        return np.ceil(pct * 5).clip(1, 5).astype(int)

    out["R"] = quint(out.recency_weeks, ascending=False)   # fewer weeks since last basket = higher score
    out["F"] = quint(out.frequency, ascending=True)
    out["M"] = quint(out.monetary, ascending=True)
    out["rfm_segment"] = rfm_segment(out.R, out.F)
    return out


def rfm_segment(R, F) -> pd.Series:
    idx = getattr(R, "index", None)
    R, F = np.asarray(R), np.asarray(F)
    seg = np.select(
        [(R >= 4) & (F >= 4), (F >= 4) & (R == 3), (R >= 4) & (F >= 2), (R >= 4), (R <= 2) & (F >= 3), (R <= 2)],
        ["Champions", "Loyal", "Potential loyalists", "New or light", "At risk", "Hibernating"], default="Need attention")
    return pd.Series(seg, index=idx)


def value_proxy(spend_per_cycle: float, margin: float, retention_per_cycle: float, cycles: int = 13, annual_discount: float = 0.10) -> float:
    """Discounted margin over the next `cycles` four-week cycles if the household keeps buying at `spend_per_cycle`.
    ASSUMPTION: margin and retention are inputs, not measurements. It ranks households; it is not a forecast of profit."""
    if not 0 <= retention_per_cycle <= 1 or margin < 0 or spend_per_cycle < 0:
        raise ValueError("retention must be in [0,1]; margin and spend must be >= 0")
    t = np.arange(1, cycles + 1)
    return float(np.sum(spend_per_cycle * margin * retention_per_cycle ** t / (1 + annual_discount) ** (t / 13.0)))


def retention_table(tx: pd.DataFrame, last_week: int, window: int = 4, periods: int = 6) -> pd.DataFrame:
    """Of the households active in one 4-week window, the share active in the next. Needs household_id, week."""
    rows = []
    for i in range(periods, 0, -1):
        a_hi, a_lo = last_week - window * i, last_week - window * (i + 1)
        b_lo, b_hi = a_hi, a_hi + window
        a = set(tx.loc[(tx.week > a_lo) & (tx.week <= a_hi), "household_id"])
        b = set(tx.loc[(tx.week > b_lo) & (tx.week <= b_hi), "household_id"])
        if a:
            rows.append({"window": f"weeks {a_lo + 1}-{a_hi}", "active": len(a), "active_next_window": len(a & b), "retention": len(a & b) / len(a), "lapse_rate": 1 - len(a & b) / len(a)})
    return pd.DataFrame(rows)
