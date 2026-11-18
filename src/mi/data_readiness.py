"""Can this project run on another retail dataset?  A readiness check against the exact design the grocery model used.

Input: a transactions table (CSV, Parquet or Excel) and, if categories live elsewhere, a products table.
Output: READY / PARTIAL / NOT_READY with one line per requirement, which categories qualify, the time split the data would
support, what the project can and cannot do with it (propensity, uplift, economics) and what to fix.

The thresholds are the ones the grocery case used (12-week look-back, 4-week horizon, cut-offs 4 weeks apart: 53 weeks for the full
design, 37 for the reduced one). Nothing here trains a model or sends anything.

Usage:  python -m mi.data_readiness --transactions file.csv [--products products.csv] [--map household_id=cust ...]
        python -m mi.data_readiness --demo             # the Complete Journey data this project was built on (expect READY)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LOOKBACK, HORIZON, STEP = 12, 4, 4
MIN_TRAIN_CUTOFFS = 3                       # reduced design: 3 train cut-offs + validation + calibration + test
FULL_WEEKS = 53                             # the grocery design: cut-offs 13..49 and a 4-week label window
MIN_WEEKS = LOOKBACK + 1 + (MIN_TRAIN_CUTOFFS + 3) * STEP + HORIZON - STEP   # = 37 weeks
PENETRATION_BAND = (0.10, 0.60)             # share of active households buying the category in the label window (project rule: 12%-55%)
MIN_POSITIVES = 100                         # buyers in the label window, so average precision is not noise
# the grocery policy's exclusions: fuel, coupons/misc, alcohol and tobacco (no promotional targeting of age-restricted goods),
# fresh meat and seafood (stock and perishability risk with no inventory data)
GUARDRAIL = re.compile(r"fuel|\bgas\b|tobacco|cigar|alcohol|\bbeer\b|\bwine\b|liquor|spirit|coupon|misc|gift ?card|pharm|prescription|lottery"
                       r"|\bbeef\b|\bpork\b|poultry|chicken|seafood|\bfish\b|fresh meat|\bmeat\b", re.I)

SYNONYMS = {
    "household_id": ["household_id", "household", "hh_id", "customer_id", "customer", "cust_id", "customerid", "user_id", "client_id", "shopper_id",
                     "member_id", "card_id", "loyalty_id", "account_id", "buyer_id", "cust_no", "customer_no", "cust_number", "customer_number",
                     "client_no", "member_no", "account_no", "clientid", "memberid", "userid"],
    "date": ["transaction_timestamp", "transaction_date", "order_date", "purchase_date", "invoice_date", "date", "timestamp", "datetime",
             "day_date", "t_dat", "trans_date", "order_datetime", "created_at", "event_time"],
    "week": ["week", "week_no", "week_number", "weekno"],
    "amount": ["sales_value", "amount", "line_total", "net_amount", "total_amount", "revenue", "sales", "sale_amount", "spend", "total", "price",
               "item_total", "value"],
    "basket_id": ["basket_id", "order_id", "transaction_id", "invoice_no", "invoice", "receipt_id", "ticket_id", "trans_id", "order_number", "basket"],
    "product_id": ["product_id", "sku", "item_id", "article_id", "upc", "stockcode", "product", "item"],
    "category": ["product_category", "category", "department", "product_type", "commodity", "category_name", "product_group", "sub_category",
                 "product_class", "class", "commodity_desc", "department_name"],
    "quantity": ["quantity", "qty", "units"],
    "treatment": ["treatment", "treated", "is_treated", "test_group", "campaign_group", "exposed", "ab_group", "variant"],
}
REQUIRED = ["household_id", "amount"]       # plus a date or a week, plus a category (directly or through a products table)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def map_columns(columns, overrides: dict | None = None) -> dict:
    """canonical field -> the column that fills it (exact normalised match, in the order of SYNONYMS; overrides win)."""
    norm = {_norm(c): c for c in columns}
    out = {k: v for k, v in (overrides or {}).items() if v in columns}
    for canon, names in SYNONYMS.items():
        if canon in out:
            continue
        for n in names:
            if n in norm:
                out[canon] = norm[n]
                break
    return out


def read_table(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(p)
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p, low_memory=False)


def proposed_temporal(span_weeks: int) -> dict | None:
    """The cut-offs the data can support (same shape as the grocery policy), or None if it is too short."""
    test = span_weeks - HORIZON
    cal, val = test - STEP, test - 2 * STEP
    train = list(range(LOOKBACK + 1, val - HORIZON + 1, STEP))   # last training outcome window must end by the validation cut-off (no leakage)
    if len(train) < MIN_TRAIN_CUTOFFS or train[0] < LOOKBACK + 1:
        return None
    return {"lookback_weeks": LOOKBACK, "horizon_weeks": HORIZON, "train_cutoffs": train, "validation_cutoff": val,
            "calibration_cutoff": cal, "test_cutoff": test, "scoring_cutoff": span_weeks, "design": "full" if span_weeks >= FULL_WEEKS else "reduced"}


def assess(tx: pd.DataFrame, products: pd.DataFrame | None = None, mapping: dict | None = None) -> dict:
    checks: list[dict] = []

    def add(cid, name, status, detail, fix=None):
        checks.append({"id": cid, "requirement": name, "status": status, "detail": detail, "fix": fix})

    m = map_columns(tx.columns, mapping)
    pm = map_columns(products.columns, mapping) if products is not None else {}
    have_cat = "category" in m or (products is not None and "product_id" in m and "product_id" in pm and "category" in pm)
    have_time = "date" in m or "week" in m
    missing = [k for k in REQUIRED if k not in m] + ([] if have_time else ["date or week"]) + ([] if have_cat else ["category (or product_id + a products table with a category)"])
    add("D01", "Columns found: customer, date or week, amount, category", "PASS" if not missing else "NOT_READY",
        "mapped " + ", ".join(f"{k}={v}" for k, v in m.items()) if not missing else f"cannot find: {', '.join(missing)}; columns present: {list(tx.columns)[:12]}",
        None if not missing else "Rename the columns, or pass --map household_id=<col> date=<col> amount=<col> category=<col>.")
    if missing:
        return _finish(checks, m, None, None, None)

    df = pd.DataFrame({"household_id": tx[m["household_id"]].astype("string"), "amount": pd.to_numeric(tx[m["amount"]], errors="coerce")})
    if "date" in m:
        dt = pd.to_datetime(tx[m["date"]], errors="coerce")
        df["date"] = dt
        week = ((dt - dt.min()).dt.days // 7 + 1) if dt.notna().any() else pd.Series(np.nan, index=tx.index)
        df["week"] = week
    else:
        df["week"] = pd.to_numeric(tx[m["week"]], errors="coerce")
    df["basket_id"] = tx[m["basket_id"]].astype("string") if "basket_id" in m else (df["household_id"].astype(str) + "|" + df["week"].astype(str))
    if "category" in m:
        df["category"] = tx[m["category"]].astype("string")
    else:
        lk = products[[pm["product_id"], pm["category"]]].drop_duplicates(pm["product_id"]).rename(columns={pm["product_id"]: "_pid", pm["category"]: "category"})
        df["category"] = pd.Series(tx[m["product_id"]].map(lk.set_index("_pid")["category"]), index=tx.index).astype("string")

    n = len(df)
    nulls = {c: float(df[c].isna().mean()) for c in ("household_id", "week", "amount", "category")}
    df = df.dropna(subset=["household_id", "week", "amount"])
    df["week"] = df["week"].astype(int)
    span = int(df.week.max() - df.week.min() + 1) if len(df) else 0
    if df.week.min() > 1:  # a numeric week column that does not start at 1: shift so cut-offs are comparable
        df["week"] = df["week"] - df.week.min() + 1
    hh = int(df.household_id.nunique())

    # D02 history length
    tmp = proposed_temporal(span)
    if span >= FULL_WEEKS:
        add("D02", f"History of at least {FULL_WEEKS} weeks (the full design)", "PASS", f"{span} weeks")
    elif tmp:
        add("D02", f"History of at least {FULL_WEEKS} weeks (the full design)", "PARTIAL", f"{span} weeks: the reduced design fits (>= {MIN_WEEKS})",
            f"Use the reduced cut-offs below, or add {FULL_WEEKS - span} more weeks for the full design.")
    else:
        add("D02", f"History of at least {MIN_WEEKS} weeks", "NOT_READY", f"{span} weeks: not enough for a look-back, three training cut-offs, validation, calibration and test",
            f"Get at least {MIN_WEEKS} weeks of transactions (53 is the full design).")

    # D03 customers
    add("D03", "Enough customers (1,000 comfortable, 300 minimum)", "PASS" if hh >= 1000 else ("PARTIAL" if hh >= 300 else "NOT_READY"),
        f"{hh:,} customers, {n:,} rows", None if hh >= 1000 else "Fewer customers give wide intervals; report them and avoid per-category claims.")

    # D04..: categories at the proposed test cut-off
    cats = pd.DataFrame()
    if tmp:
        c = tmp["test_cutoff"]
        active = set(df.loc[(df.week >= c - LOOKBACK + 1) & (df.week <= c), "household_id"])
        lab = df[(df.week > c) & (df.week <= c + HORIZON) & df.household_id.isin(active) & df.category.notna()]
        hist = df[(df.week >= c - LOOKBACK + 1) & (df.week <= c) & df.household_id.isin(active) & df.category.notna()]
        pos = lab.groupby("category").household_id.nunique()
        ever = hist.groupby("category").household_id.nunique()
        sales = df.groupby("category").amount.sum()
        cats = pd.DataFrame({"buyers_in_label_window": pos, "buyers_in_lookback": ever, "sales": sales}).fillna(0)
        cats["eligible_households"] = len(active)
        cats["penetration"] = cats.buyers_in_label_window / max(1, len(active))
        cats["excluded_by_guardrail"] = [bool(GUARDRAIL.search(str(i))) for i in cats.index]
        cats["qualifies"] = (~cats.excluded_by_guardrail) & cats.penetration.between(*PENETRATION_BAND) & (cats.buyers_in_label_window >= MIN_POSITIVES)
        cats = cats.sort_values(["qualifies", "buyers_in_label_window"], ascending=False)
        q = int(cats.qualifies.sum())
        total_cats = int(df.category.nunique())
        add("D04", "Enough categories that qualify (at least 4; the grocery case used 8)", "PASS" if q >= 4 else ("PARTIAL" if q >= 2 else "NOT_READY"),
            f"{q} of {total_cats} categories: penetration {int(PENETRATION_BAND[0]*100)}%-{int(PENETRATION_BAND[1]*100)}% in the label window, >= {MIN_POSITIVES} buyers, no guardrail category",
            None if q >= 4 else "Widen the category definition (group sub-categories), or add history so more households buy in the label window.")
        elig = len(active)
        add("D05", "Active customers at the test cut-off", "PASS" if elig >= 300 else "PARTIAL", f"{elig:,} customers bought in the 12 weeks before the test cut-off")
        # repeat behaviour: share of active households with >=2 distinct purchase weeks in the look-back
        wk = df[(df.week >= c - LOOKBACK + 1) & (df.week <= c)].groupby("household_id").week.nunique()
        rep = float((wk >= 2).mean()) if len(wk) else 0.0
        add("D06", "Repeat purchasing (a propensity model needs repeat behaviour)", "PASS" if rep >= 0.5 else "PARTIAL",
            f"{rep:.0%} of active customers bought in 2 or more different weeks", None if rep >= 0.5 else "Low repeat rates make 'who buys next' hard to predict; expect modest lift.")
    else:
        add("D04", "Enough categories that qualify", "NOT_READY", "cannot be assessed: the history is too short for a test cut-off")

    # D07 quality
    q_notes = []
    if nulls["category"] > 0.05:
        q_notes.append(f"{nulls['category']:.0%} of rows have no category")
    if (df.amount < 0).mean() > 0.02:
        q_notes.append(f"{(df.amount < 0).mean():.1%} negative amounts (returns?)")
    dup = float(tx.duplicated().mean())
    if dup > 0.02:
        q_notes.append(f"{dup:.1%} duplicate rows")
    bad_key = max(nulls["household_id"], nulls["week"], nulls["amount"])
    if bad_key > 0.02:
        q_notes.append(f"{bad_key:.1%} rows with a missing customer, date or amount (dropped)")
    add("D07", "Data quality (missing keys, returns, duplicates)", "PASS" if not q_notes else "PARTIAL", "; ".join(q_notes) or "no issue above 2-5%",
        None if not q_notes else "Clean or document these before modelling; returns should be netted or removed.")

    # D08 optional data
    extras = []
    extras.append("customer-level treatment column found (a randomized or A/B test can be analysed for uplift)" if "treatment" in m else
                  "no treatment column: propensity and decision support only, NO causal claim about any offer")
    extras.append("quantity found" if "quantity" in m else "no quantity column (not required)")
    add("D08", "Optional: treatment / experiment column", "INFO", "; ".join(extras))
    return _finish(checks, m, tmp, cats, {"rows": n, "customers": hh, "weeks": span, "null_rates": nulls})


def _finish(checks, m, tmp, cats, facts) -> dict:
    st = [c["status"] for c in checks]
    verdict = "NOT_READY" if "NOT_READY" in st else ("PARTIAL" if "PARTIAL" in st else "READY")
    can = {
        "propensity_model_who_buys_next": verdict in ("READY", "PARTIAL") and "NOT_READY" not in st,
        "uplift_or_coupon_effect": "treatment" in m,
        "profit_or_roi": False,
        "profit_or_roi_why": "needs margin, cost per contact and consent from the client: UNKNOWN in any retail file",
        "marketing_decision_card": verdict in ("READY", "PARTIAL"),
    }
    return {"verdict": verdict, "mapping": m, "facts": facts, "checks": checks, "proposed_temporal": tmp,
            "categories": (cats.reset_index().rename(columns={"index": "category"}).round(4).to_dict("records") if cats is not None and len(cats) else []),
            "recommended_categories": ([i for i in cats.index[cats.qualifies]][:8] if cats is not None and len(cats) else []),
            "can_do": can, "fixes": [c["fix"] for c in checks if c.get("fix") and c["status"] not in ("PASS", "INFO")]}


def to_markdown(r: dict) -> str:
    L = [f"# Dataset readiness: **{r['verdict']}**", ""]
    if r["facts"]:
        f = r["facts"]
        L.append(f"{f['rows']:,} rows, {f['customers']:,} customers, {f['weeks']} weeks.")
    L += ["", "| id | requirement | status | detail |", "|---|---|---|---|"]
    L += [f"| {c['id']} | {c['requirement']} | **{c['status']}** | {str(c['detail']).replace('|', '/')} |" for c in r["checks"]]
    if r["proposed_temporal"]:
        t = r["proposed_temporal"]
        L += ["", f"**Time split the data supports ({t['design']} design):** train cut-offs {t['train_cutoffs']}, validation {t['validation_cutoff']}, "
              f"calibration {t['calibration_cutoff']}, test {t['test_cutoff']}, scoring {t['scoring_cutoff']}."]
    if r["recommended_categories"]:
        L += ["", "**Categories to model:** " + ", ".join(r["recommended_categories"])]
    c = r["can_do"]
    L += ["", "**What the project can do with it**", f"- Who buys next (propensity): {'yes' if c['propensity_model_who_buys_next'] else 'no'}",
          f"- Effect of an offer (uplift): {'yes, a treatment column exists' if c['uplift_or_coupon_effect'] else 'no, needs a randomized test'}",
          f"- Profit or ROI: no ({c['profit_or_roi_why']})", f"- Marketing decision card: {'yes' if c['marketing_decision_card'] else 'no'}"]
    if r["fixes"]:
        L += ["", "**To fix**"] + [f"- {x}" for x in r["fixes"]]
    return "\n".join(L) + "\n"


def demo_complete_journey() -> dict:
    from mi.ingest.load import load
    return assess(load("transactions"), load("products"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transactions")
    ap.add_argument("--products")
    ap.add_argument("--map", nargs="*", default=[], help="canonical=column, e.g. household_id=cust_no")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if a.demo:
        r = demo_complete_journey()
    elif a.transactions:
        r = assess(read_table(a.transactions), read_table(a.products) if a.products else None, dict(x.split("=", 1) for x in a.map))
    else:
        ap.error("give --transactions or --demo")
    print(to_markdown(r))
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
    return 0 if r["verdict"] != "NOT_READY" else 1


if __name__ == "__main__":
    sys.exit(main())
