"""Historical category demand baseline (OBSERVED) with a simple, backtested 4-week naive forecast.

Weekly series: buying households and sales per category (weeks 2..53; week 1 is a single day).
Forecast candidates for the next 4-week total: naive (last 4 weeks) vs trailing 8-week mean x 4.
Backtest WAPE over rolling origins; zero-volume weeks handled by summing before dividing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mi.decision.metrics import Undefined, ratio


def weekly_series(tx: pd.DataFrame, products: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    t = tx[["household_id", "week", "sales_value", "product_id"]].merge(
        products[["product_id", "product_category"]], on="product_id")
    t = t[t.product_category.isin(categories) & (t.week >= 2)]
    return t.groupby(["product_category", "week"]).agg(households=("household_id", "nunique"),
                                                       sales=("sales_value", "sum")).reset_index()


def wape(actual, forecast):
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    r = ratio(np.abs(actual - forecast).sum(), np.abs(actual).sum(), "zero actual volume")
    return r


def backtest(series: pd.Series, horizon=4, origins=range(20, 50, 4)) -> dict:
    a, f_naive, f_ma8 = [], [], []
    s = series.sort_index()
    for o in origins:
        hist, fut = s.loc[:o], s.loc[o + 1:o + horizon]
        if len(fut) < horizon or len(hist) < 8:
            continue
        a.append(fut.sum())
        f_naive.append(hist.iloc[-4:].sum())
        f_ma8.append(hist.iloc[-8:].mean() * horizon)
    out = {"origins": len(a), "WAPE_naive_last4": wape(a, f_naive), "WAPE_trailing8_mean": wape(a, f_ma8)}
    return {k: (None if isinstance(v, Undefined) else v) for k, v in out.items()}


def demand_summary(ws: pd.DataFrame) -> list[dict]:
    rows = []
    for cat, g in ws.groupby("product_category"):
        s = g.set_index("week").sales
        h = g.set_index("week").households
        last8 = s.iloc[-8:]
        base = float(last8.mean() * 4)
        sd = float(last8.std() * 2)  # sd of a 4-week sum under independence ~ sqrt(4)*sd_week
        bt = backtest(s)
        rows.append({"category": cat, "status": "OBSERVED history; forecast = trailing-8-week baseline (not a validated demand model)",
                     "weekly_sales_mean_last8": float(last8.mean()), "weekly_households_mean_last8": float(h.iloc[-8:].mean()),
                     "next4w_sales_low": base - 1.64 * sd, "next4w_sales_base": base, "next4w_sales_high": base + 1.64 * sd,
                     "trend_last8_vs_prev8": float(last8.mean() / s.iloc[-16:-8].mean()) if len(s) >= 16 else None,
                     **bt})
    return rows
