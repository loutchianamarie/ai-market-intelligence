"""Campaign case data: checksum-gated load, audit and a data dictionary with TIMING.

The raw CSV stays local (data/raw/hillstrom/, gitignored): the source page states no terms of use.
Usage: python -m mi.campaign.data  ->  reports/campaign/data_audit.json, docs/campaign_data_dictionary.md
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from mi.campaign.contract import ARMS, CONTROL, TREATMENTS
from mi.paths import DOCS, RAW, REPORTS, ROOT

PROTOCOL = ROOT / "data" / "eval" / "hillstrom_protocol_v2.json"
CSV = RAW / "hillstrom" / "hillstrom_2008.csv"
OUT = REPORTS / "campaign"

PRE = ["recency", "history_segment", "history", "mens", "womens", "zip_code", "newbie", "channel"]
ASSIGNMENT = "segment"
POST = ["visit", "conversion", "spend"]
COLUMNS = PRE + [ASSIGNMENT] + POST
MODEL_FEATURES = ["recency", "history", "mens", "womens", "newbie", "zip_code", "channel"]     # raw columns the model may read

# column, timing, role, source definition (verbatim from the source page), how this project uses it
DICTIONARY = [
    ("recency", "PRE-EMAIL", "feature", "Months since last purchase.", "model feature (standardised); recency rule"),
    ("history_segment", "PRE-EMAIL", "not used", "Categorization of dollars spent in the past year.", "excluded: a binned copy of history"),
    ("history", "PRE-EMAIL", "feature", "Actual dollar value spent in the past year.", "model feature as log1p(history), standardised; history rule"),
    ("mens", "PRE-EMAIL", "feature", "1/0 indicator, 1 = customer purchased Mens merchandise in the past year.", "model feature. Product purchase history, NOT gender"),
    ("womens", "PRE-EMAIL", "feature", "1/0 indicator, 1 = customer purchased Womens merchandise in the past year.", "model feature. Product purchase history, NOT gender"),
    ("zip_code", "PRE-EMAIL", "feature", "Classifies zip code as Urban, Suburban, or Rural.", "model feature (one-hot). The file spells one level 'Surburban'; kept as is"),
    ("newbie", "PRE-EMAIL", "feature", "1/0 indicator, 1 = New customer in the past twelve months.", "model feature"),
    ("channel", "PRE-EMAIL", "feature", "Describes the channels the customer purchased from in the past year.", "model feature (one-hot): Phone, Web, Multichannel"),
    ("segment", "ASSIGNMENT", "treatment", "The e-mail campaign the customer received: Mens E-Mail, Womens E-Mail or No E-Mail (each 1/3, randomly chosen).",
     "the randomized arm. Enters the model only as the treatment indicator; never a customer feature"),
    ("visit", "POST-EMAIL (2 weeks)", "outcome, not used", "1/0 indicator, 1 = Customer visited website in the following two weeks.", "FORBIDDEN as a predictor or ranking input; not a v2 outcome"),
    ("conversion", "POST-EMAIL (2 weeks)", "primary outcome", "1/0 indicator, 1 = Customer purchased merchandise in the following two weeks.", "the label. FORBIDDEN as a predictor or ranking input"),
    ("spend", "POST-EMAIL (2 weeks)", "economics outcome", "Actual dollars spent in the following two weeks.", "incremental spend per contact only. FORBIDDEN as a predictor or ranking input"),
]


class CampaignDataError(RuntimeError):
    pass


def load_protocol(path: Path = PROTOCOL) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_raw(path: Path = CSV, proto: dict | None = None, enforce_checksum: bool = True) -> tuple[pd.DataFrame, dict]:
    """Load the experiment file. Returns (frame with customer_id = row index, file facts). Refuses a different file."""
    proto = proto or load_protocol()
    path = Path(path)
    if not path.exists():
        raise CampaignDataError(f"{path} not found. Download it (local only) from {proto['source']['file']}")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if enforce_checksum and sha != proto["source"]["sha256"]:
        raise CampaignDataError(f"checksum {sha[:16]} differs from the pre-registered {proto['source']['sha256'][:16]}")
    df = pd.read_csv(path)
    validate_frame(df)
    df = df.reset_index(drop=True)
    df.insert(0, "customer_id", np.arange(len(df)))
    return df, {"sha256": sha, "bytes": len(raw), "rows": int(len(df))}


def validate_frame(df: pd.DataFrame) -> None:
    """Structural checks that must hold for any file used as this case (also used on synthetic test frames)."""
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise CampaignDataError(f"missing columns: {missing}")
    if df[COLUMNS].isna().any().any():
        raise CampaignDataError("missing values present; the protocol has no imputation rule")
    arms = set(df[ASSIGNMENT].unique())
    if arms != set(ARMS):
        raise CampaignDataError(f"arms must be exactly {sorted(ARMS)}, found {sorted(arms)} (the no-e-mail control is required)")
    if not (set(df.visit.unique()) <= {0, 1} and set(df.conversion.unique()) <= {0, 1}):
        raise CampaignDataError("visit and conversion must be 0/1")
    if (df.spend < 0).any():
        raise CampaignDataError("negative spend")
    if ((df.spend > 0) & (df.conversion == 0)).any():
        raise CampaignDataError("spend without a purchase: the outcome columns are inconsistent")


def _smd(t: pd.DataFrame, c: pd.DataFrame) -> pd.Series:
    return (t.mean() - c.mean()) / np.sqrt((t.var() + c.var()) / 2)


def audit(df: pd.DataFrame, facts: dict, proto: dict) -> dict:
    from scipy.stats import chisquare
    n = len(df)
    counts = {a: int((df[ASSIGNMENT] == a).sum()) for a in ARMS}
    chi = chisquare(list(counts.values()))
    X = pd.get_dummies(df[PRE], columns=["history_segment", "zip_code", "channel"], dtype=float)
    ctrl = X[df[ASSIGNMENT] == CONTROL]
    bal = []
    for arm in TREATMENTS:
        s = _smd(X[df[ASSIGNMENT] == arm], ctrl).abs()
        bal.append({"arm": arm, "max_abs_smd": round(float(s.max()), 4), "feature_at_max": str(s.idxmax()),
                    "features_checked": int(len(s)), "all_below_0.1": bool((s < 0.1).all())})
    by_arm = {}
    for a in ARMS:
        g = df[df[ASSIGNMENT] == a]
        by_arm[a] = {"n_customers": int(len(g)), "buyers": int(g.conversion.sum()), "purchase_rate": float(g.conversion.mean()),
                     "visitors": int(g.visit.sum()), "spend_total": round(float(g.spend.sum()), 2), "spend_per_customer": float(g.spend.mean())}
    seg_edges = df.groupby("history_segment").history.agg(["min", "max", "count"]).round(2)
    return {
        "case_id": proto["case_id"], "source": proto["source"], "file": facts,
        "rows": n, "columns": list(df.columns.drop("customer_id")),
        "customer_unit": {"statement": proto["unit"], "has_customer_id_column": False, "distinct_customers_assumed": n},
        "missing_values": {c: int(df[c].isna().sum()) for c in COLUMNS},
        "duplicates": {"fully_identical_rows_beyond_first": int(df[COLUMNS].duplicated().sum()),
                       "identical_on_pre_email_fields_beyond_first": int(df[PRE].duplicated().sum()),
                       "handling": proto["duplicates"]},
        "arms": {"counts": counts, "shares": {a: round(c / n, 5) for a, c in counts.items()},
                 "chi_square_vs_equal_thirds": {"statistic": round(float(chi.statistic), 4), "p_value": round(float(chi.pvalue), 4)}},
        "balance_vs_control": bal,
        "outcomes_by_arm": by_arm,
        "outcome_integrity": {"conversion_without_visit": int(((df.conversion == 1) & (df.visit == 0)).sum()),
                              "spend_without_conversion": int(((df.spend > 0) & (df.conversion == 0)).sum()),
                              "conversion_without_spend": int(((df.conversion == 1) & (df.spend <= 0)).sum()),
                              "overall_purchase_rate": float(df.conversion.mean()), "total_buyers": int(df.conversion.sum())},
        "ranges": {"recency_months": [int(df.recency.min()), int(df.recency.max())], "history_usd": [float(df.history.min()), float(df.history.max())],
                   "zip_code_levels": sorted(df.zip_code.unique()), "channel_levels": sorted(df.channel.unique()),
                   "neither_mens_nor_womens": int(((df.mens == 0) & (df.womens == 0)).sum()),
                   "both_mens_and_womens": int(((df.mens == 1) & (df.womens == 1)).sum()),
                   "history_segment_bounds": {k: {"min": float(v["min"]), "max": float(v["max"]), "count": int(v["count"])} for k, v in seg_edges.iterrows()}},
        "feature_timing": {"pre_email": PRE, "assignment": ASSIGNMENT, "post_email_forbidden_as_features": POST,
                           "model_reads": MODEL_FEATURES, "leak_check": sorted(set(MODEL_FEATURES) & set(POST + [ASSIGNMENT]))},
        "rare_outcome_warning": f"{int(df.conversion.sum())} buyers among {n:,} customers ({df.conversion.mean():.2%}); "
                                "any subgroup or top-k cell holds few buyers, so targeting comparisons are imprecise.",
        "rights": {"publication": "public blog post by the data owner (Kevin Hillstrom, MineThatData), 20 March 2008, issued as an open analytics challenge",
                   "data_use": "the page invites anyone to analyse the file", "redistribution": "no licence or redistribution permission stated",
                   "handling": "raw file kept local (data/raw/, gitignored); never committed, zipped or sent; only aggregates leave this repo"},
    }


def dictionary_md(a: dict | None = None) -> str:
    L = ["# Campaign case data dictionary (HILLSTROM_EMAIL_2008)", "",
         "One row is one existing customer who last purchased within twelve months. The file has no customer id; the row index is the customer key.",
         "Definitions are quoted from the source page. Timing decides what the model may read.", "",
         "| Column | Timing | Role | Source definition | Use in this project |", "|---|---|---|---|---|"]
    L += [f"| `{c}` | {t} | {r} | {d} | {u} |" for c, t, r, d, u in DICTIONARY]
    L += ["", "## Timing rules", "",
          "- **Pre-e-mail** columns describe the twelve months before the campaign. Only these can be model features or ranking inputs.",
          "- **`segment`** is the randomized assignment. It selects one of three arms and is never a customer attribute.",
          "- **Post-e-mail** columns (`visit`, `conversion`, `spend`) are outcomes. They are never predictors, never ranking inputs and never used in a preprocessing statistic.",
          "- `mens` and `womens` are past-year product purchases. They do not state a customer's gender.",
          "- The outcome window is two weeks after the e-mail for every arm, including the no-e-mail control."]
    if a:
        L += ["", "## Audit summary (computed from the local file)", "",
              f"- File SHA-256 `{a['file']['sha256']}`, {a['file']['bytes']:,} bytes, {a['rows']:,} rows.",
              "- Arms: " + "; ".join(f"{k} {v:,}" for k, v in a["arms"]["counts"].items())
              + f". Chi-square against equal thirds: p = {a['arms']['chi_square_vs_equal_thirds']['p_value']}.",
              f"- Missing values: {sum(a['missing_values'].values())}.",
              f"- Fully identical rows beyond the first: {a['duplicates']['fully_identical_rows_beyond_first']}. They are kept (no id to deduplicate on).",
              "- Balance of pre-e-mail fields against the control (largest absolute standardised mean difference): "
              + "; ".join(f"{b['arm']} {b['max_abs_smd']} at `{b['feature_at_max']}`" for b in a["balance_vs_control"]) + ". Values below 0.1 count as balanced.",
              f"- Buyers: {a['outcome_integrity']['total_buyers']:,} of {a['rows']:,} customers ({a['outcome_integrity']['overall_purchase_rate']:.2%}).",
              f"- Rights: {a['rights']['redistribution']}; {a['rights']['handling']}."]
    return "\n".join(L) + "\n"


def run(write: bool = True) -> dict:
    proto = load_protocol()
    df, facts = load_raw(proto=proto)
    a = audit(df, facts, proto)
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "data_audit.json").write_text(json.dumps(a, indent=2), encoding="utf-8")
        (DOCS / "campaign_data_dictionary.md").write_text(dictionary_md(a), encoding="utf-8", newline="\n")
    return a


def main(argv=None) -> int:
    try:
        a = run()
    except CampaignDataError as e:
        print(f"CAMPAIGN DATA UNAVAILABLE: {e}", file=sys.stderr)
        return 3
    print(json.dumps({k: a[k] for k in ("rows", "arms", "balance_vs_control", "duplicates", "outcome_integrity")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
