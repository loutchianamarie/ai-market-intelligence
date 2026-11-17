"""One-page collection sheet for the 20 GEO answers, generated from the frozen prompt panel.

The sheet only tells people WHAT to ask and HOW to log it. It never contains or generates an answer:
answers must come from real fresh chats in two assistants.

  python -m mi.seo.sheet      ->  docs/geo_collection_sheet.md
"""
from __future__ import annotations

import json
import sys

from mi.paths import DOCS, SEO

PANEL = SEO / "prompt_panel.json"
LOG = SEO / "answer_log.csv"


def build() -> str:
    p = json.loads(PANEL.read_text(encoding="utf-8"))
    frozen = bool(p.get("frozen"))
    rows = "\n".join(f"| {q['id']} | {q['intent']} | {q['lang']} | {q['text']} |" for q in p["prompts"])
    counts = {k: sum(1 for q in p["prompts"] if q["intent"] == k) for k in ("Learn", "Browse", "Buy")}
    assistants = ", ".join(a if isinstance(a, str) else a.get("name", str(a)) for a in p.get("assistants", [])) or "two assistants agreed by the team"
    comp = ", ".join(c if isinstance(c, str) else c.get("name", str(c)) for c in p.get("competitors", []))
    from mi.seo.geo import check          # progress comes from the real log, never from a typed number
    done = check()["complete_rows"]
    results = (DOCS / "geo_audit_results.md").exists()
    status = (f"**Logged so far: {done}/20 complete rows** (assistants named in the panel: {assistants})."
              + (" Results and limits: `docs/geo_audit_results.md`." if done and results else "")
              + (" Rows were produced by the named assistants themselves; a different assistant needs its own log." if done else ""))
    return f"""# GEO answer collection sheet (20 real answers)

Generated from `data/seo/prompt_panel.json`. Audited brand: **{p['audited_brand']}**; competitors: {comp}. Panel status: **{'FROZEN' if frozen else 'DRAFT: freeze it before the first run (python -m mi.seo.geo freeze --by "Your Name")'}**.
{status}
This is a separate real-brand discovery workstream. It says nothing about the e-mail experiment, and **no answer may be written by the team or by a model on the assistant's behalf**: each row must be a real, fresh-chat answer from the named assistant.

## Prompts ({counts['Learn']} Learn / {counts['Browse']} Browse / {counts['Buy']} Buy)

| ID | Intent | Language | Prompt (paste exactly) |
|---|---|---|---|
{rows}

## Procedure (about 30 minutes for two people)

1. Agree the two assistants ({assistants}) and identical settings: new chat for **every** prompt, same region and language, no custom instructions, web access the same in both. Write the assistant version in the log.
2. Person 1 runs all 10 prompts in assistant 1; person 2 runs all 10 in assistant 2. One fresh chat per prompt.
3. Copy the full answer into a private file `answers/<prompt_id>_<assistant>.txt` (this folder is gitignored; only the SHA-256 of each answer goes in the log).
4. Fill one row per answer in `data/seo/answer_log.csv`: `assistant_version`, `country_setting`, `timestamp_utc`, `raw_answer_sha256`, Y/N for `brand_mentioned`, `brand_recommended`, `brand_top_pick`, competitors named / recommended, `cited_urls` exactly as shown, `collected_by`.
5. Check progress: `python -m mi.seo.geo check` (lists incomplete rows). When 20 rows are complete: `python -m mi.seo.geo analyze` writes `reports/seo_geo_audit.json`, and the app and slides show `20/20` instead of `0/20 PENDING`.
6. Rules for the Y/N columns are in `docs/seo_geo_protocol.md`. Do not count a mention you did not read in the answer.

Log file: `{LOG.relative_to(LOG.parents[2]).as_posix()}`.
"""


def main() -> int:
    out = DOCS / "geo_collection_sheet.md"
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
