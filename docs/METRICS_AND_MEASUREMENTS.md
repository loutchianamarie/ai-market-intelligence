# Metrics and measurements: what the project uses, what was missing, what was added

Written for: the two presenters and the examiners, to answer "which metrics did you use, and why".

## 1. What the project already measured

| Area | Measure | What it answers | Where it is computed |
|---|---|---|---|
| Who buys next (grocery model) | Average precision, ROC AUC | How well are likely buyers ranked above non-buyers? | `src/mi/model/train.py` |
| | Precision in the top 10%, recall at 3 categories | Is the head of the list useful? | `train.py` |
| | Brier score, log loss, calibration deciles, ECE | Does a 30% score mean about 30%? | `train.py`, `model/evaluate.py` (`ece`) |
| | Household bootstrap interval for the gain over the repeat rule | Is the gain more than noise? (+0.050, 95% interval +0.045 to +0.056) | `train.py` |
| | By category, by segment, ablation, rolling windows, documented failure | Where does it work, where not? | `train.py`, `model/evaluate.py` |
| Does an e-mail work (Hillstrom) | Additional buyers per 1,000 contacts, incremental spend per customer | What did the e-mail cause? (randomized) | `src/mi/campaign/` |
| | Qini / AUQ, top-25% policy gap versus random, paired customer bootstrap, permutation null, detectable gap and sample size | Does a targeting model beat random, and is the test big enough to tell? | `campaign/lab.py`, `lab_extras.py` |
| | Scale replication (Criteo, 14 million rows) | Is "not proven" a model problem or a test-size problem? | `campaign/scale.py` |
| Economics | Contribution = contacts x (spend x margin - cost) - setup, break-even cost, break-even uplift, additional buyers needed, ROI, ROAS, CAC, CPA, AOV | Would it pay, under stated assumptions? | `decision/scenario.py`, `decision/metrics.py`, `decision/optimizer.py`, `decision/buyer_outcomes.py` |
| Test design | Households per arm for a target response, minimum detectable effect, expand / stop / change rule, guardrails | How do we learn the real response? | `outcome/learning.py`, `configs/policy.json` |
| Cross-sell | Basket-level lift of B given A, validated on held-out weeks, benchmarked against popularity | Which partner category to offer? | `decision/opportunities.py` |
| Cohort turnover | How many households enter and leave a segment each 4 weeks | Is the segment stable? | `outcome/learning.py` (`cohort_turnover`) |
| Discovery (GEO) | Mention, recommendation and primary-pick rates, share of voice, share of recommendations, source gap, by intent | Does an AI assistant find and recommend the brand? | `seo/geo.py` |
| Governance | Provenance tags (OBSERVED, HELD_OUT_ESTIMATE, ASSUMPTION, PUBLISHED_REFERENCE, UNKNOWN), plan-hash approval, checker rules | Is every figure labelled and is a human in charge? | `claim_audit.py`, `workflow/`, `agents/` |

## 2. What was missing, and what was added in this pass

Cross-sell, ECE and cohort turnover already existed, so they were **not** duplicated.

| Gap | Why it matters in marketing | Added | Where |
|---|---|---|---|
| No lift or cumulative-gains view of the propensity model | "If I can only contact 20%, how many real buyers do I reach?" is the question a manager asks | Decile gains table, lift at any share, gains curve versus the repeat rule and random | `model/marketing_metrics.py`, page tab 5 |
| No customer tiers | Targeting and messaging differ for champions, at-risk and hibernating customers | RFM tiers (recency, frequency, spend, 1-5 scores; tied households share a score; uses only weeks up to the cut-off) | `marketing_metrics.rfm_table`, page tab 6 |
| No customer value | A customer who spends more is worth more to keep | Discounted-margin value proxy over 13 cycles, labelled ASSUMPTION (margin and retention are inputs) | `marketing_metrics.value_proxy`, tab 6 |
| No store retention measure | Lapse rate is a core CRM metric | Share of households active in one 4-week window that are active in the next | `marketing_metrics.retention_table`, tab 6 |
| No single marketing decision | Results were spread across five files and leaned toward "coupon or no coupon" | **Decision card per category:** who (segments), next best action per segment including free actions, does a paid offer pay (same engine as the portfolio), test design, cross-sell, discovery, 4 Ps, KPIs, confidence, unknowns, checker, approval PENDING_HUMAN | `decision/decision_card.py`, page tab 7, `reports/decision_cards/` |
| No way to test another dataset | You asked whether the project can take a new file | Dataset readiness check: finds the columns by name, tests history length, customers, qualifying categories, repeat purchasing, data quality, proposes the time split, says what the project can and cannot do | `data_readiness.py`, page tab 8 |
| GEO: no systematic QA, hard-coded page numbers, no export | The GEO numbers go on a slide | 20 checks (see section 4), numbers on the page computed from the log, Excel workbook | `seo/qa.py`, `reports/geo_qa_report.md`, `reports/geo_audit_answers.xlsx` |

## 3. What cannot be added without new data

| Not possible | Why | What would make it possible |
|---|---|---|
| Profit or ROI | Margin, cost per contact, consent and stock are unknown in any retail file | The client's confirmed values |
| Effect of a coupon on grocery | Coupon exposure was not randomized | A randomized holdout test (the card gives the design and the sample size) |
| A real customer lifetime value | Needs several years of retention data | Longer history; the proxy is a ranking aid only |
| Uplift on a new dataset | Needs a randomized treatment column | An A/B or randomized campaign file |

## 4. Using another dataset

```
python -m mi.data_readiness --transactions file.csv [--products products.csv] [--map household_id=cust_no]
python -m mi.data_readiness --demo        # the Complete Journey data this project was built on: expect READY
```
The check applies the same design as the grocery model: 12-week look-back, 4-week horizon, cut-offs 4 weeks apart (53 weeks for the full design, 37 for a reduced one), categories with 10% to 60% penetration in the label window and at least 100 buyers, and the same exclusions (fuel, alcohol, tobacco, coupons and miscellaneous, fresh meat and seafood). The time split it proposes for Complete Journey equals `configs/policy.json`, and a test keeps it that way for every history length from 37 to 79 weeks, so no training outcome window can run past the validation cut-off.

Verdicts: READY (everything passes), PARTIAL (works with the reduced design or with caveats), NOT_READY (a required column or enough history is missing, with the fix stated). A READY verdict means "the model can be trained and evaluated", not "it will work well": run the evaluation and read the intervals.

## 5. GEO QA: what the 20 checks cover

Panel structure and freeze (Q01, Q02); every prompt answered once by each assistant (Q03); required fields and valid Y/N codes (Q04, Q05); logical consistency, a top pick is a recommendation and a recommendation is a mention (Q06); competitors recommended were named (Q07); unique 64-character answer hashes (Q08); valid timestamps (Q09); no assistant or region drift (Q10); intent and language match the frozen panel (Q11); well-formed URLs that match the URL count in the notes (Q12); headline counts re-derived by a second code path (Q13); by-intent counts add up (Q14); 20 of 20 complete (Q15); limits recorded (Q16); second-language answers present (Q17); no typed numbers in the page source (Q18); content actions left unscored (Q19); the result says it is not traffic or sales (Q20). Each rule has a test that breaks the data on purpose and checks it is caught (`tests/test_geo_qa.py`).

Run it: `PYTHONPATH=src python -m mi.seo.qa` (writes the report and the workbook). What it does not test: whether the assistants' answers are right, other assistants or regions, repeat runs, or any effect on traffic or sales.

The workbook `reports/geo_audit_answers.xlsx` has the sheets README, Questions (10), Answers (20, one row each), Rates (overall, by intent, by language, by assistant), Share, Source_gap, Actions (impact and effort blank for the team to score) and QA.
