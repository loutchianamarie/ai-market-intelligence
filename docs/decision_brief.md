# Executive decision brief: next CRM budget (dossier CJ-GROCERY-001)

**Labels:** HISTORICAL OBSERVATION · MODEL ESTIMATE · ASSUMPTION · SIMULATED WORKFLOW · FUTURE EXPERIMENT · COMPANY SCALE ASSUMED · PENDING. Revised 2026-11-14 (third pass).
- **Live dossier:** `OPP-9DA359C3` (REVIEW_REQUESTED). It carries the advisor's REJECT FUNDING (DEFER) recommendation; a named person decides.
- **Superseded, do not approve:** `OPP-80476CCD`, `OPP-BB3F6F1E`, `OPP-390338F3`, `OPP-E9A4AF0C`.

## The decision in one paragraph
**Decision owner:**
- **Decides:** the Category & CRM manager (a hypothetical role).
- **Must also approve:** finance (budget and margin), legal/privacy (contact and consent) and operations (stock).

**Question:** where should the next limited CRM budget go, and is a coupon test worth funding?

**Recommendation: no rollout and no funded test today.** Spend the next week on $0 research (interviews, the AI-answer audit, the retailer page checks and the client's missing inputs). Reopen the coupon question only if that research moves one of the hurdles below. The advisor recommends rejecting the drafted test, and a named person decides.

## 1. What we know (HISTORICAL OBSERVATION, 2,469 anonymized households, 2017)
- **Model vs rule:** a fitted model ranks who buys a category in the next 4 weeks better than a "bought recently" rule. AP 0.662 vs 0.621 (popularity 0.352; base rate 0.275); the same gap holds in three held-out windows. It predicts purchase under historical conditions. It does **not** identify whom a coupon persuades.
- **Campaign history is selection:** campaign recipients already spent 2.0–2.6× more before campaigns, so past campaign results cannot be read as effects.
- **Return rate is not a control:** 29.9% of lapsing buyer-category pairs return within 4 weeks while normal promotions run. That is not an untreated baseline.
- **The cohort turns over:** the lapsing frozen-pizza cohort is ~385–415 panel households at each 4-week cutoff, but **55–67% are new** each time, and only 18.5% are still lapsing 8 weeks later.

## 2. Customer problem, segment and journey (HYPOTHESES until interviews)
- **Segment:** LAPSING frozen-pizza buyers, who bought in 1–2 of the last 12 weeks but not in the last 4.

| Test | Result | Status |
|---|---|---|
| Measurable | Yes. 406 panel households | HISTORICAL OBSERVATION |
| Reachable | Unknown: consent and offer mechanics | UNKNOWN |
| Substantial | Unknown. 7,308 is an assumed scale | COMPANY SCALE ASSUMED |
| Actionable | Only if the barrier is one we can change | HYPOTHESIS |

- **Job (hypothesis):** an easy dinner on a busy night.
- **Journey:** the observable leak is **Keep**. These shoppers still shop weekly, so *Learn* (awareness of the category) is unlikely to be the problem. *Browse* (comparing brands, store brand, ready meals) and *Buy* (stock, pickup) are possible leaks we cannot see in transactions. Interviews and the AI-answer audit look at those stages.

**Positioning and 4 Ps depend on the barrier:**

| If the real barrier is… | Positioning (to test, never published) | Product | Price | Place | Promotion | Coupon? |
|---|---|---|---|---|---|---|
| Lapsed habit | "the easy dinner you already like, back on your list" | as is | as is | as is | reminder, maybe offer | candidate (a reminder costs less) |
| Price | "good value for a busy night" | as is | targeted offer or value tier | as is | offer message | candidate |
| Availability | — | — | — | fix stock, shelf, pickup listing | none until fixed | **no** |
| Taste / quality | — | assortment, trial size | — | — | — | **no** |
| Convenience | "ready when you are" | — | — | pickup/delivery visibility | — | **no** |
| Discovery (shopper never sees it) | factual content where shoppers ask | — | — | — | content/listings (GEO) | **no** |

## 3. Alternatives and how money decides (ASSUMPTION-based; all money is simulated)
| Alternative | What it is | Value today |
|---|---|---|
| **NONE + research** | interviews, AI-answer audit, page checks, client inputs | $0; **recommended** |
| Non-coupon fix | stock, assortment, reminder, content: whichever P interviews point to | not costed; depends on research |
| Coupon, best base plan | Coffee / lapsing / digital | −$44 per 1,000 contacted before setup; loses at base |
| Coupon, test candidate | Frozen Pizza / lapsing / digital | −$47 per 1,000; loses at base |
| Broad mailing (illustrative comparator) | popular categories to everyone | −$651 per 1,000; over budget |

**Coffee vs Frozen Pizza:** Coffee is the least-negative plan at today's assumptions. Frozen Pizza is the cohort that needs the smallest rise in response to break even (1.59× vs 1.77× the assumed uplift). That makes Frozen Pizza the one to *test* if anything is tested. Neither is a recommendation to spend.

**Contribution per contacted household, vs a no-contact control:**

v = Δq·(g − F) − c − q0·r·F

| Term | Meaning | Status |
|---|---|---|
| Δq·(g − F) | extra buyers' margin, net of their coupon | Δq ASSUMED; g = observed spend × ASSUMED 28% margin |
| c | contact cost, $0.03 | ASSUMED |
| q0·r·F | coupons redeemed by people who would have bought anyway | q0 MODEL ESTIMATE; r ASSUMED 35%; F = OBSERVED $0.90 face value |

**Guardrails:** opt-out ≤ 2%, complaints ≤ 0.5%, no stock-outs.

## 4. Is a coupon test worth funding? Same plan, three questions (SIMULATION; COMPANY SCALE ASSUMED)
All rows: Frozen Pizza / lapsing / digital, 2,623 treated + 2,623 control, $1,500 setup per wave, 7,308 assumed reachable households.

| Question | Hurdle (true extra 4-week purchase rate) | Assumed today |
|---|---|---|
| (a) Does a contacted household add contribution at all? | **6.4 pp** (unit break-even, before setup) | 4.0 pp, so no |
| (b) Would a rollout cover its $1,500 setup? | **16.7 pp** if the *full* assumed pool is offered every cycle (upper bound); **23.1 pp** if only new entrants (observed 61.6% per cycle) are offered | no |
| (c) Is paying for the test worth it? | **27.0 pp** if the payoff is a one-off to the 4,685 households not yet offered (control + never enrolled) and must cover the test as well | no |

**What the test buys, if true uplift is…**

| True uplift | Test net cost (setup − treated-arm incremental contribution) | A: full pool every cycle (upper bound) | B: new entrants only, per cycle | C: one-off to the 4,685 not yet offered |
|---|---:|---:|---:|---:|
| 4.0 pp (assumed) | $1,623 | −$1,843 | −$1,711 | −$1,720 |
| 12.7 pp (**what the test is sized for**) | $1,168 | −$575 | −$931 | −$907 |
| 19.1 pp (3× unit break-even) | $836 | +$349 → recovers in 3 cycles | −$361 | −$315 |

Reading:
- **12.7 pp is not a commercial success.** It is the effect the 2,623/arm design can detect, and at that response every rollout scenario loses money.
- **The only payback is an upper bound.** It appears only in scenario A at ≥ 19 pp. A assumes the whole pool is offered again every cycle with the same response to repeat offers, with no fatigue, constant stock and consent, and setup paid each time. In the panel, about 40% of each cycle's cohort were already in the previous one, so repeat response matters and is unobserved.
- **Testing against the hurdle itself is impractical.** A test built to show contribution above the A hurdle, not merely above zero, needs:
  - 9,631 households per arm if true uplift is 20 pp, which is infeasible in 7,308;
  - 3,751 per arm at 22 pp, still infeasible;
  - only 1,534 per arm at 25 pp, i.e. **6× our assumption**.

  So a decision-grade test is only "feasible" if one already believes an implausibly large effect. It stays a FUTURE option.
- **Gross test outlay is $1,927** (2,623 × $0.163 + $1,500), valued at the assumed 4 pp. The first-pass claim "pays back after ~2 cycles" compared this test with Coffee's best case and is withdrawn.

**Advisor action:** the advisor recommends **REJECT FUNDING (DEFER)** and attaches a $0 research checklist. A named approver rejects in the app (tab 4) or the CLI, approving that checklist in the same versioned record. The agent then records the checklist in the sandbox as PLANNED. No contact, spend, send or field work is executed. A scripted rehearsal of the whole path is in `reports/rejection_rehearsal.json`. It ran in a throwaway store, and its "approver" is labelled as a script.

## 5. Evidence-to-decision matrix (what would change which action)
| Question | Current evidence / unknown | Low-cost method (owner) | If A → decision | If B → decision |
|---|---|---|---|---|
| Why did lapsed buyers stop? | **Unknown**: 0 interviews | 2–3 consented interviews, coded barriers (L: I01–I02, C: I03) | Habit or price → a reminder or offer stays a candidate; re-run §4 | Stock, taste, brand switch, convenience → the matching non-coupon fix (§2); **no coupon test** |
| How many consented, reachable households? | **Unknown**; 7,308 is assumed | Ask the client (both) | ≫ 7,308 or setup ≪ $1,500 → hurdles fall toward 6.4 pp; re-run §4 | ≤ 7,308 → no decision-grade test is possible; NONE |
| What is the real margin? | 28% ASSUMED | Ask finance (both) | Higher → every hurdle falls; re-run | ≤ 28% → NONE holds (it holds even at 40% under base uplift) |
| How do our offers reach shoppers? | Unknown for our retailer; competitors differ (§6) | Ask the client; verify competitor pages by hand (C) | Clip/opt-in → less subsidy to habitual buyers | Automatic → more subsidy (q0·r·F up); the coupon case weakens |
| Do assistants surface the analogue when shoppers ask how to save on frozen pizza or coffee? | **0/20 answers** | 20 fresh-chat answers on the frozen panel (L: Assistant 1, C: Assistant 2) | Absent while competitor pages are cited → content/listing action (non-coupon) | Present → discovery is not the barrier |
| Is stock available? | Unknown | Ask operations (both) | Yes → precondition met | No → no promotion of any kind |

**SEO/AEO/GEO limits:**
- The audit studies a **public analogue** (Kroger vs Walmart, Target, ALDI). It cannot be joined to the anonymous 2017 panel.
- Assistant visibility is not organic search impressions, traffic or incremental purchases.
- The panel *adapts* the class worksheet, which is a solo Lebanon-brand exercise. Fit with the official brief is pending.

## 6. Public offer mechanics at analogue retailers (checked 2026-11-14)
| Retailer, official page | What we could verify | Channel | Eligibility | Status |
|---|---|---|---|---|
| ALDI, [store terms of use](https://www.aldi.us/store/aldi/pages/terms-of-use) | Promotion codes are valid on orders via ALDI's online Services, entered at checkout; promotional prices may not apply in physical stores | site / app orders | online orders | **Fetched** (screenshot pending) |
| ALDI, [aldi.us/terms](https://www.aldi.us/terms) | Coupons apply to qualifying items displaying the offer, for a limited time, and can change; describes online Services including Instacart-operated sites/apps | online ordering | online orders | **Fetched** (screenshot pending) |
| Kroger, [coupon policy](https://www.kroger.com/i/terms/coupon-policy) | Reported: card holders without a digital account can get digital-offer pricing at the customer service desk | in-store desk; digital | card holders | **UNVERIFIED** (403) |
| Target, [Circle offers](https://www.target.com/help/articles/target-circle/target-circle-offers) | Reported: most Circle deals apply automatically at checkout for members | store / site / app | members | **UNVERIFIED** (429) |
| Walmart, [Walmart Cash](https://www.walmart.com/help/article/walmart-cash/77662758469249c29aed82885d5e554f) | Reported: manufacturer offers pay Walmart Cash after an eligible purchase (a reward, not an instant discount) | app / account | account holders | **UNVERIFIED** (bot check) |

The withdrawn claims "ALDI takes no online coupons" and "every retailer requires sign-in" are recorded in the claim audit, rows 18–19. *Our* retailer's consented, reachable pool is unknown and is not inferred from competitors.

## 7. Limits stated plainly
| Component | What it is | What it is not |
|---|---|---|
| Model | a measured purchase-ranking tool | a persuasion or uplift model |
| Optimizer | category × segment × channel allocation | a SKU or inventory optimizer |
| Demand and risk | scenario analyses | observed forecasts |
| CRM | a sandbox | anything that sends |
| RAG | evaluated on tiny sets; the old v3 set is now a development set | a validated retrieval system |
| Live LLM agents | pending; no API key | — |
| Data | one anonymous panel from 2017 | evidence about the transferability of 2017 behaviour, which is untested |
