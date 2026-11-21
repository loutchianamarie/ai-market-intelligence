"""Consumer side of the campaign case: adapter, bounded agent path, checker, approval boundary.

Every test uses a throwaway store and tmp files; nothing here touches reports/marketing_agent_trace.json or the live
campaign store. Fixtures that edit the export are labelled and never used as evidence.
"""
import copy
import hashlib
import json
import re

import pytest

from mi.consumer import advisor as A
from mi.consumer.adapter import CHECKSUM_PATH, EXPORT_PATH, load_case
from mi.campaign.contract import SAMPLE_PATH
from mi.workflow.store import DossierStore, PermissionDenied, WorkflowError, pilot_hash

pytestmark = pytest.mark.skipif(not EXPORT_PATH.exists(), reason="campaign export not present")


@pytest.fixture(scope="module")
def case():
    r = load_case()
    assert r.ok, r.reasons
    return r


@pytest.fixture
def store(tmp_path):
    return DossierStore(tmp_path / "c.sqlite")


def edited(tmp_path, mutate):
    """A SYNTHETIC EDIT of the real export (never evidence) with its own matching checksum, so only validation can reject it."""
    doc = copy.deepcopy(json.loads(EXPORT_PATH.read_bytes()))
    mutate(doc)
    p = tmp_path / "edited.json"
    raw = json.dumps(doc, indent=2).encode()
    p.write_bytes(raw)
    return load_case(p, expected_sha=hashlib.sha256(raw).hexdigest())


# ------------------------------------------------------------------ adapter
def test_live_export_loads_with_matching_checksum(case):
    assert case.status == "OK" and case.label == "COMPUTED_EXPORT"
    import hashlib
    # not pinned to one revision: the loaded hash must equal both the recorded checksum and the file on disk
    assert case.sha256 == CHECKSUM_PATH.read_text().split()[0] == hashlib.sha256(EXPORT_PATH.read_bytes()).hexdigest()


def test_missing_export_is_data_pending_not_a_substitute(tmp_path):
    r = load_case(tmp_path / "nope.json")
    assert r.status == "DATA_PENDING" and r.doc is None and r.claims() == {}


def test_checksum_mismatch_is_rejected(tmp_path):
    p = tmp_path / "x.json"
    p.write_bytes(EXPORT_PATH.read_bytes() + b" ")
    p.with_suffix(".sha256").write_text(CHECKSUM_PATH.read_text())
    r = load_case(p)
    assert r.status == "REJECTED" and "mismatch" in r.reasons[0]


def test_missing_checksum_is_rejected(tmp_path):
    p = tmp_path / "y.json"
    p.write_bytes(EXPORT_PATH.read_bytes())
    assert load_case(p).status == "REJECTED"


def test_malformed_json_is_rejected(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert load_case(p, expected_sha=hashlib.sha256(b"{not json").hexdigest()).status == "REJECTED"


def test_synthetic_fixture_never_reaches_the_empirical_view():
    r = load_case(SAMPLE_PATH)
    assert r.status == "REJECTED" and "SYNTHETIC_FIXTURE" in r.reasons[0]
    f = load_case(SAMPLE_PATH, allow_fixture=True)
    assert f.status == "FIXTURE" and f.label == "SYNTHETIC_FIXTURE"
    assert A.CampaignRun(f, persist=False).run_to_checkpoint()["status"] == "FIXTURE"   # the advisor refuses a fixture


def test_buyers_above_denominator_rejected(tmp_path):
    def m(d):
        d["observed_arm_metrics"][1]["buyers"] = d["observed_arm_metrics"][1]["n_customers"] + 1
    assert edited(tmp_path, m).status == "REJECTED"


def test_wrong_case_id_rejected(tmp_path):
    assert edited(tmp_path, lambda d: d.update(case_id="OTHER_CASE")).status == "REJECTED"


def test_unrecognised_arm_rejected(tmp_path):
    def m(d):
        d["observed_arm_metrics"][1]["arm"] = "Kids E-Mail"
    assert edited(tmp_path, m).status == "REJECTED"


def test_missing_control_arm_rejected(tmp_path):
    def m(d):
        d["observed_arm_metrics"] = [a for a in d["observed_arm_metrics"] if a["role"] != "control"]
    assert edited(tmp_path, m).status == "REJECTED"


def test_fake_source_id_rejected(tmp_path):
    def m(d):
        d["claims"][3]["source_id"] = "SRC_MADE_UP"
    r = edited(tmp_path, m)
    assert r.status == "REJECTED" and any("SRC_MADE_UP" in x for x in r.reasons)


def test_unknown_rendered_as_zero_rejected(tmp_path):
    def m(d):
        for c in d["claims"]:
            if c["claim_id"] == "CLM_MARGIN":
                c["value"] = 0
    assert edited(tmp_path, m).status == "REJECTED"


def test_scenario_mislabelled_observed_rejected(tmp_path):
    def m(d):
        d["business_scenarios"][2]["contribution"]["tag"] = "OBSERVED"
    assert edited(tmp_path, m).status == "REJECTED"


def test_ci_file_endings_are_pinned(tmp_path):
    """A CRLF checkout changes the SHA-256; .gitattributes must pin the export byte-exact."""
    ga = (EXPORT_PATH.parents[1] / ".gitattributes").read_text()
    assert "reports/campaign_case.latest.json -text" in ga


# ------------------------------------------------------------------ agent path
def run_all(case, store):
    r = A.CampaignRun(case, store, persist=False)
    out = r.run_to_checkpoint()
    return r, out


def test_full_path_reaches_the_human_checkpoint(case, store):
    r, out = run_all(case, store)
    assert out["status"] == "OK" and out["state"] == "REVIEW_REQUESTED" and out["mode"] == "DETERMINISTIC_SPECIALISTS"
    assert out["checker"] == "PASS_DRAFT_HOLD_FOR_INPUTS"
    d = store.get(out["opportunity_id"])
    assert d["approval"] is None and d["state"] == "REVIEW_REQUESTED"
    assert [s.role for s in r.steps] == ["analyst", "research", "strategist", "checker"]
    assert all(t["status"] == "DONE" for t in d["case_plan"]["tasks"] if t["role"] != "human")
    assert not store.crm_actions(out["opportunity_id"])                    # nothing recorded before a human decides
    assert "LLM" in d["llm_status"] and d["llm_status"].startswith("PENDING")


def test_every_role_calls_a_real_tool_and_traces_runtime(case, store):
    r, out = run_all(case, store)
    for s in r.steps:
        assert s.tool_calls and all(c["status"] == "ok" for c in s.tool_calls), (s.role, s.tool_calls)
        assert s.runtime_ms >= 0
    trace = store.get(out["opportunity_id"])["agent_trace"]
    assert {t["role"] for t in trace} == {"analyst", "research", "strategist", "checker"}
    assert any(c["evidence_ids"] for t in trace for c in t["tool_calls"])


def test_numbers_are_copied_from_the_export_never_recomputed(case, store):
    r, out = run_all(case, store)
    d = store.get(out["opportunity_id"])
    claims = case.claims()
    f = d["analyst_output"]["findings"]
    assert f and all(x["value"] == claims[x["claim_id"]]["value"] and x["tag"] == claims[x["claim_id"]]["tag"] for x in f)
    by = {x["claim_id"]: x for x in f}
    assert by["CLM_BUYERS_MENS"]["value"] == 267 and "21,307" in by["CLM_BUYERS_MENS"]["denominator"]
    assert by["CLM_MARGIN"]["value"] in (None, "UNKNOWN") and by["CLM_MARGIN"]["tag"] == "UNKNOWN"
    assert d["analyst_output"]["verdict"] == "MODEL_AHEAD_NOT_STABLE"


def test_no_role_has_a_send_spend_approve_publish_or_launch_tool():
    for role, tools in A.ROLE_ALLOWLIST.items():
        for t in tools:
            assert not any(w in t for w in A.FORBIDDEN_TOOL_WORDS), (role, t)
    # the real tools that exist on the dispatcher obey the same rule
    names = {n[2:] for n in dir(A.CampaignTools) if n.startswith("t_")}
    assert not [n for n in names if any(w in n for w in A.FORBIDDEN_TOOL_WORDS)]


def test_unauthorized_tool_calls_are_blocked_and_logged(case, store):
    out = A.blocked_demo(case, store, persist=False)
    assert out["strategist_calls_send_email"] == "blocked" and out["analyst_calls_draft_action"] == "blocked"
    assert out["crm_records_before_approval"]["status"] == "blocked"
    assert out["agent_self_approval"].startswith("blocked")
    assert out["no_role_has_a_send_tool"] is True
    assert {"TOOL_BLOCKED", "UNAPPROVED_ACTION_BLOCKED", "APPROVAL_BLOCKED"} <= set(out["events"])


def test_agent_cannot_approve_and_hash_mismatch_blocks_human_approval(case, store):
    r, out = run_all(case, store)
    oid = out["opportunity_id"]
    with pytest.raises(PermissionDenied):
        store.approve(oid, "strategist_agent", "agent", out["plan_hash"], "x")
    with pytest.raises(PermissionDenied):
        store.approve(oid, "Jane Doe", "approver", "0" * 64, "wrong plan")


def test_human_approval_enables_sandbox_record_only_for_that_plan(case, store):
    r, out = run_all(case, store)
    oid = out["opportunity_id"]
    # SCRIPTED test approver, not a real decision: the live path never simulates one
    store.approve(oid, "TEST approver (script)", "approver", out["plan_hash"], "test scope")
    assert r.resume(oid) == "SANDBOX_RECORDED"
    acts = store.crm_actions(oid)
    assert len(acts) == 1 and acts[0]["kind"] == "campaign_email_sandbox_record" and acts[0]["sandbox"] == 1
    assert r.resume(oid) == "SANDBOX_RECORDED" and len(store.crm_actions(oid)) == 1   # duplicate action ignored (idempotent)


def test_changing_the_plan_invalidates_a_prior_approval(case, store):
    r, out = run_all(case, store)
    oid = out["opportunity_id"]
    store.approve(oid, "TEST approver (script)", "approver", out["plan_hash"], "s")
    d = store.get(oid)
    store.update(oid, d["version"], {"pilot": {**d["pilot"], "message": d["pilot"]["message"] + " Extra line."}}, actor="x", role="agent")
    d = store.get(oid)
    assert d["approval"] is None and d["state"] == "DRAFT"
    with pytest.raises(PermissionDenied):
        r.tools.store.record_sandbox_action(oid, "late", actor="crm_agent")


def test_stale_review_version_is_refused(case, store):
    r = A.CampaignRun(case, store, persist=False)
    oid = r.create_dossier()
    res = r.tools.dispatch("strategist", "draft_action", {"opportunity_id": oid, "expected_version": 99}, oid)
    assert res["status"] == "blocked" and "expected v99" in res["provenance"]["reason"]


def test_outcome_only_after_a_recorded_action_and_counts_validated(case, store):
    r, out = run_all(case, store)
    oid = out["opportunity_id"]
    good = {"treated_n": 5000, "treated_buyers": 60, "holdout_n": 500, "holdout_buyers": 3, "observed_by": "TEST fixture, not evidence"}
    assert r.tools.dispatch("measurement", "log_outcome", {"opportunity_id": oid, "outcome": good}, oid)["status"] == "blocked"
    store.approve(oid, "TEST approver (script)", "approver", out["plan_hash"], "s")
    r.resume(oid)
    bad = {**good, "treated_buyers": 6000}
    assert r.tools.dispatch("measurement", "log_outcome", {"opportunity_id": oid, "outcome": bad}, oid)["status"] == "blocked"
    ok = r.tools.dispatch("measurement", "log_outcome", {"opportunity_id": oid, "outcome": good}, oid)
    assert ok["status"] == "ok" and ok["data"]["decision"] in ("EXPAND", "STOP", "INCONCLUSIVE")
    assert ok["data"]["outcome"]["tag"] == "OBSERVED" and store.get(oid)["state"] in ("EXPAND", "STOP", "INCONCLUSIVE")


def test_work_queue_blocks_the_send_step_and_creates_a_no_send_task(case, store):
    from mi.workflow.store import WorkQueue
    r, out = run_all(case, store)
    items = WorkQueue(store).list(out["opportunity_id"])
    by_status = {i["payload"]["title"][:25]: i["status"] for i in items}
    paid = [i for i in items if i["payload"]["kind"] == "paid_contact"]
    assert len(paid) == 1 and paid[0]["status"] == "BLOCKED_PENDING_APPROVAL"
    assert any("No-send path" in i["payload"]["title"] and i["status"] == "READY" and i["payload"]["budget_usd"] == 0 for i in items), by_status
    assert any("GEO" in i["payload"]["title"] for i in items)


def test_geo_status_is_pending_not_invented(case, store):
    r, out = run_all(case, store)
    geo = store.get(out["opportunity_id"])["research_output"]["geo"]
    from mi.seo.geo import check
    n = check()["complete_rows"]                       # the real log decides; a count is never typed here
    assert geo["answers_logged"] == n and geo["separate_from_hillstrom"] is True
    assert geo["status"].startswith("PENDING") if n < 20 else geo["status"] == "COMPLETE" and geo["limits"]


def test_research_abstains_on_unknowns(case, store):
    r, out = run_all(case, store)
    ab = {a["id"]: a for a in store.get(out["opportunity_id"])["research_output"]["abstained"]}
    assert {"U_BRAND", "U_CREATIVE", "U_CONSENT"} <= set(ab) and all(a["value"] is None for a in ab.values())


# ------------------------------------------------------------------ checker
def checker_on(case, store, mutate):
    r, out = run_all(case, store)
    d = store.get(out["opportunity_id"])
    mutate(d)
    return A.check_dossier(case, d)


def test_checker_passes_the_clean_dossier_but_blocks_launch(case, store):
    c = checker_on(case, store, lambda d: None)
    assert c["passed"] and not c["launch_ready"] and c["approval_required"] is True
    assert {"contribution margin UNKNOWN", "cost per e-mail UNKNOWN"} <= set(c["launch_blockers"])


def test_checker_rejects_assumption_shown_as_observed(case, store):
    def m(d):
        f = next(x for x in d["analyst_output"]["findings"] if x["claim_id"] == "CLM_SCENARIO_MENS_CENTRAL")
        f["tag"] = "OBSERVED"
    c = checker_on(case, store, m)
    assert not c["passed"] and any("tag" in p for p in c["problems"])


def test_checker_rejects_changed_value_or_fake_claim_or_null_as_zero(case, store):
    def m(d):
        fs = d["analyst_output"]["findings"]
        next(x for x in fs if x["claim_id"] == "CLM_BUYERS_MENS")["value"] = 300
        next(x for x in fs if x["claim_id"] == "CLM_MARGIN")["value"] = 0
        fs.append({"claim_id": "CLM_NOT_EXPORTED", "value": 1, "tag": "OBSERVED", "source_id": "SRC_HILLSTROM_2008_DATA"})
    c = checker_on(case, store, m)
    text = " ".join(c["problems"])
    assert not c["passed"] and "differs from the export value" in text and "UNKNOWN claim CLM_MARGIN" in text and "CLM_NOT_EXPORTED" in text


def test_checker_rejects_unknown_source_and_model_win_and_profit_wording(case, store):
    def m(d):
        d["analyst_output"]["findings"][0]["source_id"] = "SRC_FAKE"
        d["pilot"]["message"] += " The model beats the rule. A profit of $5,000 is expected. Unsubscribe here."
    c = checker_on(case, store, m)
    text = " ".join(c["problems"])
    assert "unknown source" in text and "model wins" in text and "profit" in text


def test_checker_rejects_model_exclusion_without_stable_gain(case, store):
    c = checker_on(case, store, lambda d: d["pilot"]["design"].update(model_used_to_exclude_anyone=True))
    assert any("exclude" in p for p in c["problems"])


def test_checker_rejects_approval_by_non_approver(case, store):
    c = checker_on(case, store, lambda d: d.update(approval={"approver": "bot", "role": "agent"}))
    assert any("approver role" in p for p in c["problems"])


def test_draft_guardrails_block_invented_offers(case, store, monkeypatch):
    r = A.CampaignRun(case, store, persist=False)
    oid = r.create_dossier()
    real = A.CampaignTools.build_pilot

    def bad(self):
        p = real(self)
        p["message"] += " 20% off, free shipping."
        return p
    monkeypatch.setattr(A.CampaignTools, "build_pilot", bad)
    res = r.tools.dispatch("strategist", "draft_action", {"opportunity_id": oid, "expected_version": 1}, oid)
    assert res["status"] == "blocked" and "unverifiable" in res["provenance"]["reason"]


def test_draft_message_is_clean_and_marked_not_sent(case, store):
    r, out = run_all(case, store)
    p = store.get(out["opportunity_id"])["pilot"]
    assert re.search("unsubscribe", p["message"], re.I) and not A._BANNED_DRAFT.search(p["message"])
    assert p["status"].startswith("DRAFT_REQUIRES_HUMAN") and p["design"]["model_used_to_exclude_anyone"] is False
    assert p["offer"]["status"].startswith("UNKNOWN") and p["budget"]["total"] is None          # unknown stays null, not zero


def test_pending_export_yields_no_dossier_and_no_numbers(tmp_path, store):
    pending = load_case(tmp_path / "absent.json")
    out = A.CampaignRun(pending, store, persist=False).run_to_checkpoint()
    assert out["status"] == "DATA_PENDING" and "opportunity_id" not in out
    with store._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM dossier_versions").fetchone()[0] == 0


def test_run_does_not_need_or_use_an_api_key(case, store, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert run_all(case, store)[1]["mode"] == "DETERMINISTIC_SPECIALISTS"


def test_grocery_store_and_dossiers_are_isolated(case, store):
    from mi.paths import DB_PATH
    assert str(A.CAMPAIGN_DB) != str(DB_PATH)
    run_all(case, store)
    assert str(store.path).endswith("c.sqlite")


# ------------------------------------------------------------------ view model, offline backup, app
def test_viewmodel_matches_export_and_refuses_a_rejected_case(case, tmp_path):
    from mi.consumer.viewmodel import backup_html, brief_markdown, build
    v = build(case)
    assert v["headline"]["value"] == pytest.approx(case.doc["buyer_impact_per_1000"]["value"])
    assert {a["arm"]: a["buyers"] for a in v["arms"]} == {"No E-Mail": 122, "Mens E-Mail": 267, "Womens E-Mail": 189}
    md, page = brief_markdown(v), backup_html(v)
    for text in (md, page):
        assert "MODEL_AHEAD_NOT_STABLE" in md and "267" in text and "unknown" in text.lower()
    assert "profit of" not in md.lower()
    with pytest.raises(ValueError):
        build(load_case(tmp_path / "absent.json"))


def test_streamlit_screen_renders_without_exception():
    st_testing = pytest.importorskip("streamlit.testing.v1")
    at = st_testing.AppTest.from_file(str(EXPORT_PATH.parents[1] / "app" / "buyer_decision.py"), default_timeout=60).run()
    assert not at.exception
    assert [m.value for m in at.metric][:2] == ["6.8", "Ahead, not stable"]


def test_live_check_is_pending_without_a_key_and_never_fabricates(case, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    out = A.live_analyst_check(case, persist=False)
    assert out["live_llm"] is False and out["status"].startswith("PENDING")


def test_lab_summary_reaches_brief_and_backup_from_generated_files(case):
    from mi.consumer.viewmodel import backup_html, brief_markdown, build, lab_summary
    lab = lab_summary()
    if lab is None:
        pytest.skip("model lab not run")
    assert lab["n_candidates"] == 8 and lab["selected"] == "S_LOGIT" and lab["challenger_shown_better"] is False
    v = build(case)
    assert "none was shown better" in brief_markdown(v) and "Model lab" in backup_html(v)
    assert lab["customers_needed"] > lab["n_test"]            # proving a gain needs more customers than the test split has


def test_geo_sheet_lists_the_panel_prompts_and_never_contains_answers():
    from mi.seo.sheet import build
    t = build()
    import json
    panel = json.loads((EXPORT_PATH.parents[1] / "data" / "seo" / "prompt_panel.json").read_text(encoding="utf-8"))
    assert all(q["text"] in t for q in panel["prompts"])
    assert "no answer may be written by the team" in t and "fresh chat" in t.lower()


def test_what_if_is_scenario_arithmetic_and_validates():
    from mi.consumer.viewmodel import what_if
    r = what_if(0.77, [0.49, 1.05], margin=0.30, cost_per_email=0.02, contacts=1000)
    assert abs(r["contribution"] - 1000 * (0.77 * 0.30 - 0.02)) < 1e-6
    assert r["kind"] == "SCENARIO, NOT MEASURED PROFIT" and r["verdict"] == "PAYS_EVEN_AT_LOW_END"
    assert what_if(0.77, [0.49, 1.05], 0.30, 0.50, 1000)["verdict"] == "DOES_NOT_PAY_EVEN_AT_HIGH_END"
    assert what_if(0.77, [0.49, 1.05], 0.30, 0.20, 1000)["verdict"] == "UNCERTAIN_INTERVAL_INCLUDES_ZERO"
    import pytest
    with pytest.raises(ValueError):
        what_if(0.77, [0.49, 1.05], 1.5, 0.02, 1000)


def test_share_curve_arithmetic():
    from mi.consumer.viewmodel import share_curve
    r = share_curve([0.5, 1.0], [10.0, 5.0], [5.0, 2.0], [15.0, 8.0], 5.0, spend_per_buyer=100.0, margin=0.5, cost_per_email=0.1, pool=1000)
    assert abs(r["model"][0] - 1000 * 0.5 * (0.010 * 100 * 0.5 - 0.1)) < 1e-9
    assert r["best_share"] == 0.5 and r["kind"] == "SCENARIO, NOT MEASURED PROFIT"
    assert all(h >= l for h, l in zip(r["high"], r["low"]))


def test_proposed_draft_guardrails_and_pending_strategist(case, monkeypatch):
    assert A.check_proposed_draft("A look at our new men's line", "Hello. Unsubscribe: [unsubscribe link]") == []
    bad = A.check_proposed_draft("Save 20% today", "Limited time! Free shipping")
    assert any("unsubscribe" in p for p in bad) and any("unverifiable" in p for p in bad)
    assert A.check_proposed_draft("x" * 200, "[unsubscribe link]")
    assert A.check_proposed_draft("Hi", "the model beats random [unsubscribe link]")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = A.live_strategist_check(case, persist=False)
    assert out["live_llm"] is False and out["status"].startswith("PENDING")


def test_diff_cases_detects_changes_and_identity(case):
    import copy
    from mi.consumer.viewmodel import diff_cases
    a = case.doc
    assert diff_cases(a, a)["identical"] is True
    b = copy.deepcopy(a)
    b["claims"][0]["value"] = (b["claims"][0]["value"] or 0) + 1
    b["model_vs_baselines"]["verdict"] = "CHANGED_FOR_TEST"
    d = diff_cases(a, b)
    assert not d["identical"] and d["changed_claims"][0]["claim_id"] == a["claims"][0]["claim_id"]
    assert any(f["field"] == "verdict" and f["new"] == "CHANGED_FOR_TEST" for f in d["changed_fields"])
    b["claims"].pop()
    assert len(diff_cases(a, b)["removed_claims"]) == 1
