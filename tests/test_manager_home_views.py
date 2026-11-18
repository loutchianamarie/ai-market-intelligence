"""The three-view manager home: every case and view renders, the consultant view follows the file verdicts, and grocery figures come from the saved reports."""
import json
import shutil

import pytest

from mi.consumer import consultant_file as CF
from mi.consumer import grocery_view as GV
from mi.paths import REPORTS, ROOT

from tests.conftest import needs_artifacts

APP = str(ROOT / "app" / "manager_home.py")
CASES = ("Grocery decision", "E-mail experiment")
VIEWS = ("1 · Trained results", "2 · Advisor and work", "3 · AI consultant (ConsultAI)")


def run_app(case=CASES[0], view=VIEWS[0]):
    st_testing = pytest.importorskip("streamlit.testing.v1")
    at = st_testing.AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.session_state["case"], at.session_state["view"] = case, view
    at.run()
    return at


def text(at):
    return " ".join([m.value for m in at.markdown] + [e.value for e in at.error] + [i.value for i in at.info] + [w.value for w in at.warning])


@needs_artifacts
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("view", VIEWS)
def test_every_case_and_view_renders_without_exception(case, view):
    at = run_app(case, view)
    assert not at.exception, at.exception
    assert "None" not in [m.value.strip() for m in at.markdown]                # no stray expression rendered by Streamlit's magic


@needs_artifacts
def test_grocery_results_view_reads_the_saved_reports():
    gv = GV.grocery_view()
    model = json.loads((REPORTS / "model_report.json").read_text(encoding="utf-8"))
    sel = "model_" + model["selected_model"]
    assert gv["model"]["ap"] == model["test"][sel]["AP"] and gv["model"]["rule"] == model["test"]["rule_repeat"]["AP"]
    assert gv["decision"]["recommended_base"].startswith("NONE") and gv["plans"][0]["is_none"]
    assert all(p["net_base"] <= 0 for p in gv["plans"])                          # no modelled plan pays under the assumptions
    assert gv["buyers"]["expected"] < gv["buyers"]["scenario_base"] < gv["buyers"]["break_even"]       # expected, extra (scenario) and break-even stay distinct numbers
    at = run_app(CASES[0], VIEWS[0])
    t = text(at)
    assert f"{gv['model']['ap']:.3f}" in t and "purchase propensity, not coupon response" in t and "We cannot say" in t
    assert "Hillstrom" not in t and "e-mail" not in t.lower().replace("e-mail case", "")        # the e-mail effect never appears on the grocery screen


@needs_artifacts
def test_email_results_view_still_shows_the_randomized_result_and_the_explanation():
    t = text(run_app(CASES[1], VIEWS[0]))
    assert "RANDOMIZED OBSERVATION" in t and "HELD-OUT MODEL ESTIMATE" in t and "We cannot say" in t and "e10868f2" in t


def _stage(tmp_path, monkeypatch, doc, sidecar=True):
    p = tmp_path / "consultant_review.latest.json"
    raw = json.dumps(doc).encode("utf-8")
    p.write_bytes(raw)
    import hashlib
    sp = tmp_path / "consultant_review.latest.sha256"
    if sidecar:
        sp.write_text(hashlib.sha256(raw).hexdigest() + "\n")
    monkeypatch.setattr(CF, "REVIEW_PATH", p)
    monkeypatch.setattr(CF, "REVIEW_SHA", sp)


@needs_artifacts
def test_consultant_view_without_a_file_says_so_and_invents_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "REVIEW_PATH", tmp_path / "none.json")
    t = text(run_app(CASES[0], VIEWS[2]))
    assert "has not delivered a review file" in t and "reference metrics match" not in t


@needs_artifacts
@pytest.mark.skipif(not CF.MANIFEST_PATH.exists(), reason="bundle manifest not built")
def test_consultant_view_shows_a_valid_file_and_labels_a_sample(tmp_path, monkeypatch):
    _stage(tmp_path, monkeypatch, CF.sample_review())
    t = text(run_app(CASES[0], VIEWS[2]))
    assert "SAMPLE FILE" in t and "9 of 9" in t and "OFFLINE_DETERMINISTIC" in t and "PENDING_HUMAN" in t
    d = CF.sample_review()
    d["is_sample"] = False
    d["review_id"] = "REAL-1"
    _stage(tmp_path, monkeypatch, d)
    t = text(run_app(CASES[0], VIEWS[2]))
    assert "SAMPLE FILE" not in t and "REAL-1" in t and "reference metrics match our own computation" in t


@needs_artifacts
@pytest.mark.skipif(not CF.MANIFEST_PATH.exists(), reason="bundle manifest not built")
def test_consultant_view_refuses_a_tampered_or_stale_file_and_hides_numbers(tmp_path, monkeypatch):
    d = CF.sample_review()
    next(m for m in d["metrics"] if m["metric_id"] == "distinct_buyers_h1__YOGURT")["value"] = 9999
    _stage(tmp_path, monkeypatch, d)
    t = text(run_app(CASES[0], VIEWS[2]))
    assert "REFUSED" in t and "numbers are hidden" in t and "9,999" not in t and "9999" not in t
    d = CF.sample_review()
    d["input"]["bundle_manifest_sha256"] = "b" * 64
    _stage(tmp_path, monkeypatch, d)
    t = text(run_app(CASES[0], VIEWS[2]))
    assert "STALE" in t and "numbers are hidden" in t
    _stage(tmp_path, monkeypatch, CF.sample_review(), sidecar=False)
    assert "REFUSED" in text(run_app(CASES[0], VIEWS[2]))


@needs_artifacts
def test_manager_page_has_no_action_control():
    src = (ROOT / "app" / "manager_home.py").read_text(encoding="utf-8")
    assert "st.button" not in src and "form_submit_button" not in src and "send_email" not in src and "record_sandbox_action" not in src


def test_static_fallback_consultant_section_is_honest():
    from mi.decision.demo_backup import consultant_html
    assert "not shown" in consultant_html(None) and "invented" in consultant_html(None)
    if CF.MANIFEST_PATH.exists():
        import hashlib
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "r.json"
            raw = json.dumps(CF.sample_review()).encode("utf-8")
            p.write_bytes(raw)
            p.with_suffix(".sha256").write_text(hashlib.sha256(raw).hexdigest())
            r = CF.load_review(p)
        html = consultant_html(r)
        assert "SAMPLE FILE" in html and "9 of 9" in html and "OFFLINE_DETERMINISTIC" in html and "PENDING_HUMAN" in html
