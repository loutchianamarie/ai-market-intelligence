# AI Market Intelligence & Product Portfolio Optimization

*with an advisor that turns decisions into approved actions.* Course project (AI for Business and Marketing), Loutchiana Marie & Charbel Mezeraani.

**Decision:** where should a retailer put its next limited CRM budget (product category × existing-household segment × channel), and is any test worth funding before expanding?
**Data:** the authentic 84.51° Complete Journey tables (2,469 households, 1.47M transaction lines, 2017; CC0, via the R package maintainers). See `docs/dataset_decision.md` for why H&M was not used.
**Manager summary:** `docs/marketing_brief.md` (buyer outcomes, 4P options, work queue) · `docs/decision_card.md` · opportunity cards `docs/opportunity_cards.md` · data dictionary `docs/data_dictionary.md`.
**Current recommendation:** no rollout and no funded test at base assumptions; $0 research first (`docs/decision_brief.md`). Advisor status: DEFER FUNDING / NO SPEND WHILE TERMS ARE UNCONFIRMED (base case: retailer-funded); live dossier in `NEXT_DAY_STATUS.md`, and a named person decides.

## Second client case: randomized e-mail campaign (`HILLSTROM_EMAIL_2008`)
A separate case with its own data, model and claims. Nothing here is grocery evidence, and no grocery number enters it.

**Decision:** which merchandise e-mail to send to which existing customers under a contact cap, how many additional purchasing customers that creates versus no e-mail, and at what cost it stops paying.
**Data:** Hillstrom / MineThatData 2008: 64,000 existing customers, randomized thirds (Mens e-mail, Womens e-mail, no e-mail), two-week purchase outcome. The raw file stays local.
**Read first:** `docs/campaign_decision_card.md` (manager), `docs/campaign_marketing_brief.md` (slide claims), `reports/campaign/model_card.md`, `docs/campaign_data_dictionary.md`.
**Cross-repo contract:** `docs/contracts/` (schema v1, synthetic fixture, handoff note). The export `reports/campaign_case.latest.json` is consumed read-only by the ConsultAI repo.

```
python -m mi.campaign.export                  # audit -> fit -> held-out policy evaluation -> economics -> export + cards (~25 s)
python -m mi.campaign.contract validate reports/campaign_case.latest.json
python -m mi.campaign.contract sample         # rewrite the SYNTHETIC_FIXTURE (deterministic)
python -m pytest -q tests/test_campaign_contract.py tests/test_campaign_case.py
```

**Consumer side (advisor, screen, deck).** The agent path reads the export only through `src/mi/consumer/adapter.py` (checksum, contract validation, `DATA_PENDING` when absent, synthetic fixture refused):

```
python -m mi.consumer.advisor run             # coordinator, analyst, research, strategist, checker -> human checkpoint (trace saved)
python -m mi.consumer.advisor blocked-demo    # send, self-approval and early CRM record all blocked
streamlit run app/buyer_decision.py           # ONE screen: buyers -> decision -> guarded action
python deck/build_campaign_deck.py            # five slides, notes, timings
python -m pytest -q tests/test_campaign_advisor.py
```

Mode is `DETERMINISTIC_SPECIALISTS`; a live LLM tool-use run is PENDING. See `docs/demo_runbook.md`, `docs/reference_patterns.md`, `docs/marketing_decision_brief.md`. `.gitattributes` pins the export byte-exact: a CRLF checkout changes its SHA-256.

**Scale replication (v4, pre-registered).** The same question on 14M randomized Criteo rows, with training sizes from 64,000 to 4M: `python -m mi.campaign.scale` then `python -m mi.campaign.scale_report` (needs `data/raw/criteo/`, hash pinned in `data/eval/criteo_protocol_v4_scale.json`). Result in `reports/criteo_scale/report.md`. Start with `START_HERE.md`.

**Visit-outcome lab (v5, pre-registered).** The same lab on website visits (15x more events, an intermediate outcome): `python -m mi.campaign.lab_visit` then `python -m mi.campaign.lab_visit report`; result in `reports/campaign_lab_visit/report.md` (not detectable on the test split).

**Master project report:** `docs/MASTER_PROJECT_REPORT.md` (generated from the computed artifacts by `python -m mi.report.master_report`): problem, methods, results, system, limits, ethics, reproducibility, references.

**Model lab (v3, pre-registered).** Eight fixed candidates compared by cross-fitted Qini area, a permutation null and one test-split confirmation: `python -m mi.campaign.lab` then `python -m mi.campaign.lab_extras` (about 1 minute). Results, six figures and a generated report are in `reports/campaign_lab/` (`report.md`). **Finding: no challenger beats the v2 baseline, and the targeting signal is not distinguishable from noise with 578 buyers; the decision rests on the randomized effect.** Needs the raw CSV in `data/raw/hillstrom/` (SHA-256 checked).

Protocol `data/eval/hillstrom_protocol_v2.json` was committed before the conversion model was fitted. The earlier visit analysis (`mi.experiments.hillstrom`, protocol v1) is unchanged.

## Quick start (Windows, Python 3.12)
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.lock.txt
pip install -e .                      # or add src/ to PYTHONPATH
python -m mi.cli all                  # download → VERIFY (data/manifest.lock.json) → audit → train → evaluate → portfolio, sensitivity & reversal → claim audit → RAG → GEO/interview checks → Hillstrom method track → agents to the human checkpoint (~8.5 min incl. the full promotions table; logs in reports/run_logs, record in reports/run_manifest.json, current claims in reports/current_claims.json)
python -m mi.cli test                 # 202 tests (grocery + advisor, campaign case, Charbel's consumer, model lab and report)
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
| Model vs rule (window weeks 50–53; repeated evaluation) | AP 0.672 vs 0.621 (repeat rule) vs 0.352 (popularity), base rate 0.275; household-bootstrap CI of the gain +0.045 to +0.056; rolling-origin gains in all 3 windows. Long-history features adopted 2026-11-14 under a pre-registered rule (was 0.662). Predicts purchase under historical conditions, **not** whom a coupon persuades. Details: `docs/technical_model_status.md` | HISTORICAL OBSERVATION (TRAINED+EVALUATED) |
| Campaign imbalance | recipients' pre-campaign weekly spend 2.0–2.6× others' (selection, not effect) | HISTORICAL OBSERVATION |
| Base-case recommendation | NONE: every plan loses per contacted household even before setup (best: Coffee/lapsing −$44 per 1,000); broad mailing is an infeasible illustrative comparator | ASSUMPTION |
| What flips it | higher true uplift (≈2–3× assumed) **and** a hypothetical company scale (100k–250k, not in data) | ASSUMPTION + COMPANY SCALE ASSUMED |
| Test candidate | Frozen Pizza/lapsing (needs the smallest uplift multiple to break even: 1.59× vs Coffee 1.77×) | ASSUMPTION |
| Is a test worth funding? | Recomputed with the adopted model: 2,737/arm detects 12.46 pp, but at that response every rollout scenario loses (full pool −$595/cycle; new entrants −$943; one-off −$934). Hurdles: unit 6.23 pp; rollout 16.55 pp (upper bound) / 22.99 pp (new entrants) / 26.87 pp (one-off incl. test). Only true uplift ≥ 4.14× the assumption flips the choice (no single other input does). **Not worth funding**; the advisor recommends rejecting | SIMULATION; FUTURE EXPERIMENT |
| Randomized e-mail experiment (Hillstrom 2008) | Visit method track (`mi.experiments.hillstrom`, protocol v1) is unchanged and never grocery evidence. A **separate buyer case** `HILLSTROM_EMAIL_2008` (protocol v2, conversion outcome) is in `docs/campaign_decision_card.md`, app tab 10 and `reports/campaign_case.latest.json`: Mens e-mail 267/21,307 vs 122/21,306 control buyers; the targeting model is ahead of random and the rule on the point estimate only (not stable) | OBSERVED (randomized) + MODEL ESTIMATE (repeated evaluation); separate case |
| Cohort turnover | lapsing frozen-pizza cohort ~385–415 panel households per 4-week cutoff; 55–67% new each time | HISTORICAL OBSERVATION |
| Interviews | 0 of 2–3; intake check ready (`mi.evidence.interviews`) | PENDING (human) |
| RAG | locked pre-registered set 11/12, conflict 0/1 (before fix); after a source-scope/conflict fix: v3 12/12 (no longer unseen), new adversarial set 3/3, conflict 1/1 | HISTORICAL OBSERVATION (small sets) |
| Retailer offer pages | ALDI terms fetched; Kroger/Target/Walmart blocked our automated check, so those details are unverified | PENDING (team check) |
| GEO audit | 20 / 20 answers logged on 2026-11-17 from two **Claude** models (not ChatGPT or Gemini): Kroger analogue mentioned 17/20, recommended 12/20, top pick 8/20 (prompt 7 names the brand; 15/18, 10/18, 6/18 without it); recommended in 0/8 Learn answers. No traffic or sales claim. `docs/geo_audit_results.md` | OBSERVED (small, one vendor); ChatGPT/Gemini rerun PENDING |
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
src/mi/ingest/verify.py      raw files vs committed data/manifest.lock.json
src/mi/model/evaluate.py     pre-registered evaluation (rolling origin, calibration drift, subgroups)
src/mi/decision/reversal.py  decision inputs (measured vs assumed) + one-at-a-time reversal
src/mi/outcome/pilot.py      randomized pilot ingestion, ITT estimate, decision rule with commercial hurdle
src/mi/experiments/          Hillstrom randomized e-mail method track (raw data local only)
src/mi/campaign/             campaign case HILLSTROM_EMAIL_2008: contract + validator, data audit, conversion uplift model,
                             randomized-policy evaluation, economics, export and generated cards (isolated from grocery code)
docs/contracts/              frozen cross-repo contract v1: schema, synthetic fixture, integration handoff
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
