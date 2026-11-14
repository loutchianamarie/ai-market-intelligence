# SEO / AEO / GEO audit protocol (team task, about 90 minutes)

Status: **0 of 20 answers collected.** The panel is frozen in `data/seo/prompt_panel.json`; the log template is `data/seo/answer_log.csv` (20 rows: 10 prompts × 2 assistants).

**Audited brand:** Kroger, as a *public US grocery analogue* with a digital-coupon program. The dataset retailer is anonymous, and we never claim the panel households are Kroger customers. **Competitors:** Walmart, Target, Aldi. You may swap the analogue before the first run, then never again.

## Steps
1. Choose two assistants (e.g., two different chatbot products). Record name, model/version and region settings in the log.
2. For each prompt, open a **new chat**. Paste the exact prompt text. Do not add personal data.
3. Save the raw answer to a local text file (not committed). Put its SHA-256 in `raw_answer_sha256` (`python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" answer.txt`).
4. Fill `brand_mentioned / brand_recommended / brand_top_pick` with Y/N. Fill `competitors_named` and `competitors_recommended` (comma-separated), and `cited_urls` (space-separated, exactly as shown).
5. Optional bonus: rerun prompt 1 in a new chat and note what changed in `refusal_or_variability`.
6. Run `python -m mi.seo.geo analyze`. It computes the worksheet's five rates with explicit denominators, the funnel leak, the top-3 source-gap domains and three candidate actions. **The team scores impact and effort (1–3)** and ranks by impact ÷ effort.

Count rule (worksheet Step 4): one appearance per brand per answer. Assistant answers are observations of specific runs. They are not search rankings, traffic or sales. Google's own guidance says there are no special requirements or optimizations for AI Overviews/AI Mode beyond normal SEO fundamentals, so treat any "GEO schema trick" with suspicion.
