from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARTS_DIR = PROJECT_ROOT / "data" / "marts"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
OUTPUT_PATH = DASHBOARD_DIR / "index.html"
FACT_PATH = PROJECT_ROOT / "data" / "model" / "fact_reviews.csv"

FILTER_SCRIPT = """(() => {
  const data = JSON.parse(document.querySelector('#dashboard-data').textContent);
  const products = data.products;
  const months = data.months;
  const controls = {
    search: document.querySelector('#product-search'),
    minimum: document.querySelector('#minimum-reviews'),
    rating: document.querySelector('#rating-filter'),
    quality: document.querySelector('#quality-flag'),
    start: document.querySelector('#start-month'),
    end: document.querySelector('#end-month')
  };
  const body = document.querySelector('#product-results');
  const watchBody = document.querySelector('#watch-results');
  const count = document.querySelector('#product-count');
  const active = document.querySelector('#active-filter-summary');
  const more = document.querySelector('#load-more');
  const labels = {
    high_volume_high_rating: 'High volume / high rating',
    high_volume_low_rating: 'Watchlist',
    monitor: 'Monitor'
  };
  let visible = 20;

  const integer = new Intl.NumberFormat('en-US');
  const pct = (value) => `${value.toFixed(2)}%`;

  function productRows(items, limit = items.length) {
    const fragment = document.createDocumentFragment();
    for (const product of items.slice(0, limit)) {
      const row = document.createElement('tr');
      const values = [product.asin, product.review_count.toLocaleString('en-US'),
        product.avg_rating.toFixed(2), product.avg_review_word_count.toFixed(1),
        labels[product.quality_flag] || product.quality_flag];
      values.forEach((value, index) => {
        const cell = document.createElement('td');
        const text = index === 0 || index === 4 ? document.createElement('span') : cell;
        text.textContent = value;
        if (index === 0) text.className = 'asin';
        if (index === 4) text.className = product.quality_flag === 'high_volume_high_rating'
          ? 'status strong' : product.quality_flag === 'high_volume_low_rating' ? 'status risk' : 'status';
        if (text !== cell) cell.append(text);
        row.append(cell);
      });
      fragment.append(row);
    }
    if (!items.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 5;
      cell.textContent = 'No data matches this selection. Reset or widen the filters.';
      row.append(cell);
      fragment.append(row);
    }
    return fragment;
  }

  function lineChart(monthly) {
    const width = 760, height = 240, left = 46, right = 20, top = 20, bottom = 42;
    const shown = monthly.slice(-30);
    const counts = shown.map((row) => row[1]);
    const max = Math.max(...counts, 1), min = Math.min(...counts, 0), span = Math.max(max - min, 1);
    const points = shown.map((row, index) => [
      left + index / Math.max(shown.length - 1, 1) * (width - left - right),
      top + (height - top - bottom) - (row[1] - min) / span * (height - top - bottom), row[0]
    ]);
    const grid = Array.from({ length: 5 }, (_, index) => {
      const y = top + (height - top - bottom) * index / 4;
      return `<line x1="${left}" y1="${y}" x2="${width - right}" y2="${y}" stroke="var(--line)"/>`;
    }).join('');
    const path = points.map((point) => `${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(' ');
    const endpoints = points.length
      ? `<text x="${left}" y="${height - 12}" class="axis-label">${points[0][2]}</text><text x="${width - right}" y="${height - 12}" text-anchor="end" class="axis-label">${points.at(-1)[2]}</text>` : '';
    return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Monthly review trend for the current selection">${grid}<polyline points="${path}" fill="none" stroke="var(--accent)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>${endpoints}</svg>`;
  }

  function barChart(ratings) {
    const width = 520, height = 210, left = 42, top = 18, chartHeight = 158;
    const max = Math.max(...ratings, 1), gap = 14, barWidth = (456 - gap * 4) / 5;
    const bars = ratings.map((value, index) => {
      const barHeight = value / max * chartHeight;
      const x = left + index * (barWidth + gap), y = top + chartHeight - barHeight;
      return `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="8" fill="var(--ink)" opacity="${0.38 + index * 0.12}"/><text x="${x + barWidth / 2}" y="${height - 10}" text-anchor="middle" class="axis-label">${index + 1} star</text><text x="${x + barWidth / 2}" y="${Math.max(y - 8, 10)}" text-anchor="middle" class="value-label">${integer.format(value)}</text>`;
    }).join('');
    return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Rating distribution for the current selection"><line x1="${left}" y1="176" x2="508" y2="176" stroke="var(--line)"/>${bars}</svg>`;
  }

  function render() {
    const query = controls.search.value.trim().toUpperCase();
    const minimum = Number(controls.minimum.value);
    const rating = Number(controls.rating.value);
    const start = controls.start.value || months[0];
    const end = controls.end.value || months.at(-1);
    const startIndex = Math.max(months.indexOf(start), 0);
    const endIndex = Math.max(months.indexOf(end), 0);
    const baseRows = data.cube.filter((row) => row[1] >= startIndex && row[1] <= endIndex
      && (!rating || row[2] === rating)
      && products[row[0]][0].includes(query)
      && (!controls.quality.value || products[row[0]][1] === controls.quality.value));

    const productCounts = new Map();
    for (const row of baseRows) productCounts.set(row[0], (productCounts.get(row[0]) || 0) + row[3]);
    const eligible = new Set([...productCounts].filter(([, reviews]) => reviews >= minimum).map(([id]) => id));
    const rows = minimum ? baseRows.filter((row) => eligible.has(row[0])) : baseRows;
    const productStats = new Map();
    const monthly = new Map();
    const ratings = [0, 0, 0, 0, 0];
    let reviews = 0, ratingTotal = 0, helpful = 0;
    for (const [productId, monthId, stars, rowCount, helpfulCount, words] of rows) {
      reviews += rowCount;
      ratingTotal += stars * rowCount;
      helpful += helpfulCount;
      ratings[stars - 1] += rowCount;
      monthly.set(monthId, (monthly.get(monthId) || 0) + rowCount);
      const stat = productStats.get(productId) || [0, 0, 0];
      stat[0] += rowCount; stat[1] += stars * rowCount; stat[2] += words;
      productStats.set(productId, stat);
    }
    const matches = [...productStats].map(([id, stat]) => ({
      asin: products[id][0], quality_flag: products[id][1], review_count: stat[0],
      avg_rating: stat[1] / stat[0], avg_review_word_count: stat[2] / stat[0]
    })).sort((a, b) => b.review_count - a.review_count);
    const monthRows = [...monthly].sort((a, b) => a[0] - b[0]).map(([id, value]) => [months[id], value]);
    const peak = monthRows.reduce((best, row) => !best || row[1] > best[1] ? row : best, null);
    const watchlist = matches.filter((product) => product.quality_flag === 'high_volume_low_rating');

    document.querySelector('#kpi-reviews').textContent = integer.format(reviews);
    document.querySelector('#kpi-products').textContent = integer.format(matches.length);
    document.querySelector('#kpi-rating').textContent = reviews ? (ratingTotal / reviews).toFixed(2) : '—';
    document.querySelector('#kpi-helpful').textContent = reviews ? pct(helpful / reviews * 100) : '—';
    document.querySelector('#meta-window').textContent = monthRows.length ? `${monthRows[0][0]} – ${monthRows.at(-1)[0]}` : 'No data';
    document.querySelector('#meta-latest').textContent = monthRows.at(-1)?.[0] || 'No data';
    document.querySelector('#meta-peak').textContent = peak?.[0] || 'No data';
    document.querySelector('#monthly-chart').innerHTML = lineChart(monthRows);
    document.querySelector('#rating-chart').innerHTML = barChart(ratings);
    body.replaceChildren(productRows(matches, visible));
    watchBody.replaceChildren(productRows(watchlist, 6));
    count.textContent = `Showing ${Math.min(visible, matches.length).toLocaleString('en-US')} of ${matches.length.toLocaleString('en-US')} products in the current selection`;
    more.hidden = visible >= matches.length;
    active.textContent = reviews ? `${integer.format(reviews)} reviews across ${integer.format(matches.length)} products; every KPI, chart and table reflects these filters.` : 'No matching reviews. Reset or widen the filters.';
    const profile = [
      ['High performers', matches.filter((product) => product.quality_flag === 'high_volume_high_rating').length],
      ['Monitor', matches.filter((product) => product.quality_flag === 'monitor').length],
      ['Watchlist', watchlist.length], ['Active months', monthRows.length]
    ];
    document.querySelector('#selection-profile').innerHTML = profile.map(([label, value]) => `<span class="chip">${label} <strong>${integer.format(value)}</strong></span>`).join('');
  }

  controls.start.min = controls.end.min = months[0];
  controls.start.max = controls.end.max = months.at(-1);
  controls.start.value = months[0];
  controls.end.value = months.at(-1);
  controls.search.addEventListener('input', () => { visible = 20; render(); });
  Object.values(controls).slice(1).forEach((control) =>
    control.addEventListener('change', () => {
      if (controls.start.value > controls.end.value) controls.end.value = controls.start.value;
      visible = 20; render();
    }));
  document.querySelector('#reset-filters').addEventListener('click', () => {
    controls.search.value = ''; controls.minimum.value = '0'; controls.rating.value = '0';
    controls.quality.value = ''; controls.start.value = months[0]; controls.end.value = months.at(-1);
    visible = 20; render();
  });
  more.addEventListener('click', () => { visible += 20; render(); });
  render();
})();"""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str | int | float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fmt_int(value: str | int | float) -> str:
    return f"{int(number(value)):,}"


def fmt_float(value: str | int | float, digits: int = 2) -> str:
    return f"{number(value):.{digits}f}"


def quality_label(flag: str) -> str:
    labels = {
        "high_volume_high_rating": "High volume / high rating",
        "high_volume_low_rating": "Watchlist",
        "low_sample_size": "Low sample",
        "monitor": "Monitor",
    }
    return labels.get(flag, flag.replace("_", " ").title())


def load_marts() -> dict[str, list[dict[str, str]]]:
    return {
        "products": read_csv(MARTS_DIR / "mart_product_performance.csv"),
        "monthly": read_csv(MARTS_DIR / "mart_monthly_review_trends.csv"),
        "ratings": read_csv(MARTS_DIR / "mart_rating_distribution.csv"),
        "quality": read_csv(MARTS_DIR / "mart_data_quality_summary.csv"),
    }


def quality_lookup(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row["metric"]: row["value"] for row in rows}


def build_dashboard_data(products: list[dict[str, str]]) -> dict[str, list]:
    product_index = {row["asin"]: index for index, row in enumerate(products)}
    cube: dict[tuple[int, str, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    with FACT_PATH.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (product_index[row["asin"]], row["review_month"], int(row["rating_id"]))
            values = cube[key]
            values[0] += 1
            values[1] += int(row["helpful_total"]) > 0
            values[2] += int(row["review_word_count"])
    months = sorted({month for _, month, _ in cube})
    month_index = {month: index for index, month in enumerate(months)}
    return {
        "products": [[row["asin"], row["quality_flag"]] for row in products],
        "months": months,
        "cube": [
            [product_id, month_index[month], rating, *values]
            for (product_id, month, rating), values in cube.items()
        ],
    }


def svg_bar_chart(ratings: list[dict[str, str]]) -> str:
    width = 520
    height = 210
    left = 42
    bottom = 34
    top = 18
    chart_h = height - top - bottom
    chart_w = width - left - 22
    max_count = max(number(row["review_count"]) for row in ratings) or 1
    bar_gap = 14
    bar_w = (chart_w - bar_gap * (len(ratings) - 1)) / len(ratings)

    bars = []
    labels = []
    for idx, row in enumerate(ratings):
        count = number(row["review_count"])
        bar_h = (count / max_count) * chart_h
        x = left + idx * (bar_w + bar_gap)
        y = top + chart_h - bar_h
        rating = html.escape(row["rating"])
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="8" fill="var(--ink)" opacity="{0.38 + idx * 0.12:.2f}"/>'
        )
        labels.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{height - 10}" text-anchor="middle" class="axis-label">{rating} star</text>'
        )
        labels.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="value-label">{fmt_int(count)}</text>'
        )

    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Rating distribution bar chart">
      <line x1="{left}" y1="{top + chart_h}" x2="{width - 12}" y2="{top + chart_h}" stroke="var(--line)" />
      {''.join(bars)}
      {''.join(labels)}
    </svg>
    """


def svg_line_chart(monthly: list[dict[str, str]]) -> str:
    recent = monthly[-30:] if len(monthly) > 30 else monthly
    width = 760
    height = 240
    left = 46
    right = 20
    top = 20
    bottom = 42
    chart_w = width - left - right
    chart_h = height - top - bottom
    counts = [number(row["review_count"]) for row in recent]
    max_count = max(counts) if counts else 1
    min_count = min(counts) if counts else 0
    span = max(max_count - min_count, 1)

    points = []
    for idx, row in enumerate(recent):
        x = left + (idx / max(len(recent) - 1, 1)) * chart_w
        y = top + chart_h - ((number(row["review_count"]) - min_count) / span) * chart_h
        points.append((x, y, row))

    point_attr = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="var(--accent)" />'
        for x, y, _ in points[:: max(len(points) // 8, 1)]
    )
    labels = ""
    if points:
        first = points[0][2]["review_month"]
        last = points[-1][2]["review_month"]
        labels = (
            f'<text x="{left}" y="{height - 12}" class="axis-label">{html.escape(first)}</text>'
            f'<text x="{width - right}" y="{height - 12}" text-anchor="end" class="axis-label">{html.escape(last)}</text>'
        )

    grid = "".join(
        f'<line x1="{left}" y1="{top + chart_h * i / 4:.1f}" x2="{width - right}" y2="{top + chart_h * i / 4:.1f}" stroke="var(--line)" />'
        for i in range(5)
    )

    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Monthly review trend line chart">
      {grid}
      <polyline points="{point_attr}" fill="none" stroke="var(--accent)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" />
      {circles}
      {labels}
    </svg>
    """


def status_class(flag: str) -> str:
    if flag == "high_volume_high_rating":
        return "status strong"
    if flag == "high_volume_low_rating":
        return "status risk"
    return "status"


def render_dashboard(data: dict[str, list[dict[str, str]]]) -> str:
    products = sorted(data["products"], key=lambda row: number(row["review_count"]), reverse=True)
    monthly = data["monthly"]
    ratings = data["ratings"]
    quality = quality_lookup(data["quality"])

    total_reviews = fmt_int(quality.get("rows_valid", "0"))
    unique_products = fmt_int(quality.get("unique_products", "0"))
    review_window = f"{quality.get('earliest_review_month', '')} - {quality.get('latest_review_month', '')}"
    helpful_coverage = f"{fmt_float(quality.get('pct_rows_with_helpful_votes', '0'))}%"
    avg_rating = sum(number(row["review_count"]) * number(row["rating"]) for row in ratings) / max(
        sum(number(row["review_count"]) for row in ratings), 1
    )

    top_products = products[:8]
    dashboard_json = json.dumps(build_dashboard_data(products), separators=(",", ":")).replace("<", "\\u003c")
    watchlist = [row for row in products if row["quality_flag"] == "high_volume_low_rating"][:6]
    if not watchlist:
        watchlist = products[8:14]

    latest_month = monthly[-1] if monthly else {"review_month": "n/a", "review_count": "0", "avg_rating": "0"}
    peak_month = max(monthly, key=lambda row: number(row["review_count"])) if monthly else latest_month

    product_rows = "\n".join(
        f"""
        <tr>
          <td><span class="asin">{html.escape(row['asin'])}</span></td>
          <td>{fmt_int(row['review_count'])}</td>
          <td>{fmt_float(row['avg_rating'])}</td>
          <td>{fmt_float(row['avg_review_word_count'], 1)}</td>
          <td><span class="{status_class(row['quality_flag'])}">{quality_label(row['quality_flag'])}</span></td>
        </tr>
        """
        for row in top_products
    )

    watch_rows = "\n".join(
        f"""
        <tr>
          <td><span class="asin">{html.escape(row['asin'])}</span></td>
          <td>{fmt_int(row['review_count'])}</td>
          <td>{fmt_float(row['avg_rating'])}</td>
          <td>{fmt_float(row['avg_review_word_count'], 1)}</td>
          <td><span class="{status_class(row['quality_flag'])}">{quality_label(row['quality_flag'])}</span></td>
        </tr>
        """
        for row in watchlist
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Retail Electronics Analytics Dashboard</title>
  <style>
    :root {{
      --bg: #f4f4f1;
      --panel: #ffffff;
      --ink: #111313;
      --muted: #646866;
      --soft: #e5e2dc;
      --line: #dedbd3;
      --accent: #0f766e;
      --accent-soft: #d8f2ec;
      --risk: #a34118;
      --risk-soft: #f7dfd2;
      --good: #186c45;
      --good-soft: #ddf3e6;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(90deg, rgba(17,19,19,0.045) 1px, transparent 1px),
        linear-gradient(180deg, rgba(17,19,19,0.045) 1px, transparent 1px),
        var(--bg);
      background-size: 44px 44px;
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
    }}

    .shell {{
      width: min(1440px, calc(100vw - 48px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }}

    header {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 24px;
      align-items: end;
      margin-bottom: 22px;
    }}

    .label {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 0 5px var(--accent-soft);
    }}

    h1 {{
      margin: 14px 0 10px;
      max-width: 880px;
      font-size: clamp(42px, 5.4vw, 84px);
      line-height: 0.94;
      letter-spacing: -0.04em;
    }}

    .subtitle {{
      margin: 0;
      max-width: 700px;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.5;
    }}

    .meta {{
      justify-self: end;
      width: min(100%, 420px);
      padding: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.74);
      border-radius: 18px;
    }}

    .meta-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}

    .mini-label {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    .mini-value {{
      margin-top: 4px;
      font-size: 15px;
      font-weight: 800;
    }}

    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 14px;
    }}

    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 50px rgba(26, 27, 25, 0.06);
    }}

    .kpi {{
      padding: 18px;
      min-height: 134px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}

    .kpi .value {{
      font-size: clamp(30px, 3vw, 48px);
      line-height: 1;
      font-weight: 900;
      letter-spacing: -0.05em;
    }}

    .kpi .note {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 14px;
      align-items: stretch;
    }}

    .panel {{
      padding: 22px;
      overflow: hidden;
    }}

    .panel-header {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      margin-bottom: 16px;
    }}

    h2 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: -0.03em;
    }}

    .panel p {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}

    .wide {{
      grid-column: 1 / -1;
    }}

    .filter-panel {{
      margin-bottom: 14px;
      padding: 18px;
    }}

    .filter-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 14px;
    }}

    .filter-head p {{
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}

    .dashboard-filters {{
      display: grid;
      grid-template-columns: 1.4fr repeat(5, minmax(0, 1fr));
      gap: 12px;
    }}

    .dashboard-filters label {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}

    .dashboard-filters input,
    .dashboard-filters select {{
      width: 100%;
      min-height: 42px;
      padding: 0 11px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      color: var(--ink);
      font: 500 14px Arial, Helvetica, sans-serif;
    }}

    .dashboard-filters :is(input, select):focus-visible,
    .reset-filters:focus-visible,
    .load-more:focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }}

    .filter-count {{
      margin: 0 0 14px !important;
      font-variant-numeric: tabular-nums;
    }}

    .active-filter-summary {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      font-variant-numeric: tabular-nums;
    }}

    .reset-filters {{
      min-height: 38px;
      padding: 0 15px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      color: var(--ink);
      font: 700 13px Arial, Helvetica, sans-serif;
      cursor: pointer;
      white-space: nowrap;
    }}

    .reset-filters:hover {{ background: var(--soft); }}

    .load-more {{
      display: block;
      margin: 18px auto 0;
      padding: 10px 18px;
      border: 1px solid var(--accent);
      border-radius: 999px;
      background: var(--panel);
      color: var(--accent);
      font: 700 13px Arial, Helvetica, sans-serif;
      cursor: pointer;
    }}

    .load-more:hover {{
      background: var(--accent-soft);
    }}

    .load-more[hidden] {{ display: none; }}

    svg {{
      width: 100%;
      height: auto;
      display: block;
    }}

    .axis-label {{
      fill: var(--muted);
      font-size: 11px;
      font-weight: 700;
    }}

    .value-label {{
      fill: var(--ink);
      font-size: 11px;
      font-weight: 800;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}

    th {{
      text-align: left;
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border-bottom: 1px solid var(--line);
      padding: 0 0 10px;
    }}

    td {{
      border-bottom: 1px solid var(--soft);
      padding: 12px 0;
      vertical-align: middle;
    }}

    th:not(:first-child),
    td:not(:first-child) {{
      text-align: right;
      padding-left: 14px;
    }}

    .asin {{
      font-family: "SFMono-Regular", Consolas, monospace;
      font-weight: 800;
      letter-spacing: -0.02em;
    }}

    .status {{
      display: inline-flex;
      justify-content: center;
      min-width: 78px;
      padding: 6px 9px;
      border-radius: 999px;
      background: #f1f0ea;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }}

    .status.strong {{
      background: var(--good-soft);
      color: var(--good);
    }}

    .status.risk {{
      background: var(--risk-soft);
      color: var(--risk);
    }}

    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 9px;
      align-content: flex-start;
    }}

    .chip {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 9px 11px;
      border-radius: 999px;
      background: #f4f3ef;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}

    .chip strong {{
      color: var(--ink);
      font-size: 12px;
    }}

    .insight-list {{
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}

    .insight-list li {{
      padding: 13px 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fbfaf7;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}

    .insight-list strong {{
      color: var(--ink);
    }}

    footer {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      margin-top: 16px;
      color: var(--muted);
      font-size: 12px;
    }}

    @media (max-width: 980px) {{
      header,
      .grid,
      .kpis {{
        grid-template-columns: 1fr;
      }}

      .dashboard-filters {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}

      .meta {{
        justify-self: stretch;
      }}
    }}

    @media (max-width: 640px) {{
      .shell {{
        width: min(100vw - 28px, 1440px);
        padding-top: 18px;
      }}

      .panel,
      .kpi {{
        padding: 16px;
      }}

      .panel {{
        overflow-x: auto;
      }}

      .dashboard-filters {{
        grid-template-columns: 1fr;
      }}

      .filter-head {{ align-items: flex-start; }}

      .meta-grid {{
        grid-template-columns: 1fr;
      }}

      table {{
        font-size: 12px;
        min-width: 560px;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <section>
        <div class="label"><span class="dot"></span> Retail Electronics Analytics</div>
        <h1>Review signals into BI-ready decisions.</h1>
        <p class="subtitle">An interactive executive dashboard generated from Amazon Electronics review data: product quality, rating mix, review trends, and data completeness.</p>
      </section>
      <aside class="meta">
        <div class="meta-grid">
          <div>
            <div class="mini-label">Dataset window</div>
            <div class="mini-value" id="meta-window">{html.escape(review_window)}</div>
          </div>
          <div>
            <div class="mini-label">Latest month</div>
            <div class="mini-value" id="meta-latest">{html.escape(latest_month['review_month'])}</div>
          </div>
          <div>
            <div class="mini-label">Peak month</div>
            <div class="mini-value" id="meta-peak">{html.escape(peak_month['review_month'])}</div>
          </div>
          <div>
            <div class="mini-label">Source</div>
            <div class="mini-value">Amazon reviews</div>
          </div>
        </div>
      </aside>
    </header>

    <section class="card filter-panel" aria-labelledby="filter-title">
      <div class="filter-head">
        <div>
          <h2 id="filter-title">Filter dashboard</h2>
          <p>Every KPI, chart and table updates from the same selection.</p>
        </div>
        <button class="reset-filters" id="reset-filters" type="button">Reset filters</button>
      </div>
      <div class="dashboard-filters">
        <label>Product ASIN <input id="product-search" type="search" placeholder="Search product ID" autocomplete="off" /></label>
        <label>From month <input id="start-month" type="month" /></label>
        <label>To month <input id="end-month" type="month" /></label>
        <label>Rating <select id="rating-filter">
          <option value="0">All ratings</option><option value="5">5 stars</option>
          <option value="4">4 stars</option><option value="3">3 stars</option>
          <option value="2">2 stars</option><option value="1">1 star</option>
        </select></label>
        <label>Minimum reviews <select id="minimum-reviews">
          <option value="0">Any volume</option><option value="100">100+</option>
          <option value="250">250+</option><option value="500">500+</option>
        </select></label>
        <label>Quality flag <select id="quality-flag">
          <option value="">All flags</option>
          <option value="high_volume_high_rating">High volume / high rating</option>
          <option value="high_volume_low_rating">Watchlist</option>
          <option value="monitor">Monitor</option>
        </select></label>
      </div>
      <p class="active-filter-summary" id="active-filter-summary" role="status" aria-live="polite"></p>
    </section>

    <section class="kpis">
      <article class="card kpi">
        <div class="mini-label">Processed reviews</div>
        <div class="value" id="kpi-reviews">{total_reviews}</div>
        <div class="note">Valid JSONL rows converted into analysis-ready marts.</div>
      </article>
      <article class="card kpi">
        <div class="mini-label">Unique products</div>
        <div class="value" id="kpi-products">{unique_products}</div>
        <div class="note">ASIN-level product keys available for KPI monitoring.</div>
      </article>
      <article class="card kpi">
        <div class="mini-label">Weighted avg rating</div>
        <div class="value" id="kpi-rating">{avg_rating:.2f}</div>
        <div class="note">Weighted across all processed review ratings.</div>
      </article>
      <article class="card kpi">
        <div class="mini-label">Helpful vote coverage</div>
        <div class="value" id="kpi-helpful">{helpful_coverage}</div>
        <div class="note">Share of reviews with at least one helpful-vote signal.</div>
      </article>
    </section>

    <section class="grid">
      <article class="card panel">
        <div class="panel-header">
          <div>
            <h2>Monthly review trend</h2>
            <p>Recent review-volume trajectory from dashboard-ready monthly mart.</p>
          </div>
        </div>
        <div id="monthly-chart">{svg_line_chart(monthly)}</div>
      </article>

      <article class="card panel">
        <div class="panel-header">
          <div>
            <h2>Rating distribution</h2>
            <p>Rating mix shows strong positive skew, with watchlist products still visible in product-level marts.</p>
          </div>
        </div>
        <div id="rating-chart">{svg_bar_chart(ratings)}</div>
      </article>

      <article class="card panel wide">
        <div class="panel-header">
          <div>
            <h2>Products in selection</h2>
            <p>Sorted by review volume after the dashboard filters are applied.</p>
          </div>
        </div>
        <p class="filter-count" id="product-count">Showing 8 highest-volume products</p>
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Reviews</th>
              <th>Avg rating</th>
              <th>Avg words</th>
              <th>Flag</th>
            </tr>
          </thead>
          <tbody id="product-results">{product_rows}</tbody>
        </table>
        <button class="load-more" id="load-more" type="button" hidden>Show 20 more</button>
      </article>

      <article class="card panel">
        <div class="panel-header">
          <div>
            <h2>Quality watchlist</h2>
            <p>Products to inspect when review volume is meaningful but satisfaction is weaker.</p>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Reviews</th>
              <th>Avg rating</th>
              <th>Avg words</th>
              <th>Flag</th>
            </tr>
          </thead>
          <tbody id="watch-results">{watch_rows}</tbody>
        </table>
      </article>

      <article class="card panel">
        <div class="panel-header">
          <div>
            <h2>Selection profile</h2>
            <p>Product mix and active months after the same dashboard filters are applied.</p>
          </div>
        </div>
        <div class="chips" id="selection-profile"></div>
      </article>

      <article class="card panel wide">
        <div class="panel-header">
          <div>
            <h2>Decision notes</h2>
            <p>How this dashboard should be interpreted by a marketplace or category team.</p>
          </div>
        </div>
        <ul class="insight-list">
          <li><strong>Review volume is the engagement proxy.</strong> The current dataset does not include sales quantity, so review count is used as a directional customer-activity signal.</li>
          <li><strong>ASIN is the product key.</strong> Product metadata can be joined later to unlock category, brand, and price-band views.</li>
          <li><strong>Quality flags are deliberately simple.</strong> They create a transparent first-pass watchlist before adding sentiment or support-ticket classification.</li>
          <li><strong>The marts are BI-ready.</strong> The CSV outputs can be connected directly to Power BI, Tableau, DuckDB, or a lightweight web dashboard.</li>
        </ul>
      </article>
    </section>

    <footer>
      <span>Generated from the review model and marts by src/build_dashboard.py</span>
      <span>Retail Electronics Analytics Pipeline</span>
    </footer>
  </main>
  <script type="application/json" id="dashboard-data">{dashboard_json}</script>
  <script>{FILTER_SCRIPT}</script>
</body>
</html>
"""


def main() -> None:
    data = load_marts()
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(line.rstrip() for line in render_dashboard(data).splitlines()) + "\n", encoding="utf-8")
    print(f"Wrote dashboard to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
