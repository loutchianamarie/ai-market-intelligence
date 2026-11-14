# One-page evidence collection checklist (Loutchiana & Charbel)

Open a terminal in the project folder: `C:\Users\admin\Desktop\USJ\s3\business and marketing\ai-market-intelligence`.

Run every command in this order. **Never invent a row, quote, answer or screenshot.** Missing evidence stays PENDING on the slides.

## Day 1: interviews (before any GEO answer)
| # | Who | Do | File / command |
|---|---|---|---|
| 1 | L | Interview I01 (lapsed frozen-pizza buyer). Read the consent script, then ask the five questions | `data\interviews\interview_template.md` (notes stay on your laptop; no names) |
| 2 | L | Interview I02 (lapsed buyer or nonbuyer) | same |
| 3 | C | Interview I03 (category nonbuyer if possible) | same |
| 4 | each | One row per interview. Barrier codes must be from: HABIT, PRICE, SWITCH, STOCK, CONVENIENCE, TASTE_HEALTH, HOUSEHOLD, NONE | `data\interviews\coding_sheet.csv` |
| 5 | either | Validate | `.venv\Scripts\python -m mi.evidence.interviews check` → `"status": "OK"` |
| 6 | either | Summarise ("n of N", counterexamples, pre-registered actions) | `.venv\Scripts\python -m mi.evidence.interviews summarize` → `reports\interview_summary.json` |

If an interviewee's own words should change a GEO prompt:
1. Edit the prompt text in `data\seo\prompt_panel.json`.
2. Add a `revision_log` entry: old text, new text, interview ID, reason.
3. Do this now, **before step 7**.

## Day 2: GEO answers (after the interviews)
| # | Who | Do | File / command |
|---|---|---|---|
| 7 | L | Freeze the panel. It refuses if any answer is already logged | `.venv\Scripts\python -m mi.seo.geo freeze --by "Loutchiana Marie"` |
| 8 | L | Assistant 1: for P01…P10, open a **new chat** and paste the exact prompt. Save the full answer as `answers\A1_P01.txt` … `A1_P10.txt` (local only) | settings: logged-out/fresh profile, region US, no custom instructions, same web setting as Assistant 2 |
| 9 | C | Assistant 2: the same, saving `answers\A2_P01.txt` … `A2_P10.txt` | same settings |
| 10 | each | Hash each answer file and paste the hash | `.venv\Scripts\python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" answers\A1_P01.txt` |
| 11 | each | Fill your 10 rows: `assistant_version`, `country_setting`, `timestamp_utc`, Y/N mention / recommend / top pick (coding rules below), competitors named and recommended, `cited_urls` exactly as shown, `collected_by` | `data\seo\answer_log.csv` |
| 12 | either | Check until complete | `.venv\Scripts\python -m mi.seo.geo check` → `complete_rows: 20`, `settings_drift: {}`, `panel_frozen: true` |
| 13 | both | Compute rates and rank the three actions by impact ÷ effort (score 1–3 together) | `.venv\Scripts\python -m mi.seo.geo analyze` → `reports\seo_geo_audit.json` |

**Coding rules:**
- **Mention:** the brand name appears anywhere.
- **Recommend:** the answer suggests using or choosing the brand.
- **Top pick:** the brand is the first or only recommendation, or is called the best.
- Count one appearance per brand per answer.

**If a prompt must change after step 7:** do not edit it. Create a new panel version, freeze it, and rerun **all 20** on that version. Never mix versions in one denominator.

## Any day: page checks and client inputs
| # | Who | Do | Where |
|---|---|---|---|
| 14 | C | Open the Kroger, Target, Walmart and both ALDI pages in a browser. Record URL, date, channel, eligibility and a one-line paraphrase; take a screenshot | `docs\decision_brief.md` §6 "Status" column (VERIFIED + date, or stays UNVERIFIED) |
| 15 | both | Ask the client: consented digital pool, margin, contact cost, setup cost, stock, offer mechanics (clip vs automatic) | app sidebar → re-run; brief §5 |
| 16 | both | Confirm the official brief: length, rubric, R$1M scenario, whether the literal Lebanon GEO worksheet is required | create `docs\scope_confirmed.md` |

## Rehearsal (the advisor demo)
| # | Who | Do |
|---|---|---|
| 17 | C | `.venv\Scripts\python -m mi.cli demo`, then tab 4 on the live dossier (sidebar shows the latest ID). Click "Try: record a coupon sandbox action now" → BLOCKED. Type your name, keep the advisor's reason, tick "Also approve the $0 research checklist", then click **Reject / defer funding**. Click "Agent: record approved research checklist" |
| 18 | either | **After rehearsing, run** `.venv\Scripts\python -m mi.agents.coordinator run` to create a fresh dossier in review for the real talk |
| 19 | both | Time the 5-minute cut twice: `docs\presentation\storyboard_talk_track_qa.md` |

## What changes on the slides when evidence arrives
| Evidence | Slide and doc that change |
|---|---|
| Interviews | slide 4 "which P is broken" (n of N); slide 12 pending list; brief §5 row 1 |
| GEO answers | slide 9 replaces "0 / 20" with the five rates and denominators; brief §5 GEO row |
| Page checks | slide 3 footnote; brief §6 |
| Client inputs | re-run `python -m mi.claim_audit`; the brief §4 table and slide 11 update from `reports\claim_audit.json` |
