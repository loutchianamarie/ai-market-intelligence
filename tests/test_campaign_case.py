"""Campaign case (HILLSTROM_EMAIL_2008): data, leakage, three-arm logic, policy evaluation, economics, export.

Edge cases run on a small SYNTHETIC frame built here. It is test scaffolding only and is never evidence for the
real case. Nothing in this file writes to reports/ or docs/: builds are pure and writers get tmp_path.
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mi.campaign import contract as K
from mi.campaign import data as D
from mi.campaign import export as X
from mi.campaign import uplift as U
from mi.campaign.contract import CONTROL, MENS, WOMENS

needs_hillstrom = pytest.mark.skipif(not D.CSV.exists(), reason="raw Hillstrom file is local-only; place it at data/raw/hillstrom/")
SRC = Path(__file__).resolve().parents[1] / "src" / "mi"


def synthetic_frame(n=6000, seed=7) -> pd.DataFrame:
    """SYNTHETIC TEST DATA with a known structure: Mens e-mail adds more buyers than Womens; high spenders respond more."""
    r = np.random.default_rng(seed)
    hist = np.round(np.exp(r.normal(5.0, 1.0, n)) + 29.99, 2)
    df = pd.DataFrame({
        "recency": r.integers(1, 13, n), "history_segment": "x", "history": hist,
        "mens": r.integers(0, 2, n), "womens": 0, "zip_code": r.choice(["Rural", "Surburban", "Urban"], n),
        "newbie": r.integers(0, 2, n), "channel": r.choice(["Multichannel", "Phone", "Web"], n),
        "segment": r.choice([CONTROL, MENS, WOMENS], n)})
    df["womens"] = np.where(df.mens == 0, 1, r.integers(0, 2, n))
    p = 0.06 + 0.05 * (df.segment == MENS) * (1 + (hist > np.median(hist))) + 0.02 * (df.segment == WOMENS)
    df["conversion"] = (r.random(n) < p).astype(int)
    df["visit"] = np.maximum(df.conversion, (r.random(n) < 0.2).astype(int))
    df["spend"] = np.round(df.conversion * r.gamma(2.0, 40.0, n), 2)
    return df


def _with_ids(df):
    out = df.reset_index(drop=True).copy()
    out.insert(0, "customer_id", np.arange(len(out)))
    return out


@pytest.fixture(scope="module")
def proto():
    return D.load_protocol()


@pytest.fixture(scope="module")
def syn():
    return _with_ids(synthetic_frame())


@pytest.fixture(scope="module")
def built(syn, proto):
    """One pure build on SYNTHETIC data (small bootstrap). Returns (doc, detail, facts)."""
    facts = {"sha256": hashlib.sha256(b"SYNTHETIC TEST DATA").hexdigest(), "bytes": 1, "rows": len(syn)}
    doc, det = X.build(syn, facts, proto, n_boot=200, n_boot_qini=40, code_commit="TEST", generated_at="2026-11-17T00:00:00Z")
    return doc, det, facts


# ------------------------------------------------------------------ source, schema, arms
@needs_hillstrom
def test_real_source_matches_the_preregistered_file_and_counts(proto):
    df, facts = D.load_raw(proto=proto)
    assert facts == {"sha256": proto["source"]["sha256"], "bytes": proto["source"]["bytes"], "rows": 64000}
    assert list(df.columns) == ["customer_id"] + D.COLUMNS and df.customer_id.is_unique
    counts = df.segment.value_counts().to_dict()
    assert set(counts) == {CONTROL, MENS, WOMENS} and sum(counts.values()) == 64000
    assert max(counts.values()) - min(counts.values()) < 100           # thirds, as the source states
    a = D.audit(df, facts, proto)
    assert sum(a["missing_values"].values()) == 0 and all(b["all_below_0.1"] for b in a["balance_vs_control"])
    assert a["outcome_integrity"]["spend_without_conversion"] == 0 and a["feature_timing"]["leak_check"] == []


def test_loader_refuses_another_file_a_missing_control_arm_and_bad_outcomes(tmp_path, proto):
    p = tmp_path / "other.csv"
    synthetic_frame(300).to_csv(p, index=False)
    with pytest.raises(D.CampaignDataError, match="checksum"):
        D.load_raw(p, proto)
    df, facts = D.load_raw(p, proto, enforce_checksum=False)
    assert facts["rows"] == 300 and df.customer_id.tolist() == list(range(300))
    with pytest.raises(D.CampaignDataError, match="no-e-mail control is required"):
        D.validate_frame(synthetic_frame(300).query("segment != @CONTROL"))
    bad = synthetic_frame(300)
    bad.loc[0, ["conversion", "spend"]] = [0, 25.0]
    with pytest.raises(D.CampaignDataError, match="spend without a purchase"):
        D.validate_frame(bad)
    bad = synthetic_frame(300)
    bad.loc[3, "history"] = np.nan
    with pytest.raises(D.CampaignDataError, match="missing values"):
        D.validate_frame(bad)


def test_duplicate_customers_are_counted_reported_and_kept(proto):
    df = synthetic_frame(400)
    dup = _with_ids(pd.concat([df, df.iloc[:25]], ignore_index=True))
    a = D.audit(dup, {"sha256": "0" * 64, "bytes": 0, "rows": len(dup)}, proto)
    assert a["duplicates"]["fully_identical_rows_beyond_first"] == 25
    assert a["rows"] == 425 and dup.customer_id.is_unique               # kept: there is no id to deduplicate on
    assert "KEPT" in a["duplicates"]["handling"]


# ------------------------------------------------------------------ leakage
def test_no_post_treatment_field_can_reach_the_model(syn, monkeypatch):
    names = U.Design().fit(syn).names
    assert len(names) == 29 and not [n for n in names if re.search(r"visit|conversion|spend|segment", n)]
    assert not set(D.MODEL_FEATURES) & set(D.POST + [D.ASSIGNMENT])
    d, clf = U.fit_slearner(syn, C=0.1)
    p0 = U.predict_arms(d, clf, syn)
    scrambled = syn.copy()
    r = np.random.default_rng(1)
    scrambled["visit"], scrambled["conversion"], scrambled["spend"] = 1 - syn.visit, r.integers(0, 2, len(syn)), r.random(len(syn)) * 999
    scrambled["segment"] = r.permutation(syn.segment.to_numpy())
    p1 = U.predict_arms(d, clf, scrambled)
    for arm in (CONTROL, MENS, WOMENS):
        assert np.array_equal(p0[arm], p1[arm]), "predictions changed when only outcomes / assignment changed"
    up = lambda p: {a: p[a] - p[CONTROL] for a in (MENS, WOMENS)}      # noqa: E731
    for a, b in zip(U.build_policies(syn, up(p0)), U.build_policies(scrambled, up(p1))):
        assert np.array_equal(a.selected, b.selected) and np.array_equal(a.assigned, b.assigned), a.spec["policy_id"]
    monkeypatch.setattr(U, "MODEL_FEATURES", D.MODEL_FEATURES + ["spend"])
    with pytest.raises(ValueError, match="post-treatment"):
        U.Design().fit(syn)


def test_scaling_statistics_come_from_the_fitting_rows_only(syn):
    a, b = syn.iloc[:3000], syn.iloc[3000:]
    d = U.Design().fit(a)
    assert d.mean["recency"] == pytest.approx(a.recency.mean()) and d.mean["recency"] != pytest.approx(b.recency.mean())


# ------------------------------------------------------------------ split
def test_split_is_seeded_stratified_disjoint_and_hashed(syn, proto):
    lab = U.make_split(syn, proto)
    assert np.array_equal(lab, U.make_split(syn, proto))                 # same seed -> same customers
    assert set(lab) == {"train", "validation", "test"} and len(lab) == len(syn)
    for arm in (CONTROL, MENS, WOMENS):
        m = (syn.segment == arm).to_numpy()
        assert (lab[m] == "train").mean() == pytest.approx(0.4, abs=0.01) and (lab[m] == "test").mean() == pytest.approx(0.4, abs=0.01)
    h = U.split_hashes(syn, lab)
    assert sum(v["n"] for v in h.values()) == len(syn) and h == U.split_hashes(syn, lab)
    other = U.make_split(syn, {**proto, "split": {**proto["split"], "seed": 1}})
    assert U.split_hashes(syn, other)["test"]["sha256_of_customer_ids"] != h["test"]["sha256_of_customer_ids"]


# ------------------------------------------------------------------ top-k evaluation, contact cap, estimators
def _tiny():
    """12 hand-made customers (SYNTHETIC). Scores put customers 0..5 on top."""
    seg = [MENS, CONTROL, MENS, CONTROL, WOMENS, WOMENS, MENS, CONTROL, WOMENS, CONTROL, MENS, CONTROL]
    conv = [1, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 1]
    df = pd.DataFrame({"customer_id": range(12), "segment": seg, "conversion": conv, "spend": [10.0 * c for c in conv],
                       "recency": [1, 1, 2, 2, 3, 3, 9, 9, 10, 10, 11, 12], "history": [900.0 - 10 * i for i in range(12)]})
    return df


def test_top_k_uplift_matches_a_hand_computation():
    df = _tiny()
    score = -np.arange(12.0)                                             # customer 0 best
    # top 50% = customers 0..5: Mens 2/2 buyers, control 1/2 -> uplift 0.5
    assert U.uplift_at_cap(df, U.order_score(df, score), MENS, 0.5) == pytest.approx(1.0 - 0.5)
    assert U.cap_size(12, 0.25) == 3 and U.top_mask(U.order_score(df, score), 3).sum() == 3
    assert list(U.order_recency(df)[:2]) == [0, 1] and list(U.order_history(df)[:3]) == [0, 1, 2]
    uplift = {MENS: score, WOMENS: score - 100.0}                        # model always prefers Mens
    pols = {p.spec["policy_id"]: p for p in U.build_policies(df, uplift)}
    ev = U.Evaluator(df, list(pols.values()))
    pt = ev.point()
    assert pt["MODEL_MENS_50"]["buyers"] == pytest.approx(0.5)
    c = ev.counts("MODEL_MENS_50")
    assert (c["contacted_n"], c["treated_n"], c["treated_buyers"], c["control_n"], c["control_buyers"]) == (6, 2, 2, 2, 1)
    # send-all Mens: 2 buyers of 4 Mens, 2 buyers of 5 control; random has the same expected value
    assert pt["SEND_ALL_MENS_100"]["buyers"] == pytest.approx(2 / 4 - 2 / 5) == pytest.approx(pt["RANDOM_MENS_25"]["buyers"])
    assert pt["SEND_ALL_MENS_100"]["spend"] == pytest.approx(10 * (2 / 4 - 2 / 5))
    assert pt["NO_EMAIL_0"]["buyers"] == 0.0 and ev.counts("NO_EMAIL_0")["contacted_n"] == 0
    assert pt["MODEL_BESTARM_50"]["buyers"] == pytest.approx(pt["MODEL_MENS_50"]["buyers"])     # same policy when the model always picks Mens


def test_multi_arm_policy_estimator_matches_the_stratified_formula():
    df = _tiny()
    # the model prefers Womens for customers 4 and 5, Mens elsewhere; everyone is contacted
    up_m = np.where(np.isin(np.arange(12), [4, 5]), 0.0, 1.0)
    pols = U.build_policies(df, {MENS: up_m, WOMENS: 1.0 - up_m})
    ev = U.Evaluator(df, pols)
    # S_womens = {4, 5}: both randomized to Womens -> mean 1/2, weight 2/12. S_mens = the other 10: Mens rows 0, 2, 6, 10 -> 2/4, weight 10/12.
    want = (2 / 12) * (1 / 2) + (10 / 12) * (2 / 4) - 2 / 5              # minus the control mean over all selected controls
    assert ev.point()["MODEL_BESTARM_100"]["buyers"] == pytest.approx(want)
    c = ev.counts("MODEL_BESTARM_100")
    assert c["treated_n"] == 6 and c["treated_buyers"] == 3 and c["control_n"] == 5 and c["assigned_split"] == {MENS: 10, WOMENS: 2}


def test_contact_cap_is_never_exceeded(built):
    doc, det, _ = built
    n = doc["model"]["split"]["n_test"]
    for x in doc["held_out_policy_metrics"]:
        assert x["eligible_n"] == n and x["contacted_n"] <= round(x["contact_share"] * n), x["policy_id"]
        if x["policy_family"] in ("RULE", "MODEL"):
            assert x["contacted_n"] == round(x["contact_share"] * n)       # the cap is used, not exceeded
            assert x["treated_n"] + x["control_n"] <= x["contacted_n"]
    none = next(x for x in doc["held_out_policy_metrics"] if x["policy_family"] == "NO_EMAIL")
    assert none["contacted_n"] == 0 and none["additional_buyers_per_1000_eligible"]["value"] == 0.0


# ------------------------------------------------------------------ three arms, same control, denominators, intervals
def test_three_arms_share_one_control_and_rates_use_own_denominators(built, syn):
    doc, _, _ = built
    rows = {m["arm"]: m for m in doc["observed_arm_metrics"]}
    assert set(rows) == {CONTROL, MENS, WOMENS} and sum(m["n_customers"] for m in rows.values()) == len(syn)
    for arm, m in rows.items():
        g = syn[syn.segment == arm]
        assert (m["n_customers"], m["buyers"]) == (len(g), int(g.conversion.sum()))
        assert m["purchase_rate"]["value"] == pytest.approx(g.conversion.mean())
        assert m["purchase_rate"]["value"] != pytest.approx(g.conversion.sum() / len(syn))     # not the whole-study denominator
    c = rows[CONTROL]
    for e in doc["average_effects"]:
        assert e["control_arm"] == CONTROL and (e["control_n"], e["control_buyers"]) == (c["n_customers"], c["buyers"])
        want = 1000 * (e["treated_buyers"] / e["treated_n"] - e["control_buyers"] / e["control_n"])
        assert e["additional_buyers_per_1000"]["value"] == pytest.approx(want)
        lo, hi = e["additional_buyers_per_1000"]["ci95"]
        assert lo < want < hi
    assert all(x["control_arm"] == CONTROL for x in doc["held_out_policy_metrics"])


def test_wald_interval_and_bootstrap_behave():
    w = U.wald(1000, 30, 1000, 10)
    se = (0.03 * 0.97 / 1000 + 0.01 * 0.99 / 1000) ** 0.5
    assert w["diff"] == pytest.approx(0.02) and w["ci95"] == pytest.approx([0.02 - 1.96 * se, 0.02 + 1.96 * se])
    df = _with_ids(synthetic_frame(3000, seed=3))
    pols = U.build_policies(df, {MENS: df.history.to_numpy(float), WOMENS: -df.history.to_numpy(float)})
    ev = U.Evaluator(df, pols)
    b1, b2 = ev.bootstrap(150, seed=5), ev.bootstrap(150, seed=5)
    assert np.array_equal(b1["MODEL_MENS_25"]["buyers"], b2["MODEL_MENS_25"]["buyers"])          # seeded -> reproducible
    pt = ev.point()
    for pid in ("SEND_ALL_MENS_100", "MODEL_MENS_25", "RULE_HISTORY_MENS_50"):
        lo, hi = U.pct_ci(b1[pid]["buyers"])
        assert lo < pt[pid]["buyers"] < hi and hi - lo > 0
    wide = U.pct_ci(b1["MODEL_MENS_25"]["buyers"])
    narrow = U.pct_ci(b1["SEND_ALL_MENS_100"]["buyers"])
    assert wide[1] - wide[0] > narrow[1] - narrow[0]                     # fewer customers in a top-k cell -> wider interval
    assert np.array_equal(b1["RANDOM_MENS_25"]["buyers"], b1["SEND_ALL_MENS_100"]["buyers"])      # random = expectation over the whole arms


def test_qini_coefficient_on_a_hand_example():
    y, t = np.array([1.0, 0, 0, 0]), np.array([True, False, True, False])
    assert U.qini_coefficient(y, t, np.arange(4)) == pytest.approx(1.0)       # the only incremental buyer is ranked first
    assert U.qini_coefficient(y, t, np.arange(4)[::-1]) < 0                   # ranked last -> below the random line
    assert U.qini_coefficient(np.zeros(4), t, np.arange(4)) is None           # no uplift at all -> undefined, not zero


# ------------------------------------------------------------------ decision rule, economics
def test_preregistered_verdict_and_fallback_decision():
    d = lambda v, lo, hi: {"value": v, "ci95": [lo, hi]}                  # noqa: E731
    assert X.verdict_of({"model_minus_random": d(3, 1, 5), "model_minus_rule": d(2, 0.5, 4)})["verdict"] == "MODEL_WIN_STABLE"
    assert X.verdict_of({"model_minus_random": d(3, -1, 5), "model_minus_rule": d(2, 0.5, 4)})["verdict"] == "MODEL_AHEAD_NOT_STABLE"
    assert X.verdict_of({"model_minus_random": d(3, 1, 5), "model_minus_rule": d(-0.1, -4, 4)})["verdict"] == "NO_MODEL_ADVANTAGE"
    ev = {"selection": {"best_overall_arm": MENS}, "primary": {"cap": 0.25, "ids": {"model": "MODEL_MENS_25"},
                                                                "model_minus_random": d(3, -1, 5), "model_minus_rule": d(2, -2, 4)}}
    fs = {"effects": {MENS: {"per_1000_ci": [5.0, 8.6]}}}
    dec = X.decide(fs, ev)
    assert dec["status"] == "BROAD_SEND_WITH_HOLDOUT_IF_ECONOMICS_CONFIRMED" and dec["policy_id"] == "SEND_ALL_MENS_100" and dec["contact_share"] == 0.9
    assert X.decide({"effects": {MENS: {"per_1000_ci": [-0.4, 8.6]}}}, ev)["status"] == "MORE_EVIDENCE_REQUIRED"      # no e-mail stays possible
    ev["primary"].update(model_minus_random=d(3, 1, 5), model_minus_rule=d(2, 1, 4))
    assert X.decide(fs, ev)["status"] == "TARGETED_SEND_WITH_HOLDOUT_IF_ECONOMICS_CONFIRMED"
    assert X.holdout_size(0.0057, 0.0125) == pytest.approx(3060, rel=0.02) and X.holdout_size(0.01, 0.01) is None


def test_unknown_costs_stay_unknown_and_scenarios_follow_the_formula(built):
    doc, _, _ = built
    unk = [s for s in doc["business_scenarios"] if s["scenario_id"].endswith("__UNKNOWN_INPUTS")]
    assert len(unk) == 2
    for s in unk:
        assert all(s[k] == {"value": None, "tag": "UNKNOWN", "unit": s[k]["unit"]} for k in ("assumed_margin", "cost_per_contact", "fixed_setup_cost"))
        assert s["contribution"]["value"] is None and s["contribution"]["tag"] == "UNKNOWN" and s["contribution"]["ci95"] is None
    for s in doc["business_scenarios"]:
        assert s["value_kind"] == "SCENARIO_NOT_MEASURED_PROFIT" and s["contribution"]["tag"] in ("ASSUMPTION", "UNKNOWN")
        if s["contribution"]["value"] is not None:
            want = s["contacts"]["value"] * (s["incremental_spend_per_contact"]["value"] * s["assumed_margin"]["value"] - s["cost_per_contact"]["value"]) - s["fixed_setup_cost"]["value"]
            assert s["contribution"]["value"] == pytest.approx(want)
    unknowns = [a for a in doc["assumptions_and_unknowns"] if a["tag"] == "UNKNOWN"]
    assert {"U_MARGIN", "U_COST_PER_CONTACT"} <= {a["id"] for a in unknowns} and all(a["value"] is None for a in unknowns)
    assert not [c for c in doc["claims"] if c["tag"] in ("ASSUMPTION", "UNKNOWN") and "measured profit" in c["text"].lower() and c["value"] is not None
                and "not measured profit" not in c["text"].lower()]
    assert next(c for c in doc["claims"] if c["claim_id"] == "CLM_MEASURED_PROFIT")["value"] is None


# ------------------------------------------------------------------ output contract
def test_export_passes_the_contract_and_mirrors_the_fixture_structure(built):
    doc, det, facts = built
    assert K.validate_case(doc) == []
    fx = K.build_fixture()
    assert K.structure_paths(doc) == K.structure_paths(fx), "the real export and the fixture must expose the same keys"
    ids = lambda d, key, f: [x[f] for x in d[key]]                        # noqa: E731
    assert ids(doc, "held_out_policy_metrics", "policy_id") == ids(fx, "held_out_policy_metrics", "policy_id")
    assert ids(doc, "business_scenarios", "scenario_id") == ids(fx, "business_scenarios", "scenario_id")
    assert ids(doc, "economic_thresholds", "threshold_id") == ids(fx, "economic_thresholds", "threshold_id")
    assert set(ids(fx, "claims", "claim_id")) <= set(ids(doc, "claims", "claim_id"))
    assert sum(x["is_primary"] for x in doc["held_out_policy_metrics"]) == 3
    assert doc["record_type"] == "COMPUTED_EXPORT" and doc["approval_required"] is True and doc["recommendation"]["human_decision_required"] is True
    assert all(d["status"] == "DRAFT_HYPOTHESIS_NOT_SENT" for d in doc["marketing"]["message_drafts"])
    assert [p["p"] for p in doc["marketing"]["four_ps"]] == ["Product", "Price", "Place", "Promotion"]
    assert any(a["status"] == "BLOCKED_UNTIL_APPROVED" for a in doc["marketing"]["action_plan"])


def test_every_claim_is_tied_to_hash_denominator_split_and_source(built):
    doc, _, facts = built
    src = {s["source_id"] for s in doc["sources"]}
    seen = set()
    for c in doc["claims"]:
        assert c["claim_id"] not in seen and c["source_id"] in src and c["case_id"] == K.CASE_ID
        seen.add(c["claim_id"])
        if c["tag"] in ("OBSERVED", "HELD_OUT_ESTIMATE"):
            assert c["dataset_sha256"] == facts["sha256"] and c["denominator"] and c["value"] is not None
        if c["tag"] == "HELD_OUT_ESTIMATE":
            assert c["split"] == "test" and c["model_version"] == doc["model_version"]
        if c["tag"] == "PUBLISHED_REFERENCE":
            assert c["source_id"] == "SRC_RADCLIFFE_2008" and c["dataset_sha256"] is None
        if c["tag"] == "UNKNOWN":
            assert c["value"] is None
    assert {c["tag"] for c in doc["claims"]} == set(K.TAGS)


def test_build_is_deterministic_for_the_same_data_and_seed(built, syn, proto):
    doc, _, facts = built
    again, _ = X.build(syn, facts, proto, n_boot=200, n_boot_qini=40, code_commit="TEST", generated_at="2026-11-17T00:00:00Z")
    assert K.dumps(again) == K.dumps(doc)


# ------------------------------------------------------------------ isolation and safe writing
def test_campaign_case_is_isolated_from_the_grocery_case(built):
    doc, _, _ = built
    forbidden = re.compile(r"^\s*(from|import)\s+mi\.(model|decision|ingest|outcome|agents|workflow|evidence|seo|content|claims_export|claim_audit)\b", re.M)
    for f in (SRC / "campaign").glob("*.py"):
        assert not forbidden.search(f.read_text(encoding="utf-8")), f"{f.name} imports grocery or agent code"
    for sub in ("decision", "outcome", "model", "ingest"):
        for f in (SRC / sub).glob("*.py"):
            text = f.read_text(encoding="utf-8")
            assert "mi.campaign" not in text and "campaign_case" not in text, f"{sub}/{f.name} reads the campaign case"
    text = K.dumps(doc).lower()
    for token in ("household", "coupon", "frozen pizza", "dunnhumby", "opp-", "fashionforward_metrics", "average precision"):
        assert token not in text, f"grocery or other-case token {token!r} leaked into the campaign export"
    assert {x["case_id"] for x in doc["claims"]} == {K.CASE_ID}


def test_writer_never_overwrites_the_live_export_with_other_data(built, tmp_path, proto):
    doc, det, facts = built
    before = X.EXPORT.read_bytes() if X.EXPORT.exists() else None
    aud = D.audit(_with_ids(synthetic_frame(300)), facts, proto)
    with pytest.raises(D.CampaignDataError, match="refusing to write the live export"):
        X.write_all(doc, det, aud, proto)                                # default paths + non-registered data -> refused
    assert (X.EXPORT.read_bytes() if X.EXPORT.exists() else None) == before
    out = tmp_path / "campaign_case.latest.json"
    checksum = X.write_all(doc, det, aud, proto, export_path=out, checksum_path=tmp_path / "c.sha256", out_dir=tmp_path / "campaign", docs_dir=tmp_path / "docs")
    assert hashlib.sha256(out.read_bytes()).hexdigest() == checksum and checksum in (tmp_path / "c.sha256").read_text()
    assert K.validate_case(json.loads(out.read_text(encoding="utf-8"))) == []
    for name in ("campaign_decision_card.md", "campaign_marketing_brief.md", "campaign_data_dictionary.md"):
        assert (tmp_path / "docs" / name).stat().st_size > 500
    card = (tmp_path / "docs" / "campaign_decision_card.md").read_text(encoding="utf-8")
    assert "UNKNOWN" in card and "not measured profit" in card and "Nothing has been sent" in card
    assert (X.EXPORT.read_bytes() if X.EXPORT.exists() else None) == before


@pytest.mark.skipif(not X.EXPORT.exists(), reason="run python -m mi.campaign.export")
def test_live_export_matches_its_checksum_and_the_contract(proto):
    raw = X.EXPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == X.CHECKSUM.read_text(encoding="utf-8").split()[0]
    doc = json.loads(raw)
    assert K.validate_case(doc) == [] and doc["record_type"] == "COMPUTED_EXPORT"
    assert doc["dataset_provenance"]["sha256"] == proto["source"]["sha256"] and doc["dataset_provenance"]["rows"] == 64000
    assert K.structure_paths(doc) == K.structure_paths(K.build_fixture())
    ledger = json.loads((X.OUT / "claims_ledger.json").read_text(encoding="utf-8"))
    assert ledger["claims"] == doc["claims"] and ledger["export_sha256"] == hashlib.sha256(raw).hexdigest()
    man = json.loads((X.OUT / "run_manifest.json").read_text(encoding="utf-8"))
    assert man["data"]["sha256"] == proto["source"]["sha256"] and man["model_version"] == doc["model_version"] and man["seed"] == proto["split"]["seed"]
    assert man["split"]["test"]["n"] == doc["model"]["split"]["n_test"]
