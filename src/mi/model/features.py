"""Time-aware features and labels for (cutoff_week, household, category).

Contract (enforced by assert_no_leakage and tests):
  * every feature uses only transactions with week <= cutoff; the 12-week features use weeks >= cutoff-lookback+1,
    and the LONG_HISTORY features (adopted 2026-11-14 under data/eval/model_eval_protocol_v1.json) use the 14 weeks
    before that lookback and any earlier week,
  * the label uses only weeks cutoff+1 .. cutoff+horizon,
  * eligibility uses only pre-cutoff data (>= 1 basket in the lookback window),
  * coupon redemptions / campaigns count only if dated on or before the cutoff week's last day.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES_V1 = [
    "cat_baskets_4w", "cat_baskets_12w", "cat_weeks_active_12w", "cat_weeks_since_last",
    "cat_spend_12w", "cat_share_spend_12w", "hh_baskets_4w", "hh_baskets_12w", "hh_weeks_active_12w",
    "hh_spend_12w", "hh_distinct_cats_12w", "cat_pop_4w", "cat_pop_trend", "hh_coupon_disc_12w",
    "hh_redemptions_12w", "hh_campaigns_started", "cat_private_share_12w",
]
LONG_HISTORY = ["cat_weeks_active_prior14", "cat_bought_before_lookback", "history_weeks_available"]
FEATURES = FEATURES_V1 + LONG_HISTORY
CAMPAIGN_FEATURES = ["hh_coupon_disc_12w", "hh_redemptions_12w", "hh_campaigns_started"]
POPULARITY_FEATURES = ["cat_pop_4w", "cat_pop_trend"]


def prepare(tx: pd.DataFrame, products: pd.DataFrame, categories: list[str]) -> dict:
    """Pre-aggregate once. Returns weekly household and household-category tables."""
    p = products[["product_id", "product_category", "brand"]]
    t = tx[["household_id", "basket_id", "product_id", "week", "sales_value", "coupon_disc",
            "transaction_timestamp"]].merge(p, on="product_id", how="left")
    week_end = t.groupby("week").transaction_timestamp.max().dt.normalize()
    hh_week = t.groupby(["household_id", "week"]).agg(
        baskets=("basket_id", "nunique"), spend=("sales_value", "sum"),
        coupon_disc=("coupon_disc", "sum")).reset_index()
    hh_week_ncat = t.dropna(subset=["product_category"]).groupby(["household_id", "week"]).product_category.unique()
    tc = t[t.product_category.isin(categories)].copy()
    tc["private"] = (tc.brand == "Private").astype(float) * tc.sales_value
    hcw = tc.groupby(["household_id", "product_category", "week"]).agg(
        baskets=("basket_id", "nunique"), spend=("sales_value", "sum"), private=("private", "sum")).reset_index()
    return {"hh_week": hh_week, "hh_week_ncat": hh_week_ncat, "hcw": hcw, "week_end": week_end,
            "categories": list(categories)}


def build_cutoff(prep: dict, cutoff: int, lookback: int, horizon: int,
                 redemptions: pd.DataFrame, campaigns: pd.DataFrame, camp_desc: pd.DataFrame,
                 with_label: bool = True) -> pd.DataFrame:
    lo = cutoff - lookback + 1
    hw, hcw, cats = prep["hh_week"], prep["hcw"], prep["categories"]
    hw_lb = hw[(hw.week >= lo) & (hw.week <= cutoff)]
    hh = hw_lb.groupby("household_id").agg(
        hh_baskets_12w=("baskets", "sum"), hh_weeks_active_12w=("week", "nunique"),
        hh_spend_12w=("spend", "sum"), hh_coupon_disc_12w=("coupon_disc", "sum"))
    hh["hh_baskets_4w"] = hw_lb[hw_lb.week > cutoff - 4].groupby("household_id").baskets.sum()
    nc = prep["hh_week_ncat"]
    nc = nc[(nc.index.get_level_values("week") >= lo) & (nc.index.get_level_values("week") <= cutoff)]
    hh["hh_distinct_cats_12w"] = nc.groupby(level="household_id").apply(
        lambda s: len(set(np.concatenate(s.values))))
    hh = hh.fillna(0)
    eligible = hh[hh.hh_baskets_12w >= 1].index
    # cartesian grid household x category
    grid = pd.MultiIndex.from_product([eligible, cats], names=["household_id", "product_category"]).to_frame(index=False)
    c_lb = hcw[(hcw.week >= lo) & (hcw.week <= cutoff)]
    cagg = c_lb.groupby(["household_id", "product_category"]).agg(
        cat_baskets_12w=("baskets", "sum"), cat_weeks_active_12w=("week", "nunique"),
        cat_spend_12w=("spend", "sum"), cat_private_12w=("private", "sum"), last_week=("week", "max"))
    c4 = c_lb[c_lb.week > cutoff - 4].groupby(["household_id", "product_category"]).baskets.sum().rename("cat_baskets_4w")
    df = grid.merge(cagg.reset_index(), how="left", on=["household_id", "product_category"]).merge(
        c4.reset_index(), how="left", on=["household_id", "product_category"])
    df["cat_weeks_since_last"] = (cutoff - df.last_week).fillna(lookback).clip(upper=lookback)
    # longer history, strictly before the 12-week lookback (still <= cutoff): weeks lo-14 .. lo-1, and any week < lo
    prior = hcw[(hcw.week < lo) & (hcw.week >= lo - 14)].groupby(["household_id", "product_category"]).week.nunique()
    before = hcw[hcw.week < lo].groupby(["household_id", "product_category"]).size().gt(0).astype(float)
    df = df.merge(prior.rename("cat_weeks_active_prior14").reset_index(), how="left", on=["household_id", "product_category"]).merge(
        before.rename("cat_bought_before_lookback").reset_index(), how="left", on=["household_id", "product_category"])
    df[["cat_weeks_active_prior14", "cat_bought_before_lookback"]] = df[["cat_weeks_active_prior14", "cat_bought_before_lookback"]].fillna(0.0)
    df["history_weeks_available"] = float(max(0, cutoff - lookback))
    df = df.drop(columns="last_week").fillna({"cat_baskets_12w": 0, "cat_weeks_active_12w": 0, "cat_spend_12w": 0,
                                              "cat_private_12w": 0, "cat_baskets_4w": 0})
    df = df.merge(hh.reset_index(), on="household_id", how="left")
    df["cat_share_spend_12w"] = np.where(df.hh_spend_12w > 0, df.cat_spend_12w / df.hh_spend_12w, 0.0)
    df["cat_private_share_12w"] = np.where(df.cat_spend_12w > 0, df.cat_private_12w / df.cat_spend_12w, 0.0)
    df = df.drop(columns="cat_private_12w")
    # cutoff-level popularity among active households, prior weeks only
    n_active_4w = hw_lb[hw_lb.week > cutoff - 4].household_id.nunique()
    pop4 = c_lb[c_lb.week > cutoff - 4].groupby("product_category").household_id.nunique() / max(n_active_4w, 1)
    pop_prev = c_lb[(c_lb.week > cutoff - 8) & (c_lb.week <= cutoff - 4)].groupby("product_category").household_id.nunique()
    n_prev = hw_lb[(hw_lb.week > cutoff - 8) & (hw_lb.week <= cutoff - 4)].household_id.nunique()
    pop_prev = pop_prev / max(n_prev, 1)
    df["cat_pop_4w"] = df.product_category.map(pop4).fillna(0)
    df["cat_pop_trend"] = df.product_category.map((pop4 / pop_prev.replace(0, np.nan)).fillna(1.0)).fillna(1.0)
    # campaign / coupon history known at cutoff date
    cutoff_date = prep["week_end"].get(cutoff, prep["week_end"].max())
    red = redemptions[(redemptions.redemption_date <= cutoff_date) &
                      (redemptions.redemption_date > cutoff_date - pd.Timedelta(weeks=int(lookback)))]
    df["hh_redemptions_12w"] = df.household_id.map(red.groupby("household_id").size()).fillna(0)
    started = camp_desc[camp_desc.start_date <= cutoff_date].campaign_id
    camp = campaigns[campaigns.campaign_id.isin(set(started))]
    df["hh_campaigns_started"] = df.household_id.map(camp.groupby("household_id").size()).fillna(0)
    df["cutoff"] = cutoff
    df["feature_max_week"] = cutoff
    if with_label:
        lab = hcw[(hcw.week > cutoff) & (hcw.week <= cutoff + horizon)].groupby(
            ["household_id", "product_category"]).agg(label_spend=("spend", "sum"))
        df = df.merge(lab.reset_index(), on=["household_id", "product_category"], how="left")
        df["label_spend"] = df.label_spend.fillna(0.0)
        df["y"] = (df.label_spend > 0).astype(int)
        df["label_window"] = f"{cutoff + 1}-{cutoff + horizon}"
    df["segment"] = assign_segment(df)
    return df


def assign_segment(df: pd.DataFrame) -> pd.Series:
    seg = np.select(
        [df.cat_weeks_active_12w >= 3,
         (df.cat_weeks_active_12w >= 1) & (df.cat_baskets_4w > 0),
         (df.cat_weeks_active_12w >= 1) & (df.cat_baskets_4w == 0),
         (df.cat_weeks_active_12w == 0) & (df.hh_baskets_12w >= 6)],
        ["REGULAR", "RECENT_LIGHT", "LAPSING", "ACTIVE_NONBUYER"], default="LOW_ACTIVITY")
    return pd.Series(seg, index=df.index)


def assert_no_leakage(df: pd.DataFrame) -> None:
    if (df.feature_max_week > df.cutoff).any():
        raise ValueError("feature_time > as_of detected")


def build_panel(prep, cutoffs, cfg, redemptions, campaigns, camp_desc, with_label=True) -> pd.DataFrame:
    t = cfg["temporal"]
    parts = [build_cutoff(prep, c, t["lookback_weeks"], t["horizon_weeks"], redemptions, campaigns, camp_desc,
                          with_label=with_label) for c in cutoffs]
    df = pd.concat(parts, ignore_index=True)
    assert_no_leakage(df)
    return df
