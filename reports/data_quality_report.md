# Data Quality Report

- Rows scanned: 250,001
- Valid review rows processed: 250,000
- Invalid JSON rows: 0
- Rows missing required fields: 0
- Rows with review text: 99.96%
- Rows with helpful votes: 50.85%
- Review window: 1999-06 to 2014-07

## Notes

- The pipeline processes a configurable sample from the 1.4GB raw JSONL file to keep GitHub outputs lightweight.
- Raw data is intentionally excluded from Git. Place `Electronics_5.json` in `data/raw/` before running locally.
- Product metadata is not included in this review dataset, so product-level marts use `asin` as the product key.
