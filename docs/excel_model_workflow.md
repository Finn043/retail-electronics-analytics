# Excel Data Model Workflow

This workflow keeps the project local and free: raw JSONL data is transformed into fact/dimension CSV tables and an Excel workbook.

## Target Flow

```text
Electronics_5.json
  -> local model export
  -> fact/dimension tables
  -> Excel workbook
  -> optional Looker Studio / Power BI / portfolio screenshots
```

## 1. Export Model Tables

```bash
make model RAW=/path/to/Electronics_5.json LIMIT=250000
```

This creates:

```text
data/model/fact_reviews.csv
data/model/dim_products.csv
data/model/dim_review_months.csv
data/model/dim_ratings.csv
```

## 2. Build The Excel Workbook

```bash
make excel
```

This creates:

```text
reports/retail_electronics_model.xlsx
```

By default, the workbook includes the first 100,000 fact rows to keep the `.xlsx` practical to open. The full modeled fact export remains available in `data/model/fact_reviews.csv`.

## 3. Workbook Structure

| Sheet | Purpose |
|---|---|
| README | Explains the model purpose and grain |
| Dashboard | Executive summary with KPI cards and charts |
| Model Relationships | Explains fact/dimension joins |
| fact_reviews | Review-level fact table |
| dim_products | Product dimension keyed by ASIN |
| dim_review_months | Month dimension |
| dim_ratings | Rating dimension |
| mart_product_performance | Product-level dashboard mart |
| mart_monthly_trends | Monthly trend mart |
| mart_rating_distribution | Rating mix mart |
| mart_data_quality | Dataset health summary |

## 4. Why This Is Better Than Just Cleaning Data

The model separates analytical responsibilities:

- `fact_reviews` keeps the event/review grain.
- Dimensions hold reusable descriptive attributes.
- Marts answer dashboard questions directly.
- Excel acts as a portable BI artifact for review and screenshots.

This mirrors the same pattern used in warehouse analytics, but stays local and free.
