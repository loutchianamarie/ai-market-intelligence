# AI Market Intelligence & Product Portfolio Optimization

*with an advisor that turns decisions into approved actions.* Course project (AI for Business and Marketing), Loutchiana Marie & Charbel Mezeraani.

**Decision:** where should a retailer put its next limited CRM budget (product category × existing-household segment × channel), and what must it test before expanding?
**Data:** the authentic 84.51° Complete Journey tables (2,469 households, 1.47M transaction lines, 2017; CC0, via the R package maintainers). See `docs/dataset_decision.md` for why H&M was not used.

## Quick start (Windows, Python 3.12)
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.lock.txt
pip install -e .                      # or add src/ to PYTHONPATH
python -m mi.cli all                  # download → audit → train/evaluate → portfolio & sensitivity → RAG eval → GEO → blocked demo → agents to the human checkpoint (~1.5 min)
python -m mi.cli test                 # 51 tests
python -m mi.cli demo                 # Streamlit manager app (offline; uses saved, hashed artifacts)
```
Human approval (after `all`): `python -m mi.agents.coordinator approve OPP-XXXX --approver "Full Name"`, then `python -m mi.agents.coordinator resume OPP-XXXX`. You can also approve in app tab 4. Rebuild the deck: `cd deck && npm install && cd .. && node deck/build_deck.js`.
Live LLM agents: set `ANTHROPIC_API_KEY`, then `python -m mi.agents.coordinator llm-smoke`.

## What is measured vs assumed (headline)
| | Result | Status |
|---|---|---|
Verified and corrected on 2026-11-14: see `docs/verification_and_claim_audit.md`.

| | Result | Status |
|---|---|---|
| Model vs rule (untouched window, weeks 50–53) | AP 0.662 vs 0.621 (repeat rule) vs 0.352 (popularity), base rate 0.275; same gap in all 3 held-out windows (+0.037/+0.043/+0.041). Predicts purchase under historical conditions, **not** who a coupon persuades | HISTORICAL OBSERVATION |
| Campaign imbalance | recipients' pre-campaign weekly spend 2.0–2.6× others' (selection, not effect) | HISTORICAL OBSERVATION |
| Base-case recommendation | NONE: every plan loses per contacted household even before setup (best −$44 per 1,000); broad mailing is an infeasible comparator | ASSUMPTION |
| What flips it | higher true uplift (≈2–3× assumed) **and** a hypothetical company scale (100k–250k, not in data) | ASSUMPTION + COMPANY SCALE ASSUMED |
| Learn-first test | contribution-based 2,623 per arm at an assumed 2× break-even uplift (5,246 consented households needed), assumed cost $1,927; overnight 866/arm design withdrawn (could not support EXPAND) | FUTURE EXPERIMENT, conditional |
| RAG | locked pre-registered set: 11/12 answer-or-abstain decisions, conflict flagged 0/1 (earlier 19/19 was on threshold-development sets) | HISTORICAL OBSERVATION (small set) |
| GEO audit | 0 / 20 real answers collected | PENDING (human) |
| Live LLM agents | Claude loop unit-tested with a mocked client only; no live call (no key) | PENDING |

## Layout
```
configs/policy.json          frozen categories, temporal split, scenario assumptions (v2; v1 kept)
src/mi/ingest/               download (sha256 manifest), loader, read-only audit
src/mi/model/                time-aware features + leakage contract, train/evaluate pipeline
src/mi/decision/             metric engine, scenario arithmetic, optimizer, demand, report, FashionForward fixture
src/mi/evidence/rag.py       dated corpus, BM25, span validation, abstention, conflict detection, eval
src/mi/seo/geo.py            frozen GEO panel checks, answer-log metrics
src/mi/outcome/learning.py   campaign history, sample size, simulated outcome, decision rule
src/mi/workflow/store.py     versioned dossier + CRM sandbox state machine (SQLite)
src/mi/agents/               tools + allowlists, Claude adapter, coordinator + 5 roles
app/streamlit_app.py         manager demo
deck/                        build_deck.js → AI_Market_Intelligence_Deck.pptx
docs/                        decision brief, research memo, agents canvas, traceability, metrics, protocols, presentation
reports/                     generated evidence (model card, portfolio, sensitivity, RAG eval, traces)
```

## Rules this repo keeps
Raw data and household-level files are never committed. No live send, spend or publication exists. Every number carries OBSERVED / MODEL ESTIMATE / ASSUMPTION / SIMULATION / FUTURE TEST. Simulated outcomes are never reported as impact. Retrieved web text is data, never instructions.
