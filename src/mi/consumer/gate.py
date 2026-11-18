"""Commercial gate for the campaign advisor: turns the manager's (illustrative or verified) inputs into a decision.

Pure and deterministic: it reads the validated export and the inputs it is given, and nothing else. It never sends, spends or
approves anything, and it never turns a missing input into a number.

Inputs (``commercial`` dict; every key optional, a missing key means NOT PROVIDED):
  margin              contribution margin on incremental revenue, 0..1          (finance)
  cost_per_email      full cost per e-mail, USD                                (CRM)
  setup               fixed setup cost, USD                                    (default 0 once cost is given)
  contacts            customers e-mailed                                       (default 57,600 = 64,000 less a 10% holdout)
  consent_verified    True only when CRM/legal verified consent for the audience
  holdout_drawn       True only when the 10% randomized holdout was drawn and frozen
  exclude_with_model  True when someone asks to suppress customers using the targeting model

Decisions (first match wins):
  REJECTED_MODEL_EXCLUSION   the plan would use the model to exclude customers, but its advantage over random is not stable
  NO_EMAIL                   cost per e-mail is at or above the break-even cost for the margin entered: do not send
  HOLD_FOR_INPUTS            margin, cost, consent or the holdout is missing: the draft is prepared, nothing may be launched
  PILOT_ONLY                 cost is below break-even but the experiment's spend interval includes a loss: randomized pilot only
  READY_FOR_HUMAN_APPROVAL   every input is present and the scenario pays even at the low end; a named human still approves
"""
from __future__ import annotations

from mi.campaign.contract import MENS
from mi.consumer.adapter import CaseResult
from mi.consumer.viewmodel import what_if

DEFAULT_CONTACTS = 57_600


def normalize(commercial: dict | None) -> dict | None:
    """Validate and canonicalise the inputs. None means 'no inputs provided' (the saved-run default)."""
    if commercial is None:
        return None
    out = {k: commercial.get(k) for k in ("margin", "cost_per_email", "setup", "contacts")}
    for k in ("consent_verified", "holdout_drawn", "exclude_with_model"):
        out[k] = bool(commercial.get(k, False))
    if out["margin"] is not None and not 0 <= float(out["margin"]) <= 1:
        raise ValueError("margin must be between 0 and 1")
    for k in ("cost_per_email", "setup", "contacts"):
        if out[k] is not None and float(out[k]) < 0:
            raise ValueError(f"{k} must be >= 0")
    return out


def _mens_effect(case: CaseResult) -> dict:
    return next(e for e in case.doc["average_effects"] if e["treatment_arm"] == MENS)


def evaluate(case: CaseResult, commercial: dict | None) -> dict:
    """The gate decision for this export and these inputs."""
    c = normalize(commercial) or {"margin": None, "cost_per_email": None, "setup": None, "contacts": None,
                                  "consent_verified": False, "holdout_drawn": False, "exclude_with_model": False}
    eff = _mens_effect(case)["incremental_spend_per_contact"]
    spend, spend_ci = eff["value"], eff["ci95"]
    mvb = case.doc["model_vs_baselines"]
    contacts = int(c["contacts"] if c["contacts"] is not None else DEFAULT_CONTACTS)
    blockers, reasons = [], []
    scenario = None
    break_even = {"point": None, "conservative": None}
    if c["margin"] is not None:
        margin = float(c["margin"])
        break_even = {"point": spend * margin, "conservative": spend_ci[0] * margin}
    if c["margin"] is None:
        blockers.append("contribution margin not provided (UNKNOWN; finance)")
    if c["cost_per_email"] is None:
        blockers.append("full cost per e-mail not provided (UNKNOWN; CRM)")
    if c["margin"] is not None and c["cost_per_email"] is not None:
        scenario = what_if(spend, spend_ci, float(c["margin"]), float(c["cost_per_email"]), contacts, float(c["setup"] or 0.0))
    if not c["consent_verified"]:
        blockers.append("consent not verified for the audience (CRM owner with legal)")
    if not c["holdout_drawn"]:
        blockers.append("10% randomized holdout not drawn and frozen (analyst)")
    blockers.append("no named human approval (marketing manager)")

    exclusion_refused = bool(c["exclude_with_model"]) and mvb["stable_vs_random"] is not True
    if exclusion_refused:
        decision = "REJECTED_MODEL_EXCLUSION"
        reasons.append("The targeting model is ahead of random on the point estimate but not stable (interval includes zero), so it may not be used to exclude customers.")
    elif scenario and scenario["contribution"] <= 0:
        decision = "NO_EMAIL"
        reasons.append(f"At margin {float(c['margin']):.0%} the break-even cost is {break_even['point']:.3f} USD per e-mail; with cost {float(c['cost_per_email']):.3f} USD"
                       f"{' and setup ' + format(float(c['setup']), ',.0f') + ' USD' if c['setup'] else ''} the scenario contribution is {scenario['contribution']:,.0f} USD: do not send.")
    elif [b for b in blockers if not b.startswith("no named human")]:
        decision = "HOLD_FOR_INPUTS"
        reasons.append("The draft is prepared, but nothing may be launched until the inputs below are supplied.")
    elif scenario["verdict"] == "UNCERTAIN_INTERVAL_INCLUDES_ZERO":
        decision = "PILOT_ONLY"
        reasons.append("Cost is below break-even at the point estimate, but the experiment's spend interval includes a loss: send only as the randomized pilot and read out after 14 days.")
    else:
        decision = "READY_FOR_HUMAN_APPROVAL"
        reasons.append("Every input is present and the scenario pays even at the low end of the interval. A named human still approves the exact plan.")
    return {"decision": decision, "reasons": reasons, "blockers": blockers, "inputs": c, "scenario": scenario, "break_even_cost": break_even,
            "contacts": contacts, "model_exclusion_refused": exclusion_refused, "draft_allowed": decision != "NO_EMAIL",
            "launch_ready": False, "kind": "SCENARIO, NOT MEASURED PROFIT" if scenario else "UNKNOWN: inputs not provided"}
