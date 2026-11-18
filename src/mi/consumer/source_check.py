"""Is the data behind the screen the verified one? Pure checks, no writes.

  verify_raw_bytes(case, data)   compare a raw file's SHA-256 with the hash recorded in the validated export's provenance
  verify_local_raw(case)         same, for the local Hillstrom CSV (which is never committed or uploaded anywhere)
  freshness(case, trace)         which saved artifacts belong to the loaded export and which are stale

A mismatch never falls back to the saved numbers: the caller must refuse the file (or recompute with python -m mi.campaign.export).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from mi.consumer.adapter import CHECKSUM_PATH, CaseResult
from mi.consumer.viewmodel import trace_is_current
from mi.paths import DATA

LOCAL_RAW = DATA / "raw" / "hillstrom" / "hillstrom_2008.csv"


def _locked(case: CaseResult) -> dict:
    p = case.doc["dataset_provenance"]
    return {"sha256": p["sha256"], "rows": p["rows"], "bytes": p["bytes"], "source_id": p["source_id"]}


def verify_raw_bytes(case: CaseResult, data: bytes) -> dict:
    """VERIFIED only when the bytes hash to the file the export was computed from. Anything else is a refusal."""
    lock = _locked(case)
    got = hashlib.sha256(data).hexdigest()
    if got == lock["sha256"]:
        return {"state": "VERIFIED", "sha256": got, "bytes": len(data),
                "text": f"Verified: this file is the exact dataset the export was computed from (SHA-256 {got[:12]}..., {len(data):,} bytes, {lock['rows']:,} rows recorded)."}
    return {"state": "REFUSED", "sha256": got, "bytes": len(data),
            "text": (f"REFUSED: SHA-256 {got[:12]}... is not the locked dataset {lock['sha256'][:12]}.... The saved export and agent trace are NOT attached to this file. "
                     "A changed dataset needs a full recomputation (python -m mi.campaign.export) and a new export before any figure is shown.")}


def verify_local_raw(case: CaseResult, path: Path | None = None) -> dict:
    p = Path(path) if path else LOCAL_RAW
    lock = _locked(case)
    if not p.exists():
        return {"state": "ABSENT", "sha256": None, "bytes": None,
                "text": (f"The local raw file is not on this machine (it is never committed: redistribution rights were not established). "
                         f"Showing the validated saved export {case.sha256[:12]}..., computed from the dataset with SHA-256 {lock['sha256'][:12]}....")}
    return verify_raw_bytes(case, p.read_bytes())


def freshness(case: CaseResult, trace: dict | None) -> dict:
    """Which artifacts agree with the loaded export. ``ok`` is False if the export itself is not the checksummed one."""
    want = CHECKSUM_PATH.read_text(encoding="utf-8").split()[0].lower() if CHECKSUM_PATH.exists() else None
    checks = {"export_matches_checksum_file": bool(want) and case.sha256 == want,
              "agent_trace_is_for_this_export": trace_is_current(trace, case.sha256)}
    stale = [k for k, v in checks.items() if not v]
    return {"ok": not stale, "checks": checks, "stale": stale}
