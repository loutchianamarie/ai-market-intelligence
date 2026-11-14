"""Client input form -> scenario engine: nothing is filled on the client's behalf."""
import json

import pytest

from mi.config import load_config
from mi.decision.client_inputs import SPEC, apply, template, validate


def _ans(**vals):
    t = template()
    for k, v in vals.items():
        t["answers"][k].update({"value": v, "source": "CFO email", "date": "2026-11-20"})
    return t


def test_blank_template_changes_nothing():
    cfg = load_config(client_inputs=False)
    assert apply(cfg, template()) == cfg
    assert validate(template()) == ({}, [])


def test_every_question_maps_to_an_engine_field():
    cfg = load_config(client_inputs=False)
    assert len(SPEC) == 11 and all(f.startswith("scenario.") for _, _, _, f, _ in SPEC)
    filled = apply(cfg, _ans(retailer_share_of_face_value=0.0, offer_face_value_usd=1.0, redemption_mechanic="clip_to_card",
                             redemption_share_of_baseline_buyers=0.2, active_customer_households=50000, eligible_consented_digital_households=20000,
                             contribution_margin_rate=0.3, setup_cost_usd=800, contact_cost_digital_usd=0.02, offer_funder="manufacturer pays face value",
                             stock_capacity_purchasing_households_4w={"FROZEN PIZZA": 5000}))
    s = filled["scenario"]
    assert s["coupon_funding"]["retailer_share"]["value"] == 0.0 and s["coupon_face_value"]["value"] == 1.0
    assert s["channels"]["digital_coupon"]["reach_share"]["value"] == pytest.approx(0.4)
    assert s["deployment_scale"]["value"] == pytest.approx(50000 / 2469)
    assert s["fixed_setup_per_plan"]["status"].startswith("CLIENT-CONFIRMED") and len(filled["client_inputs_applied"]) == 11


def test_answers_without_source_or_out_of_range_are_not_applied():
    t = template()
    t["answers"]["contribution_margin_rate"]["value"] = 0.3                  # no source/date
    t["answers"]["retailer_share_of_face_value"].update({"value": 1.7, "source": "x", "date": "d"})
    ok, problems = validate(t)
    assert ok == {} and len(problems) == 2
    ok, problems = validate(_ans(active_customer_households=1000, eligible_consented_digital_households=2000))
    assert "eligible_consented_digital_households" not in ok and problems


def test_stock_capacity_becomes_a_binding_constraint():
    pytest.importorskip("pyarrow")
    from mi.decision.optimizer import load_inputs, optimise
    from mi.paths import PROCESSED
    if not (PROCESSED / "scores_latest.parquet").exists():
        pytest.skip("artifacts missing")
    cfg = apply(load_config(client_inputs=False), _ans(stock_capacity_purchasing_households_4w={c: 1 for c in load_config(client_inputs=False)["categories"]},
                                                     retailer_share_of_face_value=0.0))
    scores, econ, _ = load_inputs()
    r = optimise(scores, econ, cfg)
    assert r["n_portfolios_feasible"] == 0 and r["recommended_base"].startswith("NONE")   # every plan exceeds a 1-household stock cap
