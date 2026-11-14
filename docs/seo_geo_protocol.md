# SEO / AEO / GEO audit protocol (two-person task, about 90 minutes in total)

Status: **0 of 20 answers collected. PENDING.**
- **Panel:** `data/seo/prompt_panel.json`, currently a *draft*. It is frozen with `python -m mi.seo.geo freeze` before the first assistant run.
- **Log:** `data/seo/answer_log.csv` (20 rows: 10 prompts × 2 assistants).
- **Progress check:** `python -m mi.seo.geo check`.

## What this audit is, and how it relates to the class worksheet
The class "GEO sprint" worksheet is an **individual** exercise. Each student picks **one Lebanese brand** (a café in Beirut, a phone-accessories web shop in Lebanon, or a beauty brand sold in Lebanon). Its language rule is "at least 2 prompts in Arabic, French or English".

This project **adapts the worksheet's measurement method** to its own market question, a US grocery analogue for the anonymous Complete Journey retailer:
- 10 buyer questions (4 Learn / 3 Browse / 3 Buy) and two assistants;
- a fresh chat per question;
- the five rates with denominators, the source gap and three ranked actions.

It is **not** the literal worksheet:
- the market is US grocery, not Lebanon;
- the second language is Spanish, the largest non-English US language;
- it is done as a pair, not alone.

We call it an *adaptation*, never "worksheet-compliant". Whether the adaptation meets the grading requirement is **PENDING** the official project brief (task 5 in `docs/team_tasks.md`).

**Rubric-fit note and fallback.**

| If the official brief says… | Then |
|---|---|
| GEO must support the project's business decision | Keep this panel (Kroger analogue, US grocery). It feeds the discovery question in the manager memo §6 |
| The literal worksheet is required (Lebanon brand, solo, Arabic/French/English) | Each student runs the worksheet alone on one of the three Lebanese brands. That takes about 45 min each with the same log format and `analyze` code (swap `audited_brand`, `competitors` and `prompts` in a copy of the panel file). Present it as a separate exercise; do not merge it into the grocery decision |
| Both | Do both; report them separately |

## The panel
- **Audited brand:** Kroger, as a *public US grocery analogue* with a digital-offer programme. The dataset retailer is anonymous, and we never claim the panel households are Kroger customers.
- **Competitors:** Walmart, Target, Aldi.
- **Rules:** the brand is named in at most 1 prompt; prompts are written as a shopper would type them.
- **Revisions:** if interviews legitimately change the wording, add an entry to `revision_log` (old text, new text, interview ID, reason). Then run `freeze`. **Never edit after the first answer.** All 20 answers must come from one frozen version, and `check` warns if they don't.

## Collection checklist (do it in this order)
| Step | Who | Done when |
|---|---|---|
| 0. Agree on the two assistants and identical settings (logged-out or fresh profile, region US, language as in the prompt, no custom instructions, web access the same in both) | both | written in the log's first row of each assistant |
| 1. `python -m mi.seo.geo freeze --by "Loutchiana Marie"` | L | panel file shows `frozen.at_utc` and `prompts_sha16` |
| 2. Assistant 1: for P01…P10, open a **new chat**, paste the exact prompt, and save the full answer to `answers/A1_P01.txt` … (local, not committed) | Loutchiana | 10 text files |
| 3. Assistant 2: the same, into `answers/A2_P01.txt` … | Charbel | 10 text files |
| 4. Hash each file: `python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" answers/A1_P01.txt` and paste the hash into `raw_answer_sha256` | each | 20 hashes |
| 5. Fill each row: `assistant_version`, `country_setting`, `timestamp_utc`, Y/N for `brand_mentioned` / `brand_recommended` / `brand_top_pick` (rules below), `competitors_named`, `competitors_recommended`, `cited_urls` exactly as shown, `collected_by` | each | — |
| 6. `python -m mi.seo.geo check` | either | `complete_rows: 20`, no `settings_drift`, `panel_frozen: true` |
| 7. `python -m mi.seo.geo analyze`, then together score impact and effort (1–3) for the 3 candidate actions and rank by impact ÷ effort | both | `reports/seo_geo_audit.json` |
| Bonus: rerun P01 in a new chat; note what changed in `refusal_or_variability` | either | — |

**Coding rules (decide before reading the answers; one appearance per brand per answer):**
- **Mention = Y:** the brand name appears anywhere in the answer.
- **Recommend = Y:** the answer suggests the shopper use or choose the brand ("try…", "a good option is…").
- **Top pick = Y:** the brand is the first or only recommended option, or explicitly called the best.
- A list item counts as a recommendation only if the list is presented as recommendations.

Never paste personal data into a chatbot. Missing rows stay empty; never fill them from memory or another run.

## What the result can and cannot say
- **It can say:** what two specific assistants said on a dated run (mention, recommendation, top-pick rates with denominators of 20, share of voice, share of recommendations), and which domains were cited when a competitor was recommended and the brand was not.
- **It cannot say:** search rankings, traffic, impressions or sales. AI-answer observations are kept separate from SEO traffic (needs site-owner analytics) and from sales (needs a randomized test).
- **Decision use:** if assistants omit the analogue on "how do I save on frozen pizza / coffee" questions while citing competitor deal pages, the discovery gap is a candidate **non-coupon** action (content, listings). If it is mentioned, discovery is not the barrier.
- **On "GEO tricks":** Google's guidance says there are no additional requirements or special optimizations for AI Overviews/AI Mode beyond normal SEO fundamentals, so treat any "GEO schema trick" with suspicion.
