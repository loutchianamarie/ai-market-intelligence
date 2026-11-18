"""Demo-readiness regressions: GEO state drives the work items, and old checks/traces cannot pass for the current export.

Everything uses throwaway stores and tmp files. Nothing here touches the live traces, dossiers or the export.
"""
import json
import re
import shutil

import pytest

from mi.consumer import advisor as A
from mi.consumer import viewmodel as VM
from mi.consumer.adapter import CHECKSUM_PATH, EXPORT_PATH, load_case
from mi.paths import DOCS, REPORTS
from mi.seo import geo
from mi.workflow.store import DossierStore, WorkQueue

from tests.conftest import needs_artifacts

_orig_state = geo.geo_state
NEW_SHA = "e" * 64
OLD_SHA = "a" * 64


# ------------------------------------------------------------------ GEO state
@pytest.fixture
def logs(tmp_path):
    """Three answer logs built from the real frozen-panel log: complete (20 rows), partial (12 rows), empty (header only)."""
    lines = geo.LOG.read_text(encoding="utf-8").splitlines()
    out = {}
    out["complete"] = tmp_path / "complete.csv"
    shutil.copy(geo.LOG, out["complete"])
    out["partial"] = tmp_path / "partial.csv"
    out["partial"].write_text("\n".join(lines[:13]) + "\n", encoding="utf-8")   # header + 12 answers
    out["empty"] = tmp_path / "empty.csv"
    out["empty"].write_text(lines[0] + "\n", encoding="utf-8")
    return out


def test_complete_panel_state(logs):
    s = geo.geo_state(logs["complete"])
    assert s["complete"] and s["answers_logged"] == 20 and s["complete_rows"] == 20 and s["answers_remaining"] == 0
    li = s["by_intent"]["Learn"]
    assert (li["n"], li["mentioned"], li["recommended"]) == (8, 5, 0)          # recommended 0/8 but mentioned 5/8: not zero visibility
    assert s["by_intent"]["Browse"]["recommended"] == 6 and s["by_intent"]["Buy"]["recommended"] == 6
    assert (s["mention_rate"]["num"], s["recommendation_rate"]["num"]) == (17, 12)
    assert s["answers_citing_urls"] == 14 and s["region_set"] is False


def test_partial_and_empty_panels_are_not_complete(logs):
    p, e = geo.geo_state(logs["partial"]), geo.geo_state(logs["empty"])
    assert not p["complete"] and p["answers_logged"] == 12 and p["answers_remaining"] == 8
    assert not e["complete"] and e["answers_logged"] == 0 and e["answers_remaining"] == 20


def test_completed_panel_never_produces_a_collect_20_task(logs):
    t = geo.geo_task(geo.geo_state(logs["complete"]))
    assert t["phase"] == "REVIEW"
    text = json.dumps(t).lower()
    assert not re.search(r"collect (the )?(remaining )?\d+|fresh-chat", text)
    assert "collect the remaining" not in text
    note = t["advisor_note"]
    for needle in ("17/20", "12/20", "recommended 0/8", "mentioned 5/8", "not the dataset retailer", "no traffic, conversion or sales effect",
                   "region not set", "6 answers made without web search", "human approval"):
        assert needle in note, needle
    assert geo.geo_pending_phrase(geo.geo_state(logs["complete"])) == "team scoring of the GEO audit and a ChatGPT/Gemini retest"


def test_incomplete_panel_still_produces_a_collection_task(logs):
    t = geo.geo_task(geo.geo_state(logs["partial"]))
    assert t["phase"] == "COLLECT" and t["title"] == "Collect the remaining 8 of 20 GEO answers"
    assert geo.geo_task(geo.geo_state(logs["empty"]))["title"] == "Collect the remaining 20 of 20 GEO answers"


@needs_artifacts
@pytest.mark.parametrize("which,phase", [("complete", "REVIEW"), ("partial", "COLLECT")])
def test_grocery_work_queue_follows_geo_state_without_duplicates(tmp_path, logs, which, phase):
    from mi.agents.coordinator import AgentOutput, Run, research_plan
    store = DossierStore(tmp_path / "g.sqlite")
    run = Run(store)
    run.persist_traces = False                       # throwaway store: never touch the live trace
    run.geo_override = geo.geo_state(logs[which])
    oid = run.run_to_checkpoint()
    items = {w["idempotency_key"].split(":")[-1]: w for w in WorkQueue(store).list(oid)}
    assert items["R2"]["payload"]["phase"] == phase
    titles = " | ".join(w["payload"]["title"] for w in items.values()).lower()
    if phase == "REVIEW":
        assert "collect 20" not in titles and "20 fresh-chat" not in titles
        assert items["R2"]["status"] == "READY" and items["R2"]["payload"]["budget_usd"] == 0
    else:
        assert "collect the remaining 8" in titles
    assert items["CONTENT1"]["status"] == "BLOCKED_PENDING_APPROVAL"          # publication always needs a named approver
    before = len(WorkQueue(store).list(oid))
    run.build_work_queue(oid, AgentOutput(role="portfolio", mode="deterministic"))   # rerun on the same dossier
    assert len(WorkQueue(store).list(oid)) == before                          # idempotency keys: no duplicates
    plan = {x["id"]: x for x in research_plan(run.geo_override)}
    assert ("Review the completed 20-answer" in plan["R2"]["task"]) == (phase == "REVIEW")


@pytest.mark.skipif(not EXPORT_PATH.exists(), reason="campaign export not present")
def test_campaign_work_items_follow_geo_state(tmp_path, logs, monkeypatch):
    case = load_case()
    store = DossierStore(tmp_path / "c.sqlite")
    plan = A.CampaignTools(case, store).t_read_marketing_plan()["data"]
    for which, phase in (("complete", "REVIEW"), ("partial", "COLLECT")):
        monkeypatch.setattr(geo, "geo_state", lambda which=which: _orig_state(logs[which]))
        item = A.CampaignRun.work_items(plan)["R_GEO"]
        assert item["phase"] == phase
        assert ("collect 20" in item["title"].lower()) is False




# ------------------------------------------------------------------ stale live check and stale trace
def _write_check(tmp_path, sha, passed=True):
    p = tmp_path / "check.json"
    p.write_text(json.dumps({"live_llm": passed, "matches_export": passed, "model": "claude-opus-5-5", "findings_returned": 5, "export_sha256": sha}), encoding="utf-8")
    return p


def test_live_check_on_older_export_is_historical_not_validation(tmp_path):
    r = VM.live_check_status(NEW_SHA, _write_check(tmp_path, OLD_SHA))
    assert r["state"] == "HISTORICAL"
    assert "NOT validated for the loaded export" in r["text"] and "PENDING for this export" in r["text"]
    assert "all match the export" not in r["text"] and "check passed:" not in r["text"].lower()
    assert OLD_SHA[:8] in r["text"] and NEW_SHA[:8] in r["text"]


def test_live_check_on_same_export_is_current(tmp_path):
    r = VM.live_check_status(NEW_SHA, _write_check(tmp_path, NEW_SHA))
    assert r["state"] == "CURRENT" and "passed on this export" in r["text"]


def test_missing_or_failed_live_check_is_pending(tmp_path):
    assert VM.live_check_status(NEW_SHA, tmp_path / "nope.json")["state"] == "NONE"
    assert VM.live_check_status(NEW_SHA, _write_check(tmp_path, NEW_SHA, passed=False))["state"] == "NOT_PASSED"
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert VM.live_check_status(NEW_SHA, p)["state"] == "NONE"


def test_trace_is_current_only_for_its_own_export():
    assert VM.trace_is_current({"export_sha256": NEW_SHA}, NEW_SHA)
    assert not VM.trace_is_current({"export_sha256": OLD_SHA}, NEW_SHA)
    assert not VM.trace_is_current({}, NEW_SHA) and not VM.trace_is_current(None, NEW_SHA)


@pytest.mark.skipif(not EXPORT_PATH.exists(), reason="campaign export not present")
def test_saved_demo_artifacts_agree_with_the_current_export():
    """The files the demo shows must be built from the export on disk (regenerate with the commands in docs/presentation/DEMO_5MIN.md)."""
    case = load_case()
    assert case.ok and case.sha256 == CHECKSUM_PATH.read_text().split()[0]
    trace = VM.latest_trace()
    assert VM.trace_is_current(trace, case.sha256), "saved campaign trace is from another export: run python -m mi.consumer.advisor run"
    assert trace["approval"] is None and trace["state"] == "REVIEW_REQUESTED"          # a rehearsal is never a recorded human approval
    assert case.sha256 in (DOCS / "marketing_decision_brief.md").read_text(encoding="utf-8")
    assert case.sha256[:16] in (REPORTS / "buyer_decision_backup.html").read_text(encoding="utf-8")
    # whatever the live-check file says, the app wording must follow the hash comparison
    status = VM.live_check_status(case.sha256)
    recorded = json.loads(VM.LIVE_CHECK.read_text(encoding="utf-8")).get("export_sha256") if VM.LIVE_CHECK.exists() else None
    if recorded and recorded != case.sha256:
        assert status["state"] == "HISTORICAL"


def test_generated_text_does_not_ask_to_collect_answers_that_exist():
    """Generated docs that follow the GEO log must not tell the team to collect the 20 answers once the panel is complete."""
    if not geo.geo_state()["complete"]:
        pytest.skip("GEO panel not complete in this checkout")
    stale = re.compile(r"(collect (the )?20 (real )?(GEO|fresh)|(?<![\d/])0/20 (answers|PENDING)|(?<!\d)0 of 20 (real )?(GEO )?answers)", re.I)
    for name in ("marketing_decision_brief.md", "campaign_marketing_brief.md", "marketing_brief.md", "opportunity_cards.md",
                 "buyer_outcomes.md", "decision_brief.md", "geo_collection_sheet.md", "QA_PREP.md", "demo_runbook.md", "WHATS_LEFT.md"):
        p = DOCS / name
        if p.exists():
            hit = stale.search(p.read_text(encoding="utf-8", errors="replace"))
            assert not hit, f"{name} still says: {hit.group(0)}"


# ------------------------------------------------------------------ static fallback
@needs_artifacts
def test_static_fallback_is_built_from_the_dossier_and_states_the_limits(tmp_path, logs):
    from mi.agents.coordinator import Run
    from mi.decision import demo_backup
    store = DossierStore(tmp_path / "f.sqlite")
    run = Run(store)
    run.persist_traces = False
    run.geo_override = geo.geo_state(logs["complete"])
    oid = run.run_to_checkpoint()
    model = json.loads((REPORTS / "model_report.json").read_text(encoding="utf-8"))
    port = json.loads((REPORTS / "portfolio.json").read_text(encoding="utf-8"))
    page = demo_backup.render(store, oid, model, port, geo.geo_state(logs["complete"]))
    assert oid in page and "DEFER FUNDING / NO SPEND WHILE TERMS ARE UNCONFIRMED" in page and ">NONE<" in page
    assert "BLOCKED_PENDING_APPROVAL" in page and "nothing is sent, spent or published" in page
    assert "Mentioned 17/20, recommended 12/20" in page and "Learn: mentioned 5/8, recommended 0/8" in page
    assert "not the dataset retailer" in page and "different retailer and dataset" in page
    assert "collect" not in page.lower().replace("answers collected", "")
