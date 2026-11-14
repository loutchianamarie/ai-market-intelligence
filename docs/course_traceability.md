# Course traceability: source → concept → implementation → slide → likely question

Sources were read from the course folder on 2026-11-14. We attribute nothing to the professor beyond what the files say. The marketing primer contains inserted editorial prose ("Here are two sections in the same fill-in style… Your document skips from 10 to 12…"); we use its content but do not attribute that wording or the MERIDIAN figures to any author.

| Course source (section) | Concept | Implementation | Slide | Likely question / limitation |
|---|---|---|---|---|
| Marketing primer §1 | Find, win, keep *profitable* customers | Objective is net contribution after coupon subsidy, not reach | 1, 10 | "Isn't more reach better?" Reach without contribution loses (heuristic −$62k) |
| Marketing primer §3 | Segment tests: measurable, reachable, substantial; behavioural basis | `configs/policy.json` segments; `segment_profile`; reachability flagged UNKNOWN | 3 | "Is LAPSING actionable?" Measurable yes; reachable only with consent |
| Marketing primer §4 | Target by value net of cost to serve, not size | Optimizer filters by expected value; REGULAR buyers carry the most subsidy | 3, 7 | "Why not the biggest segment?" |
| Marketing primer §5–7 | Positioning sentence; 4 Ps; "which P is broken" | `decision_brief.md` | 3 | Positioning is a hypothesis, not tested |
| Marketing primer §8 | Lifecycle; models trained on one phase mislead in another | Test window is the holiday period; limit stated in model card | 6 | Seasonality risk |
| Marketing primer §11–12 | Funnel KPIs; ROAS vs ROI | Metric engine; no ROAS for grocery case (no spend data) | 10 | "What's your ROAS?" Undefined without spend |
| Market research primer Part 1 | Research must change a decision; dashboards miss nonbuyers | Decision-changing question = uplift ≥ break-even; nonbuyer interview group | 2 | "Who is missing from your data?" |
| Part 3–5 | Qual before quant; past behaviour, not future intention | Interview guide asks what people did | 2 | No interviews conducted yet |
| Part 4 | Sampling frame bias | Panel = frequent shoppers of one retailer; not a market sample | 5 | External validity |
| Part 6 | "Which method? which data? what can go wrong?"; synthetic respondents never results | Claim/evidence tables; no synthetic respondents | 11 | — |
| Part 7 | Ad library shows messages, not profit | Competitor protocol: observations only | 2 | Not yet collected |
| Metrics slides (34 pp.; p. 5 "metric chain" verified; other page refs from the blueprint, not re-verified) | Ratio contracts; platform ROAS overstates; break-even; A/B; model threshold | `src/mi/decision/metrics.py`; FashionForward fixture (TikTok platform ROAS 4.44 vs shop 1.47) | 10, backup | "Does prediction prove profit?" No |
| Module 04 workbook R1–R4 | Clean before counting; sum then divide | FashionForward fixture: rule-less revenue overstated 19.6% | backup | Fixture is synthetic |
| Module 04 Part 9 | Audit an AI model's precision/recall | Locked test, calibration, segment errors, failure case | 6 | — |
| Agentic AI worksheet | Numeric goal + deadline, named tools, steps, human checkpoint, one metric, risk + guardrail, agent type | `docs/agents.md` canvas for each role | 5, 9 | "What can the agent do without approval?" Read only |
| SEO/AEO/GEO worksheet Steps 1–5 | 10 prompts 4/3/3, two assistants, 20 answers, ≤1 brand prompt, metrics with denominators, source gap, 3 ranked actions | `data/seo/prompt_panel.json`; `src/mi/seo/geo.py` validates and computes | 8 | 0/20 answers collected so far |

## Supplied videos (metadata verified via YouTube oEmbed, 2026-11-14)
Transcripts and audio were **not accessible** in this environment, so the videos were **not reviewed** by this build. The research blueprint (prior session) states it reviewed "available captions/transcripts", with audiovisual details, dates and figures *not independently verified*. Its teaching angles may be used only with that provenance stated, and no numeric claim from a video appears in the deck. Titles and channels are verified; upload dates are not. No figure from any video is used. They can serve as background only after a team member watches them.

| Video (channel) | Possible teaching angle (to confirm by watching) | Do not infer |
|---|---|---|
| How AI is changing the job market (BBC World Service) | Why applied AI judgement matters | Demand for this system |
| How did Zillow get AI so wrong (Hiten Shah) | Acting on model scores without controls | Any loss figure without primary filings |
| The AI rollout is here – and it's messy (Financial Times) | Adoption, data readiness | Universal statistics |
| Customer Journey Mapping Explained (CodeLucky) | Find → compare → buy → keep | That a drawn journey is research |
| The Ultimate Guide to Understanding Marketing KPIs (Social Geeks Digital) | KPI per funnel stage | Generic benchmarks |
| Market Research: The Secret Ingredient… (Leaders Talk – ThinkEduca) | Interviews and surveys | Intent = purchase |
| 7 AI Agents That Replace Entire Marketing Teams (Adam Erhart) | Agent roles | Savings or replacement claims |
| The RISE of AI Agents (AI Uncovered) | Agent types | Need for autonomy |
| The 5%: High Impact SEO Strategies for 2024 (Reforge, Ethan Smith) | Prioritise intent | Current search rules |
