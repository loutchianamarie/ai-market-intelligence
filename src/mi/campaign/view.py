"""Read-only view of the campaign export for the manager app.

The app never computes campaign statistics. It loads reports/campaign_case.latest.json, refuses it unless the SHA-256
matches the checksum file and the contract validates, and turns the stored values into display rows.
The only arithmetic here is the contract's own scenario formula applied to margin and cost typed by a human.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mi.campaign import contract as K
from mi.campaign.contract import CONTROL, TREATMENTS  # noqa: F401  (re-exported for the app)


class ExportRefused(RuntimeError):
    """The export is missing, altered, or does not satisfy the contract. Nothing is shown."""


def load_export(path: Path | None = None, checksum_path: Path | None = None) -> tuple[dict, str]:
    from mi.campaign.export import CHECKSUM, EXPORT           # late import: export pulls in the whole fitting stack
    path, checksum_path = Path(path or EXPORT), Path(checksum_path or CHECKSUM)
    if not path.exists():
        raise ExportRefused(f"{path.name} not found. Run: python -m mi.campaign.export")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if not checksum_path.exists():
        raise ExportRefused("checksum file missing; the export cannot be trusted")
    want = checksum_path.read_text(encoding="utf-8").split()[0]
    if sha != want:
        raise ExportRefused(f"checksum mismatch: file {sha[:12]} vs recorded {want[:12]}")
    doc = json.loads(raw)
    errs = K.validate_case(doc)
    if errs:
        raise ExportRefused(f"{len(errs)} contract violation(s); first: {errs[0]}")
    if doc["record_type"] != "COMPUTED_EXPORT":
        raise ExportRefused("record_type is not COMPUTED_EXPORT (a fixture is never shown as a result)")
    return doc, sha


def _fmt(v, d=1, unit=""):
    return "UNKNOWN" if v is None else f"{v:,.{d}f}{unit}"


def _ci(t, d=1):
    c = t.get("ci95")
    return "n/a" if not c else f"{c[0]:,.{d}f} to {c[1]:,.{d}f}"


def arm_rows(doc: dict) -> list[dict]:
    eff = {e["treatment_arm"]: e for e in doc["average_effects"]}
    out = []
    for m in doc["observed_arm_metrics"]:
        e = eff.get(m["arm"])
        out.append({"arm": m["arm"], "customers": f"{m['n_customers']:,}", "buyers": f"{m['buyers']:,}",
                    "purchase rate": f"{100 * m['purchase_rate']['value']:.2f}%",
                    "additional buyers per 1,000 e-mailed": "reference (control)" if e is None else _fmt(e["additional_buyers_per_1000"]["value"]),
                    "95% interval": "" if e is None else _ci(e["additional_buyers_per_1000"]),
                    "incremental spend per e-mail (USD)": "" if e is None else _fmt(e["incremental_spend_per_contact"]["value"], 2),
                    "label": "OBSERVED"})
    return out


def policy_rows(doc: dict, share: float | None = None) -> list[dict]:
    share = doc["model_vs_baselines"]["primary_contact_share"] if share is None else share
    best = doc["buyer_impact_per_1000"]["arm"]
    out = []
    for x in doc["held_out_policy_metrics"]:
        if x["contact_share"] != share or x["arm_assignment"] not in (best, "MODEL_CHOOSES_ARM"):
            continue
        a = x["additional_buyers_per_1000_contacts"]
        out.append({"policy": x["label"], "primary": "yes" if x["is_primary"] else "",
                    "contacted (test)": f"{x['contacted_n']:,}",
                    "buyers / e-mailed": f"{x['treated_buyers']} / {x['treated_n']:,}",
                    "buyers / not e-mailed": f"{x['control_buyers']} / {x['control_n']:,}",
                    "additional buyers per 1,000": _fmt(a["value"]), "95% interval": _ci(a), "label": "HELD_OUT_ESTIMATE"})
    return out


def threshold_rows(doc: dict) -> list[dict]:
    return [{"e-mail": t["arm"], "assumed margin": f"{t['assumed_margin']['value']:.0%}",
             "break-even cost per e-mail (USD)": _fmt(t["break_even_cost_per_contact"]["value"], 3),
             "on the lower bound (USD)": _fmt(t["break_even_cost_per_contact_conservative"]["value"], 3), "label": "ASSUMPTION"} for t in doc["economic_thresholds"]]


def human_scenario(doc: dict, arm: str, margin: float | None, cost: float | None, setup: float | None, contacts: float | None = None) -> dict:
    """Scenario contribution from numbers a person typed. Any missing input leaves the result UNKNOWN, never zero."""
    e = next(x for x in doc["average_effects"] if x["treatment_arm"] == arm)["incremental_spend_per_contact"]
    base = next(s for s in doc["business_scenarios"] if s["arm"] == arm and s["scenario_id"].endswith("__CENTRAL"))["contacts"]["value"]
    contacts = base if contacts is None else contacts
    point = K.scenario_contribution(contacts, e["value"], margin, cost, setup)
    lo, hi = e["ci95"]
    rng = None if point is None else sorted((K.scenario_contribution(contacts, lo, margin, cost, setup), K.scenario_contribution(contacts, hi, margin, cost, setup)))
    return {"arm": arm, "contacts": contacts, "contribution": point, "range": rng, "label": "SCENARIO (inputs typed by a person; not measured profit)",
            "break_even_cost": None if margin is None else e["value"] * margin}
