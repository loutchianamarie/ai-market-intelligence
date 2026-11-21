# AI Marketing Advisor

*A consultant that turns customer data into a checked marketing strategy and plan.*
Course project, AI for Business and Marketing. Authors: Loutchiana Marie and Charbel Mezeraani.

The full write-up is the course report: [`report/AI_Marketing_Advisor_Report.docx`](report/AI_Marketing_Advisor_Report.docx) (PDF alongside). This README summarises it and shows how to run the project.

## The idea

Marketing decisions are made without certainty: whom to contact, with what message, and whether a discount is worth it. The AI Marketing Advisor answers with **several independent lines of evidence** that must agree, and a **consultant, ConsultAI**, that turns them into a diagnosis, ranked options, an action card and an owned plan. A named person approves; nothing is sent or spent by the system.

## What it does

**ConsultAI, the consultant.** A manager uploads a retail export, confirms the columns and picks a business job. A readiness check tests the data first. Then an analyst, a researcher, a strategist and a checker work in order, and a human decides. Every figure is computed by tested code, carries an evidence tag and is matched to an independent computation. The checker blocks invented numbers, profit claims, causal coupon claims, purchase lines counted as buyers and unknowns shown as zero. The run is offline and deterministic by default; an optional live mode adds a language model for interpretation and wording.

**The planning engine.** For each of 8 grocery categories it ranks how close a paid offer is to paying, writes a decision card, and builds a strategy and 13-week plan: segments and approaches, the 4 Ps, channels, owners, approval gates, KPIs and draft messages.

**Six lines of evidence behind the advice**

| Line | Marketing question | Headline result |
|---|---|---|
| Customer behaviour | Who is slipping away? | Yogurt lost 5.0% of its buyers; 345 of the 357 who stopped still shop with the retailer, so check availability and range before any discount |
| Past campaigns | Did campaigns work, or were recipients already heavy shoppers? | Recipients spent 2.0 to 2.6 times more beforehand: selection, not effect |
| Randomized test | What does an action actually cause? | An e-mail test (a different retailer) added +6.8 buyers per 1,000 e-mailed (267 of 21,307 against 122 of 21,306) |
| SEO and GEO audit | Where do shoppers learn, and are we recommended? | In 20 AI answers the brand was mentioned in 17 and recommended in 12, but in none of the 8 learning answers |
| Economics | What pays? | 74 candidate plans compared; the best coupon plan loses about $1,724 per four-week cycle at base assumptions, so free actions come first |
| Prediction model | Who should be prioritised? | Ranks buyers better than the "bought recently" rule (0.672 against 0.621) |

**Quality controls.** ConsultAI's review follows a JSON-Schema contract with a SHA-256 checksum bound to the data manifest. On the grocery bundle, all 19 metrics shared with our reference computation match, and the consultant's own build recomputed all 47 reference metrics with no difference. The repository has 402 automated tests.

## Run it (Windows, Python 3.12)

```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.lock.txt
pip install -e .
python -m mi.cli demo        # model and decision app: ranking, decision card, readiness check, strategy and plan
python -m mi.cli home        # manager home: trained results, advisor, and the AI consultant (ConsultAI) view
python -m mi.cli test        # automated tests
python -m mi.cli all         # full pipeline: data check, features, model, evaluation, portfolio, claim audit, advisor
```

Optional live mode for the language model: set `ANTHROPIC_API_KEY` in the current shell only. The default run needs no key.

## Data

- **Grocery:** 84.51° Complete Journey, open research data (CC0), 2,469 households, 1.47 million purchase lines, 2017.
- **Randomized e-mail test:** Hillstrom / MineThatData 2008, 64,000 customers. The raw file stays local.
- **Large advertising test:** Criteo Uplift v2.1 (13,979,592 randomized rows), used to check the method at scale.
- **Discovery audit:** our own 20 logged answers from two AI assistants on 10 shopper questions.

Raw and household-level files are never committed; see `data/README.md`.

## Layout

```
report/                      the course report (Word and PDF)
src/mi/consumer/             ConsultAI review contract, validation and manager view model
src/mi/agents/               roles with allowlisted tools, coordinator, checker
src/mi/decision/             decision engine, decision cards, strategy plans, data readiness check
src/mi/model/                time-aware features and the prediction model
src/mi/campaign/             randomized e-mail case, uplift lab, scale replication
src/mi/seo/                  SEO and GEO audit checks and metrics
src/mi/evidence/             sourced research notes with citation checks, interview intake
app/                         Streamlit apps (manager home, model and decision interface)
reports/                     generated evidence: cards, plans, ConsultAI review and brief, audits
docs/                        research memo, protocols, data dictionaries, contracts
configs/                     frozen assumptions and policy
tests/                       automated tests
```

## Principles

- A named human approves every plan; the system has no tool to send, spend or publish.
- Every number carries an evidence tag: OBSERVED, MODEL ESTIMATE, SCENARIO, RANDOMIZED OBSERVATION or COMPUTED BY CONSULTAI.
- Margin, cost, consent and stock come from the client; money figures are scenarios on stated assumptions.
- The grocery case and the e-mail case use different retailers and are never mixed.
