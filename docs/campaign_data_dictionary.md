# Campaign case data dictionary (HILLSTROM_EMAIL_2008)

One row is one existing customer who last purchased within twelve months. The file has no customer id; the row index is the customer key.
Definitions are quoted from the source page. Timing decides what the model may read.

| Column | Timing | Role | Source definition | Use in this project |
|---|---|---|---|---|
| `recency` | PRE-EMAIL | feature | Months since last purchase. | model feature (standardised); recency rule |
| `history_segment` | PRE-EMAIL | not used | Categorization of dollars spent in the past year. | excluded: a binned copy of history |
| `history` | PRE-EMAIL | feature | Actual dollar value spent in the past year. | model feature as log1p(history), standardised; history rule |
| `mens` | PRE-EMAIL | feature | 1/0 indicator, 1 = customer purchased Mens merchandise in the past year. | model feature. Product purchase history, NOT gender |
| `womens` | PRE-EMAIL | feature | 1/0 indicator, 1 = customer purchased Womens merchandise in the past year. | model feature. Product purchase history, NOT gender |
| `zip_code` | PRE-EMAIL | feature | Classifies zip code as Urban, Suburban, or Rural. | model feature (one-hot). The file spells one level 'Surburban'; kept as is |
| `newbie` | PRE-EMAIL | feature | 1/0 indicator, 1 = New customer in the past twelve months. | model feature |
| `channel` | PRE-EMAIL | feature | Describes the channels the customer purchased from in the past year. | model feature (one-hot): Phone, Web, Multichannel |
| `segment` | ASSIGNMENT | treatment | The e-mail campaign the customer received: Mens E-Mail, Womens E-Mail or No E-Mail (each 1/3, randomly chosen). | the randomized arm. Enters the model only as the treatment indicator; never a customer feature |
| `visit` | POST-EMAIL (2 weeks) | outcome, not used | 1/0 indicator, 1 = Customer visited website in the following two weeks. | FORBIDDEN as a predictor or ranking input; not a v2 outcome |
| `conversion` | POST-EMAIL (2 weeks) | primary outcome | 1/0 indicator, 1 = Customer purchased merchandise in the following two weeks. | the label. FORBIDDEN as a predictor or ranking input |
| `spend` | POST-EMAIL (2 weeks) | economics outcome | Actual dollars spent in the following two weeks. | incremental spend per contact only. FORBIDDEN as a predictor or ranking input |

## Timing rules

- **Pre-e-mail** columns describe the twelve months before the campaign. Only these can be model features or ranking inputs.
- **`segment`** is the randomized assignment. It selects one of three arms and is never a customer attribute.
- **Post-e-mail** columns (`visit`, `conversion`, `spend`) are outcomes. They are never predictors, never ranking inputs and never used in a preprocessing statistic.
- `mens` and `womens` are past-year product purchases. They do not state a customer's gender.
- The outcome window is two weeks after the e-mail for every arm, including the no-e-mail control.

## Audit summary (computed from the local file)

- File SHA-256 `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece`, 3,964,977 bytes, 64,000 rows.
- Arms: No E-Mail 21,306; Mens E-Mail 21,307; Womens E-Mail 21,387. Chi-square against equal thirds: p = 0.9037.
- Missing values: 0.
- Fully identical rows beyond the first: 6562. They are kept (no id to deduplicate on).
- Balance of pre-e-mail fields against the control (largest absolute standardised mean difference): Mens E-Mail 0.0164 at `history_segment_2) $100 - $200`; Womens E-Mail 0.0143 at `history_segment_2) $100 - $200`. Values below 0.1 count as balanced.
- Buyers: 578 of 64,000 customers (0.90%).
- Rights: no licence or redistribution permission stated; raw file kept local (data/raw/, gitignored); never committed, zipped or sent; only aggregates leave this repo.
