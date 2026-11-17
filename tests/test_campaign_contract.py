"""Contract v1 for the campaign case: the frozen schema, the null-only fixture and the violations it must catch.

Everything here runs on the SYNTHETIC_FIXTURE or on mutations of it. Nothing reads or writes reports/.
"""
import copy
import json

import pytest

from mi.campaign import contract as C


@pytest.fixture
def doc():
    return C.build_fixture()


def _errs(d, **kw):
    return C.validate_case(d, **kw)


def test_committed_sample_is_the_deterministic_fixture_and_is_valid(doc):
    assert C.SAMPLE_PATH.read_text(encoding="utf-8") == C.dumps(doc)
    assert _errs(doc) == []
    assert doc["record_type"] == "SYNTHETIC_FIXTURE" and doc["contract_version"] == "1.0"
    assert doc["approval_required"] is True and doc["approval_status"] == "DRAFT_REQUIRES_HUMAN"


def test_fixture_carries_no_empirical_value_anywhere(doc):
    empirical = [(p, n) for p, n in C._walk(doc) if isinstance(n, dict) and n.get("tag") in ("OBSERVED", "HELD_OUT_ESTIMATE") and "value" in n]
    assert len(empirical) > 100
    assert all(n["value"] is None for _, n in empirical)
    counts = [m[k] for m in doc["observed_arm_metrics"] for k in ("n_customers", "buyers")]
    assert counts == [None] * 6
    assert doc["dataset_provenance"]["sha256"] is None and doc["model_version"] is None


def test_every_tagged_value_uses_one_of_the_five_tags(doc):
    tags = {n["tag"] for _, n in C._walk(doc) if isinstance(n, dict) and "tag" in n}
    assert tags <= set(C.TAGS) and {"OBSERVED", "HELD_OUT_ESTIMATE", "ASSUMPTION", "PUBLISHED_REFERENCE", "UNKNOWN"} == tags


def test_missing_control_arm_is_rejected(doc):
    d = copy.deepcopy(doc)
    d["arms"] = [a for a in d["arms"] if a["role"] != "control"] + [{"name": "Mens E-Mail", "role": "treatment"}]
    assert any("arms" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["observed_arm_metrics"] = [m for m in d["observed_arm_metrics"] if m["arm"] != C.CONTROL]
    assert any("observed_arm_metrics" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["average_effects"][0]["control_arm"] = "Womens E-Mail"       # an e-mail arm may never stand in for the untreated control
    assert any("control_arm" in e for e in _errs(d))


def test_negative_buyers_are_rejected(doc):
    d = copy.deepcopy(doc)
    d["observed_arm_metrics"][1]["buyers"] = -1
    assert any("buyers" in e and "minimum" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["held_out_policy_metrics"][3]["treated_buyers"] = -4
    assert _errs(d)


def test_counts_above_their_denominator_are_rejected(doc):
    d = copy.deepcopy(doc)
    d["observed_arm_metrics"][0].update(n_customers=10, buyers=11)
    assert any("buyers above the arm's customers" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["held_out_policy_metrics"][3].update(treated_n=5, treated_buyers=6)
    assert any("treated buyers above treated customers" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["held_out_policy_metrics"][3].update(eligible_n=100, contacted_n=101)
    assert any("contacted above eligible" in e for e in _errs(d))


def test_contact_cap_is_enforced(doc):
    d = copy.deepcopy(doc)
    row = next(x for x in d["held_out_policy_metrics"] if x["policy_id"] == "MODEL_MENS_25")
    for x in d["held_out_policy_metrics"]:
        x["eligible_n"] = 1000
    row["contacted_n"] = 300                                     # 25% of 1,000 allows 250
    assert any("exceeds the contact cap 250" in e for e in _errs(d))


def test_scenario_mislabelled_as_observed_is_rejected(doc):
    d = copy.deepcopy(doc)
    d["business_scenarios"][1]["contribution"]["tag"] = "OBSERVED"
    assert any("contribution" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["business_scenarios"][1]["value_kind"] = "MEASURED_PROFIT"
    assert any("value_kind" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["business_scenarios"][1]["assumed_margin"]["tag"] = "OBSERVED"   # nobody observed a margin in this dataset
    assert any("assumed_margin" in e for e in _errs(d))


def test_unknown_margin_rendered_as_zero_is_rejected(doc):
    d = copy.deepcopy(doc)
    s = next(x for x in d["business_scenarios"] if x["scenario_id"].endswith("__UNKNOWN_INPUTS"))
    assert s["assumed_margin"] == {"value": None, "tag": "UNKNOWN", "unit": s["assumed_margin"]["unit"]}
    assert s["contribution"]["value"] is None and s["contribution"]["tag"] == "UNKNOWN"
    s["assumed_margin"]["value"] = 0
    assert any("assumed_margin" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    u = next(a for a in d["assumptions_and_unknowns"] if a["id"] == "U_MARGIN")
    u["value"] = 0.0
    assert any("assumptions_and_unknowns" in e for e in _errs(d))
    with pytest.raises(C.ContractError, match="UNKNOWN"):
        C.tv(0.0, "UNKNOWN", "share")


def test_contribution_stays_unknown_when_an_input_is_unknown_and_arithmetic_is_checked(doc):
    assert C.scenario_contribution(1000, 0.5, None, 0.01, 100) is None
    assert C.scenario_contribution(1000, 0.5, 0.3, 0.01, 100) == pytest.approx(1000 * (0.5 * 0.3 - 0.01) - 100)
    d = copy.deepcopy(doc)
    s = next(x for x in d["business_scenarios"] if x["scenario_id"].endswith("__UNKNOWN_INPUTS"))
    s["contribution"] = {"value": 0.0, "tag": "ASSUMPTION", "unit": "USD", "ci95": None, "ci_method": None}
    assert any("must be UNKNOWN" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    s = next(x for x in d["business_scenarios"] if x["scenario_id"].endswith("__CENTRAL"))
    s["contribution"]["value"] = 123456.0                         # a hand-typed number that the formula does not give
    assert any("does not equal the contract formula" in e for e in _errs(d))


def test_mismatched_case_id_is_rejected(doc):
    d = copy.deepcopy(doc)
    d["claims"][0]["case_id"] = "GROCERY_FROZEN_PIZZA"
    assert any("case_id" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["case_id"] = "GROCERY_FROZEN_PIZZA"
    assert any("case_id" in e for e in _errs(d))
    assert any("not the expected case" in e for e in _errs(doc, expected_case_id="FASHIONFORWARD_2026"))


def test_rate_must_use_its_own_arm_denominator(doc):
    """Dividing an arm's buyers by the whole study population is the classic error; the validator recomputes the rate."""
    d = copy.deepcopy(doc)
    d["record_type"] = "COMPUTED_EXPORT"                          # SYNTHETIC TEST NUMBERS, never written anywhere
    m = d["observed_arm_metrics"][1]
    m.update(n_customers=1000, buyers=12)
    m["purchase_rate"]["value"] = 12 / 3000
    assert any("is not buyers / this arm's customers" in e for e in _errs(d))


def test_both_emails_must_be_compared_with_the_same_control(doc):
    d = copy.deepcopy(doc)
    for m, (n, b) in zip(d["observed_arm_metrics"], ((1000, 5), (1000, 12), (1000, 9))):     # SYNTHETIC TEST NUMBERS
        m.update(n_customers=n, buyers=b)
    d["average_effects"][0].update(treated_n=1000, treated_buyers=12, control_n=1000, control_buyers=5)
    d["average_effects"][1].update(treated_n=1000, treated_buyers=9, control_n=1000, control_buyers=12)    # Mens used as "control"
    assert any("control counts are not the shared No E-Mail arm" in e for e in _errs(d))


def test_post_treatment_fields_cannot_be_declared_as_features(doc):
    for leak in ("visit", "conversion", "spend"):
        d = copy.deepcopy(doc)
        d["model"]["features_pre_treatment"].append(leak)
        assert any("features_pre_treatment" in e for e in _errs(d)), leak
    d = copy.deepcopy(doc)
    d["model"]["features_pre_treatment"].append("segment")        # the randomized assignment is the treatment, not a customer feature
    assert any("assignment fields used as features" in e for e in _errs(d))


def test_approval_cannot_be_switched_off_and_published_figures_keep_their_tag(doc):
    d = copy.deepcopy(doc)
    d["approval_required"] = False
    assert any("approval_required" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["approval_status"] = "APPROVED"
    assert any("approval_status" in e for e in _errs(d))
    d = copy.deepcopy(doc)
    d["published_references"][0]["tag"] = "OBSERVED"              # a published figure is never our observation
    assert any("published_references" in e for e in _errs(d))
    assert {r["tag"] for r in doc["published_references"]} == {"PUBLISHED_REFERENCE"}


def test_fixture_with_a_made_up_empirical_number_is_rejected(doc):
    d = copy.deepcopy(doc)
    d["average_effects"][0]["additional_buyers_per_1000"]["value"] = 6.8
    assert any("must not carry an empirical value" in e for e in _errs(d))


def test_policy_catalog_covers_every_required_policy_family_and_cap(doc):
    fam = {(x["policy_family"], x["contact_share"]) for x in doc["held_out_policy_metrics"]}
    for share in (0.25, 0.5):
        assert {("RANDOM", share), ("RULE", share), ("MODEL", share)} <= fam
    assert ("SEND_ALL", 1.0) in fam and ("NO_EMAIL", 0.0) in fam
    none = next(x for x in doc["held_out_policy_metrics"] if x["policy_family"] == "NO_EMAIL")
    assert none["arm_assignment"] == "NONE" and none["additional_buyers_per_1000_contacts"]["tag"] == "UNKNOWN"
    assert all(x["control_arm"] == C.CONTROL and x["split"] == "test" for x in doc["held_out_policy_metrics"])


def test_sample_json_on_disk_parses_and_names_only_known_sources():
    d = json.loads(C.SAMPLE_PATH.read_text(encoding="utf-8"))
    src = {s["source_id"] for s in d["sources"]}
    assert set(d["evidence_ids"]) == src and all(c["source_id"] in src for c in d["claims"])


def test_validator_works_when_copied_next_to_the_schema_in_another_repo(tmp_path, doc):
    """The consumer copies contract.py and the schema into its own tree; nothing else from this repo is needed."""
    import importlib.util
    import shutil
    shutil.copy(C.__file__, tmp_path / "contract.py")
    shutil.copy(C.SCHEMA_PATH, tmp_path / "campaign_case.v1.schema.json")
    spec = importlib.util.spec_from_file_location("consumer_copy_of_contract", tmp_path / "contract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.SCHEMA_PATH == tmp_path / "campaign_case.v1.schema.json"
    assert mod.validate_case(doc) == []
    bad = copy.deepcopy(doc)
    bad["observed_arm_metrics"][0]["buyers"] = -1
    assert mod.validate_case(bad)
