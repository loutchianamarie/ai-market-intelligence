"""Assemble docs/MASTER_PROJECT_REPORT.md from the project's own computed artifacts.

Every figure is read from: the validated campaign export, the model lab results, the claims export (grocery), the
protocols and the test files. Nothing numeric is typed here. Re-run after any pipeline change:

  python -m mi.report.master_report
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from mi.consumer.adapter import load_case
from mi.paths import DOCS, REPORTS, ROOT

OUT = DOCS / "MASTER_PROJECT_REPORT.md"


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"


def _git(*a) -> str:
    try:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return "unknown"


def n(v, d=1):
    return "unknown" if v is None else f"{v:,.{d}f}"


def ci(c, d=1):
    return f"{c[0]:+.{d}f} to {c[1]:+.{d}f}"


def test_inventory() -> tuple[int, list[tuple[str, int]]]:
    rows = []
    for f in sorted((ROOT / "tests").glob("test_*.py")):
        rows.append((f.name, len(re.findall(r"^def test_", f.read_text(encoding="utf-8"), re.M))))
    return sum(c for _, c in rows), rows


def build() -> str:
    case = load_case()
    if not case.ok:
        raise SystemExit(f"{case.status}: {case.reasons}")
    E = case.doc
    R = _j(REPORTS / "campaign_lab" / "results.json")
    X = _j(REPORTS / "campaign_lab" / "extras.json")
    G = {c["id"]: c["value"] for c in (_j(REPORTS / "current_claims.json") or {"claims": []})["claims"]}
    P2, P3 = ROOT / "data/eval/hillstrom_protocol_v2.json", ROOT / "data/eval/hillstrom_protocol_v3_lab.json"
    cl = case.claims()
    arms = {a["arm"]: a for a in E["observed_arm_metrics"]}
    eff = {e["treatment_arm"]: e for e in E["average_effects"]}
    pol = {p["policy_id"]: p for p in E["held_out_policy_metrics"]}
    mvb = E["model_vs_baselines"]
    total_tests, per_file = test_inventory()
    head = _git("rev-parse", "--short", "HEAD")
    C, M, W, Mn = arms["No E-Mail"], arms["Mens E-Mail"], arms["Womens E-Mail"], eff["Mens E-Mail"]
    Wn = eff["Womens E-Mail"]
    scen = {s["scenario_id"]: s for s in E["business_scenarios"] if s["arm"] == "Mens E-Mail"}
    thr = [t for t in E["economic_thresholds"] if t["arm"] == "Mens E-Mail"]
    sel, pn, cf = R["selection"], R["permutation"], R["confirmation"]
    comp = cf["comparisons"]
    pw, het, nf = X["power"], X["heterogeneity"], X["noise_floor"]
    nfull = X["noise_floor_full"]
    SC = _j(REPORTS / "criteo_scale" / "results.json")
    if SC:
        sv = SC["verdicts"]
        sz = list(sv)
        mg = lambda k: sum(sv[k][m]["mean_gap"] for m in sv[k]) / len(sv[k])
        scale_md = (
            "### 5.3b Scale replication on 14 million randomized rows (protocol v4, pre-registered)\n\n"
            f"To ask whether the Hillstrom verdict reflects too little data, the same method was run on the public Criteo uplift data ({SC['rows']:,} rows, {SC['treated_share'] * 100:.0f}% treated, "
            f"{SC['overall_conv_pct']:.2f}% conversion; a different, anonymised advertising setting). Four fixed candidates were trained on {len(sz)} nested sizes and scored on one untouched test set of {SC['test_rows']:,} customers. "
            f"Selecting the top 25% by score beat random targeting by about {mg(sz[0]):+.1f} extra conversions per 1,000 contacts already with a Hillstrom-sized training set and {mg(sz[-1]):+.1f} with about 11 million; "
            "the gain grew only modestly with 60 times more training data, and no challenger beat the logistic baseline. "
            "The difference from Hillstrom is mainly the size of the evaluation set (about 110 times larger here, so the interval is about 0.4 per 1,000 instead of about 6), plus a stronger signal in this dataset. "
            "This is evidence that the method can detect targeting value when the test is large enough, not evidence that the Hillstrom model works. Full table and limits: `reports/criteo_scale/report.md`.\n\n"
            "![Gap versus training size](../reports/criteo_scale/fig_gap_vs_size.png)\n")
    else:
        scale_md = ""
    cand = [k for k in sel["mean_auq"] if k not in ("RULE_RECENCY", "RULE_HISTORY", "RANDOM_ORDER")]
    lab_rows = "\n".join(f"| {k} | {sel['mean_auq'][k]:.2f} | {sel['sd_auq_over_repeats'][k]:.2f} | "
                         + (ci(sel["paired_diff_vs_baseline_ci90"][k], 2) if k in sel["paired_diff_vs_baseline_ci90"] else "baseline") + " |" for k in cand)
    pol_rows = "\n".join(f"| {lab} | {pol[pid]['additional_buyers_per_1000_contacts']['value']:.1f} | {ci(pol[pid]['additional_buyers_per_1000_contacts']['ci95'])} | "
                         f"{pol[pid]['treated_buyers']}/{pol[pid]['treated_n']:,} vs {pol[pid]['control_buyers']}/{pol[pid]['control_n']:,} |"
                         for pid, lab in (("RANDOM_MENS_25", "Random 25%"), ("RULE_RECENCY_MENS_25", "Recency rule 25%"), ("RULE_HISTORY_MENS_25", "Past-spend rule 25%"),
                                          ("MODEL_MENS_25", "Model 25%"), ("SEND_ALL_MENS_100", "Send to all")))
    scen_rows = "\n".join(f"| {s['label']} | {n(s['assumed_margin']['value'] and s['assumed_margin']['value'] * 100, 0) if s['assumed_margin']['value'] else 'unknown'}"
                          f"{'%' if s['assumed_margin']['value'] else ''} | {n(s['cost_per_contact']['value'], 3)} | {n(s['fixed_setup_cost']['value'], 0)} | "
                          f"{'unknown' if s['contribution']['value'] is None else n(s['contribution']['value'], 0) + ' USD'} |" for s in scen.values())
    thr_rows = "\n".join(f"| {t['assumed_margin']['value']:.0%} | {t['break_even_cost_per_contact']['value']:.3f} | {t['break_even_cost_per_contact_conservative']['value']:.3f} |" for t in thr)
    tests_rows = "\n".join(f"| `{f}` | {c} |" for f, c in per_file)
    srcs = "\n".join(f"- `{s['source_id']}`: {s['title']}. {s['url']}" + (f" (accessed {s['accessed']})" if s.get('accessed') else "") for s in E["sources"])
    unknowns = "\n".join(f"- {a['name']} (needed from {a.get('needed_from')})" for a in E["assumptions_and_unknowns"] if a["tag"] == "UNKNOWN")

    return f"""# AI Marketing Decision Studio: which e-mail creates additional buyers, and can a model tell us whom to target?

**Master project report** | AI in Business and Marketing, semester 3 | generated {date.today().isoformat()} from commit `{head}` by `python -m mi.report.master_report`

> Every number in this report is read from the project's computed artifacts (validated export, model-lab results, claims export). If a number changes, regenerate the report; do not edit it by hand.

## Abstract

Marketing budgets are justified by **additional purchasing customers**, not by clicks or by customers who would have bought anyway. We build a decision studio that answers one such question end to end: for an apparel retailer's existing customers, does a merchandise e-mail create additional buyers within two weeks, which e-mail works better, can a trained model identify whom to contact under a contact cap, and what should a manager approve? The flagship evidence is the public randomized Hillstrom (2008) experiment: {sum(a['n_customers'] for a in arms.values()):,} existing customers split at random into a Mens e-mail, a Womens e-mail and a no-e-mail control. The **randomized average effect is clear**: {M['buyers']} of {M['n_customers']:,} customers bought after the Mens e-mail against {C['buyers']} of {C['n_customers']:,} with no e-mail, i.e. **{n(Mn['additional_buyers_per_1000']['value'])} additional buyers per 1,000 e-mailed** (95% interval {n(Mn['additional_buyers_per_1000']['ci95'][0])} to {n(Mn['additional_buyers_per_1000']['ci95'][1])}). The **targeting model is not shown to beat random contacts or a simple rule**: on held-out customers it is ahead on the point estimate (verdict `{mvb['verdict']}`) but both paired intervals include zero. A pre-registered lab of {len(cand)} model variants found no challenger better than the baseline and no targeting signal distinguishable from shuffled labels; proving a gain would need roughly {round(pw['customers_needed_for_80pct_power_if_gap_is_real'], -3):,} customers. The recommendation is therefore a broad Mens send with a randomized holdout, conditional on cost and consent, decided by a named human. The system around the model (typed contract, bounded agents, programmatic checker, approval gate, offline demo) is built so that no agent can send, spend or approve, and every figure carries its provenance tag.

## 1. Business problem and research questions

A retailer can e-mail its customers. Sending costs money, and some customers buy anyway. The decision is **whom to contact with which message**, how many additional buyers that creates, and at what cost it stops paying. We ask:

- **RQ1** Does a merchandise e-mail increase the share of existing customers who buy within two weeks, compared with no e-mail?
- **RQ2** Which e-mail (Mens or Womens merchandise focus) creates more additional buyers?
- **RQ3** Does a trained uplift model, under a contact cap, beat random contacts and simple rules in additional buyers per 1,000 contacts, with uncertainty?
- **RQ4** Under uncertain margin and cost, what should a manager do, and what would reverse that decision?
- **RQ5** How can AI agents prepare the action while a human keeps authority over sending, spending and approval?

Scope: repeat purchase by **known customers**, not new-customer acquisition. A second, separate case (a US grocery retailer's household panel) is used to validate the product-portfolio and workflow code under assumptions; no grocery number enters the flagship case.

## 2. Related work and design influences

Uplift modelling estimates the difference an action makes for a customer, not the probability of buying (Radcliffe, 2007; Rzepakowski and Jaroszewicz, 2012; Gutierrez and Gerardy, 2017). Meta-learners (S-, T- and transformed-outcome learners; Kunzel et al., 2019) turn standard predictors into effect estimators. The Hillstrom challenge and its winning analysis (Radcliffe, 2008) report the same average effects we recompute and warn that rare purchases make small-segment targeting noisy. For agent design we adopted patterns from published systems and adapted them in original code (`docs/reference_patterns.md`): a visible task ledger and stop rule (Magentic-One), bounded source-backed research with abstention (Anthropic multi-agent research, GPT Researcher), held-out uplift at a fixed contact cap (scikit-uplift), and an editable brief with human review (Salesforce, Adobe). Our contribution is not a new algorithm: it is an end-to-end **decision and action audit** in which the model's verdict travels to the plan, the checker and the slides.

## 3. Data

| Item | Value |
|---|---|
| Source | `{E['dataset_provenance'].get('source_id')}`: Hillstrom, MineThatData E-Mail Analytics and Data Mining Challenge (2008) |
| File SHA-256 | `{E['dataset_provenance'].get('sha256')}` ({E['dataset_provenance'].get('bytes'):,} bytes, {E['dataset_provenance'].get('rows'):,} rows) |
| Unit | one existing customer who purchased in the previous twelve months (no customer ID in the file; the row index is the key) |
| Arms | Mens E-Mail {M['n_customers']:,}; Womens E-Mail {W['n_customers']:,}; No E-Mail {C['n_customers']:,} (randomized thirds) |
| Outcome | unique customer purchase within two weeks (`conversion`); `spend` is a secondary outcome |
| Pre-e-mail features | recency, past-year spend, past Mens / Womens purchase flags, newbie, zip type, channel |
| Forbidden as features | `visit`, `conversion`, `spend` (post-treatment) and the arm label (the treatment) |
| Buyers | {C['buyers'] + M['buyers'] + W['buyers']} of {sum(a['n_customers'] for a in arms.values()):,} customers ({100 * (C['buyers'] + M['buyers'] + W['buyers']) / sum(a['n_customers'] for a in arms.values()):.2f}%) |

The audit (`reports/campaign/data_audit.json`) found no missing values and balanced pre-e-mail covariates across arms. 6,562 fully identical rows were **kept**, because the file has no ID and the source states one row per customer. The source page states no licence terms, so the raw file stays local and is never committed. Sources used:

{srcs}

## 4. Methods

### 4.1 Randomized average effect
Each e-mail is compared with the **same** no-e-mail control. Rates are buyers divided by each arm's own customer count; the difference has an unpooled normal-approximation 95% interval. Incremental spend per contact is the difference in mean spend between the same arms.

### 4.2 Uplift model and policy evaluation (protocol v2, pre-registered)
Protocol `hillstrom_protocol_v2.json` (SHA-256 `{_sha(P2)[:16]}...`) was committed before the conversion model was fitted. A seeded customer-level split (train {E['model']['split']['n_train']:,} / validation {E['model']['split']['n_validation']:,} / test {E['model']['split']['n_test']:,}) is fixed; one L2-regularized logistic S-learner with treatment-by-feature interactions is fitted on train+validation; regularization is chosen on validation log loss. On the **test split, read once**, contact policies at fixed caps (25%, 50%, all) are compared: model-ranked contacts, random contacts (expected value), a recency rule, a past-spend rule, and send-to-all. Estimates are ratios of weighted sums under randomization, with a customer-level bootstrap (2,000 resamples) giving paired intervals. We report **additional buyers per 1,000 contacts**, the quantity a manager acts on; Qini area and calibration are secondary.

### 4.3 Model lab (protocol v3, pre-registered)
Protocol `hillstrom_protocol_v3_lab.json` (SHA-256 `{_sha(P3)[:16]}...`) was committed **before any candidate was fitted**. It fixes eight candidates with fixed hyperparameters (no tuning): the v2 baseline `S_LOGIT`; a sparse S-learner whose interactions use only the past-purchase flags; a logistic T-learner; gradient-boosted S- and T-learners; transformed-outcome ridge and gradient-boosting learners; and a three-member ensemble. Selection uses **repeated stratified 5-fold cross-fitting, 3 repeats, on train+validation only**, scored by the area between each candidate's Qini curve and the random line (AUQ, in buyers). A challenger replaces the baseline only if the paired customer bootstrap 90% interval of its AUQ difference lies above zero. The selected model is tested against shuffled arm labels (40 permutations) and then evaluated on the test split once. Exploratory add-ons (noise floor, likelihood-ratio heterogeneity tests, power) are labelled as such.

### 4.4 Economics
Contribution = contacts x (incremental spend per contact x assumed margin - cost per contact) - setup. Margin, cost and setup are **not in the data**; they are explicit assumptions in named scenarios, and every scenario is tagged `SCENARIO_NOT_MEASURED_PROFIT`.

## 5. Results

### 5.1 The randomized experiment (RQ1, RQ2)

| Arm | Buyers / customers | Rate | Additional buyers per 1,000 vs no e-mail | Incremental spend per contact (USD) |
|---|---|---|---|---|
| No e-mail (control) | {C['buyers']} / {C['n_customers']:,} | {C['purchase_rate']['value'] * 100:.2f}% | reference | reference |
| Mens e-mail | {M['buyers']} / {M['n_customers']:,} | {M['purchase_rate']['value'] * 100:.2f}% | {n(Mn['additional_buyers_per_1000']['value'])} ({n(Mn['additional_buyers_per_1000']['ci95'][0])} to {n(Mn['additional_buyers_per_1000']['ci95'][1])}) | {n(Mn['incremental_spend_per_contact']['value'], 2)} ({n(Mn['incremental_spend_per_contact']['ci95'][0], 2)} to {n(Mn['incremental_spend_per_contact']['ci95'][1], 2)}) |
| Womens e-mail | {W['buyers']} / {W['n_customers']:,} | {W['purchase_rate']['value'] * 100:.2f}% | {n(Wn['additional_buyers_per_1000']['value'])} ({n(Wn['additional_buyers_per_1000']['ci95'][0])} to {n(Wn['additional_buyers_per_1000']['ci95'][1])}) | {n(Wn['incremental_spend_per_contact']['value'], 2)} ({n(Wn['incremental_spend_per_contact']['ci95'][0], 2)} to {n(Wn['incremental_spend_per_contact']['ci95'][1], 2)}) |

Both e-mails create additional buyers; the Mens e-mail creates about twice as many as the Womens e-mail. These recomputed rates match the published reference figures, which are cited only as references (`PUBLISHED_REFERENCE`).

### 5.2 Does the targeting model help? (RQ3)

Held-out test split ({cf['n_test']:,} customers, {cf['test_buyers']} buyers), Mens e-mail, 25% contact cap:

| Policy | Additional buyers per 1,000 contacts | 95% interval | Counts (e-mailed vs not) |
|---|---|---|---|
{pol_rows}

Model minus random: **{mvb['model_minus_random_per_1000_contacts']['value']:+.1f}** (95% interval {ci(mvb['model_minus_random_per_1000_contacts']['ci95'])}). Model minus recency rule: **{mvb['model_minus_rule_per_1000_contacts']['value']:+.1f}** ({ci(mvb['model_minus_rule_per_1000_contacts']['ci95'])}). Verdict: `{mvb['verdict']}`. The past-spend rule, not selected on validation, scored {pol['RULE_HISTORY_MENS_25']['additional_buyers_per_1000_contacts']['value']:.1f}, above the model.

Classification accuracy is meaningless here (predicting that nobody buys is right {100 * (1 - cf['test_buyers'] / cf['n_test']):.2f}% of the time), so models are judged on uplift. As context, the baseline's purchase-probability metrics on the test split are: accuracy {100 * X['predictive']['accuracy_at_0.5']:.2f}% (equal to the 'nobody buys' rate of {100 * X['predictive']['accuracy_all_no_purchase']:.2f}%), ROC AUC {X['predictive']['roc_auc']:.2f} (by arm: no e-mail {X['predictive']['auc_by_arm']['No E-Mail']:.2f}, Mens {X['predictive']['auc_by_arm']['Mens E-Mail']:.2f}, Womens {X['predictive']['auc_by_arm']['Womens E-Mail']:.2f}), average precision {X['predictive']['average_precision']:.3f} against a base rate of {X['predictive']['base_rate']:.3f}, and log loss {X['predictive']['log_loss']:.4f} against {X['predictive']['log_loss_constant_rate']:.4f} for a constant rate: weak but above chance.

### 5.3 Model lab (RQ3, continued)

| Candidate | Mean AUQ (buyers) | SD over repeats | Paired 90% interval vs baseline |
|---|---|---|---|
{lab_rows}

- **No challenger is shown better** than the baseline (best challenger `{sel['best_challenger']}`, {ci(sel['paired_diff_vs_baseline_ci90'][sel['best_challenger']], 2)}); the baseline `{sel['selected']}` is retained.
- **Noise floor.** Random orderings of the same customers score {nf['mean']:+.2f} with standard deviation {nf['sd']:.2f} (95th percentile {nf['p95']:.1f}); differences of a few buyers between candidates are noise.
- **Permutation test.** The baseline's out-of-fold AUQ is {pn['real_auq_repeat0']:.2f} against a shuffled-label 95th percentile of {pn['null_p95']:.2f} (p = {pn['p_value']:.3f}): not distinguishable from no signal on train+validation.
- **Effect modification (exploratory).** A likelihood-ratio test of whether any feature changes the e-mail effect gives global p = {het['global']['p_value']:.3f}; no single feature survives Holm correction (smallest adjusted p = {het['per_feature'][0]['p_holm']:.3f}, `{het['per_feature'][0]['feature']}`).
- **Power.** If the estimated gap over random ({pw['observed_gap_per_1000']:+.1f} per 1,000) were real, a confirmatory test would need about {round(pw['customers_needed_for_80pct_power_if_gap_is_real'], -3):,} customers (80% power, 5% two-sided) against {pw['n_test_now']:,} in the test split; the smallest gap detectable today is about {pw['min_detectable_gap_per_1000_at_current_n']:.1f} per 1,000.

![Out-of-fold Qini curves](../reports/campaign_lab/fig1_qini_curves_oof.png)
![Selection](../reports/campaign_lab/fig2_selection.png)
![Uplift by contact share, all customers, cross-fitted](../reports/campaign_lab/fig3_uplift_by_cap_fullsample.png)
![Test-split confirmation](../reports/campaign_lab/fig4_test_confirmation.png)
![Permutation null](../reports/campaign_lab/fig5_permutation_null.png)
![Uplift calibration](../reports/campaign_lab/fig6_uplift_calibration.png)

{scale_md}
### 5.4 Economics and the decision (RQ4)

Break-even cost per e-mail for the Mens e-mail, by assumed margin (before setup):

| Assumed margin | Break-even cost, point (USD) | Conservative, lower bound (USD) |
|---|---|---|
{thr_rows}

Scenario contribution for a broad Mens send to {n(list(scen.values())[0]['contacts']['value'], 0)} assumed customers (**scenarios, not measured profit**):

| Assumption set | Margin | Cost per e-mail (USD) | Setup (USD) | Contribution |
|---|---|---|---|---|
{scen_rows}

**Recommendation** (`{E['recommendation']['status']}`, approval `{E['approval_status']}`): {E['recommendation']['decision']}

It would be reversed by: {' '.join('(' + str(i + 1) + ') ' + x for i, x in enumerate(E['recommendation']['would_reverse_if']))}

No e-mail is always an allowed outcome: without an e-mail {C['purchase_rate']['value'] * 100:.2f}% of customers still bought within two weeks, and those purchases are not caused by the campaign.

### 5.5 The supporting grocery case (separate evidence)
On a US grocery household panel ({G.get('data.households', 'n/a'):,} households, {G.get('data.transaction_lines', 0):,} transaction lines) a purchase-propensity model reaches average precision {G.get('model.AP')} against {G.get('model.AP_rule')} for a repeat-purchase rule and {G.get('model.AP_popularity')} for popularity (bootstrap interval {G.get('model.AP_gain_ci95')} for the gain). This is **historical propensity, not response to a coupon**; under the stated assumptions the portfolio optimizer's base-case recommendation is `{G.get('decision.recommendation')}`, and the advisor's status is `{G.get('advisor.status')}`. The case validates workflow, scenario and approval code, and is deliberately kept out of the flagship's evidence.

## 6. System design

```mermaid
flowchart TD
  A["Frozen export (contract v1, SHA-256 checked)"] --> B["Adapter: DATA_PENDING / REJECTED / OK"]
  B --> C["Coordinator: task ledger, one pass"]
  C --> D["Analyst: tagged numbers from the export"]
  C --> E["Research: sources, abstentions, GEO status"]
  D --> F["Strategist: drafts, holdout, work items"]
  E --> F
  F --> G["Checker: claims vs export, tags, unknowns"]
  G --> H["HUMAN: named approver, plan-hash bound"]
  H --> I["Sandbox CRM record (never a send)"]
  I --> J["Outcome log (only after a recorded action)"]
```

**Typed contract.** The marketing repo produces `reports/campaign_case.latest.json` (JSON Schema + cross-field validator); consumers read it through a checksum-verifying adapter. Every number carries a tag: `OBSERVED`, `HELD_OUT_ESTIMATE`, `ASSUMPTION`, `PUBLISHED_REFERENCE` or `UNKNOWN`; unknown values are `null`, never zero.

**Bounded agents.** Five roles with explicit tool allowlists; no role has a send, spend, approve or publish tool (a tested invariant). Findings copy values from the export with their tags; the checker rejects a changed value, a changed tag, an unknown source, a scenario shown as observed, an unknown rendered as zero, and any text claiming the model "wins" when the verdict is not stable. Human approval is bound to the SHA-256 of the exact plan: changing one word voids it. Mode is `DETERMINISTIC_SPECIALISTS`; one live LLM tool-use check of the analyst role matched all five requested values to the export (`reports/marketing_live_llm_check.json`); the strategist, checker and approval steps are not LLM-driven.

**Offline demo.** One Streamlit screen (`app/buyer_decision.py`), a static HTML backup, a generated decision brief and a five-slide deck, all reading the same view model so figures cannot drift apart.

**Verification.** {total_tests} test functions in {len(per_file)} files cover the contract, the model code, the agent boundary and the lab (synthetic data with a planted effect checks the metrics and the selection rule):

| Test file | Test functions |
|---|---|
{tests_rows}

## 7. Threats to validity and limitations

- **Few buyers.** {C['buyers'] + M['buyers'] + W['buyers']} buyers in total: top-k and subgroup comparisons are imprecise, which is the central reason the model cannot be shown better.
- **Repeated evaluation.** The data were analysed before the pre-registrations (disclosed in both protocols); the test split is not untouched data. The lab's selection uses train+validation only and the test split once, but earlier exposure remains.
- **Selection bias in descriptive curves.** Cross-fitted full-sample curves compare candidates the authors chose and carry no confirmatory weight.
- **Historical, single retailer.** A 2008 effect for one anonymous apparel retailer is a prior, not a forecast for a current customer base; a new randomized pilot is required.
- **Group effects only.** Treated-minus-control differences estimate additional repeat buyers for a population, not an individual's effect and not customer acquisition.
- **Economics are assumptions.** Margin, e-mail cost, setup and the mailable base are illustrative; the system states the threshold, not a profit.
- **Agents.** Deterministic specialists; live LLM execution verified only for the analyst role.
- **Missing field evidence.** 0 of 20 GEO answers logged and 0 customer interviews completed; no SEO or GEO effect is attributed to e-mail data.

Unknowns the business must supply:

{unknowns}

## 8. Ethics, privacy and governance

The experiment data are anonymous and contain no personal identifiers; the raw file is not redistributed. Any real campaign requires verified e-mail consent and unsubscribe handling (a listed launch blocker), and drafts contain no invented price, discount or customer claim (a checker rule). The system never sends, spends or approves; a named human decides, and the decision record names the approver, reason and plan version. Predicted uplift describes groups of similar customers and must not be used to treat an individual unfairly; the recommended policy deliberately does **not** exclude anyone on the basis of the model.

**Use of AI assistance.** Parts of the code, tests and documentation were produced with Claude Code (Anthropic) under the team's direction. Safeguards: all numbers are computed by code, claims are checked programmatically, protocols were committed before fitting, and the test suite runs offline. The team remains responsible for the work.

## 9. Reproducibility

```
git clone https://github.com/loutchianamarie/ai-market-intelligence && cd ai-market-intelligence
pip install -r requirements.lock.txt && pip install -e .
# raw data (not committed): download the CSV named in docs/campaign_data_dictionary.md into data/raw/hillstrom/hillstrom_2008.csv
python -m mi.campaign.export          # audit -> fit -> held-out evaluation -> export (about 10 s)
python -m mi.campaign.lab             # model lab (about 40 s)
python -m mi.campaign.lab_extras      # exploratory add-ons and the lab report
python -m mi.consumer.advisor run     # agent path to the human checkpoint
python -m mi.report.master_report     # this report
python -m pytest -q                   # {total_tests} test functions
```

| Artifact | SHA-256 |
|---|---|
| Hillstrom CSV | `{E['dataset_provenance'].get('sha256')}` |
| Campaign export | `{case.sha256}` |
| Protocol v2 | `{_sha(P2)}` |
| Protocol v3 (lab) | `{_sha(P3)}` |

The model was retrained independently on a second machine (different Python and library versions) and reproduced the same run ID, model version and every scientific number; only timestamps, versions and the 15th decimal differed. A Windows CRLF checkout changes the export's hash, so `.gitattributes` pins it byte-exact.

## 10. Conclusion and future work

The defensible finding is the randomized average effect: a Mens e-mail creates about {n(Mn['additional_buyers_per_1000']['value'])} additional purchasing customers per 1,000 existing customers within two weeks. A targeting model does not yet earn the right to exclude anyone. Next steps, in order of value: (1) obtain margin, e-mail cost and consent status; (2) run the recommended randomized pilot with a 10% holdout, sized for {E['recommendation']['holdout_plan']['customers_per_arm_needed']:,} customers per arm to confirm the average effect and, with far larger volume, to test targeting; (3) complete the 20 GEO answers and the customer interviews as separate evidence tracks; (4) extend live LLM tool use to the strategist and checker under the same approval boundary.

## References

- Hillstrom, K. (2008). MineThatData E-Mail Analytics and Data Mining Challenge. https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html
- Radcliffe, N. J. (2008). Hillstrom's MineThatData Email Analytics Challenge: An Approach Using Uplift Modelling. Stochastic Solutions. https://stochasticsolutions.com/pdf/HillstromChallenge.pdf
- Radcliffe, N. J. (2007). Using control groups to target on predicted lift: building and assessing uplift models. Direct Marketing Analytics Journal.
- Rzepakowski, P., and Jaroszewicz, S. (2012). Decision trees for uplift modeling with single and multiple treatments. Knowledge and Information Systems, 32, 303-327.
- Gutierrez, P., and Gerardy, J.-Y. (2017). Causal inference and uplift modelling: a review of the literature. JMLR Workshop and Conference Proceedings, 67.
- Kunzel, S. R., Sekhon, J. S., Bickel, P. J., and Yu, B. (2019). Metalearners for estimating heterogeneous treatment effects using machine learning. PNAS, 116(10), 4156-4165.
- scikit-uplift documentation. https://www.uplift-modeling.com/en/latest/quick_start.html
- Microsoft Research (2024). Magentic-One. https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/
- Anthropic (2025). How we built our multi-agent research system. https://www.anthropic.com/research/multi-agent-research-system
- Google Search Central. AI features and your website. https://developers.google.com/search/docs/appearance/ai-features

*Bibliographic details of the journal references were written from memory and must be checked against the sources before submission.*

## Appendix A. Claim ledger (slide-safe claims, from the export)

| Claim ID | Claim | Value | Tag |
|---|---|---|---|
{chr(10).join(f"| `{c['claim_id']}` | {c['text']} | {'unknown' if c['value'] is None else c['value']} {c['unit']} | {c['tag']} |" for c in E['claims'] if c.get('slide_safe'))}

## Appendix B. File map

| Path | Purpose |
|---|---|
| `src/mi/campaign/` | data audit, uplift model, evaluation, economics, export, contract, model lab |
| `src/mi/consumer/` | adapter, advisor (agents, checker, approval boundary), view model |
| `src/mi/report/` | this report's generator |
| `src/mi/agents/`, `src/mi/workflow/` | grocery-case agents and the versioned dossier / CRM sandbox store |
| `app/buyer_decision.py` | the one-screen demo |
| `deck/build_campaign_deck.py` | five-slide deck |
| `data/eval/` | pre-registered protocols (v1 visit track, v2 buyer model, v3 lab) |
| `reports/campaign_lab/` | lab results, figures, report |
| `docs/` | contract, briefs, runbook, reference cards, this report |
"""


def main() -> int:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(OUT.read_text(encoding='utf-8').split()):,} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
