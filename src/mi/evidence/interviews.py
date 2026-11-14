"""Interview intake: validate the coded sheet and summarise barriers as "n of N" (never percentages).

The team fills data/interviews/coding_sheet.csv (one row per consented interview; no names). This code never
creates rows. Usage: python -m mi.evidence.interviews check | summarize
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

from mi.paths import REPORTS

SHEET = Path(__file__).resolve().parents[3] / "data" / "interviews" / "coding_sheet.csv"
CODES = {"HABIT", "PRICE", "SWITCH", "STOCK", "CONVENIENCE", "TASTE_HEALTH", "HOUSEHOLD", "NONE"}
REQUIRED = ["interview_id", "date", "screen_group", "consent_recorded", "barrier_codes", "barrier_evidence_behaviour",
            "implication_decision"]
# pre-registered mapping (docs/market_research_memo.md §5); used only to summarise what the TEAM coded
ACTION = {"HABIT": "reminder or offer stays a candidate", "PRICE": "offer stays a candidate; check store-brand gap",
          "SWITCH": "assortment action; coupon unlikely", "STOCK": "fix Place first; no test",
          "CONVENIENCE": "pickup/delivery visibility; no coupon", "TASTE_HEALTH": "not actionable by price; NONE",
          "HOUSEHOLD": "not actionable; NONE", "NONE": "no barrier described"}


def read(path=SHEET) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def codes(r) -> list[str]:
    return [c.strip().upper() for c in (r.get("barrier_codes") or "").replace(";", ",").split(",") if c.strip()]


def check(path=SHEET) -> dict:
    rows, problems = read(path), []
    for r in rows:
        rid = r.get("interview_id") or "?"
        empty = [k for k in REQUIRED if not (r.get(k) or "").strip()]
        if empty:
            problems.append({"row": rid, "empty": empty})
        if (r.get("consent_recorded") or "").strip().lower() not in {"y", "yes", "true", "1"}:
            problems.append({"row": rid, "issue": "consent not recorded: remove the row"})
        bad = [c for c in codes(r) if c not in CODES]
        if bad:
            problems.append({"row": rid, "issue": f"unknown barrier codes {bad}; use {sorted(CODES)}"})
    return {"interviews": len(rows), "target": "2-3 (exploratory)", "problems": problems,
            "status": "PENDING: 0 interviews" if not rows else ("OK" if not problems else "FIX ROWS")}


def summarize(path=SHEET) -> dict:
    rows = read(path)
    n = len(rows)
    if n == 0:
        return {"status": "PENDING: 0 interviews; nothing to summarise", "interviews": 0}
    cnt = Counter(c for r in rows for c in set(codes(r)))
    groups = Counter((r.get("screen_group") or "?").strip() for r in rows)
    return {"status": "OBSERVED (convenience sample; exploratory)", "interviews": n, "by_screen_group": dict(groups),
            "barriers": [{"code": c, "n_of_N": f"{k} of {n}", "pre_registered_action": ACTION.get(c, "?")} for c, k in cnt.most_common()],
            "counterexamples": [r["counterexample_to_hypothesis"] for r in rows if (r.get("counterexample_to_hypothesis") or "").strip()],
            "team_implications": [r["implication_decision"] for r in rows if (r.get("implication_decision") or "").strip()],
            "caveat": "Report as n of N with counterexamples. Never as a share of shoppers; no invented or paraphrased quotes."}


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["check"])[0]
    res = check() if cmd == "check" else summarize()
    if cmd == "summarize":
        (REPORTS / "interview_summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
