from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MARTS_DIR = PROJECT_ROOT / "data" / "marts"
REPORTS_DIR = PROJECT_ROOT / "reports"


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "you",
    "are",
    "was",
    "but",
    "have",
    "not",
    "very",
    "from",
    "they",
    "will",
    "all",
    "one",
    "had",
    "has",
    "use",
    "out",
    "can",
    "get",
    "its",
    "it's",
    "just",
    "like",
    "would",
    "when",
    "what",
    "your",
    "about",
    "there",
    "their",
    "been",
    "more",
    "than",
    "good",
    "great",
    "product",
    "works",
    "work",
    "well",
}


@dataclass
class PipelineStats:
    rows_seen: int = 0
    rows_valid: int = 0
    rows_invalid_json: int = 0
    rows_missing_required: int = 0
    rows_with_review_text: int = 0
    rows_with_helpful_votes: int = 0
    earliest_review: str | None = None
    latest_review: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build dashboard-ready marts from Amazon Electronics review JSONL data."
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
        help="Maximum valid review rows to process for the portfolio dataset.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10_000,
        help="Maximum cleaned review rows to write to data/processed for GitHub review.",
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


def review_month(unix_time: int | float | None) -> str:
    if not unix_time:
        return "unknown"
    return datetime.fromtimestamp(int(unix_time), tz=timezone.utc).strftime("%Y-%m")


def helpful_ratio(helpful: Any) -> tuple[int, int, float | None]:
    if not isinstance(helpful, list) or len(helpful) != 2:
        return 0, 0, None
    yes, total = helpful
    try:
        yes_i = int(yes)
        total_i = int(total)
    except (TypeError, ValueError):
        return 0, 0, None
    if total_i <= 0:
        return yes_i, total_i, None
    return yes_i, total_i, yes_i / total_i


def word_counter(text: str) -> Counter[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z']{2,}", text.lower())
    return Counter(word for word in words if word not in STOPWORDS)


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def ensure_dirs() -> None:
    for directory in (PROCESSED_DIR, MARTS_DIR, REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def avg(values: list[float]) -> float:
    return round(mean(values), 3) if values else 0.0


def pct(part: int | float, whole: int | float) -> float:
    return round((part / whole) * 100, 2) if whole else 0.0


def build_pipeline(input_path: Path, limit: int, sample_size: int) -> PipelineStats:
    ensure_dirs()

    stats = PipelineStats()
    cleaned_sample: list[dict[str, Any]] = []
    product_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "review_count": 0,
            "ratings": [],
            "helpful_yes": 0,
            "helpful_total": 0,
            "review_lengths": [],
            "first_month": None,
            "last_month": None,
        }
    )
    monthly_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"review_count": 0, "ratings": [], "helpful_total": 0}
    )
    rating_distribution: Counter[str] = Counter()
    text_terms: Counter[str] = Counter()

    for raw in iter_reviews(input_path):
        stats.rows_seen += 1
        if raw is None:
            stats.rows_invalid_json += 1
            continue

        asin = str(raw.get("asin", "")).strip()
        reviewer_id = str(raw.get("reviewerID", "")).strip()
        rating = safe_float(raw.get("overall"))
        review_text = str(raw.get("reviewText", "") or "").strip()
        summary = str(raw.get("summary", "") or "").strip()
        month = review_month(raw.get("unixReviewTime"))

        if not asin or not reviewer_id or rating is None:
            stats.rows_missing_required += 1
            continue

        if stats.rows_valid >= limit:
            break

        stats.rows_valid += 1
        if review_text:
            stats.rows_with_review_text += 1

        helpful_yes, helpful_total, helpful_rate = helpful_ratio(raw.get("helpful"))
        if helpful_total:
            stats.rows_with_helpful_votes += 1

        if month != "unknown":
            if stats.earliest_review is None or month < stats.earliest_review:
                stats.earliest_review = month
            if stats.latest_review is None or month > stats.latest_review:
                stats.latest_review = month

        review_length = len(review_text.split())
        rating_key = str(int(rating)) if rating.is_integer() else str(rating)
        rating_distribution[rating_key] += 1
        text_terms.update(word_counter(f"{summary} {review_text}"))

        product = product_stats[asin]
        product["review_count"] += 1
        product["ratings"].append(rating)
        product["helpful_yes"] += helpful_yes
        product["helpful_total"] += helpful_total
        product["review_lengths"].append(review_length)
        if month != "unknown":
            product["first_month"] = month if product["first_month"] is None else min(product["first_month"], month)
            product["last_month"] = month if product["last_month"] is None else max(product["last_month"], month)

        monthly = monthly_stats[month]
        monthly["review_count"] += 1
        monthly["ratings"].append(rating)
        monthly["helpful_total"] += helpful_total

        if len(cleaned_sample) < sample_size:
            cleaned_sample.append(
                {
                    "reviewer_id": reviewer_id,
                    "asin": asin,
                    "rating": rating,
                    "review_month": month,
                    "helpful_yes": helpful_yes,
                    "helpful_total": helpful_total,
                    "helpful_rate": round(helpful_rate, 4) if helpful_rate is not None else "",
                    "review_word_count": review_length,
                    "summary": summary[:180],
                }
            )

    write_csv(
        PROCESSED_DIR / "cleaned_reviews_sample.csv",
        [
            "reviewer_id",
            "asin",
            "rating",
            "review_month",
            "helpful_yes",
            "helpful_total",
            "helpful_rate",
            "review_word_count",
            "summary",
        ],
        cleaned_sample,
    )

    product_rows = []
    for asin, values in product_stats.items():
        review_count = int(values["review_count"])
        avg_rating = avg(values["ratings"])
        helpful_total = int(values["helpful_total"])
        helpful_yes = int(values["helpful_yes"])
        product_rows.append(
            {
                "asin": asin,
                "review_count": review_count,
                "avg_rating": avg_rating,
                "helpful_votes": helpful_total,
                "helpful_rate": round(helpful_yes / helpful_total, 4) if helpful_total else "",
                "avg_review_word_count": avg(values["review_lengths"]),
                "first_review_month": values["first_month"] or "",
                "last_review_month": values["last_month"] or "",
                "quality_flag": quality_flag(review_count, avg_rating),
            }
        )
    product_rows.sort(key=lambda row: (int(row["review_count"]), float(row["avg_rating"])), reverse=True)

    write_csv(
        MARTS_DIR / "mart_product_performance.csv",
        [
            "asin",
            "review_count",
            "avg_rating",
            "helpful_votes",
            "helpful_rate",
            "avg_review_word_count",
            "first_review_month",
            "last_review_month",
            "quality_flag",
        ],
        product_rows,
    )

    monthly_rows = []
    for month, values in monthly_stats.items():
        monthly_rows.append(
            {
                "review_month": month,
                "review_count": values["review_count"],
                "avg_rating": avg(values["ratings"]),
                "helpful_votes": values["helpful_total"],
            }
        )
    monthly_rows.sort(key=lambda row: row["review_month"])
    write_csv(
        MARTS_DIR / "mart_monthly_review_trends.csv",
        ["review_month", "review_count", "avg_rating", "helpful_votes"],
        monthly_rows,
    )

    rating_rows = [
        {
            "rating": rating,
            "review_count": count,
            "review_share_pct": pct(count, stats.rows_valid),
        }
        for rating, count in sorted(rating_distribution.items(), key=lambda item: float(item[0]))
    ]
    write_csv(
        MARTS_DIR / "mart_rating_distribution.csv",
        ["rating", "review_count", "review_share_pct"],
        rating_rows,
    )

    quality_rows = [
        {"metric": "rows_seen", "value": stats.rows_seen},
        {"metric": "rows_valid", "value": stats.rows_valid},
        {"metric": "rows_invalid_json", "value": stats.rows_invalid_json},
        {"metric": "rows_missing_required", "value": stats.rows_missing_required},
        {"metric": "pct_rows_with_review_text", "value": pct(stats.rows_with_review_text, stats.rows_valid)},
        {"metric": "pct_rows_with_helpful_votes", "value": pct(stats.rows_with_helpful_votes, stats.rows_valid)},
        {"metric": "unique_products", "value": len(product_stats)},
        {"metric": "earliest_review_month", "value": stats.earliest_review or ""},
        {"metric": "latest_review_month", "value": stats.latest_review or ""},
    ]
    write_csv(MARTS_DIR / "mart_data_quality_summary.csv", ["metric", "value"], quality_rows)

    keyword_rows = [
        {"term": term, "count": count}
        for term, count in text_terms.most_common(50)
    ]
    write_csv(MARTS_DIR / "mart_top_review_terms.csv", ["term", "count"], keyword_rows)

    write_reports(stats, product_rows, monthly_rows, rating_rows, keyword_rows)
    return stats


def quality_flag(review_count: int, avg_rating: float) -> str:
    if review_count >= 100 and avg_rating < 3.5:
        return "high_volume_low_rating"
    if review_count >= 100 and avg_rating >= 4.5:
        return "high_volume_high_rating"
    if review_count < 5:
        return "low_sample_size"
    return "monitor"


def write_reports(
    stats: PipelineStats,
    product_rows: list[dict[str, Any]],
    monthly_rows: list[dict[str, Any]],
    rating_rows: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
) -> None:
    top_products = product_rows[:10]
    flagged = [row for row in product_rows if row["quality_flag"] == "high_volume_low_rating"][:10]
    top_months = sorted(monthly_rows, key=lambda row: int(row["review_count"]), reverse=True)[:5]

    REPORTS_DIR.joinpath("data_quality_report.md").write_text(
        "\n".join(
            [
                "# Data Quality Report",
                "",
                f"- Rows scanned: {stats.rows_seen:,}",
                f"- Valid review rows processed: {stats.rows_valid:,}",
                f"- Invalid JSON rows: {stats.rows_invalid_json:,}",
                f"- Rows missing required fields: {stats.rows_missing_required:,}",
                f"- Rows with review text: {pct(stats.rows_with_review_text, stats.rows_valid)}%",
                f"- Rows with helpful votes: {pct(stats.rows_with_helpful_votes, stats.rows_valid)}%",
                f"- Review window: {stats.earliest_review or 'unknown'} to {stats.latest_review or 'unknown'}",
                "",
                "## Notes",
                "",
                "- The pipeline processes a configurable sample from the 1.4GB raw JSONL file to keep GitHub outputs lightweight.",
                "- Raw data is intentionally excluded from Git. Place `Electronics_5.json` in `data/raw/` before running locally.",
                "- Product metadata is not included in this review dataset, so product-level marts use `asin` as the product key.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    executive_lines = [
        "# Executive Summary",
        "",
        "## Business Question",
        "",
        "How can an electronics marketplace monitor product review quality, rating distribution, and customer engagement signals from raw review data?",
        "",
        "## Pipeline Output",
        "",
        f"The pipeline processed {stats.rows_valid:,} valid electronics reviews and produced dashboard-ready marts for product performance, monthly review trends, rating distribution, data quality, and common review terms.",
        "",
        "## Top Products By Review Volume",
        "",
        "| ASIN | Reviews | Avg Rating | Quality Flag |",
        "|---|---:|---:|---|",
    ]
    for row in top_products:
        executive_lines.append(
            f"| {row['asin']} | {int(row['review_count']):,} | {float(row['avg_rating']):.2f} | {row['quality_flag']} |"
        )
    executive_lines.extend(["", "## Highest Review-Volume Months", "", "| Month | Reviews | Avg Rating |", "|---|---:|---:|"])
    for row in top_months:
        executive_lines.append(
            f"| {row['review_month']} | {int(row['review_count']):,} | {float(row['avg_rating']):.2f} |"
        )
    executive_lines.extend(["", "## Rating Mix", "", "| Rating | Reviews | Share |", "|---|---:|---:|"])
    for row in rating_rows:
        executive_lines.append(
            f"| {row['rating']} | {int(row['review_count']):,} | {float(row['review_share_pct']):.2f}% |"
        )
    executive_lines.extend(["", "## Quality Watchlist", ""])
    if flagged:
        executive_lines.extend(["| ASIN | Reviews | Avg Rating |", "|---|---:|---:|"])
        for row in flagged:
            executive_lines.append(
                f"| {row['asin']} | {int(row['review_count']):,} | {float(row['avg_rating']):.2f} |"
            )
    else:
        executive_lines.append("No high-volume low-rating products were found in the processed sample.")
    executive_lines.extend(
        [
            "",
            "## Common Review Terms",
            "",
            ", ".join(row["term"] for row in keyword_rows[:20]),
            "",
            "## Recommended Next Steps",
            "",
            "- Add product metadata to group performance by category, brand, and price band.",
            "- Connect marts to Power BI or Tableau for executive monitoring.",
            "- Add anomaly flags for sudden rating drops or review-volume spikes.",
            "- Add a lightweight sentiment model to separate product-quality issues from shipping/support issues.",
        ]
    )
    REPORTS_DIR.joinpath("executive_summary.md").write_text("\n".join(executive_lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(
            f"Input dataset not found: {input_path}\n"
            "Place Electronics_5.json in data/raw/ or pass --input /path/to/Electronics_5.json."
        )
    stats = build_pipeline(input_path, limit=args.limit, sample_size=args.sample_size)
    print(f"Processed {stats.rows_valid:,} valid reviews from {input_path}")
    print(f"Wrote outputs to {PROCESSED_DIR}, {MARTS_DIR}, and {REPORTS_DIR}")


if __name__ == "__main__":
    main()

