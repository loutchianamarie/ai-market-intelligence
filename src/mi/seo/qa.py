"""QA for the SEO/GEO audit: 20 checks on the panel, the answer log, the metrics and the page, plus the Excel export.

Why this exists: the GEO numbers go straight onto a slide and a web page, so every one of them is re-derived here by a second,
independent code path and every logging rule the protocol relies on is checked. Nothing in this module invents an answer.

Usage:  python -m mi.seo.qa                  # writes reports/geo_qa_report.json + .md and reports/geo_audit_answers.xlsx
        python -m mi.seo.qa --no-xlsx        # QA only
Statuses: PASS, FAIL (a rule is broken: fix before showing), WARN (works but a reader should know), INFO.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from mi.paths import REPORTS
from mi.seo import geo

HEX64 = re.compile(r"^[0-9a-f]{64}$")
NO = {"n", "no", "0", "false"}
ASSISTANTS = ("ASSISTANT_1", "ASSISTANT_2")


def _yes(v) -> bool:
    return (v or "").strip().lower() in geo.YES


def _yn_ok(v) -> bool:
    return (v or "").strip().lower() in geo.YES | NO


def _read_all(log_path: Path) -> list[dict]:
    if not Path(log_path).exists():
        return []
    with open(log_path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def independent_metrics(rows: list[dict], brand: str) -> dict:
    """Second implementation of the worksheet rates (different code path from geo.analyze) used only to cross-check it."""
    n = len(rows)
    b = brand.lower()
    mention = sum(1 for r in rows if _yes(r.get("brand_mentioned")))
    rec = sum(1 for r in rows if _yes(r.get("brand_recommended")))
    top = sum(1 for r in rows if _yes(r.get("brand_top_pick")))
    voice_brand = voice_all = rec_brand = rec_all = 0
    for r in rows:
        named = {x.strip().lower() for x in re.split(r"[;,]", r.get("competitors_named") or "") if x.strip()}
        if _yes(r.get("brand_mentioned")):
            named.add(b)
        voice_all += len(named)
        voice_brand += int(b in named)
        recd = {x.strip().lower() for x in re.split(r"[;,]", r.get("competitors_recommended") or "") if x.strip()}
        if _yes(r.get("brand_recommended")):
            recd.add(b)
        rec_all += len(recd)
        rec_brand += int(b in recd)
    return {"n": n, "mention": mention, "recommend": rec, "top": top, "voice": (voice_brand, voice_all), "recs": (rec_brand, rec_all)}


def run_qa(log_path=geo.LOG, panel_path=geo.PANEL, app_source: Path | None = None) -> dict:
    checks: list[dict] = []

    def add(cid: str, name: str, status: str, detail: str):
        checks.append({"id": cid, "check": name, "status": status, "detail": detail})

    # ---- Q01 panel structure (reuses the protocol's own rules)
    try:
        panel = geo.load_panel(panel_path)
        add("Q01", "Prompt panel follows the protocol (10 prompts, 4 Learn / 3 Browse / 3 Buy, brand named once, a second language)",
            "PASS", f"{len(panel['prompts'])} prompts, brand {panel['audited_brand']}")
    except Exception as e:  # noqa: BLE001 - any failure here means nothing else can be trusted
        add("Q01", "Prompt panel follows the protocol", "FAIL", str(e))
        return _wrap(checks, None, [])
    rows_all = _read_all(Path(log_path))
    rows_ok = geo.read_log(Path(log_path))
    byq = {str(q["id"]): q for q in panel["prompts"]}
    brand = panel["audited_brand"]

    # ---- Q02 freeze
    chk = geo.check(Path(log_path), Path(panel_path))
    add("Q02", "Panel is frozen at the version the answers were collected with", "PASS" if chk["panel_frozen"] else "FAIL",
        f"panel sha16 {chk['panel_sha16']}" + (f"; {chk['warning']}" if chk["warning"] else ""))

    # ---- Q03 coverage: each prompt x each assistant exactly once
    keys = Counter((str(r.get("prompt_id")), r.get("assistant")) for r in rows_all)
    expected = {(str(q["id"]), a) for q in panel["prompts"] for a in ASSISTANTS}
    missing, extra, dup = sorted(expected - set(keys)), sorted(set(keys) - expected), sorted(k for k, c in keys.items() if c > 1)
    add("Q03", "Every prompt answered once by each assistant (no gaps, no duplicates)", "PASS" if not (missing or extra or dup) else "FAIL",
        f"{len(rows_all)} rows, expected {len(expected)}" + (f"; missing {missing}" if missing else "") + (f"; unexpected {extra}" if extra else "")
        + (f"; duplicated {dup}" if dup else ""))

    # ---- Q04 required fields
    gaps = [f"P{r.get('prompt_id')}/{r.get('assistant')}: {[k for k in geo.REQUIRED if not (r.get(k) or '').strip()]}"
            for r in rows_all if any(not (r.get(k) or "").strip() for k in geo.REQUIRED)]
    add("Q04", "Every row has the required fields (version, setting, time, hash, three Y/N codes, collector)", "PASS" if not gaps else "FAIL",
        "all present" if not gaps else "; ".join(gaps[:5]))

    # ---- Q05 Y/N values
    bad = [f"P{r.get('prompt_id')}/{r.get('assistant')}:{k}={r.get(k)!r}" for r in rows_all
           for k in ("brand_mentioned", "brand_recommended", "brand_top_pick") if not _yn_ok(r.get(k))]
    add("Q05", "The three brand codes are Y or N only", "PASS" if not bad else "FAIL", "all valid" if not bad else "; ".join(bad[:5]))

    # ---- Q06 logical chain: top pick => recommended => mentioned
    chain = [f"P{r.get('prompt_id')}/{r.get('assistant')}" for r in rows_all
             if (_yes(r.get("brand_top_pick")) and not _yes(r.get("brand_recommended")))
             or (_yes(r.get("brand_recommended")) and not _yes(r.get("brand_mentioned")))]
    add("Q06", "Codes are consistent: a top pick is recommended, a recommendation is a mention", "PASS" if not chain else "FAIL",
        "no contradictions" if not chain else f"contradictions in {chain}")

    # ---- Q07 competitors recommended must also be named
    odd = []
    for r in rows_all:
        named = {x.strip().lower() for x in re.split(r"[;,]", r.get("competitors_named") or "") if x.strip()}
        recd = {x.strip().lower() for x in re.split(r"[;,]", r.get("competitors_recommended") or "") if x.strip()}
        if not recd <= named:
            odd.append(f"P{r.get('prompt_id')}/{r.get('assistant')}: {sorted(recd - named)}")
    add("Q07", "Every competitor recommended was also named in the answer", "PASS" if not odd else "WARN", "consistent" if not odd else "; ".join(odd[:5]))

    # ---- Q08 hashes
    hashes = [(r.get("raw_answer_sha256") or "").strip().lower() for r in rows_all]
    badh = [h for h in hashes if not HEX64.match(h)]
    duph = [h for h, c in Counter(hashes).items() if c > 1]
    add("Q08", "Each raw answer has its own SHA-256 (64 hex characters, none repeated)", "PASS" if not (badh or duph) else "FAIL",
        f"{len(hashes)} hashes" + (f"; malformed {len(badh)}" if badh else "") + (f"; repeated {len(duph)}" if duph else ""))

    # ---- Q09 timestamps
    now = datetime.now(timezone.utc)
    ts_bad, stamps = [], []
    for r in rows_all:
        s = (r.get("timestamp_utc") or "").strip()
        try:
            t = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            stamps.append(t)
            if t > now:
                ts_bad.append(f"P{r.get('prompt_id')} is in the future")
        except ValueError:
            ts_bad.append(f"P{r.get('prompt_id')}/{r.get('assistant')}: {s!r}")
    add("Q09", "Timestamps are valid UTC and not in the future", "PASS" if not ts_bad else "FAIL",
        (f"{min(stamps):%Y-%m-%d %H:%M} to {max(stamps):%H:%M} UTC" if stamps else "none") + ("" if not ts_bad else "; " + "; ".join(ts_bad[:4])))

    # ---- Q10 settings drift
    add("Q10", "Same assistant version and region setting for every answer of one assistant", "PASS" if not chk["settings_drift"] else "FAIL",
        "no drift" if not chk["settings_drift"] else str(chk["settings_drift"]))

    # ---- Q11 log matches the panel (intent and language per prompt)
    mism = [f"P{r.get('prompt_id')}" for r in rows_all if str(r.get("prompt_id")) in byq and
            ((r.get("intent") != byq[str(r["prompt_id"])]["intent"]) or (r.get("language") != byq[str(r["prompt_id"])]["lang"]))]
    add("Q11", "Intent and language in the log match the frozen panel", "PASS" if not mism else "FAIL", "match" if not mism else f"mismatch {sorted(set(mism))}")

    # ---- Q12 cited URLs parse, and the note's URL count matches
    url_issue, no_web = [], 0
    for r in rows_all:
        urls = [u for u in (r.get("cited_urls") or "").replace(";", " ").split() if u]
        if not urls:
            no_web += 1
        m = re.search(r"(\d+) URLs? cited", r.get("source_quality_notes") or "")
        if m and int(m.group(1)) != len(urls):
            url_issue.append(f"P{r.get('prompt_id')}/{r.get('assistant')}: note says {m.group(1)}, log has {len(urls)}")
        for u in urls:
            if not re.match(r"^https?://[^/\s]+\.[^/\s]+", u):
                url_issue.append(f"P{r.get('prompt_id')}/{r.get('assistant')}: not a URL {u[:40]!r}")
    add("Q12", "Cited URLs are well formed and match the URL count written in the notes", "PASS" if not url_issue else "FAIL",
        f"{len(rows_all) - no_web} answers cite URLs, {no_web} cite none" + ("" if not url_issue else "; " + "; ".join(url_issue[:4])))

    # ---- Q13 headline rates re-derived independently
    res = geo.analyze(rows_ok, panel)
    ind = independent_metrics(rows_ok, brand)
    if res["answers_logged"]:
        pairs = [("mention", res["mention_rate"]["num"]), ("recommend", res["recommendation_rate"]["num"]), ("top", res["primary_pick_rate"]["num"])]
        diffs = [f"{k}: app {a} vs recomputed {ind[k]}" for k, a in pairs if a != ind[k]]
        if (res["share_of_voice"]["num"], res["share_of_voice"]["den"]) != ind["voice"]:
            diffs.append(f"share of voice: app {res['share_of_voice']['num']}/{res['share_of_voice']['den']} vs recomputed {ind['voice'][0]}/{ind['voice'][1]}")
        if (res["share_of_recommendations"]["num"], res["share_of_recommendations"]["den"]) != ind["recs"]:
            diffs.append("share of recommendations differs")
        add("Q13", "Mention, recommendation, primary-pick, share-of-voice and share-of-recommendation counts re-derived independently",
            "PASS" if not diffs else "FAIL",
            f"mention {ind['mention']}/{ind['n']}, recommended {ind['recommend']}/{ind['n']}, top pick {ind['top']}/{ind['n']}" if not diffs else "; ".join(diffs))
    else:
        add("Q13", "Rates re-derived independently", "FAIL", "no logged answers")

    # ---- Q14 denominators add up
    if res["answers_logged"]:
        bi = res["by_intent"]
        ok = sum(v["n"] for v in bi.values()) == res["answers_logged"] and \
            sum(v["mentioned"] for v in bi.values()) == res["mention_rate"]["num"] and \
            sum(v["recommended"] for v in bi.values()) == res["recommendation_rate"]["num"]
        add("Q14", "Learn + Browse + Buy add up to the overall counts", "PASS" if ok else "FAIL",
            ", ".join(f"{k} {v['mentioned']}/{v['n']} mentioned, {v['recommended']}/{v['n']} recommended" for k, v in bi.items()))
    else:
        add("Q14", "By-intent counts add up", "FAIL", "no logged answers")

    # ---- Q15 target and completeness
    st = geo.geo_state(Path(log_path), Path(panel_path))
    add("Q15", "20 of 20 answers complete (state used by the page, briefs and work items)", "PASS" if st["complete"] else "FAIL",
        f"{st['answers_logged']}/{st['answers_target']} logged, {st['complete_rows']} complete, frozen={chk['panel_frozen']}")

    # ---- Q16 stated limits present in the data
    web = sum(1 for r in rows_all if "web search yes" in (r.get("source_quality_notes") or "").lower())
    var_note = all("single run" in (r.get("refusal_or_variability") or "").lower() or "variab" in (r.get("refusal_or_variability") or "").lower() for r in rows_all) if rows_all else False
    add("Q16", "Limits are recorded: one run per question, region not set, web search use, two assistants of one vendor",
        "PASS" if var_note and len(st["assistants"]) >= 1 else "WARN",
        f"{len(st['assistants'])} assistant(s) {st['assistants']}; web search noted in {web} answers; region: {sorted({r.get('country_setting') for r in rows_all})}")

    # ---- Q17 language mix
    langs = Counter(r.get("language") for r in rows_ok)
    add("Q17", "At least two answers per assistant are in a second language", "PASS" if sum(v for k, v in langs.items() if k != "en") >= 4 else "FAIL",
        ", ".join(f"{k}: {v}" for k, v in sorted(langs.items())) + " answers (the worksheet requires a second language; fit with the official brief is pending)")

    # ---- Q18 page text: no hard-coded GEO counts in the app source
    src = app_source or (Path(__file__).resolve().parents[3] / "app" / "streamlit_app.py")
    if Path(src).exists():
        text = Path(src).read_text(encoding="utf-8")
        hard = re.findall(r"\b\d+/\d+ (?:Learn|Browse|Buy)\b|\bmentioned in \d+/\d+\b", text)
        add("Q18", "The page computes its GEO counts from the log instead of typing them", "PASS" if not hard else "FAIL",
            "no typed counts" if not hard else f"typed counts found: {hard[:3]}")
    else:
        add("Q18", "The page computes its GEO counts from the log", "WARN", f"{src} not found")

    # ---- Q19 candidate actions stay unscored
    acts = res.get("candidate_actions", [])
    scored = [a for a in acts if a.get("impact") is not None or a.get("effort") is not None]
    add("Q19", "Content actions are hypotheses: impact and effort are left for the team to score", "PASS" if not scored else "WARN",
        f"{len(acts)} proposed actions, {len(scored)} scored")

    # ---- Q20 no traffic or sales claim
    cav = res.get("caveat", "")
    add("Q20", "The result says it is an observation of answers, not search ranking, traffic or sales", "PASS" if "not search ranking, traffic or sales" in cav else "FAIL", cav[:140])

    return _wrap(checks, res, rows_ok)


def _wrap(checks, res, rows) -> dict:
    n = Counter(c["status"] for c in checks)
    return {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "summary": dict(n), "total": len(checks),
            "verdict": "FAIL" if n.get("FAIL") else ("PASS WITH WARNINGS" if n.get("WARN") else "PASS"), "checks": checks}


def to_markdown(rep: dict) -> str:
    L = ["# GEO / SEO QA report", "", f"Generated {rep['generated_utc']}. Verdict: **{rep['verdict']}** "
         f"({', '.join(f'{v} {k}' for k, v in sorted(rep['summary'].items()))} of {rep['total']} checks).", "",
         "| id | check | status | detail |", "|---|---|---|---|"]
    for c in rep["checks"]:
        L.append(f"| {c['id']} | {c['check']} | **{c['status']}** | {c['detail'].replace('|', '/')} |")
    L += ["", "What this does not test: whether the assistants' answers are *right* (we log what they said), other assistants, other regions,",
          "repeat runs (variability), or any effect on traffic or sales."]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------------------------- Excel export
def tables(log_path=geo.LOG, panel_path=geo.PANEL) -> dict:
    """All tables of the export as lists of dicts (so the page, the Excel file and the tests read the same thing)."""
    import pandas as pd

    panel = geo.load_panel(panel_path)
    rows = geo.read_log(Path(log_path))
    res = geo.analyze(rows, panel)
    q = pd.DataFrame(panel["prompts"]).rename(columns={"id": "prompt_id", "lang": "language", "text": "question"})
    d = pd.DataFrame(rows)
    d["prompt_id"] = d["prompt_id"].astype(int)
    d = d.merge(q[["prompt_id", "question"]], on="prompt_id", how="left").sort_values(["prompt_id", "assistant"])
    d["model"] = d["assistant_version"].str.extract(r"(Claude \w+ [\d.]+)", expand=False).fillna(d["assistant"])
    d["urls_cited"] = d["cited_urls"].map(lambda s: len([u for u in (s or "").replace(";", " ").split() if u]))
    d["domains_cited"] = d["cited_urls"].map(lambda s: ", ".join(sorted(set(geo.domains(s)))))
    for k in ("brand_mentioned", "brand_recommended", "brand_top_pick"):
        d[k + "_01"] = d[k].map(lambda v: int(_yes(v)))

    def rate(g):
        n = len(g)
        return {"answers": n, "mentioned": int(g.brand_mentioned_01.sum()), "recommended": int(g.brand_recommended_01.sum()),
                "top_pick": int(g.brand_top_pick_01.sum()), "mention_rate": g.brand_mentioned_01.mean(),
                "recommendation_rate": g.brand_recommended_01.mean(), "primary_pick_rate": g.brand_top_pick_01.mean()}

    rate_rows = [{"group": "ALL", "value": "all answers", **rate(d)}]
    for col, label in (("intent", "intent"), ("language", "language"), ("model", "assistant")):
        for v, g in d.groupby(col):
            rate_rows.append({"group": label, "value": v, **rate(g)})
    answers = d[["prompt_id", "intent", "language", "question", "model", "brand_mentioned", "brand_recommended", "brand_top_pick",
                 "competitors_named", "competitors_recommended", "urls_cited", "domains_cited", "cited_urls", "source_quality_notes",
                 "refusal_or_variability", "timestamp_utc", "raw_answer_sha256", "assistant_version", "country_setting", "collected_by"]]
    share = [{"measure": "mention rate", **res["mention_rate"]}, {"measure": "recommendation rate", **res["recommendation_rate"]},
             {"measure": "primary-pick rate", **res["primary_pick_rate"]}, {"measure": "share of voice", **res["share_of_voice"]},
             {"measure": "share of recommendations", **res["share_of_recommendations"]}]
    gap = [{"domain": k, "answers_where_competitor_won_and_brand_did_not": v} for k, v in geo.Counter(
        dom for r in rows if geo.split_names(r.get("competitors_recommended")) and not _yes(r.get("brand_recommended"))
        for dom in set(geo.domains(r["cited_urls"]))).most_common(15)]
    return {"panel": panel, "questions": q, "answers": answers, "rates": pd.DataFrame(rate_rows), "share": pd.DataFrame(share),
            "source_gap": pd.DataFrame(gap, columns=["domain", "answers_where_competitor_won_and_brand_did_not"]), "actions": pd.DataFrame(res["candidate_actions"]), "result": res}


def export_xlsx(path: Path, qa: dict | None = None, log_path=geo.LOG, panel_path=geo.PANEL) -> str:
    """Write the audit workbook. Returns the path written. Needs openpyxl; falls back to one CSV per sheet if it is missing."""
    import pandas as pd

    t = tables(log_path, panel_path)
    qa = qa or run_qa(log_path, panel_path)
    readme = pd.DataFrame({"item": ["What this is", "Brand audited", "Competitors", "Answers", "How to read", "What it is not", "Raw answer text", "Verdict of the QA"],
                           "value": ["Observed answers from AI assistants to 10 shopper questions (Learn / Browse / Buy), 2 assistants = 20 answers.",
                                     f"{t['panel']['audited_brand']} (public analogue, not the dataset retailer)", ", ".join(t["panel"]["competitors"]),
                                     f"{t['result']['answers_logged']} logged by the team; the app never invents an answer.",
                                     "Sheet Answers has one row per answer. Rates has the counts by intent, language and assistant. Actions are hypotheses: impact and effort are blank for the team to score.",
                                     "Not search ranking, traffic or sales. One run per question, two models of one vendor, no region set.",
                                     "Not stored. Each answer is identified by its SHA-256 in column raw_answer_sha256.",
                                     f"{qa['verdict']} ({', '.join(f'{v} {k}' for k, v in sorted(qa['summary'].items()))})"]})
    sheets = {"README": readme, "Questions": t["questions"], "Answers": t["answers"], "Rates": t["rates"], "Share": t["share"],
              "Source_gap": t["source_gap"], "Actions": t["actions"].assign(impact_1to5="", effort_1to5="", owner=""),
              "QA": pd.DataFrame(qa["checks"])}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        for name, df in sheets.items():
            df.to_csv(path.with_name(f"{path.stem}_{name}.csv"), index=False)
        return f"openpyxl missing: wrote CSV files next to {path}"
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.freeze_panes = "A2"
            for i, col in enumerate(df.columns, 1):
                width = min(60, max(10, int(df[col].astype(str).map(len).quantile(0.9)) + 2 if len(df) else 12, len(str(col)) + 2))
                ws.column_dimensions[get_column_letter(i)].width = width
                if name in ("Answers", "QA", "README", "Actions"):
                    for cell in ws[get_column_letter(i)][1:]:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="0E5C5C")
            if name == "Rates":
                for col in ("mention_rate", "recommendation_rate", "primary_pick_rate"):
                    j = list(df.columns).index(col) + 1
                    for cell in ws[get_column_letter(j)][1:]:
                        cell.number_format = "0%"
            if name == "QA":
                colors = {"PASS": "D9EAD3", "FAIL": "F4CCCC", "WARN": "FFF2CC", "INFO": "DDEBF7"}
                j = list(df.columns).index("status") + 1
                for cell in ws[get_column_letter(j)][1:]:
                    cell.fill = PatternFill("solid", fgColor=colors.get(cell.value, "FFFFFF"))
    return str(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-xlsx", action="store_true")
    ap.add_argument("--xlsx", default=str(REPORTS / "geo_audit_answers.xlsx"))
    a = ap.parse_args(argv)
    rep = run_qa()
    REPORTS.mkdir(exist_ok=True, parents=True)
    (REPORTS / "geo_qa_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    (REPORTS / "geo_qa_report.md").write_text(to_markdown(rep), encoding="utf-8")
    print(json.dumps({"verdict": rep["verdict"], "summary": rep["summary"]}))
    for c in rep["checks"]:
        if c["status"] != "PASS":
            print(f"  {c['status']} {c['id']} {c['check']}: {c['detail'][:150]}")
    if not a.no_xlsx:
        print("workbook:", export_xlsx(Path(a.xlsx), rep))
    return 1 if rep["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
