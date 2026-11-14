"""Dated source corpus, BM25 retrieval and span-verified grounded answers.

* Sources carry url/owner/type/retrieved_at/sha/rights/market; chunks keep exact text so every cited
  span can be verified as a substring (validator), not just a source id.
* Retrieved text is UNTRUSTED DATA: instruction-like text is flagged and never executed; the research
  role's tool allowlist cannot approve, spend or send regardless of what a page says.
* Abstains when retrieval support is weak. Flags numeric conflicts between sources.
* LLM path (if runtime credentials exist): the model sees only retrieved excerpts and must return JSON
  claims with spans; the same validator drops any span not found verbatim.

Usage: python -m mi.evidence.rag build | ask "question" | eval
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone

from mi.paths import REPORTS, SOURCES

CACHE = SOURCES / "_cache"
CORPUS = SOURCES / "corpus.jsonl"

REGISTRY = {
    "cj_pkg_index": {"owner": "R package maintainer (Boehmke & Mortimer)", "type": "dataset_documentation", "rights": "public docs; CC0 data", "market": "US grocery (anonymous retailer)"},
    "cj_coupon_redemptions": {"owner": "R package maintainer", "type": "dataset_documentation", "rights": "public docs", "market": "US grocery"},
    "cj_campaigns": {"owner": "R package maintainer", "type": "dataset_documentation", "rights": "public docs", "market": "US grocery"},
    "cj_transactions": {"owner": "R package maintainer", "type": "dataset_documentation", "rights": "public docs", "market": "US grocery"},
    "cj_py_port_readme": {"owner": "third-party Python port (cunningjames)", "type": "third_party_readme", "rights": "public README (MIT repo)", "market": "n/a"},
    "google_ai_features": {"owner": "Google Search Central", "type": "platform_guidance", "rights": "public docs, short extracts", "market": "global"},
    "course_marketing_primer": {"owner": "course handout (author attribution unverified)", "type": "course_material", "rights": "course use only", "market": "n/a"},
    "course_market_research_primer": {"owner": "course handout", "type": "course_material", "rights": "course use only", "market": "n/a"},
    "course_metrics_workbook": {"owner": "course handout (Module 04 TP)", "type": "course_material", "rights": "course use only", "market": "n/a"},
    "course_metrics_slides": {"owner": "course slides (Marketing main metrics)", "type": "course_material", "rights": "course use only", "market": "n/a"},
    "course_agent_worksheet": {"owner": "course worksheet", "type": "course_material", "rights": "course use only", "market": "n/a"},
    "course_seo_geo_worksheet": {"owner": "course worksheet", "type": "course_material", "rights": "course use only", "market": "n/a"},
}
INTERNAL_REPORTS = {"report_data_audit": "data_audit.md", "report_model_card": "model_card.md", "report_portfolio": "portfolio.md"}

STOP = set("""a an the of to in on for and or is are was were be by with as at from that this it its into what which who how
why does do did can could should would will not no than then there their they them we our you your i me my about over under per
any all each more most less such these those only also if when where between vs versus""".split())
INSTRUCTION_PATTERNS = re.compile(r"(ignore (all|any|previous|prior) (instructions|rules)|you are now|system prompt|"
                                  r"call the tool|approve (this|the) (plan|pilot)|send (the|this) (message|email|coupon)|"
                                  r"transfer|disregard)", re.I)


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9'\-\.]*[a-z0-9]|[a-z0-9]", text.lower()) if t not in STOP]


def chunk(text: str, size=700, overlap=120) -> list[str]:
    lines, out, cur = [l.strip() for l in text.splitlines() if l.strip()], [], ""
    for l in lines:
        if len(cur) + len(l) + 1 > size and cur:
            out.append(cur)
            cur = cur[-overlap:] + " " + l
        else:
            cur = (cur + " " + l).strip()
    if cur:
        out.append(cur)
    return out


def clean_markdown(text: str) -> str:
    """Drop badge/image lines and markdown markup so cited spans are plain text."""
    out = []
    for line in text.splitlines():
        if "[![" in line or line.strip().startswith("```"):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"^\s*#{1,6}\s*", "", line).replace("**", "").replace("> ", "")
        out.append(line)
    return "\n".join(out)


def build() -> list[dict]:
    log = json.loads((CACHE / "fetch_log.json").read_text()) if (CACHE / "fetch_log.json").exists() else {}
    rows = []
    items = [(sid, CACHE / f"{sid}.txt", meta) for sid, meta in REGISTRY.items()]
    items += [(sid, REPORTS / fn, {"owner": "this project (generated)", "type": "internal_report",
                                   "rights": "own work", "market": "US grocery panel"}) for sid, fn in INTERNAL_REPORTS.items()]
    for sid, path, meta in items:
        if not path.exists():
            continue
        text = clean_markdown(path.read_text(encoding="utf-8", errors="ignore"))
        fl = log.get(sid, {})
        src = {"source_id": sid, "url": fl.get("url") or (f"local:{path.name}"), **meta,
               "retrieved_at": fl.get("retrieved_at") or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
               "content_sha16": hashlib.sha256(text.encode()).hexdigest()[:16]}
        if sid == "cj_py_port_readme":
            src["url"] = "https://github.com/cunningjames/completejourney_py (readme.md)"
        for i, c in enumerate(chunk(text)):
            rows.append({**src, "chunk_id": f"{sid}#{i}", "text": c,
                         "instruction_like": bool(INSTRUCTION_PATTERNS.search(c))})
    with open(CORPUS, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


class BM25:
    def __init__(self, docs: list[dict], k1=1.4, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.toks = [tokens(d["text"]) for d in docs]
        self.avgdl = sum(map(len, self.toks)) / max(1, len(self.toks))
        df = Counter(t for ts in self.toks for t in set(ts))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - v + 0.5) / (v + 0.5)) for t, v in df.items()}
        self.tf = [Counter(ts) for ts in self.toks]

    def search(self, query: str, k=5, as_of: str | None = None) -> list[tuple[float, dict]]:
        q = tokens(query)
        scored = []
        for i, d in enumerate(self.docs):
            if as_of and d.get("retrieved_at", "") > as_of:
                continue  # never retrieve a source that did not exist at the decision date
            tf, dl, s = self.tf[i], len(self.toks[i]), 0.0
            for t in q:
                if t in tf:
                    s += self.idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if s > 0:
                scored.append((s, d))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]


def load_corpus() -> list[dict]:
    if not CORPUS.exists():
        build()
    return [json.loads(l) for l in open(CORPUS, encoding="utf-8")]


_INDEX = None


def index() -> BM25:
    global _INDEX
    if _INDEX is None:
        _INDEX = BM25(load_corpus())
    return _INDEX


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[\.\!\?])\s+|\s\|\s|\n", text) if len(s.strip()) > 25]


def validate_claims(claims: list[dict], chunks_by_id: dict) -> tuple[list[dict], list[dict]]:
    ok, bad = [], []
    for c in claims:
        ch = chunks_by_id.get(c.get("chunk_id"))
        if ch and c.get("span") and c["span"] in ch["text"]:
            ok.append({**c, "source_id": ch["source_id"], "url": ch["url"], "retrieved_at": ch["retrieved_at"]})
        else:
            bad.append({**c, "reason": "span not found verbatim in cited chunk" if ch else "unknown chunk id"})
    return ok, bad


NUM_NOUN = re.compile(r"(\d[\d,\.]*)\s+(households|transactions|transaction records|rows|campaigns|coupons)", re.I)


def find_conflicts(claims: list[dict]) -> list[dict]:
    seen = {}
    for c in claims:
        for num, noun in NUM_NOUN.findall(c["span"]):
            key = noun.lower()
            seen.setdefault(key, {}).setdefault(num.replace(",", ""), set()).add(c["source_id"])
    out = []
    for noun, vals in seen.items():
        if len(vals) > 1:
            out.append({"about": noun, "values": {k: sorted(v) for k, v in vals.items()}})
    return out


def answer(question: str, k=5, min_score=4.0, min_terms=2, min_coverage=0.45, as_of=None, llm=None) -> dict:
    """Grounded answer. Deterministic extractive path unless an LLM client is passed."""
    hits = index().search(question, k=k, as_of=as_of)
    q = set(tokens(question))
    res = {"question": question, "retrieved": [{"chunk_id": d["chunk_id"], "score": round(s, 3), "source_id": d["source_id"],
                                               "instruction_like": d["instruction_like"]} for s, d in hits],
           "method": "bm25+extractive", "abstained": False}
    flagged = [d["chunk_id"] for _, d in hits if d["instruction_like"]]
    if flagged:
        res["untrusted_instruction_text_ignored"] = flagged
    top_terms = len(q & set(tokens(hits[0][1]["text"]))) if hits else 0
    coverage = top_terms / max(1, len(q))
    res["top1_query_coverage"] = round(coverage, 3)
    # v2 rule (frozen 2026-11-14 after v1 answered 3/3 unanswerable questions): require coverage too
    if not hits or hits[0][0] < min_score or top_terms < min_terms or coverage < min_coverage:
        res.update({"abstained": True, "answer": "UNKNOWN — the corpus does not support an answer.",
                    "supported_claims": [], "next_research_action": "collect a primary source or run the measurement"})
        return res
    by_id = {d["chunk_id"]: d for _, d in hits}
    if llm is not None:
        claims = llm.grounded_claims(question, [d for _, d in hits])
        res["method"] = "bm25+llm"
    else:
        claims = []
        wants_number = bool(re.match(r"\s*(how many|how much|what (number|share|percent))", question, re.I))
        for s, d in hits[:3]:
            best = max(sentences(d["text"]) or [d["text"][:300]],
                       key=lambda x: len(q & set(tokens(x))) + (3.0 if wants_number and any(
                           n.lower() in q for _, n in NUM_NOUN.findall(x)) else 0))
            if len(q & set(tokens(best))) >= min_terms:
                claims.append({"claim": best, "chunk_id": d["chunk_id"], "span": best})
    ok, bad = validate_claims(claims, by_id)
    if not ok:
        res.update({"abstained": True, "answer": "UNKNOWN — no verifiable span.", "supported_claims": [], "rejected_claims": bad})
        return res
    res.update({"answer": " ".join(c["span"] for c in ok[:2]), "supported_claims": ok, "rejected_claims": bad,
                "conflicts": find_conflicts(ok),
                "next_research_action": "verify semantic adequacy by a human reviewer before quoting on a slide"})
    return res


EVAL = [
    {"q": "How many households are in the Complete Journey data?", "expect": ["cj_pkg_index", "cj_py_port_readme"], "answerable": True, "conflict": True},
    {"q": "Is the completejourney_py Python package authentic consumer data or simulated?", "expect": ["cj_py_port_readme"], "answerable": True},
    {"q": "What does the coupon redemptions table record?", "expect": ["cj_coupon_redemptions"], "answerable": True},
    {"q": "Which households received which campaigns?", "expect": ["cj_campaigns"], "answerable": True},
    {"q": "Does Google require special markup or schema to appear in AI Overviews?", "expect": ["google_ai_features"], "answerable": True},
    {"q": "What is the break-even ROAS formula given a gross margin?", "expect": ["course_metrics_workbook", "course_metrics_slides"], "answerable": True},
    {"q": "Why should research ask about missing customers who are not in the dashboard?", "expect": ["course_market_research_primer"], "answerable": True},
    {"q": "What are the three tests every real segment must pass: measurable reachable substantial?", "expect": ["course_marketing_primer"], "answerable": True},
    {"q": "Where must a human approve in the agent canvas: money and public messages?", "expect": ["course_agent_worksheet"], "answerable": True},
    {"q": "How many prompts and answers does the GEO sprint log?", "expect": ["course_seo_geo_worksheet"], "answerable": True},
    {"q": "What is the retailer's actual product gross margin on frozen pizza?", "expect": [], "answerable": False},
    {"q": "What was Kroger's digital coupon redemption rate in 2025?", "expect": [], "answerable": False},
    {"q": "How many stores does the anonymous retailer operate in Ohio?", "expect": [], "answerable": False},
]


HELD_OUT = [  # written before running the v2 rule; never used to choose thresholds
    {"q": "Which campaign types appear in the campaign descriptions?", "expect": ["cj_pkg_index", "cj_campaigns", "report_data_audit"], "answerable": True},
    {"q": "What does Google say about AI Overviews and AI Mode eligibility for a page?", "expect": ["google_ai_features"], "answerable": True},
    {"q": "Why should we sum first and then divide when computing CTR?", "expect": ["course_metrics_workbook", "course_metrics_slides"], "answerable": True},
    {"q": "What did Walmart spend on digital coupon advertising last quarter?", "expect": [], "answerable": False},
    {"q": "What is the return rate for frozen pizza at this retailer?", "expect": [], "answerable": False},
    {"q": "Which Instagram influencers does the retailer pay?", "expect": [], "answerable": False},
]


def evaluate() -> dict:
    out = _evaluate(EVAL)
    out["held_out"] = {k: v for k, v in _evaluate(HELD_OUT, write=False).items() if k != "baseline_no_retrieval"}
    (REPORTS / "rag_eval.json").write_text(json.dumps(out, indent=2))
    return out


def _evaluate(items, write=True) -> dict:
    EVAL_ = items
    rows, n_ans, hit5, abst_ok, conflict_ok = [], 0, 0, 0, 0
    for e in EVAL_:
        r = answer(e["q"])
        got = [x["source_id"] for x in r["retrieved"]]
        rec = any(s in got for s in e["expect"]) if e["expect"] else None
        correct_abst = (r["abstained"] == (not e["answerable"]))
        if e["answerable"]:
            n_ans += 1
            hit5 += bool(rec)
        abst_ok += correct_abst
        if e.get("conflict"):
            conflict_ok += bool(r.get("conflicts"))
        rows.append({"q": e["q"], "answerable": e["answerable"], "abstained": r["abstained"], "recall_at_5": rec,
                     "correct_abstention_decision": correct_abst, "conflicts": r.get("conflicts"),
                     "top": got[:3], "answer": r["answer"][:240]})
    summary = {"n": len(EVAL_), "answerable": n_ans, "passage_recall_at_5": hit5 / n_ans,
               "abstention_decision_accuracy": abst_ok / len(EVAL_),
               "conflict_detected": f"{conflict_ok}/{sum(1 for e in EVAL_ if e.get('conflict'))}",
               "baseline_no_retrieval": {"passage_recall_at_5": 0.0, "abstention_decision_accuracy":
                                         sum(1 for e in EVAL_ if not e["answerable"]) / len(EVAL_),
                                         "note": "always-abstain baseline"},
               "status": "OBSERVED on a 13-question authored set; semantic support still needs two human reviewers",
               "rows": rows}
    return summary


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    cmd = argv[0] if argv else "eval"
    if cmd == "build":
        rows = build()
        print(f"{len(rows)} chunks from {len({r['source_id'] for r in rows})} sources -> {CORPUS}")
    elif cmd == "ask":
        print(json.dumps(answer(" ".join(argv[1:])), indent=1, ensure_ascii=False))
    else:
        build()
        s = evaluate()
        print(json.dumps({k: v for k, v in s.items() if k not in ("rows", "held_out")}, indent=1))
        print("held-out:", {k: v for k, v in s["held_out"].items() if k != "rows"})
        for r in s["rows"] + s["held_out"]["rows"]:
            print(("ABST " if r["abstained"] else "ANS  ") + ("ok " if r["correct_abstention_decision"] else "XX ") + f"R@5={r['recall_at_5']} | {r['q'][:70]} | {r['top']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def evaluate_locked(path) -> dict:
    """Run a pre-registered, locked evaluation file once; never used to tune thresholds."""
    spec = json.loads(open(path, encoding="utf-8").read())
    rows = []
    for e in spec["items"]:
        r = answer(e["q"], as_of=e.get("as_of"))
        got = [x["source_id"] for x in r["retrieved"]]
        rows.append({"id": e["id"], "type": e["type"], "answerable": e["answerable"], "abstained": r["abstained"],
                     "decision_correct": r["abstained"] == (not e["answerable"]),
                     "recall_at_5": (any(s in got for s in e["expect"]) if e["expect"] else None),
                     "conflict_flagged": bool(r.get("conflicts")) if e.get("conflict") else None,
                     "top3": got[:3], "coverage": r.get("top1_query_coverage"), "answer": r["answer"][:200]})
    by_type = {}
    for t in sorted({x["type"] for x in rows}):
        rr = [x for x in rows if x["type"] == t]
        by_type[t] = f"{sum(x['decision_correct'] for x in rr)}/{len(rr)} correct answer-or-abstain decisions"
    out = {"file": str(path), "n": len(rows), "decisions_correct": sum(x["decision_correct"] for x in rows),
           "recall_at_5_answerable": f"{sum(bool(x['recall_at_5']) for x in rows if x['answerable'])}/{sum(x['answerable'] for x in rows)}",
           "conflicts_flagged": f"{sum(bool(x['conflict_flagged']) for x in rows if x['conflict_flagged'] is not None)}/{sum(1 for x in rows if x['conflict_flagged'] is not None)}",
           "by_type": by_type, "rows": rows,
           "status": "OBSERVED on a small locked set; semantic adequacy still needs human review"}
    return out
