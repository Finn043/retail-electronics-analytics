from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "data" / "model"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Looker/Supabase-ready data model tables from Amazon Electronics JSONL reviews."
    )
    parser.add_argument(
        "--input",
        default=str(PROJECT_ROOT / "data" / "raw" / "Electronics_5.json"),
        help="Path to Electronics_5.json JSON Lines dataset.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=250_000,
        help="Maximum valid review rows to model.",
    )
    return parser.parse_args()


def iter_reviews(path: Path) -> Iterable[dict[str, Any] | None]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield None


def review_date(unix_time: int | float | None) -> tuple[str, str, int, int]:
    if not unix_time:
        return "", "unknown", 0, 0
    dt = datetime.fromtimestamp(int(unix_time), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m"), dt.year, dt.month


def helpful_fields(value: Any) -> tuple[int, int, float | None]:
    if not isinstance(value, list) or len(value) != 2:
        return 0, 0, None
    try:
        yes = int(value[0])
        total = int(value[1])
    except (TypeError, ValueError):
        return 0, 0, None
    if total <= 0:
        return yes, total, None
    return yes, total, yes / total


def safe_rating(value: Any) -> int | None:
    try:
        rating = int(float(value))
    except (TypeError, ValueError):
        return None
    if rating < 1 or rating > 5:
        return None
    return rating


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_model(input_path: Path, limit: int) -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    fact_rows: list[dict[str, Any]] = []
    products: dict[str, dict[str, Any]] = {}
    months: dict[str, dict[str, Any]] = {}
    rating_counts: defaultdict[int, int] = defaultdict(int)

    valid_count = 0
    for raw in iter_reviews(input_path):
        if raw is None:
            continue

        asin = str(raw.get("asin", "")).strip()
        reviewer_id = str(raw.get("reviewerID", "")).strip()
        rating = safe_rating(raw.get("overall"))
        if not asin or not reviewer_id or rating is None:
            continue

        if valid_count >= limit:
            break

        review_date_value, review_month, review_year, review_month_number = review_date(raw.get("unixReviewTime"))
        helpful_yes, helpful_total, helpful_rate = helpful_fields(raw.get("helpful"))
        review_text = str(raw.get("reviewText", "") or "")
        summary = str(raw.get("summary", "") or "")
        review_word_count = len(review_text.split())

        review_id = f"r_{valid_count + 1:09d}"
        fact_rows.append(
            {
                "review_id": review_id,
                "reviewer_id": reviewer_id,
                "asin": asin,
                "review_month": review_month,
                "rating_id": rating,
                "review_date": review_date_value,
                "helpful_yes": helpful_yes,
                "helpful_total": helpful_total,
                "helpful_rate": round(helpful_rate, 4) if helpful_rate is not None else "",
                "review_word_count": review_word_count,
                "has_review_text": bool(review_text.strip()),
                "summary": summary[:220],
            }
        )

        product = products.setdefault(
            asin,
            {
                "asin": asin,
                "first_review_month": review_month if review_month != "unknown" else "",
                "last_review_month": review_month if review_month != "unknown" else "",
                "modeled_product_name": f"Product {asin}",
                "metadata_status": "metadata_not_joined",
            },
        )
        if review_month != "unknown":
            product["first_review_month"] = min(product["first_review_month"] or review_month, review_month)
            product["last_review_month"] = max(product["last_review_month"] or review_month, review_month)

        if review_month != "unknown":
            months[review_month] = {
                "review_month": review_month,
                "review_year": review_year,
                "review_month_number": review_month_number,
                "month_start_date": f"{review_month}-01",
            }

        rating_counts[rating] += 1
        valid_count += 1

    rating_rows = [
        {
            "rating_id": rating,
            "rating_label": f"{rating} star",
            "rating_sentiment": rating_sentiment(rating),
            "rating_sort": rating,
        }
        for rating in range(1, 6)
    ]

    write_csv(
        MODEL_DIR / "fact_reviews.csv",
        [
            "review_id",
            "reviewer_id",
            "asin",
            "review_month",
            "rating_id",
            "review_date",
            "helpful_yes",
            "helpful_total",
            "helpful_rate",
            "review_word_count",
            "has_review_text",
            "summary",
        ],
        fact_rows,
    )
    write_csv(
        MODEL_DIR / "dim_products.csv",
        [
            "asin",
            "modeled_product_name",
            "metadata_status",
            "first_review_month",
            "last_review_month",
        ],
        sorted(products.values(), key=lambda row: row["asin"]),
    )
    write_csv(
        MODEL_DIR / "dim_review_months.csv",
        ["review_month", "review_year", "review_month_number", "month_start_date"],
        sorted(months.values(), key=lambda row: row["review_month"]),
    )
    write_csv(
        MODEL_DIR / "dim_ratings.csv",
        ["rating_id", "rating_label", "rating_sentiment", "rating_sort"],
        rating_rows,
    )

    return valid_count


def rating_sentiment(rating: int) -> str:
    if rating >= 4:
        return "positive"
    if rating == 3:
        return "neutral"
    return "negative"


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(
            f"Input dataset not found: {input_path}\n"
            "Place Electronics_5.json in data/raw/ or pass --input /path/to/Electronics_5.json."
        )
    count = export_model(input_path, args.limit)
    print(f"Exported {count:,} modeled reviews to {MODEL_DIR}")


if __name__ == "__main__":
    main()

