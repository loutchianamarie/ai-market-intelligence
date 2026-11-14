# Catalog intake (read-only)

No authorized Odoo export exists in this project, so real Odoo integration is **PENDING**. `example_catalog_SYNTHETIC.csv` holds invented rows that exercise the validator; they are not products and must never be presented as data.

**To use a real export:**
1. Place an authorized CSV with the columns `sku, public_name, description, price, currency, valid_from, image_ref, availability` (optional: `category, margin_rate`) outside Git.
2. Run `python -m mi.content.catalog validate <file>`.

**Rules:**
- Personal columns (email, phone, customer, address, and so on) are dropped automatically.
- Never map catalog SKUs to anonymous Complete Journey product IDs.
