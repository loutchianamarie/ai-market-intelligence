# Market research memo

## 1. Decision question
Which product category × existing-household segment × channel deserves the next limited CRM test, and is a test worth running at all? Research matters only if it can change that choice (course market-research primer, Part 1).

## 2. What each evidence type can and cannot answer

| Evidence | Answers | Cannot answer |
|---|---|---|
| Secondary sources (dataset docs, platform guidance, course material) | Data provenance, definitions, what Google says about AI features | Shopper motives; retailer costs |
| Historical transactions (2,469 households, 2017) | Who bought what, when; segment sizes; purchase propensity; demand baseline | Why people lapsed; anyone *outside* the panel; response to a *new* coupon |
| Campaign/redemption records | Who received and redeemed what | Causal effect: recipients were pre-selected heavy shoppers (2.0–2.6× pre-period spend) |
| Interviews (to do; none conducted yet) | Reasons, alternatives, friction, language | Frequencies or market size |
| AI-answer audit (done: 20/20 answers from two Claude models, one dated run, public analogue; ChatGPT/Gemini retest pending) | What specific assistants said on a dated run | Rankings, traffic, sales |
| Randomized pilot (future) | Incremental contribution | — |

## 3. Evidence ledger (source → claim)

| ID | Source (retrieved 2026-11-14) | Claim supported | Status |
|---|---|---|---|
| E1 | bradleyboehmke.github.io/completejourney (index) | 2,469 households who are frequent shoppers at one retailer; one year of all purchases | OBSERVED |
| E2 | github.com/cunningjames/completejourney_py readme | The Python port contains **simulated** data and says not to use it for research; it reports 801 households | OBSERVED (conflict with E1, resolved by our audit) |
| E3 | `reports/data_audit.md` | 1,469,307 lines; 0 exact duplicate rows; discounts stored as positive magnitudes; 801/2,469 households have demographics; campaign assignment undocumented | OBSERVED |
| E4 | developers.google.com/search/docs/appearance/ai-features | "There are no additional requirements to appear in AI Overviews or AI Mode, nor other special optimizations necessary." | OBSERVED |
| E5 | Course marketing primer §3–7 | Segment tests (measurable, reachable, substantial); positioning sentence; 4 Ps diagnostic | Course material |
| E6 | Course market-research primer Parts 1, 4, 6 | Dashboards miss nonbuyers; sampling-frame bias; synthetic respondents are never results | Course material |
| E7 | Course metrics slides / Module 04 workbook | Sum first, then divide; break-even ROAS = 1 / margin; platform ROAS overstates | Course material |
| E8 | `reports/model_card.md` | Model vs rule on a locked test | OBSERVED backtest |
| E9 | `campaign_history()` output | Campaign recipients' pre-period spend is 2.0–2.6× other households' | OBSERVED descriptive |
| E10 | aldi.us/store/aldi/pages/terms-of-use; aldi.us/terms (fetched 2026-11-14) | ALDI's online terms allow promotion codes / coupons on online orders | OBSERVED (screenshot pending) |
| E11 | Kroger coupon policy; Target Circle offers; Walmart Cash help (2026-11-14) | Offer mechanics differ (assisted in-store access, automatic member deals, post-purchase reward) | **UNVERIFIED by us**: pages returned 403 / 429 / bot check; details are the reviewer's reading until the team checks them live |
| — | aldi.us/about-us/faqs/aldi-gift-cards/ | Cited earlier for "ALDI takes no online coupons" | **WITHDRAWN**: the URL redirects (301) to an unrelated payments help page |

## 4. Competitor / analogue observations
Updated 2026-11-14 (second pass). The verified/unverified table is in `docs/decision_brief.md` §5. Corrections:
- **"ALDI takes no online coupons": removed.** ALDI's own online terms describe promotion codes entered at checkout and coupons on qualifying items, for online orders. The URL we had cited redirects to an unrelated payments page.
- **"Every analogue retailer requires a signed-in digital account": removed.**
  - Kroger's coupon policy reportedly gives card holders without a digital account an assisted path at the customer service desk.
  - Target reportedly applies most Circle deals automatically for members.
  - Walmart's manufacturer offers reportedly pay Walmart Cash after purchase, which is a reward, not an instant discount.
  - All three pages blocked our automated access, so each detail stays **UNVERIFIED** until a team member checks the live page and screenshots it (task 4 in `docs/team_tasks.md`). We do not rely on search snippets.
- **What we keep:** our *hypothetical* retailer's eligible, consented and reachable pool is unknown, and none of these programmes tells us its size.

Protocol for the team (15 min per page):
1. Open the page in a normal browser.
2. Record the exact URL, access date, channel (in-store / site / app), eligibility and a one-line paraphrase.
3. Take a screenshot.
4. Mark anything you cannot see as unverified.

Optional: a Meta Ad Library search for the same brands (course primer Part 7). Record only what is visible, e.g. "this ad ran for 11 weeks", never "this ad is profitable".

## 5. Interview guide (2–3 consented convenience interviews this week; exploratory)
The full script and consent wording are in `data/interviews/interview_template.md`, and coding goes in `data/interviews/coding_sheet.csv`.

Screen into two groups:
- (a) **lapsed frozen-pizza buyers**, who bought before but not in the last month;
- (b) **nonbuyers** of the category who shop weekly. Include one if possible.

The five questions ask about past behaviour, and none mentions coupons or deals before the respondent does:
1. **Last real purchase:** "Think about the last time you bought frozen pizza (nonbuyer: a quick dinner you didn't cook). Walk me through it: where, when, what you picked."
2. **Stopping or switching:** "Was there a stretch when you stopped buying it, or bought something else instead? What was going on then?"
3. **Trade-offs:** "When you chose, what did you compare: price, brand, what was in stock, how easy it was to get? Tell me about a time one of those changed what you bought."
4. **Discovery path:** "The last time you worked out what to buy or where it was cheaper, what did you look at or ask? A person, a flyer, an app, a search, an AI assistant?"
5. **Last decision not to buy:** "Think of the last time you could have bought it and didn't. What happened?"

**Avoid:**
- "Would you use a coupon for frozen pizza?" It is future and leading.
- Any mention of our offer.

**Reporting rules:**
- Report coded themes and counterexamples with n ("2 of 3"), never population percentages.
- No invented or paraphrased-as-quote text.
- Record refusals.

**How a barrier would change the decision (pre-registered):**

| Barrier observed | Segment | Offer | Decision |
|---|---|---|---|
| Habit lapsed / stopped thinking of it | keep LAPSING | reminder or offer stays a candidate | test still conditional on §4 of the brief |
| Price | keep | offer stays a candidate; check store-brand price gap | as above |
| Switched to store brand / other meal | redefine (brand-switchers) | a coupon may only subsidise a switch back | likely NONE; consider an assortment action |
| Out of stock / not on pickup | keep | no offer | fix Place first; no test |
| Taste / health / household change | not actionable by price | no offer | NONE |

## 6. STP, positioning, 4 Ps
- **Segmentation (behavioural):** REGULAR, RECENT_LIGHT, LAPSING, ACTIVE_NONBUYER per category, from pre-cutoff purchases only. Demographics are not used: they cover 801 of 2,469 households, and the course primer notes they are a weak predictor.
- **Targeting:** LAPSING frozen-pizza buyers. Measurable (406 panel households, OBSERVED). Reachable: UNKNOWN (the 7,308 at 40× scale and 45% digital share are ASSUMPTIONS). Substantial: UNKNOWN for a real company. It is the cohort needing the smallest multiple of assumed uplift to break even. The criterion is *value net of cost to serve*, not size. Under Assumption A1 (historical propensity ≈ no-coupon purchase), coupons to REGULAR buyers would mostly discount purchases they make anyway. That is an assumption to test, not a measured fact. The 7,308 figure is a hypothetical company-scale count, not data.
- **Positioning hypothesis:** see `decision_brief.md`. It must be validated in interviews before any public claim.
- **4 Ps:** see `decision_brief.md`. Diagnosis: if the friction is habit loss (Keep stage), Promotion to lapsed buyers is appropriate. If interviews reveal Product/Price issues (e.g., store-brand switching), a coupon is the wrong lever (primer §7, "which P is broken").

## 7. Funnel diagnosis
Historical data cover only the bottom of the funnel: purchase and repeat among existing shoppers. The observable bottleneck is **Keep**: across the eight categories, 29.9% of LAPSING household-category pairs bought again within the 4-week test window. That is an *observed return under historical conditions*, not an untreated baseline, because the retailer's existing promotions were running (30.5% is the model's mean estimate for frozen pizza at week 53). Discovery and comparison cannot be diagnosed from transactions; that is what the GEO audit and interviews are for.

## 8. Two alternative actions and why the target is actionable
- **A. Popularity-led broad mailing** (an *illustrative comparator*, not a documented status quo at a real company): easy, but over budget and the most negative in every scenario.
- **B. Content/discovery action** (from GEO findings, after the audit): factual FAQ/comparison content. Measurable only with site-owner analytics.
- **Chosen now: NONE + research.** A learn-first test on LAPSING frozen-pizza buyers is the candidate *if* research supports it. It is the cohort closest to flipping the decision. But at the assumed scale the test does not recover its cost unless true uplift is ≥ 16.7 pp (brief §4).

## 9. Comparable work and build / buy / rule
| Option | What it gives | Why not alone |
|---|---|---|
| Analyst spreadsheet + "bought recently" rule | Cheap and transparent; AP 0.621 on our test | Loses to the fitted model (AP +0.041), and has no economics or approval trail |
| Commercial journey/assortment suites (e.g., Adobe Journey Optimizer, Blue Yonder, Salesforce Einstein; vendor descriptions only) | Orchestration and decisioning at scale | Licences and integration; their claims are vendor descriptions, not audited for this decision |
| Google Meridian (MMM) | Media-mix budget allocation | Needs channel spend series, which this data does not have |
| **This prototype** | Transparent decision layer: tested model + labelled-assumption optimizer + approval workflow | Educational; no real costs, consent or stock |
