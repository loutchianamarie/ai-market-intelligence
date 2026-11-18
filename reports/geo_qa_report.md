# GEO / SEO QA report

Generated 2026-11-18T18:51:16Z. Verdict: **PASS** (20 PASS of 20 checks).

| id | check | status | detail |
|---|---|---|---|
| Q01 | Prompt panel follows the protocol (10 prompts, 4 Learn / 3 Browse / 3 Buy, brand named once, a second language) | **PASS** | 10 prompts, brand Kroger |
| Q02 | Panel is frozen at the version the answers were collected with | **PASS** | panel sha16 1b0f0cf38c72a773 |
| Q03 | Every prompt answered once by each assistant (no gaps, no duplicates) | **PASS** | 20 rows, expected 20 |
| Q04 | Every row has the required fields (version, setting, time, hash, three Y/N codes, collector) | **PASS** | all present |
| Q05 | The three brand codes are Y or N only | **PASS** | all valid |
| Q06 | Codes are consistent: a top pick is recommended, a recommendation is a mention | **PASS** | no contradictions |
| Q07 | Every competitor recommended was also named in the answer | **PASS** | consistent |
| Q08 | Each raw answer has its own SHA-256 (64 hex characters, none repeated) | **PASS** | 20 hashes |
| Q09 | Timestamps are valid UTC and not in the future | **PASS** | 2026-11-17 19:16 to 19:19 UTC |
| Q10 | Same assistant version and region setting for every answer of one assistant | **PASS** | no drift |
| Q11 | Intent and language in the log match the frozen panel | **PASS** | match |
| Q12 | Cited URLs are well formed and match the URL count written in the notes | **PASS** | 14 answers cite URLs, 6 cite none |
| Q13 | Mention, recommendation, primary-pick, share-of-voice and share-of-recommendation counts re-derived independently | **PASS** | mention 17/20, recommended 12/20, top pick 8/20 |
| Q14 | Learn + Browse + Buy add up to the overall counts | **PASS** | Learn 5/8 mentioned, 0/8 recommended, Browse 6/6 mentioned, 6/6 recommended, Buy 6/6 mentioned, 6/6 recommended |
| Q15 | 20 of 20 answers complete (state used by the page, briefs and work items) | **PASS** | 20/20 logged, 20 complete, frozen=True |
| Q16 | Limits are recorded: one run per question, region not set, web search use, two assistants of one vendor | **PASS** | 2 assistant(s) ['Claude Opus 5.5', 'Claude Sonnet 5.5']; web search noted in 14 answers; region: ['none set (no geolocation; shopper question implies US)'] |
| Q17 | At least two answers per assistant are in a second language | **PASS** | en: 16, es: 4 answers (the worksheet requires a second language; fit with the official brief is pending) |
| Q18 | The page computes its GEO counts from the log instead of typing them | **PASS** | no typed counts |
| Q19 | Content actions are hypotheses: impact and effort are left for the team to score | **PASS** | 2 proposed actions, 0 scored |
| Q20 | The result says it is an observation of answers, not search ranking, traffic or sales | **PASS** | Assistant answers vary by run, version and settings; these are observations of specific answers, not search ranking, traffic or sales. |

What this does not test: whether the assistants' answers are *right* (we log what they said), other assistants, other regions,
repeat runs (variability), or any effect on traffic or sales.
