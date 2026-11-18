# AI Marketing Decision Studio: results and models in one place

Written for: the two presenters and the course examiners, as a plain overview. Every number is taken from `docs/MASTER_PROJECT_REPORT.md` or the saved files in `reports/` (source named in brackets). Where a number is an assumption or unknown, it says so.

## 1. The project in one paragraph
A retailer wants to know two things: does an e-mail create additional buyers, and can a model tell us whom to e-mail? The flagship case is a randomized e-mail experiment (Hillstrom, 64,000 customers). A supporting grocery case (84.51 Complete Journey, 2,469 households, 1,469,307 purchase lines, 2017) tests the same workflow on a different kind of data. A bounded agent path prepares a draft, a checker verifies every figure, and a named human decides. Nothing is ever sent.

## 2. Headline results

| Question | Answer | Status |
|---|---|---|
| Does the Men's e-mail create buyers? | Yes: 267 of 21,307 bought vs 122 of 21,306 with no e-mail = **6.8 additional buyers per 1,000 e-mailed** (95% interval 5.0 to 8.6) | Randomized, measured |
| And the Women's e-mail? | About 3.1 additional buyers per 1,000 | Randomized, measured |
| Incremental spend per customer e-mailed | 0.77 USD (Men's) vs 0.42 USD (Women's) | Randomized, measured |
| Does a model beat random targeting? | Point estimate yes (10.0 vs 7.4 extra buyers per 1,000 at the top 25%), but the gap +2.6 has interval -3.5 to +8.7, which includes zero | **Not proven** |
| Does a simple rule do as well? | Past-spend rule 11.6, recency rule 8.6 (per 1,000, top 25%) | Same caveat |
| Is the e-mail profitable? | Not shown: margin and cost per e-mail are unknown. Break-even at a 35% margin is about 0.27 USD cost per e-mail (0.17 on the conservative bound) | Scenario, not measured profit |
| Recommendation | Send the Men's e-mail broadly with a 10% no-e-mail holdout, only after finance confirms cost is below break-even; do not use the model to exclude anyone; a named human approves | Conditional |

**Why accuracy is not reported:** accuracy is 99.06%, exactly what "nobody buys" scores, because only about 1% buy. The meaningful measures are ranking (AUC about 0.64) and uplift (additional buyers per 1,000 contacts).

## 3. The models we used

### 3.1 Flagship: Hillstrom uplift models (protocols v2 and v3, written before fitting)
An uplift model estimates, for each customer, how much more likely they are to buy if e-mailed than if not.

| Model | Idea | Mean AUQ (buyers) | Paired 90% interval vs baseline |
|---|---|---|---|
| S_LOGIT (baseline) | One logistic model with treatment-by-feature interactions | 4.85 | baseline |
| S_LOGIT_SPARSE | Same, interactions only on past-purchase flags | 7.13 | -1.02 to +4.94 |
| T_LOGIT | Two logistic models (e-mailed, not e-mailed), subtract | 5.29 | -0.83 to +2.40 |
| S_HGB | Gradient-boosted S-learner | 4.42 | -2.68 to +6.63 |
| T_HGB | Gradient-boosted T-learner | 5.67 | -5.13 to +4.64 |
| TO_RIDGE | Transformed-outcome ridge | 5.55 | -1.00 to +2.86 |
| TO_HGB | Transformed-outcome gradient boosting | 2.09 | -8.07 to +1.22 |
| ENSEMBLE | Average of three members | 5.46 | -0.51 to +2.01 |

How it was kept honest: customer-level split (train 25,598 / validation 12,799 / test 25,603); settings fixed in advance (no tuning); selection by repeated 5-fold cross-fitting on train plus validation only; the test split read once; paired customer bootstrap for every interval.

What it showed:
- **No challenger was shown better** than the baseline, so the baseline S_LOGIT was kept.
- The baseline's signal is **not distinguishable from shuffled labels** (permutation p = 0.146).
- Random orderings of the same customers differ from each other by about as much as the candidates do (standard deviation about 3.4 buyers of Qini area), so differences of a few buyers are noise.
- About **284,000 customers** would be needed to confirm a gap of the observed size; the test split has 25,603. The smallest gap detectable today is about 8.8 per 1,000.

### 3.2 Scale replication on Criteo (protocol v4)
Question: is the Hillstrom "not stable" verdict a model problem or a data-size problem? Data: Criteo Uplift v2.1, 13,979,592 randomized rows (about 85% treated, 0.292% conversion), 2.8 million held out as test. Four fixed models (S_LOGIT, T_LOGIT, S_HGB, T_HGB) trained on 64,000 / 256,000 / 1 million / 4 million customers.

- Targeting beat random by about **+2.0 extra conversions per 1,000 contacts** with a Hillstrom-sized training set and about **+2.8** with 4 million.
- No challenger beat the plain logistic baseline; more training data helped only modestly.
- Reading: the Hillstrom verdict is **mostly an evaluation-power limit** (a big test set detects the gap, a small one cannot). This is a different advertising dataset, so it is a method check, **not evidence that Hillstrom's model works**.

### 3.3 Visit-outcome lab (protocol v5)
Same eight candidates, but on website visits (about 15% of customers, roughly 15 times more events than purchases). The selected model looked better in cross-fitting (permutation p = 0.024), but on the untouched test split the gain over random was **+12.0 visits per 1,000 with interval -8.4 to +32.8: not detectable**. A visit is not a purchase; this changes nothing about the buyer conclusions.

### 3.4 Supporting grocery case: purchase-propensity model
Predicts whether a household buys a category in the next four weeks (20 features, gradient-boosted `hgb_small`, isotonic calibration).

| Scorer | Average precision | ROC AUC |
|---|---|---|
| Trained model | **0.672** | 0.827 |
| Repeat-purchase rule | 0.621 | 0.787 |
| Popularity rule | 0.352 | 0.613 |

The gain over the repeat rule is +0.050 average precision (95% interval +0.045 to +0.056). **This is historical propensity, not response to a coupon**: past campaign recipients already spent 2.0 to 2.6 times more, so the history shows selection, not effect, and no coupon effect is claimed. At current assumptions no modelled plan pays per contacted household, so the advisor's status is "defer funding / no spend while terms are unconfirmed" and it creates 0 USD research and operations work instead. [model_card.md]

## 4. The agent and governance layer (not a predictive model)
- **Bounded roles:** coordinator, analyst, research, strategist, checker, CRM and measurement, each with a tool allowlist. No role has a send, spend, approve or publish tool (a test enforces this).
- **Deterministic specialists** carry the decision path, so every number traces to the validated export. One live check had a Claude model act as the analyst through read tools; it reported five claims that all matched the export.
- **Human approval** is bound to the hash of the exact plan; any change needs a new review. Approval only records a sandbox draft.
- **Checker rules:** every figure is tagged (OBSERVED, HELD_OUT_ESTIMATE, ASSUMPTION, PUBLISHED_REFERENCE, UNKNOWN); unknown values are null, never zero; drafts with prices, discounts or model-win claims are rejected.
- **What-if tool:** contribution = contacts x (spend x margin - cost per e-mail) - setup, always labelled "scenario, not measured profit".

## 5. ConsultAI review of the grocery bundle (Charbel's repo)
An offline, deterministic "Marketing Consultant" run on the shared grocery bundle, delivered as `reports/consultant_review.latest.json` (contract `consultant_review.v1`):
- **47 of 47** reference metrics recomputed by ConsultAI match our own manifest; this project's validator returns OK (19 of 19 shared metrics matched).
- Default case, yogurt: distinct buyers 1,196 (weeks 1-26) to 1,136 (weeks 27-53); 357 households stopped; **345 of them still shopped** at the retailer, 12 bought nothing in weeks 27-53; 519 households match the simple lapsing rule.
- Recommendation: check availability and assortment before any discount. Coupon effect, margin, cost, consent and stock are UNKNOWN. A one-page manager brief and a saved example of the checker blocking three unsupported drafts are in `reports/`.
- ConsultAI counts and compares; it does not score households with our trained model. The run used no API key and cost nothing.

## 6. Discovery (SEO/GEO) audit
20 answers from two Claude models (Sonnet 5.5 and Opus 5.5) on a public analogue brand (Kroger): mention rate 17/20 (85%), recommendation rate 12/20 (60%), primary pick 8/20 (40%). Kroger is recommended in all Browse and Buy answers but in none of the 8 Learn answers, which is a content gap. Limits: two models from one vendor, single run each, region not set, web search used in 14 of 20 answers. No traffic or sales effect is claimed. [geo_audit_results.md]

## 7. What we can and cannot claim

Can claim:
- The e-mail causes additional buyers (randomized): 6.8 per 1,000 (Men's).
- The workflow is bounded, checked and needs a human decision.
- Hillstrom's "model not proven" is mostly a test-size limit (Criteo replication).

Cannot claim:
- That the targeting model beats random for Hillstrom customers.
- Any profit (margin, cost and consent are unknown), any coupon effect, or any 2026 sales trend (the data are 2008 and 2017).
- That the discovery audit says anything about other AI assistants or about sales.

## 8. Still needs a human
Real margin and cost per e-mail and consent; two timed rehearsals; one real human approval in the app; interviews (0 of 2 to 3 done); deploying the app on your own account; optional live strategist and ConsultAI live runs with a new API key. See `docs/WHATS_LEFT.md`.

## 9. Where to look
`docs/MASTER_PROJECT_REPORT.md` (full report), `reports/campaign_lab/report.md`, `reports/criteo_scale/report.md`, `reports/campaign_lab_visit/report.md`, `reports/model_card.md`, `docs/geo_audit_results.md`, `docs/QA_PREP.md`, `START_HERE.md`.
