"""QA of the GEO audit: the real log passes, and every rule fails when its data is broken on purpose."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from mi.paths import SEO
from mi.seo import geo, qa


@pytest.fixture()
def seo_copy(tmp_path):
    log, panel = tmp_path / "answer_log.csv", tmp_path / "prompt_panel.json"
    shutil.copy(geo.LOG, log)
    shutil.copy(geo.PANEL, panel)
    return log, panel


def _rows(log):
    with open(log, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return list(r), r.fieldnames


def _write(log, rows, fields):
    with open(log, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)


def _status(rep, cid):
    return next(c["status"] for c in rep["checks"] if c["id"] == cid)


def test_real_log_has_no_failed_check():
    rep = qa.run_qa()
    failed = [c for c in rep["checks"] if c["status"] == "FAIL"]
    assert not failed, failed
    assert rep["total"] == 20


def test_rates_match_a_plain_pandas_count_of_the_csv():
    d = pd.read_csv(SEO / "answer_log.csv", dtype=str).fillna("")
    y = lambda col: d[col].str.lower().isin(["y", "yes", "1", "true"]).sum()  # noqa: E731
    res = geo.analyze(geo.read_log(), geo.load_panel())
    assert res["mention_rate"]["num"] == y("brand_mentioned")
    assert res["recommendation_rate"]["num"] == y("brand_recommended")
    assert res["primary_pick_rate"]["num"] == y("brand_top_pick")
    assert res["answers_logged"] == len(d) == 20


@pytest.mark.parametrize("cid,mutate", [
    ("Q06", lambda r: r[0].update(brand_top_pick="Y", brand_recommended="N", brand_mentioned="Y")),
    ("Q05", lambda r: r[0].update(brand_mentioned="maybe")),
    ("Q08", lambda r: r[1].update(raw_answer_sha256=r[0]["raw_answer_sha256"])),
    ("Q09", lambda r: r[0].update(timestamp_utc="yesterday afternoon")),
    ("Q09", lambda r: r[0].update(timestamp_utc="2099-01-01T00:00:00Z")),
    ("Q10", lambda r: r[0].update(assistant_version="Claude Sonnet 4 (older)")),
    ("Q11", lambda r: r[0].update(intent="Buy")),
    ("Q12", lambda r: r[0].update(cited_urls="not a url")),
    ("Q04", lambda r: r[0].update(collected_by="")),
])
def test_each_rule_catches_its_break(seo_copy, cid, mutate):
    log, panel = seo_copy
    rows, fields = _rows(log)
    mutate(rows)
    _write(log, rows, fields)
    rep = qa.run_qa(log, panel)
    assert _status(rep, cid) == "FAIL", rep["checks"]
    assert rep["verdict"] == "FAIL"


def test_missing_and_duplicate_rows_fail_coverage(seo_copy):
    log, panel = seo_copy
    rows, fields = _rows(log)
    _write(log, rows[1:], fields)  # drop one answer
    assert _status(qa.run_qa(log, panel), "Q03") == "FAIL"
    _write(log, rows + [rows[0]], fields)  # duplicate one
    assert _status(qa.run_qa(log, panel), "Q03") == "FAIL"


def test_editing_a_prompt_after_collection_breaks_the_freeze(seo_copy):
    log, panel = seo_copy
    p = json.loads(panel.read_text(encoding="utf-8"))
    p["prompts"][0]["text"] = "A different question than the one that was asked."
    panel.write_text(json.dumps(p), encoding="utf-8")
    assert _status(qa.run_qa(log, panel), "Q02") == "FAIL"


def test_competitor_recommended_but_not_named_is_flagged(seo_copy):
    log, panel = seo_copy
    rows, fields = _rows(log)
    rows[0].update(competitors_named="Target", competitors_recommended="Walmart")
    _write(log, rows, fields)
    assert _status(qa.run_qa(log, panel), "Q07") == "WARN"


def test_typed_counts_in_the_page_source_are_caught(tmp_path):
    src = tmp_path / "app.py"
    src.write_text('st.caption("Recommended in 0/8 Learn answers")', encoding="utf-8")
    assert _status(qa.run_qa(app_source=src), "Q18") == "FAIL"
    src.write_text("st.caption(f\"Recommended in {n}/{m} Learn answers\")", encoding="utf-8")
    assert _status(qa.run_qa(app_source=src), "Q18") == "PASS"


def test_the_real_app_source_has_no_typed_geo_counts():
    assert _status(qa.run_qa(), "Q18") == "PASS"


def test_workbook_has_every_answer_and_the_same_rates(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    out = qa.export_xlsx(tmp_path / "a.xlsx")
    wb = openpyxl.load_workbook(out)
    assert {"README", "Questions", "Answers", "Rates", "Share", "Source_gap", "Actions", "QA"} <= set(wb.sheetnames)
    assert wb["Answers"].max_row == 21  # header + 20 answers
    assert wb["Questions"].max_row == 11  # header + 10 prompts
    rates = pd.read_excel(out, sheet_name="Rates")
    allrow = rates[rates.group == "ALL"].iloc[0]
    res = geo.analyze(geo.read_log(), geo.load_panel())
    assert (allrow.mentioned, allrow.recommended, allrow.top_pick) == (
        res["mention_rate"]["num"], res["recommendation_rate"]["num"], res["primary_pick_rate"]["num"])
    by_intent = rates[rates.group == "intent"].set_index("value")
    assert int(by_intent.loc["Learn", "answers"]) == res["by_intent"]["Learn"]["n"]
    hashes = pd.read_excel(out, sheet_name="Answers")["raw_answer_sha256"]
    assert hashes.is_unique and hashes.str.len().eq(64).all()
    # actions are left unscored for the team
    act = pd.read_excel(out, sheet_name="Actions")
    assert act["impact_1to5"].isna().all() and act["effort_1to5"].isna().all()


def test_export_never_adds_an_answer_that_is_not_in_the_log(tmp_path):
    pytest.importorskip("openpyxl")
    out = qa.export_xlsx(tmp_path / "b.xlsx")
    ans = pd.read_excel(out, sheet_name="Answers")
    log = pd.read_csv(geo.LOG, dtype=str)
    assert set(ans["raw_answer_sha256"]) == set(log["raw_answer_sha256"])
