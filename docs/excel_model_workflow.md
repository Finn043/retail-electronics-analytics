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
- Excel acts as a portable data model artifact for review, upload, or BI-tool connection.

This mirrors the same pattern used in warehouse analytics, but stays local and free.

## 5. Looker Studio Dashboard Layout

Use the marts first. They are easier to drag into charts than the raw fact table.

### Page 1: Executive Overview

Recommended data sources:

- `mart_data_quality`
- `mart_monthly_trends`
- `mart_rating_distribution`
- `mart_product_performance`

Suggested layout:

```text
Title row
  Retail Electronics Review Performance

KPI row
  Total Reviews | Unique Products | Avg Rating | Helpful Vote Coverage

Middle row
  Monthly Review Trend line chart | Rating Distribution bar chart

Bottom row
  Top Products table | Quality Watchlist table
```

Charts:

| Section | Data source | Chart type | Dimension | Metric |
|---|---|---|---|---|
| Total Reviews | `mart_data_quality` | Scorecard | Filter metric = `rows_valid` | `value` |
| Unique Products | `mart_data_quality` | Scorecard | Filter metric = `unique_products` | `value` |
| Monthly Trend | `mart_monthly_trends` | Time series / line chart | `review_month` | `review_count` |
| Rating Mix | `mart_rating_distribution` | Bar chart | `rating` | `review_count` |
| Top Products | `mart_product_performance` | Table | `asin`, `quality_flag` | `review_count`, `avg_rating`, `helpful_rate` |
| Watchlist | `mart_product_performance` | Table with filter | `asin` | filter `quality_flag = high_volume_low_rating` |

### Page 2: Product Performance

Purpose: inspect product-level review engagement and satisfaction.

Suggested charts:

- Table: `asin`, `review_count`, `avg_rating`, `helpful_rate`, `avg_review_word_count`, `quality_flag`
- Scatter plot:
  - Dimension: `asin`
  - X-axis: `review_count`
  - Y-axis: `avg_rating`
  - Color: `quality_flag`
- Bar chart:
  - Dimension: `quality_flag`
  - Metric: count of products or sum of `review_count`

Recommended filters:

- `quality_flag`
- `avg_rating`
- `review_count`

### Page 3: Review Quality And Ratings

Purpose: understand satisfaction distribution and review signal quality.

Suggested charts:

- Bar chart: rating distribution
  - Source: `mart_rating_distribution`
  - Dimension: `rating`
  - Metric: `review_count`
- Scorecards:
  - `pct_rows_with_review_text`
  - `pct_rows_with_helpful_votes`
- Table:
  - Source: `mart_product_performance`
  - Fields: `asin`, `avg_rating`, `helpful_votes`, `helpful_rate`

### Design Notes

- Keep the first page simple: 4 scorecards, 2 charts, 2 tables.
- Use one accent color for important values, such as teal or dark green.
- Use conditional formatting in tables:
  - `high_volume_low_rating`: red/orange
  - `high_volume_high_rating`: green
  - `monitor`: gray
- Avoid too many pie charts. Use bar charts for rating mix and quality flags.
- Use tables for product-level details because ASINs are high-cardinality identifiers.
