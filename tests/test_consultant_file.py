"""consultant_review.v1: the marketing web accepts a ConsultAI file only if it is checksummed, schema-valid, current and RECONCILES with our own
reference metrics. Every refusal path is tested on tmp copies; the real reports/ folder is never touched."""
import copy
import hashlib
import json

import pytest

from mi.consumer import consultant_file as CF

pytestmark = pytest.mark.skipif(not CF.MANIFEST_PATH.exists(), reason="bundle manifest not built")


def write(tmp_path, doc, name="review.json", sidecar=True, sha=None):
    p = tmp_path / name
    raw = json.dumps(doc).encode("utf-8")
    p.write_bytes(raw)
    if sidecar:
        p.with_suffix(".sha256").write_text((sha or hashlib.sha256(raw).hexdigest()) + "\n")
    return p


def good():
    return copy.deepcopy(CF.sample_review())


def test_a_good_file_is_ok_and_reconciles(tmp_path):
    r = CF.load_review(write(tmp_path, good()))
    assert r.ok and r.reconciliation["total"] == 9 and r.reconciliation["matched"] == 9 and r.is_sample


def test_absent_file(tmp_path):
    assert CF.load_review(tmp_path / "nope.json").status == "ABSENT"


def test_missing_or_wrong_checksum_is_refused(tmp_path):
    assert CF.load_review(write(tmp_path, good(), sidecar=False)).status == "REFUSED"
    r = CF.load_review(write(tmp_path, good(), sha="0" * 64))
    assert r.status == "REFUSED" and "SHA-256 mismatch" in r.reasons[0]


def test_a_metric_that_differs_from_our_computation_is_refused(tmp_path):
    d = good()
    next(m for m in d["metrics"] if m["metric_id"] == "distinct_buyers_h1__YOGURT")["value"] += 1     # a changed value, checksum recomputed
    r = CF.load_review(write(tmp_path, d))
    assert r.status == "REFUSED" and "distinct_buyers_h1__YOGURT" in " ".join(r.reasons) and r.reconciliation["mismatches"][0]["reference"] == 1196


def test_lines_reported_as_buyers_are_caught(tmp_path):
    d = good()
    next(m for m in d["metrics"] if m["metric_id"] == "distinct_buyers_h1__YOGURT")["value"] = 13405    # the line count (lines are not buyers)
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"


def test_a_different_bundle_is_stale_and_hides_numbers(tmp_path):
    d = good()
    d["input"]["bundle_manifest_sha256"] = "a" * 64
    r = CF.load_review(write(tmp_path, d))
    assert r.status == "STALE" and "numbers hidden" in r.reasons[0]


def test_approval_must_stay_pending_human(tmp_path):
    d = good()
    d["action_card"]["approval_state"] = "APPROVED"
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"
    d = good()
    d["action_card"]["sandbox_only"] = False
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"
    d = good()
    d["roles"][-1]["status"] = "OK"
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"


def test_more_than_five_roles_is_refused(tmp_path):
    d = good()
    d["roles"] += [{"role": "analyst", "tools": [], "status": "OK", "summary": "x"} for _ in range(3)]
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"


def test_a_metric_without_a_formula_or_an_unknown_reference_is_refused(tmp_path):
    d = good()
    d["metrics"][0]["formula"] = ""
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"
    d = good()
    d["headline"]["numbers"][0]["metric_id"] = "invented_metric"
    r = CF.load_review(write(tmp_path, d))
    assert r.status == "REFUSED" and "unknown metric" in " ".join(r.reasons)


def test_run_mode_rules(tmp_path):
    d = good()
    d["run"]["mode"] = "LIVE_LLM"                                    # live without model id and cost
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"
    d["run"].update(model_id="claude-opus-5-5", cost_usd=0.31, calls=7)
    assert CF.load_review(write(tmp_path, d)).ok
    d = good()
    d["run"]["calls"] = 3                                            # offline but claims model calls
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"


def test_extra_fields_and_a_wrong_case_are_refused(tmp_path):
    d = good()
    d["surprise"] = 1
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"
    d = good()
    d["input"]["case_id"] = "HILLSTROM_EMAIL_2008"
    assert CF.load_review(write(tmp_path, d)).status == "REFUSED"


def test_the_committed_sample_is_valid_and_marked_as_a_sample():
    if not CF.SAMPLE_PATH.exists():
        pytest.skip("sample not written")
    r = CF.load_review(CF.SAMPLE_PATH)
    assert r.ok and r.is_sample and r.doc["review_id"].startswith("SAMPLE")
