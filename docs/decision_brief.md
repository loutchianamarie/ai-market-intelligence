# Manager memo: CRM budget decision (dossier CJ-GROCERY-001)

**Labels:** HISTORICAL OBSERVATION · MODEL ESTIMATE · ASSUMPTION · SIMULATED WORKFLOW · FUTURE EXPERIMENT · COMPANY SCALE ASSUMED · PENDING.
Revised 2026-11-14 (second pass) after the same-plan economics reconciliation and the retailer-page check. It supersedes the earlier versions.
- Live dossier: **`OPP-390338F3`**.
- Superseded, do not approve: `OPP-80476CCD` (866/arm design) and `OPP-BB3F6F1E` (its worth-it check compared this test with a different plan).

**To:** Category & CRM manager (hypothetical role; finance approves budget, legal/privacy approves contact)
**Decision:** where to put the next limited CRM budget (category × existing-household segment × channel), and whether any test is worth funding.
**Recommendation:** **No rollout at base assumptions.** Do the cheap research in §6 first. A randomized test is not worth funding at the assumed company scale unless the research gives a credible reason to expect a much larger response than we assume (§4).

## 1. What the real data show (HISTORICAL OBSERVATION; 2,469 anonymized frequent-shopper households, 2017)
- **Model vs rule:** the fitted model ranks *who buys a category in the next 4 weeks* better than a "bought it recently" rule.
  - Average precision 0.662 vs 0.621 (popularity 0.352; base rate 0.275) on an untouched final window.
  - The gap is similar in all three non-training windows (+0.037, +0.043, +0.041). A paired household bootstrap gives +0.037 to +0.046, which covers household sampling within one holiday window only.
- **What the model is not:** it estimates purchase *under historical conditions*. It does **not** say who would buy without a coupon or whom a coupon would persuade. AP is not coupon uplift.
- **Returns without our offer:** 29.9% of LAPSING household-category pairs bought the category again within the 4-week test window. That is an *observed return under historical conditions*. The retailer's existing promotions and exposures were running, so it is not an untreated control.
- **Campaign history is selection:** households that received past campaigns spent **2.0–2.6× more per week before** those campaigns. Ever- vs never-recipients differ 4.1× in early weeks. This is observational imbalance, not campaign impact.
- **Weak spot:** for households with no recent category history the model is weak (AP 0.198, base rate 0.104), and the repeat rule has no signal at all.

## 2. Segment, positioning, 4 Ps

### Segment tests, checked separately
**Segment (behavioural):** LAPSING frozen-pizza buyers, who bought in weeks −12..−5 and not in the last 4.

| Test | Result | Status |
|---|---|---|
| Measurable | Yes. 406 panel households; model mean 4-week purchase probability 0.305 | HISTORICAL OBSERVATION / MODEL ESTIMATE |
| Reachable | **Unknown.** The panel is anonymized and cannot be contacted. Reach at a real retailer depends on consent and on how its offers are delivered (§5) | UNKNOWN |
| Substantial | **Unknown for a real company.** 7,308 reachable households is an assumed scale, not data | COMPANY SCALE ASSUMED |
| Actionable | Only if the reason for lapsing is something an offer can change. Otherwise a different P is broken (below) | HYPOTHESIS, needs interviews |

### Hypothesized job and barrier
- **Job (HYPOTHESIS):** an easy dinner on a busy night.
- **Barriers (HYPOTHESES, competing):** the habit lapsed (Keep stage); price; switched to a store brand or another meal solution; out of stock; taste or health.
- **Positioning hypothesis (to test, not to publish):** *For lapsing frozen-pizza buyers who already shop with us weekly, a one-tap digital offer makes it easy to pick the category back up, unlike broad circulars that reach everyone, including habitual buyers.*

### 4 Ps, each tied to a buyer question

| P | Current plan | Buyer question (interviews) | If the answer points here, the action is… |
|---|---|---|---|
| Product | Existing frozen pizza range; stock UNKNOWN | "Did you switch to a store brand or stop liking it?" | Assortment or trial size, not a coupon |
| Price | $0.90 coupon (historical mean discount) | "Was price the reason you stopped?" | A price test remains a candidate |
| Place | Stores + app; offer mechanics at our retailer UNKNOWN | "Was it out of stock, or hard to get on pickup/delivery?" | Fix stock or online listing, not a coupon |
| Promotion | One digital message with opt-out, no superlatives | "Did you simply stop thinking of it?" | A reminder or offer remains a candidate |

The coupon is one candidate response. If interviews show availability, taste, convenience or brand switching as the barrier, the better action is the matching non-coupon response above, at lower cost and with no subsidy to habitual buyers.

## 3. Options (ASSUMPTION-based scenarios; per contacted household first, then company scale)

| Option | Per 1,000 contacted, before setup | 4-week net at **assumed** 40× scale | Status |
|---|---:|---:|---|
| Popularity-led broad mailing (*illustrative comparator*, not a documented status quo) | −$651 | −$61,914 | **Infeasible** (over the $25k cap) |
| Best base plan: Coffee / lapsing / digital | −$44 | −$1,781 | feasible, loses at base |
| Test candidate: Frozen Pizza / lapsing / digital | −$47 | −$1,843 | feasible, loses at base |
| **NONE: research first** | $0 | $0 | **recommended** |

- **No company size rescues these plans.** A negative per-1,000 value means the plan loses on *every* contacted household before fixed costs.
- **Flips need two assumptions.** The reversals in the app (e.g., Frozen Pizza at 2× uplift with ~250k households) need *both* a higher true uplift *and* a hypothetical company scale. The 100k/250k figures are not in the data.
- **"Model-filtered" rests on Assumption A1.** That audience wins in some scenarios only because coupon cost to baseline buyers is approximated by historical propensity, with uplift held constant within a segment. It is a **stratification hypothesis** for a test, not measured targeting.

**Why the test candidate is not the best base plan.** Both lose at base, and Coffee loses slightly less ($44 vs $47 per 1,000). A test is worth running only where its answer could flip the decision. Frozen Pizza / lapsing needs the **smallest multiple of the assumed uplift** to break even:
- 1.59× vs Coffee's 1.77× per household;
- 4.17× vs 5.87× after setup, at the assumed scale;
- it is the first plan to flip in the reversal grid.

So it is the cohort closest to changing the answer. That makes it the test candidate, not a better plan.

## 4. Is a test worth funding? Same-plan reconciliation (SIMULATION; COMPANY SCALE ASSUMED)
Every row below is the **same plan**: Frozen Pizza / lapsing / digital, base margin 28%, redemption 35%, contact $0.03, setup $1,500 per cycle, 7,308 assumed reachable households.

**Design (FUTURE EXPERIMENT, not performed):**
- 50/50 randomized holdout, stratified by model-score half.
- Contribution-based sizing: **2,623 per arm**, assuming true uplift is 2× break-even (2 × 6.36 = 12.7 pp).
- It needs **5,246 eligible, consented households**, 72% of the assumed pool. The real panel has 406 such households and cannot be contacted.
- The overnight 866/arm design is withdrawn: it can only detect uplift *at* break-even, where contribution is zero.

| If the true uplift is… | Value per contacted household | Test net cost vs doing nothing (setup − treated-arm value) | Holdout value forgone | One rollout cycle after EXPAND | Whole cycles to recover the test |
|---|---:|---:|---:|---:|---|
| 4.0 pp (assumed) | −$0.047 | $1,623 | $0 | −$1,843 | never (rule says STOP) |
| 12.7 pp (**the uplift the test is sized for**) | +$0.126 | $1,168 | $332 | **−$575** | **never** |
| 16.7 pp (rollout break-even) | +$0.205 | $962 | $538 | $0 | never |
| 19.1 pp (3× break-even) | +$0.253 | $836 | $664 | +$349 | 3 |

**Reading:**
- **The test is sized for an uplift at which rollout still loses.** At 12.7 pp, each later 4-week rollout cycle to 7,308 households earns $924 of contribution but pays $1,500 setup, so it loses ~$575.
- **Recovery needs a much larger response.** The test recovers its cost only if true uplift is at least **16.7 pp**, i.e. 4.2× our 4 pp assumption and 2.6× break-even. Even at 19.1 pp it takes **3 whole cycles**.
- **Gross test cost is $1,927.** That is 2,623 × $0.163 plus $1,500 setup, valued at the assumed 4 pp. Net of the contribution the treated arm earns, it is $836–$1,623, depending on true uplift.
- **The earlier "pays back after ~2 favourable cycles" claim is withdrawn.** It divided this Frozen Pizza test cost by **Coffee's** all-favourable +$875 cycle, a different plan with different uplift, contact cost, reach and scale. Even on its own terms, 2 × $875 = $1,750 < $1,927.
- **What would change this:**
  - a much larger consented pool, so setup is spread over more households;
  - lower setup cost;
  - higher margin;
  - interview evidence that the barrier is one a coupon fixes, which would make a large uplift credible.
- **Statistical feasibility is not a reason to fund a test.**

**Launch preconditions (all UNKNOWN today):**
- consented pool ≥ 5,246;
- stock confirmed;
- margin confirmed by finance;
- consent/legal sign-off;
- a credible prior that true uplift reaches the rollout break-even for the real pool.

**Prewritten rule:**
- **EXPAND** if the 95% CI lower bound of incremental contribution per household is > 0 and guardrails pass (opt-out ≤ 2%, complaints ≤ 0.5%, no stock-outs).
- **STOP** if the upper bound is < 0 or any guardrail fails.
- **CHANGE** if positive but uncertain; otherwise **INCONCLUSIVE**.

## 5. Public offer mechanics at analogue retailers (checked 2026-11-14)
Our first-pass table said every analogue retailer requires a signed-in digital account and that ALDI takes no online coupons. **Both statements are withdrawn.** The ALDI claim cited a gift-card FAQ URL that now redirects (301) to an unrelated "forms of payment" help page.

| Retailer, official page | What we could verify | Channel | Eligibility | Status |
|---|---|---|---|---|
| ALDI, [aldi.us/store/aldi/pages/terms-of-use](https://www.aldi.us/store/aldi/pages/terms-of-use) | Promotion codes are valid on orders placed via ALDI's online Services and are entered at checkout; promotional prices may not be available in physical stores | site / app orders | online orders | **Fetched 2026-11-14** (screenshot pending) |
| ALDI, [aldi.us/terms](https://www.aldi.us/terms) | Coupons apply to qualifying items displaying the offer, for a limited time, and can be changed or cancelled. The terms describe online Services, including Instacart-operated sites/apps | online ordering services | online orders | **Fetched 2026-11-14** (screenshot pending) |
| Kroger, [coupon policy](https://www.kroger.com/i/terms/coupon-policy) | Reported (reviewer): Shopper's Card holders without a digital account can get digital-offer pricing by asking at a customer service desk | in-store desk; digital | card holders | **UNVERIFIED by us** (HTTP 403) |
| Target, [Circle offers](https://www.target.com/help/articles/target-circle/target-circle-offers) | Reported (reviewer): most Circle deals apply automatically at checkout for members | store / site / app | Circle members | **UNVERIFIED by us** (HTTP 429) |
| Walmart, [Walmart Cash](https://www.walmart.com/help/article/walmart-cash/77662758469249c29aed82885d5e554f) | Reported (reviewer): manufacturer offers pay out Walmart Cash *after* an eligible purchase, i.e. a post-purchase reward, not an instant discount | app / account | account holders | **UNVERIFIED by us** (bot check) |

**Implication:** retailers deliver offers through different mechanics: codes at online checkout, assisted in-store access, automatic member pricing, post-purchase rewards. Two consequences follow:
- **Our 45% "digital reach" share is a pure assumption.** It cannot be borrowed from any of these programmes.
- **Automatic application raises the subsidy to habitual buyers.** It increases redemption among people who would have bought anyway, the q0·r·F cost term.

*Our hypothetical retailer's* eligible, consented and reachable pool is **unknown** and is not inferred from competitors. These pages describe public offer mechanics. They do not show sales impact, and none of these retailers is the anonymous dataset retailer.

## 6. What to do this week: one decision-changing question per missing input

| Missing input | Question | If the answer is A → | If B → |
|---|---|---|---|
| Buyer interviews (2–3, exploratory) | Why did lapsed buyers stop: habit, price, store brand, stock, taste? | Habit/price → keep a price or reminder test as a candidate | Stock/taste/brand switch → drop the coupon; fix Product or Place; no test |
| Consented reach | How many eligible households have consented to digital offers? | ≫ 7,308 → setup is spread thinner; re-run §4 | < 5,246 → no decision-grade test is possible; NONE |
| Margin | What is finance's frozen-pizza contribution margin? | Well above 28% → break-even falls; re-run | ≤ 28% → NONE holds (it holds even at 40% under base uplift) |
| Stock | Can operations support extra units for 4 weeks? | Yes → precondition met | No → no promotion of any kind |
| Offer mechanics | Does our offer load automatically, need clipping, or have an in-store path? | Clip/opt-in → lower subsidy to habitual buyers | Automatic → more subsidy; the coupon case weakens |
| SEO/GEO discovery (20 answers) | When shoppers ask assistants how to save on frozen pizza or coffee, is the analogue mentioned, and which sources are cited? | Absent while competitors are cited → a content/discovery action (non-coupon) | Present → discovery is not the barrier |

Re-run the app with the answers. Approve a test **only** if the same-plan value in §4 turns positive for the real pool under a credible uplift.
