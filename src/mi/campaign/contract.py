"""Campaign-case contract v1: typed producer helpers, the synthetic fixture and the validator.

The marketing repo PRODUCES reports/campaign_case.latest.json; the ConsultAI repo CONSUMES a copy read-only.
This file is dependency-light on purpose (stdlib + jsonschema) so the consumer may copy it next to the schema.

  python -m mi.campaign.contract sample            rewrite docs/contracts/campaign_case.sample.json (deterministic)
  python -m mi.campaign.contract validate <path>   schema + cross-field validation of any campaign-case JSON

Rules that every number obeys:
  * a number never travels without a provenance tag (OBSERVED / HELD_OUT_ESTIMATE / ASSUMPTION /
    PUBLISHED_REFERENCE / UNKNOWN); UNKNOWN is always null, never zero;
  * a rate is buyers divided by ITS OWN arm's customers; both e-mails are compared with the SAME no-e-mail control;
  * scenario contribution is arithmetic on assumptions and is never tagged OBSERVED;
  * the SYNTHETIC_FIXTURE carries no empirical value at all (every OBSERVED / HELD_OUT_ESTIMATE value is null).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Iterator, Literal, Optional, Sequence, TypedDict

CONTRACT_VERSION = "1.0"
CASE_ID = "HILLSTROM_EMAIL_2008"
CONTROL, MENS, WOMENS = "No E-Mail", "Mens E-Mail", "Womens E-Mail"
ARMS = (CONTROL, MENS, WOMENS)
TREATMENTS = (MENS, WOMENS)
ARM_KEY = {MENS: "MENS", WOMENS: "WOMENS"}
OUTCOME = "conversion_within_two_weeks"
SHARES = (0.25, 0.50)                    # fixed contact caps (besides "all eligible" = 1.0); frozen before fitting
SMALL_CELL_BUYERS = 10                   # fewer buyers than this in a treated or control cell -> small_cell_warning
FORMULA = "contribution = contacts * (incremental_spend_per_contact * assumed_margin - cost_per_contact) - fixed_setup_cost"
CI_BOOT = "customer-level bootstrap percentile"
CI_WALD = "normal approximation (unpooled Wald)"

Tag = Literal["OBSERVED", "HELD_OUT_ESTIMATE", "ASSUMPTION", "PUBLISHED_REFERENCE", "UNKNOWN"]
TAGS: tuple[str, ...] = ("OBSERVED", "HELD_OUT_ESTIMATE", "ASSUMPTION", "PUBLISHED_REFERENCE", "UNKNOWN")
Number = Optional[float]
CI = Optional[Sequence[float]]

_REPO = Path(__file__).resolve().parents[3]
SCHEMA_PATH = _REPO / "docs" / "contracts" / "campaign_case.v1.schema.json"
SAMPLE_PATH = _REPO / "docs" / "contracts" / "campaign_case.sample.json"
EXPORT_RELPATH = "reports/campaign_case.latest.json"

# Source ledger (IDs are part of the contract; the consumer cites these, never free text).
SOURCES: list[dict] = [
    {"source_id": "SRC_HILLSTROM_2008_DATA", "kind": "DATASET",
     "title": "Kevin Hillstrom, MineThatData E-Mail Analytics and Data Mining Challenge (blog post, 20 March 2008)",
     "url": "https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html", "accessed": "2026-11-17",
     "note": "64,000 customers who last purchased within twelve months; thirds randomly assigned to Mens e-mail, Womens e-mail "
             "or no e-mail; results tracked for two weeks. No licence or terms stated on the page: raw file kept local."},
    {"source_id": "SRC_RADCLIFFE_2008", "kind": "PUBLICATION",
     "title": "N. J. Radcliffe, Hillstrom's MineThatData Email Analytics Challenge: An Approach Using Uplift Modelling "
              "(Stochastic Solutions Limited, 2008)",
     "url": "https://stochasticsolutions.com/pdf/HillstromChallenge.pdf", "accessed": "2026-11-17",
     "note": "Winning analysis. Its figures are PUBLISHED_REFERENCE values, never this project's model output."},
    {"source_id": "SRC_SKLIFT_DOCS", "kind": "DOCUMENTATION",
     "title": "scikit-uplift documentation: quick start, uplift_at_k (strategy='overall'), qini_auc_score",
     "url": "https://www.uplift-modeling.com/en/latest/quick_start.html", "accessed": "2026-11-17",
     "note": "Metric definitions only (uplift at k, Qini). The library is not a dependency; metrics are implemented locally."},
    {"source_id": "SRC_LOCAL_PROTOCOL_V2", "kind": "LOCAL_ARTIFACT",
     "title": "Pre-registered conversion-uplift protocol v2 (split, features, policies, primary metric, decision rule)",
     "url": "data/eval/hillstrom_protocol_v2.json", "accessed": None,
     "note": "Committed before the conversion model was fitted on the new split."},
    {"source_id": "SRC_LOCAL_RUN", "kind": "LOCAL_ARTIFACT",
     "title": "Campaign run manifest (data hash, code commit, seed, feature list, split hashes, model version)",
     "url": "reports/campaign/run_manifest.json", "accessed": None, "note": "Written by python -m mi.campaign.export."},
]

# Published full-sample reference figures, read from Table 2 (page 3) of SRC_RADCLIFFE_2008 on 2026-11-17.
PUBLISHED_REFERENCES: list[dict] = [
    {"id": "REF_PURCHASE_RATE_MENS", "label": "Published purchase rate, Mens e-mail (full sample)", "value": 1.25, "unit": "percent"},
    {"id": "REF_PURCHASE_RATE_WOMENS", "label": "Published purchase rate, Womens e-mail (full sample)", "value": 0.88, "unit": "percent"},
    {"id": "REF_PURCHASE_RATE_CONTROL", "label": "Published purchase rate, no e-mail control (full sample)", "value": 0.57, "unit": "percent"},
    {"id": "REF_PURCHASE_UPLIFT_MENS", "label": "Published purchase-rate uplift, Mens e-mail vs control", "value": 0.68, "unit": "percentage points"},
    {"id": "REF_PURCHASE_UPLIFT_WOMENS", "label": "Published purchase-rate uplift, Womens e-mail vs control", "value": 0.31, "unit": "percentage points"},
    {"id": "REF_SPEND_UPLIFT_MENS", "label": "Published spend uplift per head, Mens e-mail vs control", "value": 0.77, "unit": "USD per customer"},
    {"id": "REF_SPEND_UPLIFT_WOMENS", "label": "Published spend uplift per head, Womens e-mail vs control", "value": 0.42, "unit": "USD per customer"},
]

# Economic assumption sets: illustrative, chosen by the project team, NOT from the dataset or any client.
ASSUMED_ELIGIBLE_BASE = 64000            # assumes the mailable base equals the 64,000 customers in the experiment
ASSUMED_HOLDOUT_SHARE = 0.10             # randomized no-e-mail holdout kept out of a broad send
ASSUMPTION_SETS: dict[str, Optional[dict]] = {
    "UNKNOWN_INPUTS": None,              # the honest current state: margin and cost have not been supplied
    "CONSERVATIVE": {"margin": 0.20, "cost_per_contact": 0.10, "setup": 2000.0},
    "CENTRAL": {"margin": 0.35, "cost_per_contact": 0.03, "setup": 1000.0},
    "FAVOURABLE": {"margin": 0.50, "cost_per_contact": 0.005, "setup": 500.0},
}
THRESHOLD_MARGINS = (0.20, 0.35, 0.50)


class TaggedValue(TypedDict, total=False):
    value: Number
    tag: str
    unit: str
    ci95: Optional[list]
    ci_method: Optional[str]
    note: str


class ContractError(ValueError):
    pass


# ---------------------------------------------------------------- typed row helpers (shared by fixture and export)
def tv(value: Number, tag: Tag, unit: str, *, ci95: CI = None, ci_method: Optional[str] = None,
       with_ci: bool = False, note: Optional[str] = None) -> TaggedValue:
    """A tagged number. UNKNOWN can never carry a value (so an unknown margin cannot be rendered as 0)."""
    if tag not in TAGS:
        raise ContractError(f"unknown provenance tag {tag!r}")
    if tag == "UNKNOWN" and value is not None:
        raise ContractError("UNKNOWN must have value None, never a number")
    if value is not None and (isinstance(value, bool) or not math.isfinite(float(value))):
        raise ContractError(f"non-finite value {value!r}")
    out: TaggedValue = {"value": None if value is None else float(value), "tag": tag, "unit": unit}
    if with_ci or ci95 is not None:
        out["ci95"] = None if (ci95 is None or tag == "UNKNOWN") else [float(ci95[0]), float(ci95[1])]
        out["ci_method"] = ci_method
    if note:
        out["note"] = note
    return out


def _rate(b: Optional[int], n: Optional[int]) -> Number:
    return None if (b is None or not n) else b / n


def arm_metric(arm: str, n: Optional[int] = None, buyers: Optional[int] = None, spend_mean: Number = None) -> dict:
    """One randomized arm, full sample. purchase_rate is ALWAYS buyers / this arm's own customers."""
    return {"case_id": CASE_ID, "arm": arm, "role": "control" if arm == CONTROL else "treatment", "split": "full_sample",
            "n_customers": n, "buyers": buyers,
            "purchase_rate": tv(_rate(buyers, n), "OBSERVED", "share of this arm's customers who purchased within two weeks"),
            "spend_per_customer": tv(spend_mean, "OBSERVED", "USD per customer in this arm, two weeks")}


def average_effect(arm: str, tn: Optional[int] = None, tb: Optional[int] = None, cn: Optional[int] = None,
                   cb: Optional[int] = None, *, rate_ci: CI = None, spend_diff: Number = None, spend_ci: CI = None) -> dict:
    """Randomized average effect of one e-mail versus the shared no-e-mail control (full sample)."""
    rt, rc = _rate(tb, tn), _rate(cb, cn)
    d = None if (rt is None or rc is None) else rt - rc
    per1000 = None if d is None else 1000 * d
    ci1000 = None if rate_ci is None else [1000 * rate_ci[0], 1000 * rate_ci[1]]
    rel = None if (d is None or not rc) else d / rc
    return {"case_id": CASE_ID, "treatment_arm": arm, "control_arm": CONTROL, "split": "full_sample",
            "treated_n": tn, "treated_buyers": tb, "control_n": cn, "control_buyers": cb,
            "rate_difference": tv(d, "OBSERVED", "difference in purchase rate (treated minus control)", ci95=rate_ci, ci_method=CI_WALD, with_ci=True),
            "additional_buyers_per_1000": tv(per1000, "OBSERVED", "additional purchasing customers per 1,000 customers e-mailed, vs no e-mail, two weeks",
                                             ci95=ci1000, ci_method=CI_WALD, with_ci=True),
            "relative_lift": tv(rel, "OBSERVED" if (rel is not None or d is None) else "UNKNOWN", "rate difference divided by the control purchase rate"),
            "incremental_spend_per_contact": tv(spend_diff, "OBSERVED", "USD per customer e-mailed (treated mean spend minus control mean spend), two weeks",
                                                ci95=spend_ci, ci_method=CI_WALD, with_ci=True)}


def policy_catalog(shares: Sequence[float] = SHARES) -> list[dict]:
    """Every policy evaluated on the held-out test split. IDs are stable; consumers read fields, not ID text."""
    P = [{"policy_id": "NO_EMAIL_0", "policy_family": "NO_EMAIL", "arm_assignment": "NONE", "contact_share": 0.0,
          "label": "Send nothing (reference: the randomized no-e-mail control)"}]
    for arm in TREATMENTS:
        P.append({"policy_id": f"SEND_ALL_{ARM_KEY[arm]}_100", "policy_family": "SEND_ALL", "arm_assignment": arm,
                  "contact_share": 1.0, "label": f"{arm} to every eligible customer"})
    for s in shares:
        pct = int(round(100 * s))
        for arm in TREATMENTS:
            k = ARM_KEY[arm]
            P += [{"policy_id": f"RANDOM_{k}_{pct}", "policy_family": "RANDOM", "arm_assignment": arm, "contact_share": s,
                   "label": f"{arm} to a random {pct}% (expected value: the average effect over the whole held-out arms)"},
                  {"policy_id": f"RULE_RECENCY_{k}_{pct}", "policy_family": "RULE", "arm_assignment": arm, "contact_share": s,
                   "label": f"{arm} to the {pct}% who purchased most recently"},
                  {"policy_id": f"RULE_HISTORY_{k}_{pct}", "policy_family": "RULE", "arm_assignment": arm, "contact_share": s,
                   "label": f"{arm} to the {pct}% with the highest past-year spend"},
                  {"policy_id": f"MODEL_{k}_{pct}", "policy_family": "MODEL", "arm_assignment": arm, "contact_share": s,
                   "label": f"{arm} to the {pct}% with the highest model-predicted uplift for that e-mail"}]
        P.append({"policy_id": f"MODEL_BESTARM_{pct}", "policy_family": "MODEL", "arm_assignment": "MODEL_CHOOSES_ARM", "contact_share": s,
                  "label": f"Model picks the e-mail per customer; contact the {pct}% with the highest predicted uplift"})
    P.append({"policy_id": "MODEL_BESTARM_100", "policy_family": "MODEL", "arm_assignment": "MODEL_CHOOSES_ARM", "contact_share": 1.0,
              "label": "Model picks the e-mail per customer; contact every eligible customer"})
    return P


def policy_metric(spec: dict, *, eligible_n: Optional[int] = None, contacted_n: Optional[int] = None,
                  tn: Optional[int] = None, tb: Optional[int] = None, cn: Optional[int] = None, cb: Optional[int] = None,
                  per_1000_contacts: Number = None, ci_contacts: CI = None, per_1000_eligible: Number = None, ci_eligible: CI = None,
                  spend_per_contact: Number = None, spend_ci: CI = None, comparisons: Optional[list] = None,
                  is_primary: bool = False, fixture: bool = False) -> dict:
    """One policy on the held-out test split. For NO_EMAIL the per-contact metric is not applicable (nobody is contacted)."""
    none = spec["policy_family"] == "NO_EMAIL"
    unit_c = "additional purchasing customers per 1,000 customers contacted, vs no e-mail, two weeks"
    unit_e = "additional purchasing customers per 1,000 eligible customers (contacted or not), vs no e-mail, two weeks"
    if none:
        a = tv(None, "UNKNOWN", unit_c, with_ci=True, note="NOT APPLICABLE: this policy contacts nobody")
        e = tv(None if fixture else 0.0, "HELD_OUT_ESTIMATE", unit_e, ci95=None if fixture else [0.0, 0.0], ci_method="by definition", with_ci=True,
               note="reference policy: zero additional buyers by definition")
        sp = tv(None, "UNKNOWN", "USD per customer contacted, two weeks", with_ci=True, note="NOT APPLICABLE: this policy contacts nobody")
    else:
        a = tv(per_1000_contacts, "HELD_OUT_ESTIMATE", unit_c, ci95=ci_contacts, ci_method=CI_BOOT, with_ci=True)
        e = tv(per_1000_eligible, "HELD_OUT_ESTIMATE", unit_e, ci95=ci_eligible, ci_method=CI_BOOT, with_ci=True)
        sp = tv(spend_per_contact, "HELD_OUT_ESTIMATE", "USD per customer contacted (treated minus control inside the selected set), two weeks",
                ci95=spend_ci, ci_method=CI_BOOT, with_ci=True)
    cells = [x for x in (tb, cb) if x is not None]
    return {"case_id": CASE_ID, "policy_id": spec["policy_id"], "policy_family": spec["policy_family"], "label": spec["label"],
            "arm_assignment": spec["arm_assignment"], "control_arm": CONTROL, "split": "test", "contact_share": spec["contact_share"],
            "eligible_n": eligible_n, "contacted_n": (None if fixture else 0) if none else contacted_n,
            "treated_n": tn, "treated_buyers": tb, "control_n": cn, "control_buyers": cb,
            "additional_buyers_per_1000_contacts": a, "additional_buyers_per_1000_eligible": e, "incremental_spend_per_contact": sp,
            "comparisons": comparisons or [], "small_cell_warning": (min(cells) < SMALL_CELL_BUYERS) if len(cells) == 2 and not none else (None if not cells else False),
            "is_primary": bool(is_primary)}


def comparison(against_policy_id: str, diff: Number = None, ci: CI = None) -> dict:
    return {"against_policy_id": against_policy_id,
            "difference_per_1000_contacts": tv(diff, "HELD_OUT_ESTIMATE", "this policy minus the other, additional buyers per 1,000 contacts",
                                               ci95=ci, ci_method=CI_BOOT + " (paired: same resamples)", with_ci=True),
            "ci_excludes_zero": None if ci is None else bool(ci[0] > 0 or ci[1] < 0)}


def scenario_contribution(contacts: Number, spend: Number, margin: Number, cost: Number, setup: Number) -> Number:
    """The contract formula. Any missing input makes the contribution unknown (None), never zero."""
    if any(x is None for x in (contacts, spend, margin, cost, setup)):
        return None
    return contacts * (spend * margin - cost) - setup


def scenario(policy_id: str, arm: str, set_name: str, contacts: float, *, spend: Number = None, spend_ci: CI = None,
             spend_tag: Tag = "OBSERVED") -> dict:
    """Scenario economics for one policy under one assumption set. Never a measured profit."""
    a = ASSUMPTION_SETS[set_name]
    m, c, s = (None, None, None) if a is None else (a["margin"], a["cost_per_contact"], a["setup"])
    tag: Tag = "UNKNOWN" if a is None else "ASSUMPTION"
    contrib = scenario_contribution(contacts, spend, m, c, s)
    ci = None
    if spend_ci is not None and a is not None:
        ci = sorted(scenario_contribution(contacts, x, m, c, s) for x in spend_ci)
    return {"case_id": CASE_ID, "scenario_id": f"{policy_id}__{set_name}", "label": f"{set_name.replace('_', ' ').title()} assumptions, {arm}",
            "value_kind": "SCENARIO_NOT_MEASURED_PROFIT", "policy_id": policy_id, "arm": arm,
            "contacts": tv(contacts, "ASSUMPTION", "customers e-mailed",
                           note=f"assumed mailable base {ASSUMED_ELIGIBLE_BASE:,} x contact share, less a {ASSUMED_HOLDOUT_SHARE:.0%} randomized holdout for a broad send"),
            "incremental_spend_per_contact": tv(spend, spend_tag, "USD per customer e-mailed, two weeks", ci95=spend_ci, ci_method=CI_WALD, with_ci=True),
            "assumed_margin": tv(m, tag, "share of incremental revenue kept as contribution"),
            "cost_per_contact": tv(c, tag, "USD per e-mail sent (delivery, offer and handling)"),
            "fixed_setup_cost": tv(s, tag, "USD per campaign"),
            "contribution": tv(contrib, "UNKNOWN" if a is None else "ASSUMPTION", "USD per campaign (scenario arithmetic, not measured profit)",
                               ci95=ci, ci_method="range from the 95% interval of incremental spend; assumptions held fixed", with_ci=True),
            "formula": FORMULA}


def threshold(arm: str, margin: float, *, spend: Number = None, spend_low: Number = None) -> dict:
    """Break-even e-mail cost at an assumed margin: the most a contact may cost before the campaign loses money."""
    return {"case_id": CASE_ID, "threshold_id": f"BREAK_EVEN_COST_{ARM_KEY[arm]}_M{int(round(100 * margin))}", "arm": arm,
            "label": f"Break-even cost per e-mail, {arm}, at an assumed {margin:.0%} margin (before fixed setup)",
            "assumed_margin": tv(margin, "ASSUMPTION", "share of incremental revenue kept as contribution"),
            "break_even_cost_per_contact": tv(None if spend is None else spend * margin, "ASSUMPTION", "USD per e-mail",
                                              note="incremental spend per contact x assumed margin"),
            "break_even_cost_per_contact_conservative": tv(None if spend_low is None else spend_low * margin, "ASSUMPTION", "USD per e-mail",
                                                           note="uses the lower 95% bound of incremental spend per contact")}


def claim(claim_id: str, text: str, value: Any, unit: str, tag: Tag, *, sha: Optional[str] = None, denominator: Optional[str] = None,
          period: Optional[str] = "two weeks after the e-mail", arm: Optional[str] = None, split: str = "full_sample",
          model_version: Optional[str] = None, uncertainty: Optional[str] = None, source_id: str = "SRC_LOCAL_RUN",
          slide_safe: bool = True) -> dict:
    """One ledger line: a displayed figure tied to its hash, denominator, period, arm, split, model and source."""
    return {"claim_id": claim_id, "case_id": CASE_ID, "text": text, "value": None if tag == "UNKNOWN" else value, "unit": unit, "tag": tag,
            "dataset_sha256": sha, "denominator": denominator, "period": period, "arm": arm, "split": split,
            "model_version": model_version, "uncertainty": uncertainty, "source_id": source_id, "slide_safe": bool(slide_safe)}


def published_references() -> list[dict]:
    return [{**r, "tag": "PUBLISHED_REFERENCE", "source_id": "SRC_RADCLIFFE_2008", "locator": "Table 2, page 3",
             "note": "published full-sample figure; not recomputed by, and not an output of, this project's model"} for r in PUBLISHED_REFERENCES]


def assumptions_and_unknowns() -> list[dict]:
    A = [{"id": "A_ELIGIBLE_BASE", "name": "Mailable customer base", "value": ASSUMED_ELIGIBLE_BASE, "tag": "ASSUMPTION", "unit": "customers",
          "needed_from": "CRM owner", "note": "set equal to the 64,000 customers in the experiment; the retailer's current consented base is unknown"},
         {"id": "A_HOLDOUT_SHARE", "name": "Randomized no-e-mail holdout", "value": ASSUMED_HOLDOUT_SHARE, "tag": "ASSUMPTION", "unit": "share of the base",
          "needed_from": "marketing manager", "note": "kept out of any send so the next campaign can be measured"}]
    for name, s in ASSUMPTION_SETS.items():
        if s is None:
            continue
        A += [{"id": f"A_MARGIN_{name}", "name": f"Contribution margin ({name.lower()})", "value": s["margin"], "tag": "ASSUMPTION", "unit": "share of revenue",
               "needed_from": "finance", "note": "illustrative; no margin is in the dataset"},
              {"id": f"A_COST_PER_CONTACT_{name}", "name": f"Cost per e-mail ({name.lower()})", "value": s["cost_per_contact"], "tag": "ASSUMPTION", "unit": "USD per e-mail",
               "needed_from": "CRM owner", "note": "illustrative; delivery, offer and handling cost are not in the dataset"},
              {"id": f"A_SETUP_{name}", "name": f"Fixed campaign setup ({name.lower()})", "value": s["setup"], "tag": "ASSUMPTION", "unit": "USD per campaign",
               "needed_from": "marketing manager", "note": "illustrative; creative and setup cost are not in the dataset"}]
    U = [("U_MARGIN", "Actual contribution margin on incremental sales", "share of revenue", "finance"),
         ("U_COST_PER_CONTACT", "Actual cost per e-mail including any offer or discount", "USD per e-mail", "CRM owner"),
         ("U_OFFER_TERMS", "Price or discount terms shown in the 2008 e-mails", "-", "not recoverable from the source"),
         ("U_CREATIVE", "The creative, subject line and products shown in the 2008 e-mails", "-", "not recoverable from the source"),
         ("U_CONSENT_RATE", "Share of the current base with valid e-mail consent", "share of the base", "CRM owner / legal"),
         ("U_RETAILER_IDENTITY", "Retailer name, market and campaign date", "-", "not published by the source"),
         ("U_EFFECT_BEYOND_TWO_WEEKS", "Effect after the two-week window (pull-forward, unsubscribes, fatigue)", "-", "new measurement"),
         ("U_EFFECT_TODAY", "Whether a 2008 effect holds for a current customer base", "-", "a new randomized pilot")]
    return A + [{"id": i, "name": n, "value": None, "tag": "UNKNOWN", "unit": u, "needed_from": w, "note": "not in the dataset; shown as unknown, never as zero"}
                for i, n, u, w in U]


def provenance(sha256: Optional[str], n_bytes: Optional[int], rows: Optional[int]) -> dict:
    return {"source_id": "SRC_HILLSTROM_2008_DATA", "source_url": SOURCES[0]["url"],
            "file_url": "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv",
            "sha256": sha256, "bytes": n_bytes, "rows": rows, "period": "two_weeks_after_email",
            "period_note": "outcomes tracked for two weeks after the e-mail; the campaign date is not published (data released 20 March 2008)",
            "terms": "no licence or terms of use stated on the source page (checked 2026-11-14 and 2026-11-17)",
            "redistribution": "RAW_FILE_LOCAL_ONLY_NOT_REDISTRIBUTED"}


def outcome_block() -> dict:
    return {"name": OUTCOME, "horizon_days": 14,
            "definition": "A unique existing customer who purchased merchandise in the two weeks after the e-mail (source column 'conversion' = 1). "
                          "A customer who would have purchased anyway is not an additional buyer; treated-minus-control differences estimate "
                          "additional repeat buyers for a group, never an individual's effect, and never new-customer acquisition."}


def arms_block() -> list[dict]:
    return [{"name": a, "role": "control" if a == CONTROL else "treatment"} for a in ARMS]


# ---------------------------------------------------------------- the synthetic fixture (no empirical value anywhere)
def build_fixture() -> dict:
    """Deterministic SYNTHETIC_FIXTURE: the exact v1 shape with every empirical value null. Not evidence for anything."""
    fx = "SYNTHETIC FIXTURE: shape only, no analysis has been run for this file."
    pol = [policy_metric(p, fixture=True, comparisons=[comparison(f"RANDOM_{ARM_KEY[p['arm_assignment']]}_{int(round(100 * p['contact_share']))}"),
                                                       comparison(f"RULE_HISTORY_{ARM_KEY[p['arm_assignment']]}_{int(round(100 * p['contact_share']))}")]
                         if (p["policy_family"] == "MODEL" and p["arm_assignment"] in ARM_KEY and p["contact_share"] < 1) else None)
           for p in policy_catalog()]
    scen = [scenario(f"SEND_ALL_{ARM_KEY[arm]}_100", arm, name, ASSUMED_ELIGIBLE_BASE * (1 - ASSUMED_HOLDOUT_SHARE))
            for arm in TREATMENTS for name in ASSUMPTION_SETS]
    claims = [claim("CLM_DATA_ROWS", "Customers in the experiment file", None, "customers", "OBSERVED", denominator=None, arm=None, period=None, slide_safe=False),
              claim("CLM_RATE_CONTROL", "Purchase rate without an e-mail", None, "percent", "OBSERVED", arm=CONTROL, slide_safe=False),
              claim("CLM_BUYERS_PER_1000_MENS", "Additional purchasing customers per 1,000 Mens e-mails vs no e-mail", None, "per 1,000 e-mailed", "OBSERVED", arm=MENS, slide_safe=False),
              claim("CLM_MODEL_VS_RANDOM", "Model targeting minus random targeting at the primary contact cap", None, "additional buyers per 1,000 contacts", "HELD_OUT_ESTIMATE",
                    split="test", slide_safe=False),
              claim("CLM_MARGIN", "Contribution margin on incremental sales", None, "share of revenue", "UNKNOWN", period=None, split="not_applicable",
                    source_id="SRC_HILLSTROM_2008_DATA", slide_safe=False)]
    return {
        "contract_version": CONTRACT_VERSION, "record_type": "SYNTHETIC_FIXTURE", "case_id": CASE_ID,
        "generated_at": "2026-11-17T00:00:00Z",
        "producer": {"repo": "ai-market-intelligence", "code_commit": None, "command": "python -m mi.campaign.contract sample"},
        "dataset_provenance": provenance(None, None, None),
        "unit": "unique_existing_customer", "outcome": outcome_block(), "arms": arms_block(),
        "observed_arm_metrics": [arm_metric(a) for a in ARMS],
        "average_effects": [average_effect(a) for a in TREATMENTS],
        "model": {"model_version": None, "status": "NOT_RUN",
                  "model_type": "regularized logistic S-learner (one model, three arms, treatment x feature interactions)",
                  "outcome": OUTCOME,
                  "features_pre_treatment": ["recency", "history", "mens", "womens", "newbie", "zip_code", "channel"],
                  "forbidden_post_treatment": ["visit", "conversion", "spend"],
                  "split": {"method": "seeded customer-level train / validation / test, stratified by arm", "seed": None,
                            "n_train": None, "n_validation": None, "n_test": None},
                  "protocol_path": "data/eval/hillstrom_protocol_v2.json", "model_card_path": "reports/campaign/model_card.md",
                  "secondary_metrics": [{"name": "qini_coefficient", "arm": MENS, "score": "model predicted uplift",
                                         "metric": tv(None, "HELD_OUT_ESTIMATE", "normalised area between the Qini curve and the random line", with_ci=True)}],
                  "repeated_evaluation_caveat": fx},
        "held_out_policy_metrics": pol,
        "model_vs_baselines": {"primary_contact_share": 0.25, "model_policy_id": None, "random_policy_id": None, "rule_policy_id": None,
                               "model_minus_random_per_1000_contacts": tv(None, "HELD_OUT_ESTIMATE", "additional buyers per 1,000 contacts", with_ci=True),
                               "model_minus_rule_per_1000_contacts": tv(None, "HELD_OUT_ESTIMATE", "additional buyers per 1,000 contacts", with_ci=True),
                               "point_estimate_beats_random": None, "point_estimate_beats_rule": None, "stable_vs_random": None, "stable_vs_rule": None,
                               "verdict": "NOT_RUN", "verdict_text": fx},
        "buyer_impact_per_1000": {"value": None, "tag": "OBSERVED", "unit": "additional purchasing customers per 1,000 customers e-mailed, vs no e-mail, two weeks",
                                  "policy_id": None, "arm": None, "control_arm": CONTROL, "split": "full_sample",
                                  "treated_n": None, "treated_buyers": None, "control_n": None, "control_buyers": None, "note": fx},
        "buyer_impact_interval_per_1000": {"low": None, "high": None, "level": 0.95, "method": CI_WALD},
        "business_scenarios": scen,
        "economic_thresholds": [threshold(arm, m) for arm in TREATMENTS for m in THRESHOLD_MARGINS],
        "recommendation": {"status": "PENDING_ANALYSIS", "decision": fx, "recommended_policy_id": None, "recommended_arm": None, "contact_share": None,
                           "conditions": [], "rationale": [], "would_reverse_if": [], "alternative_if_model_inconclusive": fx, "no_email_option": fx,
                           "holdout_plan": {"randomized": True, "holdout_share": ASSUMED_HOLDOUT_SHARE, "customers_per_arm_needed": None,
                                            "primary_metric": "unique purchasing customers within two weeks, treated minus holdout", "review_after_days": 14},
                           "human_decision_required": True},
        "marketing": {"research_question": fx, "audience": fx, "segmentation": fx, "targeting": fx, "positioning": fx,
                      "four_ps": [{"p": p, "decision": fx, "alternatives": [], "tag": t, "note": fx}
                                  for p, t in (("Product", "OBSERVED"), ("Price", "UNKNOWN"), ("Place", "OBSERVED"), ("Promotion", "ASSUMPTION"))],
                      "journey_barrier_hypotheses": [fx],
                      "message_drafts": [{"draft_id": "DRAFT_MENS_A", "arm": MENS, "subject": fx, "body": fx, "status": "DRAFT_HYPOTHESIS_NOT_SENT"},
                                         {"draft_id": "DRAFT_WOMENS_A", "arm": WOMENS, "subject": fx, "body": fx, "status": "DRAFT_HYPOTHESIS_NOT_SENT"}],
                      "action_plan": [{"step": 1, "owner_role": "marketing manager", "action": fx, "status": "PENDING_HUMAN"}],
                      "success_metric": fx},
        "assumptions_and_unknowns": assumptions_and_unknowns(),
        "published_references": published_references(),
        "claims": claims,
        "sources": SOURCES,
        "evidence_ids": [s["source_id"] for s in SOURCES],
        "model_version": None, "run_id": None,
        "approval_required": True, "approval_status": "DRAFT_REQUIRES_HUMAN",
        "warnings": ["SYNTHETIC_FIXTURE: every empirical value is null. Do not present this file as a result.",
                     "No e-mail is ever sent, scheduled or approved by this system; a named human decides."],
    }


# ---------------------------------------------------------------- validation
def load_schema(path: Path = SCHEMA_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _walk(node: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def cross_field_errors(doc: dict, expected_case_id: str = CASE_ID) -> list[str]:
    """Rules JSON Schema cannot express. Assumes the document already passed the schema."""
    E: list[str] = []
    fixture = doc["record_type"] == "SYNTHETIC_FIXTURE"
    if doc["case_id"] != expected_case_id:
        E.append(f"$.case_id: {doc['case_id']!r} is not the expected case {expected_case_id!r}")
    for path, node in _walk(doc):
        if not isinstance(node, dict):
            continue
        if "case_id" in node and node["case_id"] != doc["case_id"]:
            E.append(f"{path}.case_id: {node['case_id']!r} differs from the document case_id")
        if "value" in node and "tag" in node:
            v, t, ci = node["value"], node["tag"], node.get("ci95")
            if t == "UNKNOWN" and v is not None:
                E.append(f"{path}: UNKNOWN must be null, got {v!r}")
            if fixture and t in ("OBSERVED", "HELD_OUT_ESTIMATE") and v is not None:
                E.append(f"{path}: a SYNTHETIC_FIXTURE must not carry an empirical value ({t} = {v!r})")
            if not fixture and v is None and t != "UNKNOWN":
                E.append(f"{path}: null value must be tagged UNKNOWN in a COMPUTED_EXPORT (tag is {t})")
            if ci is not None:
                if ci[0] > ci[1]:
                    E.append(f"{path}.ci95: lower bound above upper bound")
                elif isinstance(v, (int, float)) and not (ci[0] - 1e-9 <= v <= ci[1] + 1e-9):
                    E.append(f"{path}.ci95: interval {ci} does not contain the value {v}")

    def le(path: str, small: Optional[int], big: Optional[int], what: str) -> None:
        if small is not None and big is not None and small > big:
            E.append(f"{path}: {what} ({small} > {big})")

    def need(path: str, **vals: Any) -> None:
        if not fixture:
            for k, v in vals.items():
                if v is None:
                    E.append(f"{path}.{k}: required (non-null) in a COMPUTED_EXPORT")

    # --- arms: own denominators, three arms adding up to the file
    arm_rows = {m["arm"]: m for m in doc["observed_arm_metrics"]}
    for i, m in enumerate(doc["observed_arm_metrics"]):
        p = f"$.observed_arm_metrics[{i}]"
        need(p, n_customers=m["n_customers"], buyers=m["buyers"])
        le(p, m["buyers"], m["n_customers"], "buyers above the arm's customers")
        r = m["purchase_rate"]["value"]
        if r is not None and m["n_customers"]:
            if not _close(r, m["buyers"] / m["n_customers"], 1e-9):
                E.append(f"{p}.purchase_rate: {r} is not buyers / this arm's customers ({m['buyers']}/{m['n_customers']})")
    ns = [m["n_customers"] for m in doc["observed_arm_metrics"]]
    rows = doc["dataset_provenance"]["rows"]
    if rows is not None and all(n is not None for n in ns) and sum(ns) != rows:
        E.append(f"$.observed_arm_metrics: arm sizes sum to {sum(ns)}, not the {rows} rows of the dataset")
    need("$.dataset_provenance", sha256=doc["dataset_provenance"]["sha256"], rows=rows, bytes=doc["dataset_provenance"]["bytes"])

    # --- average effects: the same no-e-mail control for both e-mails
    ctrl = arm_rows.get(CONTROL, {})
    for i, e in enumerate(doc["average_effects"]):
        p = f"$.average_effects[{i}]"
        le(p, e["treated_buyers"], e["treated_n"], "treated buyers above treated customers")
        le(p, e["control_buyers"], e["control_n"], "control buyers above control customers")
        t = arm_rows.get(e["treatment_arm"], {})
        if (e["treated_n"], e["treated_buyers"]) != (t.get("n_customers"), t.get("buyers")):
            E.append(f"{p}: treated counts differ from the observed row of {e['treatment_arm']}")
        if (e["control_n"], e["control_buyers"]) != (ctrl.get("n_customers"), ctrl.get("buyers")):
            E.append(f"{p}: control counts are not the shared {CONTROL} arm")
        v = e["additional_buyers_per_1000"]["value"]
        if v is not None and e["treated_n"] and e["control_n"]:
            want = 1000 * (e["treated_buyers"] / e["treated_n"] - e["control_buyers"] / e["control_n"])
            if not _close(v, want):
                E.append(f"{p}.additional_buyers_per_1000: {v} is not 1000 x (treated rate - control rate) = {want:.6f}")

    # --- held-out policies: counts inside the selected set, contact cap respected
    ids = [x["policy_id"] for x in doc["held_out_policy_metrics"]]
    if len(ids) != len(set(ids)):
        E.append("$.held_out_policy_metrics: duplicate policy_id")
    elig = {x["eligible_n"] for x in doc["held_out_policy_metrics"]}
    if len(elig) > 1:
        E.append(f"$.held_out_policy_metrics: policies do not share one eligible_n ({sorted(map(str, elig))})")
    n_test = doc["model"]["split"]["n_test"]
    for i, x in enumerate(doc["held_out_policy_metrics"]):
        p = f"$.held_out_policy_metrics[{i}] ({x['policy_id']})"
        need(p, eligible_n=x["eligible_n"], contacted_n=x["contacted_n"], treated_n=x["treated_n"], treated_buyers=x["treated_buyers"],
             control_n=x["control_n"], control_buyers=x["control_buyers"])
        le(p, x["treated_buyers"], x["treated_n"], "treated buyers above treated customers")
        le(p, x["control_buyers"], x["control_n"], "control buyers above control customers")
        le(p, x["contacted_n"], x["eligible_n"], "contacted above eligible")
        if x["eligible_n"] is not None and n_test is not None and x["eligible_n"] != n_test:
            E.append(f"{p}: eligible_n {x['eligible_n']} is not the held-out test size {n_test}")
        if x["policy_family"] != "NO_EMAIL" and x["contacted_n"] is not None and x["eligible_n"] is not None:
            cap = int(round(x["contact_share"] * x["eligible_n"]))
            if x["contacted_n"] > cap:
                E.append(f"{p}: contacted_n {x['contacted_n']} exceeds the contact cap {cap} ({x['contact_share']:.0%} of {x['eligible_n']})")
            # RANDOM rows report the expectation (the whole held-out arms), so their counts are not a selected subset
            if x["policy_family"] != "RANDOM" and x["treated_n"] is not None and x["control_n"] is not None and x["treated_n"] + x["control_n"] > x["contacted_n"]:
                E.append(f"{p}: treated_n + control_n exceeds the customers selected")
        v = x["additional_buyers_per_1000_contacts"]["value"]
        if v is not None and x["arm_assignment"] in TREATMENTS and x["treated_n"] and x["control_n"]:
            want = 1000 * (x["treated_buyers"] / x["treated_n"] - x["control_buyers"] / x["control_n"])
            if not _close(v, want):
                E.append(f"{p}.additional_buyers_per_1000_contacts: {v} is not 1000 x (treated rate - control rate) inside the selected set = {want:.6f}")
        for c in x["comparisons"]:
            if c["against_policy_id"] not in ids:
                E.append(f"{p}.comparisons: unknown policy {c['against_policy_id']!r}")

    # --- model versus baselines
    mv = doc["model_vs_baselines"]
    for k in ("model_policy_id", "random_policy_id", "rule_policy_id"):
        if mv[k] is not None and mv[k] not in ids:
            E.append(f"$.model_vs_baselines.{k}: unknown policy {mv[k]!r}")
    for key, flag, beat in (("model_minus_random_per_1000_contacts", "stable_vs_random", "point_estimate_beats_random"),
                            ("model_minus_rule_per_1000_contacts", "stable_vs_rule", "point_estimate_beats_rule")):
        d = mv[key]
        if d["value"] is not None:
            if mv[beat] != (d["value"] > 0):
                E.append(f"$.model_vs_baselines.{beat}: inconsistent with the difference {d['value']}")
            if d.get("ci95") is not None and mv[flag] != (d["ci95"][0] > 0):
                E.append(f"$.model_vs_baselines.{flag}: must be true only when the 95% interval lies above zero")
    want_verdict = ("NOT_RUN" if mv["point_estimate_beats_random"] is None else
                    "MODEL_WIN_STABLE" if (mv["stable_vs_random"] and mv["stable_vs_rule"]) else
                    "MODEL_AHEAD_NOT_STABLE" if (mv["point_estimate_beats_random"] and mv["point_estimate_beats_rule"]) else "NO_MODEL_ADVANTAGE")
    if mv["verdict"] != want_verdict:
        E.append(f"$.model_vs_baselines.verdict: {mv['verdict']} but the differences imply {want_verdict}")
    if fixture and (doc["model"]["status"] != "NOT_RUN" or doc["recommendation"]["status"] != "PENDING_ANALYSIS"):
        E.append("$: a SYNTHETIC_FIXTURE must have model.status NOT_RUN and recommendation.status PENDING_ANALYSIS")
    if not fixture:
        if doc["model"]["status"] != "FITTED_REPEATED_EVALUATION" or doc["recommendation"]["status"] == "PENDING_ANALYSIS":
            E.append("$: a COMPUTED_EXPORT needs a fitted model status and a non-pending recommendation")
        need("$", model_version=doc["model_version"], run_id=doc["run_id"])
        need("$.producer", code_commit=doc["producer"]["code_commit"])
        need("$.model.split", seed=doc["model"]["split"]["seed"], n_train=doc["model"]["split"]["n_train"],
             n_validation=doc["model"]["split"]["n_validation"], n_test=n_test)
        if doc["model_version"] != doc["model"]["model_version"]:
            E.append("$.model_version: differs from $.model.model_version")
    leaked = set(doc["model"]["features_pre_treatment"]) & {"visit", "conversion", "spend", "segment"}
    if leaked:
        E.append(f"$.model.features_pre_treatment: post-treatment or assignment fields used as features: {sorted(leaked)}")

    # --- headline buyer impact
    b, iv = doc["buyer_impact_per_1000"], doc["buyer_impact_interval_per_1000"]
    le("$.buyer_impact_per_1000", b["treated_buyers"], b["treated_n"], "treated buyers above treated customers")
    le("$.buyer_impact_per_1000", b["control_buyers"], b["control_n"], "control buyers above control customers")
    if b["value"] is not None:
        if b["arm"] in TREATMENTS and b["treated_n"] and b["control_n"]:
            want = 1000 * (b["treated_buyers"] / b["treated_n"] - b["control_buyers"] / b["control_n"])
            if not _close(b["value"], want):
                E.append(f"$.buyer_impact_per_1000: {b['value']} is not 1000 x (treated rate - control rate) = {want:.6f}")
        if iv["low"] is None or iv["high"] is None:
            E.append("$.buyer_impact_interval_per_1000: a reported buyer impact needs its interval")
        elif not (iv["low"] - 1e-9 <= b["value"] <= iv["high"] + 1e-9):
            E.append("$.buyer_impact_interval_per_1000: interval does not contain the value")

    # --- scenarios: unknown inputs stay unknown; arithmetic is reproducible
    for i, s in enumerate(doc["business_scenarios"]):
        p = f"$.business_scenarios[{i}] ({s['scenario_id']})"
        ins = [s[k]["value"] for k in ("contacts", "incremental_spend_per_contact", "assumed_margin", "cost_per_contact", "fixed_setup_cost")]
        c = s["contribution"]
        if any(s[k]["tag"] == "UNKNOWN" for k in ("assumed_margin", "cost_per_contact", "fixed_setup_cost")) and (c["value"] is not None or c["tag"] != "UNKNOWN"):
            E.append(f"{p}: contribution must be UNKNOWN (null) when margin, cost or setup is UNKNOWN")
        want = scenario_contribution(*ins)
        if c["value"] is not None and (want is None or not _close(c["value"], want)):
            E.append(f"{p}: contribution {c['value']} does not equal the contract formula ({want})")
        if s["policy_id"] is not None and s["policy_id"] not in ids:
            E.append(f"{p}: unknown policy {s['policy_id']!r}")
    eff = {e["treatment_arm"]: e["incremental_spend_per_contact"] for e in doc["average_effects"]}
    for i, t in enumerate(doc["economic_thresholds"]):
        sp, m, v = eff.get(t["arm"], {}), t["assumed_margin"]["value"], t["break_even_cost_per_contact"]["value"]
        if v is not None and sp.get("value") is not None and m is not None and not _close(v, sp["value"] * m):
            E.append(f"$.economic_thresholds[{i}]: break-even cost {v} is not incremental spend x margin")

    # --- ledger and sources
    src = {s["source_id"] for s in doc["sources"]}
    for sid in doc["evidence_ids"]:
        if sid not in src:
            E.append(f"$.evidence_ids: {sid!r} is not in sources")
    for r in doc["published_references"]:
        if r["source_id"] not in src:
            E.append(f"$.published_references ({r['id']}): unknown source {r['source_id']!r}")
    cids = [c["claim_id"] for c in doc["claims"]]
    if len(cids) != len(set(cids)):
        E.append("$.claims: duplicate claim_id")
    sha = doc["dataset_provenance"]["sha256"]
    for c in doc["claims"]:
        p = f"$.claims ({c['claim_id']})"
        if c["source_id"] not in src:
            E.append(f"{p}: unknown source {c['source_id']!r}")
        if not fixture and c["tag"] in ("OBSERVED", "HELD_OUT_ESTIMATE"):
            if c["dataset_sha256"] != sha:
                E.append(f"{p}: dataset_sha256 does not match the dataset provenance")
            if not c["denominator"]:
                E.append(f"{p}: an {c['tag']} claim needs its denominator")
            if c["tag"] == "HELD_OUT_ESTIMATE" and (c["split"] != "test" or not c["model_version"]):
                E.append(f"{p}: a HELD_OUT_ESTIMATE claim needs split 'test' and a model_version")
    return E


def validate_case(doc: dict, expected_case_id: str = CASE_ID, schema: Optional[dict] = None) -> list[str]:
    """Return every contract violation (empty list = valid). Schema first; cross-field rules only on a schema-valid document."""
    from jsonschema import Draft202012Validator
    v = Draft202012Validator(schema or load_schema())
    errs = [f"$.{'.'.join(str(x) for x in e.absolute_path)}: {e.message[:300]}" for e in sorted(v.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path)))]
    return errs if errs else cross_field_errors(doc, expected_case_id)


def assert_valid(doc: dict, expected_case_id: str = CASE_ID) -> dict:
    errs = validate_case(doc, expected_case_id)
    if errs:
        raise ContractError(f"{len(errs)} contract violation(s):\n  " + "\n  ".join(errs[:40]))
    return doc


def dumps(doc: dict) -> str:
    """Deterministic JSON text (ASCII, 2-space indent, trailing newline) so checksums are reproducible."""
    return json.dumps(doc, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def structure_paths(doc: Any, path: str = "$") -> set[str]:
    """Object key paths with list indices collapsed (scalar list items are not paths): the fixture and the real
    export must expose the same structure, whatever the values and however many rows a list holds."""
    out = {path}
    if isinstance(doc, dict):
        for k, v in doc.items():
            out |= structure_paths(v, f"{path}.{k}")
    elif isinstance(doc, list):
        for v in doc:
            if isinstance(v, (dict, list)):
                out |= structure_paths(v, f"{path}[]")
    return out


def main(argv: Optional[list] = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:]) or ["sample"]
    if args[0] == "sample":
        doc = assert_valid(build_fixture())
        SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE_PATH.write_text(dumps(doc), encoding="utf-8", newline="\n")
        print(f"wrote {SAMPLE_PATH.relative_to(_REPO)} (SYNTHETIC_FIXTURE, contract {CONTRACT_VERSION})")
        return 0
    if args[0] == "validate" and len(args) > 1:
        errs = validate_case(json.loads(Path(args[1]).read_text(encoding="utf-8")))
        print("VALID" if not errs else "INVALID:\n  " + "\n  ".join(errs))
        return 0 if not errs else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
