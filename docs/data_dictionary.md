# Data dictionary and business-meaning audit (Complete Journey, 2017)

Source: maintainer guide https://bradleyboehmke.github.io/completejourney/articles/completejourney.html and reference https://bradleyboehmke.github.io/completejourney/reference/promotions.html; data CC0 at commit 5b5d0619 (hashes in `data/manifest.lock.json`). Counts from `reports/accounting_audit.json` and `reports/promotions_audit.json`.

| field / table | unit | definition | basis |
|---|---|---|---|
| transactions.sales_value | USD per line | amount the RETAILER receives for the line (not the shopper's outlay); includes manufacturer coupon reimbursement | guide |
| transactions.retail_disc | USD per line, positive magnitude | loyalty-card discount (retailer programme) | guide |
| transactions.coupon_disc | USD per line, positive magnitude | manufacturer coupon discount (reimbursed to the retailer) | guide |
| transactions.coupon_match_disc | USD per line, positive magnitude | retailer's match of a manufacturer coupon (retailer-funded) | guide |
| transactions.quantity | units (fuel in gallons) | quantity; zero on some lines; FUEL/MISC carry very large values | audit |
| transactions.week | 1-53 | week of the transaction; week 1 is a single day | audit |
| products.* | - | product_id, manufacturer_id, department, brand (National/Private), product_category, product_type, package_size; NO descriptions, images, prices, cost or stock | guide + audit |
| coupons | coupon_upc x product_id x campaign_id | products ELIGIBLE for a campaign coupon; not what a household received | guide |
| campaigns | household x campaign | households that received a campaign; Type A recipients got 16 of the pool (which 16 unknown); assignment undocumented | guide |
| coupon_redemptions | household x coupon x campaign x date | campaign coupons actually redeemed | guide |
| promotions | product x store x week | display_location / mailer_location codes; ONLY promoted rows; 112 stores (98.7% of transaction lines) | reference + audit |
| label y (model) | 0/1 per household x category x cutoff | any purchase of the category in weeks cutoff+1..cutoff+4 | repo |
| q0 (model) | probability | calibrated probability of buying under historical conditions; NOT a no-coupon counterfactual | repo |

## Quality counts

- 1,469,307 lines; 8,869 zero-quantity; 11,226 zero-value; 0 lines with any negative value → **returns are not represented**.
- Loyalty discount exceeds the line's sales_value on 37,634 lines; manufacturer coupon exceeds it on 3,507.
- Retailer match = 17.2% of manufacturer coupon value; match only occurs with a manufacturer coupon: True.
- 2,102 campaign redemptions vs 21,889 manufacturer-coupon lines (9.6%).
- Coupon pool by campaign type: {'Type A': 717, 'Type B': 240, 'Type C': 74}. each Type A recipient got 16 coupons from the pool; WHICH 16 is not recorded -> exact exposure cannot be reconstructed.
- Products: 92,331; package_size missing 33.1%; category missing 0.58%; 4,836 transaction lines lack product metadata.

## What changes in the economics

- Category 'spend' in the economics is retailer receipts (sales_value), not shopper outlay; margin is applied to receipts.
- The coupon face value used (mean coupon_disc per couponed line) averages ALL manufacturer coupons; only 2102 of 21889 couponed lines are campaign redemptions, so it is not a measured campaign-coupon value.
- Manufacturer coupons are reimbursed to the retailer. Separately, the retailer recorded a match on 47% of couponed lines (usually equal to the coupon), which sums to 17% of manufacturer coupon VALUE (value-weighted; reports/funding_audit.json). That describes past coupon accounting, not who would fund a NEW offer: the offer contract is an ASSUMPTION (coupon_funding.retailer_share; base 1.0 = retailer-funded) until the client confirms it.
- Unit prices: sales_value / quantity is undefined on zero-quantity lines; no price list exists.
