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
| AI-answer audit (to do; 0/20 answers logged) | What specific assistants said on a dated run | Rankings, traffic, sales |
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
| — | Kroger / Walmart / Target / Aldi pages | **Not collected**: automated fetches returned 403/429. The team must record observations manually with date and screenshot | PENDING |

## 4. Competitor / analogue observations
**Update 2026-11-14 (verification pass):** a web search of official retailer pages produced summaries of their digital-offer mechanics; see the table in `docs/decision_brief.md` §5 (Kroger, Target, Walmart, ALDI, with URLs). They are *search summaries*, not verbatim quotes, so the team must verify each against the live page (task 4 in `docs/team_tasks.md`) before quoting on a slide. Direct automated fetches still return 403/429.
The original note follows: automated fetching of the retailer pages was blocked, so **no competitor observations were claimed** at that time. Protocol for the team (15 min each): open the public digital-coupon page of Kroger, Walmart, Target and Aldi; record date, URL, how coupons are loaded, whether an account/app is required, and category examples; screenshot. Optional: Meta Ad Library search for the same brands (course primer Part 7). Record only what is visible, e.g. "this ad ran for 11 weeks", never "this ad is profitable".

## 5. Interview guide (6–10 consented interviews; recruit outside friends where possible)
Screen into two groups: (a) **lapsed category buyers** (bought frozen pizza before, not in the last month); (b) **nonbuyers** of the category who shop weekly.
1. "Walk me through your last grocery trip. What did you plan to buy and what did you add?"
2. "When did you last buy frozen pizza? What did you eat instead in the weeks you didn't?" (behaviour, not intention)
3. "Where do you see grocery deals: app, paper circular, shelf tags, email? Show me if you can."
4. "Tell me about a digital coupon you actually used. What made you load it?"
5. "Which store would you go to for frozen pizza, and why that one?"
6. Nonbuyers: "What would have to be true for frozen pizza to be on your list?" (listen for price, health, household, habit)
Avoid: "Would you use a coupon for frozen pizza?" (future, leading). Report refusals; do not extrapolate frequencies; no synthetic respondents as findings.

## 6. STP, positioning, 4 Ps
- **Segmentation (behavioural):** REGULAR, RECENT_LIGHT, LAPSING, ACTIVE_NONBUYER per category, from pre-cutoff purchases only. Demographics are not used: they cover 801 of 2,469 households, and the course primer notes they are a weak predictor.
- **Targeting:** LAPSING frozen-pizza buyers. Measurable (406 panel households; 7,308 reachable at 40× scale and 45% digital consent, both ASSUMPTION), reachable only with consent, and closest to break-even. The criterion is *value net of cost to serve*, not size. Under Assumption A1 (historical propensity ≈ no-coupon purchase), coupons to REGULAR buyers would mostly discount purchases they make anyway. That is an assumption to test, not a measured fact. The 7,308 figure is a hypothetical company-scale count, not data.
- **Positioning hypothesis:** see `decision_brief.md`. It must be validated in interviews before any public claim.
- **4 Ps:** see `decision_brief.md`. Diagnosis: if the friction is habit loss (Keep stage), Promotion to lapsed buyers is appropriate. If interviews reveal Product/Price issues (e.g., store-brand switching), a coupon is the wrong lever (primer §7, "which P is broken").

## 7. Funnel diagnosis
Historical data cover only the bottom of the funnel: purchase and repeat among existing shoppers. The observable bottleneck is **Keep**: across the eight categories, 29.9% of LAPSING household-category pairs bought again within the 4-week test window with no known intervention (and 30.5% is the model's mean estimate for frozen pizza at week 53). Discovery and comparison cannot be diagnosed from transactions; that is what the GEO audit and interviews are for.

## 8. Two alternative actions and why the target is actionable
- **A. Popularity-led broad mailing:** easy, but over budget and the most negative in every scenario.
- **B. Content/discovery action** (from GEO findings, after the audit): factual FAQ/comparison content. Measurable only with site-owner analytics.
- **Chosen: learn-first test** on LAPSING buyers. Actionable because it is defined by logged behaviour, reachable through the loyalty/app channel if consent exists, and leads to a different action than the status quo.

## 9. Comparable work and build / buy / rule
| Option | What it gives | Why not alone |
|---|---|---|
| Analyst spreadsheet + "bought recently" rule | Cheap and transparent; AP 0.621 on our test | Loses to the fitted model (AP +0.041), and has no economics or approval trail |
| Commercial journey/assortment suites (e.g., Adobe Journey Optimizer, Blue Yonder, Salesforce Einstein; vendor descriptions only) | Orchestration and decisioning at scale | Licences and integration; their claims are vendor descriptions, not audited for this decision |
| Google Meridian (MMM) | Media-mix budget allocation | Needs channel spend series, which this data does not have |
| **This prototype** | Transparent decision layer: tested model + labelled-assumption optimizer + approval workflow | Educational; no real costs, consent or stock |
