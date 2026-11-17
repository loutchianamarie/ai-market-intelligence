# GEO audit results (20 answers, two Claude models)

Generated from `data/seo/answer_log.csv` and `reports/seo_geo_audit.json`. Questions: `data/seo/prompt_panel.json` (frozen 2026-11-17 before the first answer, hash `1b0f0cf38c72a773`). Audited brand: **Kroger**, a public US grocery **analogue**; the dataset retailer is anonymous. Competitors tracked: Walmart, Target, Aldi.

## What was run, and what that limits
- **Assistant 1:** Claude Sonnet 5.5. **Assistant 2:** Claude Opus 5.5. Each question went to a fresh sub-agent with no project context and a web search tool available. Same settings, same wording.
- **These are not ChatGPT or Gemini.** Both assistants come from one vendor, so the result says what two Claude models answered on one date, not what other assistants would say. The worksheet's "two assistants" is met only loosely.
- Web search was used in 14 of 20 answers; 6 were answered from model knowledge with no sources. Where search was used, several answers state they read only result snippets. The source gap in the worksheet (domains cited when a competitor won) therefore cannot be computed: it is empty.
- Single run each; variability was not measured. Region was not set.

## The five rates (denominator 20)

| Metric | Value |
|---|---|
| Mention rate | 17/20 = 85% |
| Recommendation rate | 12/20 = 60% |
| Primary-pick rate | 8/20 = 40% |
| Share of voice | 17/56 = 30% |
| Share of recommendations | 12/34 = 35% |

**Read with care:** prompt 7 names the brand in the question, so Kroger's mention there is automatic. Excluding it (18 answers): mention 15/18, recommendation 10/18, primary pick 6/18.

## By intent

| Intent | Answers | Mentioned | Recommended |
|---|---:|---:|---:|
| Learn | 8 | 5/8 | 0/8 |
| Browse | 6 | 6/6 | 6/6 |
| Buy | 6 | 6/6 | 6/6 |

## By assistant

| Assistant | Mentioned | Recommended | Top pick |
|---|---:|---:|---:|
| Claude Sonnet 5.5 | 8/10 | 6/10 | 4/10 |
| Claude Opus 5.5 | 9/10 | 6/10 | 4/10 |

## What the answers show
- **Browse and Buy questions (12 answers):** Kroger is recommended in all of them. It is the top pick in all 6 Browse answers (best coupon app, loyalty programs, Kroger-vs-others for coffee) but in only 2 of the 6 Buy answers: for the 'this week' pizza deal and for Spanish coffee-with-coupon, other stores (Target, Walmart, Amazon) lead in some answers.
- **Learn questions (8 answers):** Kroger is recommended in none. It appears only as one example among several names (5 of 8 answers) and is absent from 3 (coffee cost twice, frozen-pizza quality once). The assistants answer these with general advice, not store names.
- **The leak in the worksheet funnel is the top pick:** when Kroger is recommended it is first in two thirds of cases, otherwise Target, Walmart or a deal on another store leads.
- **What it cannot say:** how a real shopper is treated, search rankings, traffic or sales. The assistants themselves note they could not verify this week's deals.

## Cited domains (where search was used)

- grocerychop.com: cited in 7 answers
- thekrazycouponlady.com: cited in 4 answers
- hip2save.com: cited in 4 answers
- thedailymeal.com: cited in 3 answers
- inkl.com: cited in 3 answers
- slickdeals.net: cited in 3 answers
- thepennyhoarder.com: cited in 2 answers
- tastingtable.com: cited in 2 answers

Retailers' own pages cited: harristeeter.com (a Kroger-owned banner), shop.lowesfoods.com, heb.com and target.com, each for a single deal or help page. kroger.com itself is never cited; iheartkroger.com is a fan deal blog, not the retailer. Most citations are coupon and deal blogs. That is a hypothesis for the content action, not a finding about buyers.

## Candidate actions (proposal; the team scores impact and effort 1 to 3)
1. **Learn-intent gap:** a factual, source-cited FAQ on how digital coupons work, limits and stacking, because no Learn answer recommends the brand. Evidence: 0 of 8 Learn answers recommend it. Cost: low.
2. **Official source gap:** the assistants cite deal blogs rather than the retailer's own coupon pages. Keep one consistent, current description of the offer on owned pages. Evidence: cited domains above. Cost: low.
3. **Repeat in ChatGPT and Gemini** with the same frozen questions before any claim about those assistants. Cost: about 25 minutes each.

Impact and effort are deliberately not filled in: they are the team's judgement. No visibility lift, traffic or conversion is claimed.
