"""Read-only loader for the ConsultAI consultant review of the shared grocery bundle (contract consultant_review.v1).

  python -m mi.consumer.consultant_file            print the verdict for reports/consultant_review.latest.json
  python -m mi.consumer.consultant_file sample     rewrite docs/contracts/consultant_review.sample.json (deterministic, marked is_sample)

Verdicts
  ABSENT   no file: the web says so and shows nothing from ConsultAI
  STALE    the review was built on a different bundle than the current manifest: numbers are hidden
  REFUSED  bad checksum, schema violation, a metric that does not match our own computation, an unknown metric id, or a rule broken
  OK       everything above passed; ``reconciliation`` says how many metrics were checked against the manifest

The marketing web never recomputes ConsultAI's numbers. It RECONCILES them with the reference metrics that our own code wrote into the bundle
manifest: counts must match exactly, sums to a relative 1e-6. Nothing here sends, spends or approves anything.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from mi.paths import DOCS, REPORTS

REVIEW_PATH = REPORTS / "consultant_review.latest.json"
REVIEW_SHA = REPORTS / "consultant_review.latest.sha256"
MANIFEST_PATH = REPORTS / "grocery_bundle_manifest.json"
SCHEMA_PATH = DOCS / "contracts" / "consultant_review.v1.schema.json"
SAMPLE_PATH = DOCS / "contracts" / "consultant_review.sample.json"
MODE_TEXT = {"OFFLINE_DETERMINISTIC": "deterministic, no model call",
             "LIVE_LLM": "live model run (interpretation only; numbers come from computed metrics)"}


@dataclass
class ReviewResult:
    status: str                     # OK | REFUSED | STALE | ABSENT
    reasons: list = field(default_factory=list)
    doc: dict | None = None
    sha256: str | None = None
    reconciliation: dict = field(default_factory=lambda: {"matched": 0, "total": 0, "mismatches": []})

    @property
    def ok(self) -> bool:
        return self.status == "OK"

    @property
    def is_sample(self) -> bool:
        return bool(self.doc and self.doc.get("is_sample"))

    def metric(self, metric_id: str) -> dict:
        return next(m for m in self.doc["metrics"] if m["metric_id"] == metric_id)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if float(a).is_integer() and float(b).is_integer() and isinstance(a, int) and isinstance(b, int):
            return a == b                                   # counts match exactly
        return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
    return a == b


def load_manifest(path: Path | None = None) -> dict | None:
    p = Path(path) if path else MANIFEST_PATH
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def reconcile(doc: dict, manifest: dict) -> dict:
    ref = {m["metric_id"]: m for m in manifest["reference_metrics"]}
    matched, mism = 0, []
    for m in doc["metrics"]:
        r = ref.get(m["metric_id"])
        if r is None:
            continue
        if _close(m["value"], r["value"]):
            matched += 1
        else:
            mism.append({"metric_id": m["metric_id"], "consultant": m["value"], "reference": r["value"]})
    total = sum(1 for m in doc["metrics"] if m["metric_id"] in ref)
    return {"matched": matched, "total": total, "mismatches": mism}


def load_review(path: Path | None = None, sha_path: Path | None = None, manifest_path: Path | None = None, schema_path: Path | None = None) -> ReviewResult:
    p = Path(path) if path else REVIEW_PATH
    if not p.exists():
        return ReviewResult("ABSENT", [f"{p.name} not found: ConsultAI has not delivered a review"])
    raw = p.read_bytes()
    sha = _sha(raw)
    sp = Path(sha_path) if sha_path else (REVIEW_SHA if p == REVIEW_PATH else p.with_suffix(".sha256"))
    want = sp.read_text(encoding="utf-8").split()[0].lower() if sp.exists() and sp.read_text(encoding="utf-8").split() else None
    if not want:
        return ReviewResult("REFUSED", ["no SHA-256 sidecar to verify the file against"], sha256=sha)
    if sha != want:
        return ReviewResult("REFUSED", [f"SHA-256 mismatch: file {sha[:12]}... expected {want[:12]}... (edited or stale)"], sha256=sha)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return ReviewResult("REFUSED", [f"not valid JSON: {e}"], sha256=sha)
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(schema_path) if schema_path else SCHEMA_PATH).read_text(encoding="utf-8"))
    errs = sorted(f"{'/'.join(map(str, e.absolute_path)) or 'top level'}: {e.message}" for e in Draft202012Validator(schema).iter_errors(doc))
    if errs:
        return ReviewResult("REFUSED", errs[:8], sha256=sha)
    problems = []
    ids = [m["metric_id"] for m in doc["metrics"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate metric ids")
    known = set(ids)
    for n in doc["headline"]["numbers"]:
        if n["metric_id"] not in known:
            problems.append(f"headline refers to unknown metric {n['metric_id']!r}")
    for o in doc["options"]:
        problems += [f"option {o['option']!r} refers to unknown metric {i!r}" for i in o["metric_ids"] if i not in known]
    run = doc["run"]
    if run["mode"] == "LIVE_LLM" and (not run["model_id"] or run["cost_usd"] is None):
        problems.append("a LIVE_LLM run must record its model id and cost")
    if run["mode"] == "OFFLINE_DETERMINISTIC" and (run["model_id"] or run["calls"]):
        problems.append("an OFFLINE_DETERMINISTIC run cannot record model calls")
    if sum(1 for r in doc["roles"] if r["role"] == "human") and any(r["status"] != "PENDING_HUMAN" for r in doc["roles"] if r["role"] == "human"):
        problems.append("the human step must stay PENDING_HUMAN")
    if problems:
        return ReviewResult("REFUSED", problems, doc, sha)
    man = load_manifest(manifest_path)
    if man is None:
        return ReviewResult("STALE", ["the bundle manifest is not available here, so the review cannot be tied to the current data"], doc, sha)
    man_sha = _sha((Path(manifest_path) if manifest_path else MANIFEST_PATH).read_bytes())
    if doc["input"]["bundle_manifest_sha256"] != man_sha:
        return ReviewResult("STALE", [f"built on bundle {doc['input']['bundle_manifest_sha256'][:12]}..., current bundle is {man_sha[:12]}...: numbers hidden"], doc, sha)
    rec = reconcile(doc, man)
    if rec["mismatches"]:
        return ReviewResult("REFUSED", [f"{len(rec['mismatches'])} metric(s) differ from our own computation: "
                                        + ", ".join(m["metric_id"] for m in rec["mismatches"][:4])], doc, sha, rec)
    return ReviewResult("OK", [], doc, sha, rec)


def sample_review(manifest: dict | None = None) -> dict:
    """A deterministic, schema-valid sample built ONLY from the manifest's reference metrics. Marked is_sample: never a ConsultAI run."""
    man = manifest or load_manifest()
    ref = {m["metric_id"]: m for m in man["reference_metrics"]}
    want = ["households_total", "lines_total", "distinct_buyers_h1__YOGURT", "distinct_buyers_h2__YOGURT", "buyer_change__YOGURT",
            "yogurt_stopped_category", "yogurt_stopped_but_still_shopping", "yogurt_left_retailer", "lapsing_simple__YOGURT"]
    metrics = [{**ref[i], "tag": "COMPUTED FROM UPLOADED DATA"} for i in want]
    return {
        "schema": "consultant_review.v1", "review_id": "SAMPLE-NOT-A-CONSULTANT-RUN", "generated_at": "2026-11-18T00:00:00Z", "is_sample": True,
        "run": {"mode": "OFFLINE_DETERMINISTIC", "model_id": None, "cost_usd": None, "calls": 0, "consultai_commit": "SAMPLE"},
        "input": {"case_id": "GROCERY_84_51_2017_BUNDLE", "bundle_manifest_sha256": _sha(MANIFEST_PATH.read_bytes()) if manifest is None else "0" * 64},
        "roles": [{"role": "analyst", "tools": ["kpi", "sql"], "status": "OK", "summary": "Sample only."},
                  {"role": "checker", "tools": ["checker"], "status": "OK", "summary": "Sample only."},
                  {"role": "human", "tools": [], "status": "PENDING_HUMAN", "summary": "A named person approves; nothing is sent."}],
        "metrics": metrics,
        "headline": {"decision": "SAMPLE: check availability and assortment of the shrinking category before any discount.",
                     "numbers": [{"label": "Yogurt buyers, first half", "metric_id": "distinct_buyers_h1__YOGURT"},
                                 {"label": "Yogurt buyers, second half", "metric_id": "distinct_buyers_h2__YOGURT"},
                                 {"label": "Stopped yogurt but still shopping", "metric_id": "yogurt_stopped_but_still_shopping"}]},
        "options": [{"option": "Check availability and assortment", "tag": "COMPUTED FROM UPLOADED DATA", "metric_ids": ["yogurt_stopped_but_still_shopping"],
                     "verdict": "first", "condition": "most lost yogurt buyers still shop here"},
                    {"option": "No spend", "tag": "UNKNOWN", "metric_ids": [], "verdict": "always allowed", "condition": "coupon effect unknown"}],
        "action_card": {"segment": "SAMPLE segment rule", "four_ps": {"product": "sample", "price": "no change", "place": "sample", "promotion": "none"},
                        "alternative": "no spend", "owner": "SAMPLE owner", "kpi": "distinct buyers in a stated window", "approval_state": "PENDING_HUMAN", "sandbox_only": True},
        "unavailable": ["stock", "margin", "consent", "any year other than 2017"],
        "checker": {"verdict": "SAMPLE", "problems": []},
    }


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if a and a[0] == "sample":
        s = sample_review()
        SAMPLE_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
        SAMPLE_PATH.with_suffix(".sha256").write_text(_sha(SAMPLE_PATH.read_bytes()) + f"  {SAMPLE_PATH.name}\n", encoding="utf-8", newline="\n")
        print(f"wrote {SAMPLE_PATH.relative_to(DOCS.parent)}")
        return 0
    r = load_review()
    print(json.dumps({"status": r.status, "reasons": r.reasons, "sha256": r.sha256, "reconciliation": {k: r.reconciliation[k] for k in ("matched", "total")}}, indent=1))
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
