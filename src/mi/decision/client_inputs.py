"""Client input form -> scenario-engine fields. Never fills missing answers.

The client fills data/client_inputs/client_inputs.json (copy of client_inputs_TEMPLATE.json). Each answer maps to
one documented field in configs/policy.json (the scenario engine). An answer is applied ONLY if it has a value,
a source and a date; it is then labelled CLIENT-CONFIRMED. Blank answers leave the ASSUMED/UNKNOWN value in place.
mi.config.load_config() applies valid answers automatically, so every module sees the same inputs.

Usage: python -m mi.decision.client_inputs check | form   (form -> docs/client_input_form.md)
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "data" / "client_inputs" / "client_inputs_TEMPLATE.json"
ANSWERS = ROOT / "data" / "client_inputs" / "client_inputs.json"
PANEL_ACTIVE_HOUSEHOLDS = 2469

# id, question, unit / allowed values, engine field (config path), validator
SPEC = [
    ("offer_funder", "Who funds the EXACT proposed digital offer (retailer, manufacturer or shared), and who reimburses whom?",
     "text: retailer | manufacturer | shared + reimbursement terms", "scenario.coupon_funding.contract.funder_and_reimbursement", "text"),
    ("retailer_share_of_face_value", "What share of the offer's face value does the RETAILER bear after any reimbursement (incl. any retailer match)?",
     "0..1", "scenario.coupon_funding.retailer_share.value", (0.0, 1.0)),
    ("offer_face_value_usd", "Face value of the proposed offer per redemption.", "USD > 0", "scenario.coupon_face_value.value", (0.01, 50.0)),
    ("redemption_mechanic", "How is the offer redeemed / opted into (clip to card, automatic at checkout, code at checkout)?",
     "clip_to_card | automatic_at_checkout | code_at_checkout", "scenario.offer_mechanics.mechanic",
     ["clip_to_card", "automatic_at_checkout", "code_at_checkout"]),
    ("redemption_share_of_baseline_buyers", "Of contacted households who would buy anyway, what share redeem the offer (from your past digital offers)?",
     "0..1", "scenario.redemption_share_of_buyers.value", (0.0, 1.0)),
    ("active_customer_households", "Active loyalty households in the eligible base (all segments).", "count",
     "scenario.deployment_scale.value (= answer / 2,469 panel households)", (1, 10_000_000)),
    ("eligible_consented_digital_households", "Of those, households with valid consent for digital offers.", "count",
     "scenario.channels.digital_coupon.reach_share.value (= answer / active_customer_households)", (0, 10_000_000)),
    ("contribution_margin_rate", "Contribution margin on the category's retailer receipts (after cost of goods, before marketing).",
     "0..1", "scenario.contribution_margin_rate.value", (0.0, 0.9)),
    ("setup_cost_usd", "One-off setup cost per campaign wave (creative, configuration, QA, legal review).", "USD",
     "scenario.fixed_setup_per_plan.value", (0, 1_000_000)),
    ("contact_cost_digital_usd", "Cost per digital contact (send + platform fee).", "USD per household",
     "scenario.channels.digital_coupon.contact_cost.value", (0.0, 5.0)),
    ("stock_capacity_purchasing_households_4w", "For each category, how many purchasing households among CONTACTED households can stock support per 4 weeks (baseline + extra buyers)?",
     "object {category: count}", "scenario.stock_capacity.value", "dict"),
]


def template() -> dict:
    return {"_instructions": "Fill value + source + date for each answer you can CONFIRM. Leave value null if unknown; it will not be applied.",
            "answers": {i: {"question": q, "unit": u, "engine_field": f, "value": None, "source": None, "date": None} for i, q, u, f, _ in SPEC}}


def _valid(i, v, rule):
    if rule == "text":
        return isinstance(v, str) and v.strip() != ""
    if rule == "dict":
        return isinstance(v, dict) and all(isinstance(x, (int, float)) and x >= 0 for x in v.values())
    if isinstance(rule, list):
        return v in rule
    lo, hi = rule
    return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


def validate(answers: dict) -> tuple[dict, list[str]]:
    ok, problems = {}, []
    a = answers.get("answers", {})
    for i, _q, _u, _f, rule in SPEC:
        x = a.get(i) or {}
        if x.get("value") is None:
            continue
        if not x.get("source") or not x.get("date"):
            problems.append(f"{i}: value given without source and date -> not applied")
            continue
        if not _valid(i, x["value"], rule):
            problems.append(f"{i}: value {x['value']!r} outside the allowed {rule}")
            continue
        ok[i] = x
    if "eligible_consented_digital_households" in ok and "active_customer_households" not in ok:
        problems.append("eligible_consented_digital_households needs active_customer_households to set the reach share -> not applied")
        ok.pop("eligible_consented_digital_households")
    if "eligible_consented_digital_households" in ok and ok["eligible_consented_digital_households"]["value"] > ok["active_customer_households"]["value"]:
        problems.append("consented households exceed active households -> not applied")
        ok.pop("eligible_consented_digital_households")
    return ok, problems


def apply(cfg: dict, answers: dict) -> dict:
    ok, problems = validate(answers)
    if not ok:
        return cfg
    c = copy.deepcopy(cfg)
    s = c["scenario"]
    tag = lambda x: f"CLIENT-CONFIRMED ({x['source']}, {x['date']})"  # noqa: E731
    if "offer_funder" in ok:
        s.setdefault("coupon_funding", {}).setdefault("contract", {})["funder_and_reimbursement"] = ok["offer_funder"]["value"]
        s["coupon_funding"]["contract"]["status"] = tag(ok["offer_funder"])
    if "retailer_share_of_face_value" in ok:
        s.setdefault("coupon_funding", {})["retailer_share"] = {"value": float(ok["retailer_share_of_face_value"]["value"]), "status": tag(ok["retailer_share_of_face_value"])}
    if "offer_face_value_usd" in ok:
        s["coupon_face_value"].update({"value": float(ok["offer_face_value_usd"]["value"]), "status": tag(ok["offer_face_value_usd"])})
    if "redemption_mechanic" in ok:
        s["offer_mechanics"] = {"mechanic": ok["redemption_mechanic"]["value"], "status": tag(ok["redemption_mechanic"])}
    for i, path in (("redemption_share_of_baseline_buyers", ("redemption_share_of_buyers",)),
                    ("contribution_margin_rate", ("contribution_margin_rate",)), ("setup_cost_usd", ("fixed_setup_per_plan",))):
        if i in ok:
            s[path[0]].update({"value": float(ok[i]["value"]), "status": tag(ok[i]), "range": [float(ok[i]["value"])] * 2})
    if "contact_cost_digital_usd" in ok:
        s["channels"]["digital_coupon"]["contact_cost"].update({"value": float(ok["contact_cost_digital_usd"]["value"]),
                                                               "range": [float(ok["contact_cost_digital_usd"]["value"])] * 2, "status": tag(ok["contact_cost_digital_usd"])})
    if "active_customer_households" in ok:
        s["deployment_scale"].update({"value": ok["active_customer_households"]["value"] / PANEL_ACTIVE_HOUSEHOLDS, "status": tag(ok["active_customer_households"])})
    if "eligible_consented_digital_households" in ok:
        share = ok["eligible_consented_digital_households"]["value"] / ok["active_customer_households"]["value"]
        s["channels"]["digital_coupon"]["reach_share"].update({"value": share, "range": [share, share], "status": tag(ok["eligible_consented_digital_households"])})
    if "stock_capacity_purchasing_households_4w" in ok:
        s["stock_capacity"] = {"value": ok["stock_capacity_purchasing_households_4w"]["value"], "unit": "purchasing households among contacted households per 4 weeks",
                               "status": tag(ok["stock_capacity_purchasing_households_4w"])}
    c["client_inputs_applied"] = sorted(ok)
    return c


def load_answers(path: Path = ANSWERS) -> dict | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else None


def form_md() -> str:
    L = ["# Client input form (send to the client; do not fill in on their behalf)", "",
         "Answer only what you can confirm. Give a **source** (document, system or person) and a **date** for each answer.",
         "Blank answers stay ASSUMED or UNKNOWN in the model. Return the answers as `data/client_inputs/client_inputs.json`, "
         "a copy of `client_inputs_TEMPLATE.json`.", "",
         "| # | Question | Unit / allowed values | Scenario-engine field it sets |", "|---|---|---|---|"]
    L += [f"| {n} | {q} | {u.replace('|', '/')} | `{f}` |" for n, (i, q, u, f, _) in enumerate(SPEC, 1)]
    L += ["", "**After the answers arrive:**",
          "1. Run `python -m mi.decision.client_inputs check`.",
          "2. Run `python -m mi.cli all`.",
          "3. The dossier, decision card and claims export show which inputs became CLIENT-CONFIRMED.",
          "", "**The historical match shares do not answer question 1 or 2.** Those shares (17% overall and 35% Frozen Pizza, value-weighted, on past coupon lines) describe past coupon accounting, not the terms of this offer."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["check"])[0]
    if cmd == "form":
        (ROOT / "docs" / "client_input_form.md").write_text(form_md(), encoding="utf-8")
        TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
        TEMPLATE.write_text(json.dumps(template(), indent=2), encoding="utf-8")
        print("form -> docs/client_input_form.md; template ->", TEMPLATE.relative_to(ROOT))
        return 0
    ans = load_answers()
    if ans is None:
        print("PENDING: no client answers (data/client_inputs/client_inputs.json absent); all inputs stay ASSUMED/UNKNOWN")
        return 0
    ok, problems = validate(ans)
    print(json.dumps({"applied": sorted(ok), "problems": problems}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
