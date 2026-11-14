"""Verify the raw Complete Journey files against the COMMITTED lock (data/manifest.lock.json).

Checks, for every file: presence, byte size, SHA-256 and expected row count of the loaded table. Any mismatch
raises DataIntegrityError with a readable message, so the pipeline stops instead of training on altered or
substituted data. Usage: python -m mi.ingest.verify
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from mi.paths import RAW, REPORTS, ROOT

LOCK = ROOT / "data" / "manifest.lock.json"
FILE_TO_TABLE = {"transactions.rds": "transactions", "products.rda": "products", "campaigns.rda": "campaigns",
                 "campaign_descriptions.rda": "campaign_descriptions", "coupons.rda": "coupons",
                 "coupon_redemptions.rda": "coupon_redemptions", "demographics.rda": "demographics"}


class DataIntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify(raw: Path = RAW, lock_path: Path = LOCK, check_rows: bool = True) -> dict:
    lock = json.loads(Path(lock_path).read_text())
    rows, problems = [], []
    for f in lock["files"]:
        p = Path(raw) / f["name"]
        r = {"name": f["name"], "present": p.exists()}
        if not p.exists():
            problems.append(f"{f['name']}: missing (run python -m mi.ingest.download)")
            rows.append(r)
            continue
        r["bytes_ok"] = p.stat().st_size == f["bytes"]
        r["sha256_ok"] = sha256(p) == f["sha256"]
        if not r["bytes_ok"] or not r["sha256_ok"]:
            problems.append(f"{f['name']}: checksum/size mismatch with the committed lock (commit {lock['commit'][:12]})")
        rows.append(r)
    if check_rows and not problems:
        from mi.ingest.load import load
        for r, f in zip(rows, lock["files"]):
            n = len(load(FILE_TO_TABLE[f["name"]]))
            r["rows"] = n
            r["rows_ok"] = n == f["expected_rows"]
            if not r["rows_ok"]:
                problems.append(f"{f['name']}: {n} rows, expected {f['expected_rows']}")
    out = {"lock": str(Path(lock_path).relative_to(ROOT)) if str(lock_path).startswith(str(ROOT)) else str(lock_path),
           "source_commit": lock["commit"], "licence": lock.get("licence"), "files": rows,
           "ok": not problems, "problems": problems}
    if problems:
        raise DataIntegrityError("Raw data does not match data/manifest.lock.json:\n  - " + "\n  - ".join(problems))
    return out


def main(argv=None) -> int:
    try:
        res = verify()
    except DataIntegrityError as e:
        print(f"DATA INTEGRITY FAILURE\n{e}", file=sys.stderr)
        return 2
    (REPORTS / "data_verification.json").write_text(json.dumps(res, indent=2))
    print(f"verified {len(res['files'])} files against {res['lock']} (source commit {res['source_commit'][:12]}): OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
