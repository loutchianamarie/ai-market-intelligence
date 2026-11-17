"""Read-only consumer adapter for reports/campaign_case.latest.json (contract v1).

The advisor, the app and the deck read the case ONLY through this file. It never recomputes a statistic.

  status OK            real COMPUTED_EXPORT whose SHA-256 matches its checksum and which passes the contract validator
  status DATA_PENDING  the export file does not exist yet: nothing empirical may be shown, no demo figure is substituted
  status REJECTED      file present but unusable (bad checksum, invalid, wrong case, synthetic fixture, unknown source ID)
  status FIXTURE       only when allow_fixture=True: shape-only fixture, every screen must say SYNTHETIC_FIXTURE

  python -m mi.consumer.adapter             print the adapter verdict for the live export
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mi.campaign.contract import CASE_ID, TAGS, validate_case
from mi.paths import REPORTS

EXPORT_PATH = REPORTS / "campaign_case.latest.json"
CHECKSUM_PATH = REPORTS / "campaign_case.latest.sha256"


@dataclass
class CaseResult:
    status: str
    reasons: list = field(default_factory=list)
    doc: Optional[dict] = None
    sha256: Optional[str] = None
    path: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "OK"

    @property
    def label(self) -> str:
        return {"OK": "COMPUTED_EXPORT", "FIXTURE": "SYNTHETIC_FIXTURE", "DATA_PENDING": "DATA_PENDING",
                "REJECTED": "REJECTED_EXPORT"}[self.status]

    def claims(self) -> dict:
        return {c["claim_id"]: c for c in (self.doc or {}).get("claims", [])}

    def claim(self, claim_id: str) -> dict:
        """One claim from the claim ledger, exactly as exported. KeyError if the producer did not export it."""
        return self.claims()[claim_id]

    def source_ids(self) -> set:
        return {s["source_id"] for s in (self.doc or {}).get("sources", [])}


def _expected_sha(sha_path: Path) -> Optional[str]:
    if not sha_path.exists():
        return None
    m = re.match(r"\s*([0-9a-fA-F]{64})", sha_path.read_text(encoding="utf-8", errors="replace"))
    return m.group(1).lower() if m else None


def load_case(path: Path | str | None = None, *, expected_sha: Optional[str] = None, sha_path: Path | str | None = None,
              allow_fixture: bool = False) -> CaseResult:
    p = Path(path) if path else EXPORT_PATH
    if not p.exists():
        return CaseResult("DATA_PENDING", [f"{p.name} not found: ask the marketing repo for the export; no figure is shown or substituted"],
                          path=str(p))
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return CaseResult("REJECTED", [f"not valid JSON: {e}"], sha256=sha, path=str(p))
    if not isinstance(doc, dict):
        return CaseResult("REJECTED", ["top level is not an object"], sha256=sha, path=str(p))

    rtype = doc.get("record_type")
    if rtype == "SYNTHETIC_FIXTURE":
        if not allow_fixture:
            return CaseResult("REJECTED", ["SYNTHETIC_FIXTURE is shape-only and may never appear in the empirical view"], sha256=sha, path=str(p))
        errs = validate_case(doc, expected_case_id=CASE_ID)
        return CaseResult("FIXTURE" if not errs else "REJECTED", errs[:10] or ["SYNTHETIC_FIXTURE: no empirical value"], doc, sha, str(p))

    want = (expected_sha or _expected_sha(Path(sha_path) if sha_path else (CHECKSUM_PATH if p == EXPORT_PATH else p.with_suffix(".sha256")))
            or "").lower()
    if not want:
        return CaseResult("REJECTED", ["no SHA-256 to verify the export against (send the checksum with the file)"], sha256=sha, path=str(p))
    if sha != want:
        return CaseResult("REJECTED", [f"SHA-256 mismatch: file {sha[:12]}... expected {want[:12]}... (stale, edited, or line endings rewritten)"],
                          sha256=sha, path=str(p))
    if rtype != "COMPUTED_EXPORT":
        return CaseResult("REJECTED", [f"record_type must be COMPUTED_EXPORT, got {rtype!r}"], sha256=sha, path=str(p))

    errs = validate_case(doc, expected_case_id=CASE_ID)
    ids = {s.get("source_id") for s in doc.get("sources", []) if isinstance(s, dict)}
    for c in doc.get("claims", []):
        if c.get("source_id") not in ids:
            errs.append(f"claim {c.get('claim_id')} cites unknown source_id {c.get('source_id')!r}")
        if c.get("tag") not in TAGS:
            errs.append(f"claim {c.get('claim_id')} has unknown tag {c.get('tag')!r}")
        if c.get("tag") == "UNKNOWN" and c.get("value") not in (None, "UNKNOWN"):
            errs.append(f"claim {c.get('claim_id')} is UNKNOWN but carries a value")
    if errs:
        return CaseResult("REJECTED", errs[:12], sha256=sha, path=str(p))
    return CaseResult("OK", [], doc, sha, str(p))


if __name__ == "__main__":
    r = load_case()
    print(json.dumps({"status": r.status, "label": r.label, "reasons": r.reasons, "sha256": r.sha256, "claims": len(r.claims())}, indent=1))
    sys.exit(0 if r.ok else 1)
