"""
backfill_weather.py — One-time weather history backfill script.

Downloads monthly average temperature and total rainfall from the
Open-Meteo Archive API for years 2019–2024.

IMPORTANT DESIGN NOTES:
  - Uses a central-India reference location (Nagpur: 21.1°N, 79.1°E)
    which is geographically representative of Indian agricultural zones.
    This is an approximation used ONLY as a climate feature — not as
    actual local weather for any specific district.
  - Run this script ONCE. Output is committed to the repository.
  - Training NEVER calls any weather API. It always reads weather_history.csv.
  - Weather features (avg_temp_monthly, total_rainfall_monthly) serve as
    seasonal climate proxies in the price prediction model.

Usage:
    python -m app.data.backfill_weather

Output:
    app/data/weather_history.csv  (columns: year, month, avg_temp, total_rainfall)
"""

import csv
import logging
import time
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

# Central India reference location (Nagpur) — geographically representative
# of the Indo-Gangetic Plain and Deccan agricultural belt.
REF_LAT = 21.1458
REF_LON = 79.0882

YEARS = range(2019, 2025)        # 2019 inclusive → 2024 inclusive

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

OUTPUT_PATH = Path(__file__).parent / "weather_history.csv"


# ── Fetch one month's data ─────────────────────────────────────────────────────

def fetch_monthly_weather(year: int, month: int) -> dict[str, float]:
    """
    Fetch daily temperature and rainfall for one calendar month from
    Open-Meteo Archive API, then aggregate to monthly averages/totals.

    Args:
        year:  Calendar year (e.g. 2019).
        month: Calendar month 1–12.

    Returns:
        dict with keys: avg_temp (°C), total_rainfall (mm)

    Raises:
        RuntimeError: if the API call fails or returns no data.
    """
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end   = f"{year}-{month:02d}-{last_day:02d}"

    params = {
        "latitude":   REF_LAT,
        "longitude":  REF_LON,
        "start_date": start,
        "end_date":   end,
        "daily":      "temperature_2m_mean,precipitation_sum",
        "timezone":   "Asia/Kolkata",
    }

    try:
        resp = httpx.get(ARCHIVE_URL, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"API error for {year}-{month:02d}: {exc}") from exc

    daily = data.get("daily", {})
    temps  = [t for t in daily.get("temperature_2m_mean", []) if t is not None]
    rains  = [r for r in daily.get("precipitation_sum",   []) if r is not None]

    if not temps:
        raise RuntimeError(f"No temperature data returned for {year}-{month:02d}")

    avg_temp       = round(sum(temps) / len(temps), 2)
    total_rainfall = round(sum(rains), 2) if rains else 0.0

    return {"avg_temp": avg_temp, "total_rainfall": total_rainfall}


# ── Main backfill routine ──────────────────────────────────────────────────────

def run_backfill() -> None:
    """
    Download monthly weather for all months in 2019–2024 and write to CSV.

    Skips months already present in the CSV (safe to re-run).
    """
    # Load existing rows to support resume on partial failure
    existing: set[tuple[int, int]] = set()
    rows: list[dict] = []

    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, newline="") as f:
            for row in csv.DictReader(f):
                yr, mo = int(row["year"]), int(row["month"])
                existing.add((yr, mo))
                rows.append(row)
        logger.info(f"Resuming — {len(existing)} months already in CSV")

    new_rows = 0
    errors   = 0

    for year in YEARS:
        for month in range(1, 13):
            if (year, month) in existing:
                logger.debug(f"  Skip {year}-{month:02d} (already fetched)")
                continue

            logger.info(f"Fetching {year}-{month:02d} …")
            try:
                result = fetch_monthly_weather(year, month)
                rows.append({
                    "year":            year,
                    "month":           month,
                    "avg_temp":        result["avg_temp"],
                    "total_rainfall":  result["total_rainfall"],
                })
                new_rows += 1
                logger.info(
                    f"  ✓ {year}-{month:02d}: "
                    f"avg_temp={result['avg_temp']}°C, "
                    f"total_rainfall={result['total_rainfall']}mm"
                )
            except RuntimeError as exc:
                logger.error(f"  ✗ {year}-{month:02d}: {exc}")
                errors += 1

            # Polite delay to avoid rate-limiting (Open-Meteo free tier)
            time.sleep(0.3)

    # Write all rows sorted by year, month
    rows.sort(key=lambda r: (int(r["year"]), int(r["month"])))

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "month", "avg_temp", "total_rainfall"])
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    logger.info(
        f"\n=== Backfill Complete ===\n"
        f"  Total months in CSV : {total}\n"
        f"  New months fetched  : {new_rows}\n"
        f"  Errors              : {errors}\n"
        f"  Output              : {OUTPUT_PATH}"
    )

    if errors > 0:
        logger.warning(
            f"{errors} months failed. Re-run the script to retry failed months."
        )


if __name__ == "__main__":
    run_backfill()
