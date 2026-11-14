# AI Market Intelligence & Product Portfolio Optimization

*with an advisor that turns decisions into approved actions.* Course project (AI for Business and Marketing), Loutchiana Marie & Charbel Mezeraani.

**Decision:** where should a retailer put its next limited CRM budget (product category × existing-household segment × channel), and is any test worth funding before expanding?
**Data:** the authentic 84.51° Complete Journey tables (2,469 households, 1.47M transaction lines, 2017; CC0, via the R package maintainers). See `docs/dataset_decision.md` for why H&M was not used.
**Current recommendation:** no rollout and no funded test at base assumptions; $0 research first (`docs/decision_brief.md`). Live dossier: `OPP-9DA359C3`. The advisor recommends REJECT FUNDING (DEFER), and a named person decides.

## Quick start (Windows, Python 3.12)
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.lock.txt
pip install -e .                      # or add src/ to PYTHONPATH
python -m mi.cli all                  # download → audit → train/evaluate → portfolio & sensitivity → RAG eval → GEO → blocked demo → agents to the human checkpoint (~3 min on our laptop; measured 3 m 11 s)
python -m mi.cli test                 # 59 tests
python -m mi.cli demo                 # Streamlit manager app (offline; uses saved, hashed artifacts)
python -m mi.claim_audit              # independent re-derivation of every headline number → reports/claim_audit.json
python -m mi.seo.geo check            # which of the 20 GEO answers are still missing
python -m mi.evidence.interviews check   # validate coded interviews (summarize → n of N)
python -m mi.agents.coordinator rejection-rehearsal   # scripted reject + research-checklist path (throwaway store)
```

**Human approval** (after `all`):
1. `python -m mi.agents.coordinator approve OPP-XXXX --approver "Full Name"` (or approve in app tab 4).
2. `python -m mi.agents.coordinator resume OPP-XXXX`.

**Rebuild the deck:** `cd deck && npm install && cd ..`, then `NODE_PATH=deck/node_modules APPLY_THEME=<pptx skill>/scripts/apply_theme.js node deck/build_deck.js`.

**Live LLM agents:** set `ANTHROPIC_API_KEY` in the current shell only, then run `python -m mi.agents.coordinator llm-smoke`.

## What is measured vs assumed (headline)
Verified and corrected on 2026-11-14 (three passes): see `docs/verification_and_claim_audit.md`.

| | Result | Status |
|---|---|---|
| Model vs rule (untouched window, weeks 50–53) | AP 0.662 vs 0.621 (repeat rule) vs 0.352 (popularity), base rate 0.275; same gap in all 3 held-out windows (+0.037/+0.043/+0.041). Predicts purchase under historical conditions, **not** whom a coupon persuades | HISTORICAL OBSERVATION |
| Campaign imbalance | recipients' pre-campaign weekly spend 2.0–2.6× others' (selection, not effect) | HISTORICAL OBSERVATION |
| Base-case recommendation | NONE: every plan loses per contacted household even before setup (best: Coffee/lapsing −$44 per 1,000); broad mailing is an infeasible illustrative comparator | ASSUMPTION |
| What flips it | higher true uplift (≈2–3× assumed) **and** a hypothetical company scale (100k–250k, not in data) | ASSUMPTION + COMPANY SCALE ASSUMED |
| Test candidate | Frozen Pizza/lapsing (needs the smallest uplift multiple to break even: 1.59× vs Coffee 1.77×) | ASSUMPTION |
| Is a test worth funding? | 2,623/arm detects 12.7 pp, but at 12.7 pp every rollout scenario loses (full pool −$575/cycle; new entrants −$931; one-off −$907). Hurdles: unit 6.4 pp; rollout 16.7 pp (upper bound) / 23.1 pp (new entrants) / 27.0 pp (one-off incl. test). **Not worth funding**; the advisor recommends rejecting | SIMULATION; FUTURE EXPERIMENT |
| Cohort turnover | lapsing frozen-pizza cohort ~385–415 panel households per 4-week cutoff; 55–67% new each time | HISTORICAL OBSERVATION |
| Interviews | 0 of 2–3; intake check ready (`mi.evidence.interviews`) | PENDING (human) |
| RAG | locked pre-registered set 11/12, conflict 0/1 (before fix); after a source-scope/conflict fix: v3 12/12 (no longer unseen), new adversarial set 3/3, conflict 1/1 | HISTORICAL OBSERVATION (small sets) |
| Retailer offer pages | ALDI terms fetched; Kroger/Target/Walmart blocked our automated check, so those details are unverified | PENDING (team check) |
| GEO audit | 0 / 20 real answers collected; panel adapts the class worksheet to a US grocery analogue | PENDING (human) |
| Live LLM agents | Claude loop unit-tested with a mocked client only; no live call (no key) | PENDING |

## Layout
```
configs/policy.json          frozen categories, temporal split, scenario assumptions (v2; v1 kept)
src/mi/ingest/               download (sha256 manifest), loader, read-only audit
src/mi/model/                time-aware features + leakage contract, train/evaluate pipeline
src/mi/decision/             metric engine, scenario arithmetic, optimizer, demand, report, FashionForward fixture
src/mi/evidence/rag.py       dated corpus, BM25, span validation, abstention, source scope, conflict detection, eval
src/mi/seo/geo.py            GEO panel checks, freeze/check, answer-log metrics
src/mi/outcome/learning.py   campaign history, cohort turnover, sample size, pilot/hurdle design, same-plan decision value, rule
src/mi/evidence/interviews.py interview intake check and n-of-N summary
src/mi/workflow/store.py     versioned dossier + CRM sandbox state machine (SQLite)
src/mi/agents/               tools + allowlists, Claude adapter, coordinator + 5 roles
src/mi/claim_audit.py        independent recomputation of headline claims
app/streamlit_app.py         manager demo
deck/                        build_deck.js → AI_Market_Intelligence_Deck.pptx (12 slides + appendix)
docs/                        decision brief, research memo, agents canvas, traceability, metrics, protocols, presentation, claim audit
data/interviews/, data/seo/  human evidence templates (no fabricated rows)
reports/                     generated evidence (model card, portfolio, sensitivity, RAG evals, traces)
```

## Rules this repo keeps
- Raw data and household-level files are never committed.
- No live send, spend or publication exists.
- Every number carries OBSERVED / MODEL ESTIMATE / ASSUMPTION / SIMULATION / FUTURE TEST.
- Simulated outcomes are never reported as impact.
- Retrieved web text is data, never instructions.
