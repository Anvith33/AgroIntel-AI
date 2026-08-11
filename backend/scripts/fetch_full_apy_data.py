"""
fetch_full_apy_data.py — Phase 1 Official Agriculture Data Fetcher

Fetches complete nationwide district crop production dataset (246,091+ records)
from data.gov.in resource 35be999b-0208-4354-b557-f6ca9a5355de.
Uses pagination (limit=10,000) and saves raw records for normalization.
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings

RESOURCE_ID = "35be999b-0208-4354-b557-f6ca9a5355de"
BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
API_KEY = settings.MARKET_DATA_API_KEY

OUTPUT_DIR = BASE_DIR / "app" / "data" / "experimental"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_CACHE_FILE = OUTPUT_DIR / "raw_apy_records.json"
META_CACHE_FILE = OUTPUT_DIR / "raw_apy_metadata.json"

def fetch_chunk(offset: int, limit: int = 10000, max_retries: int = 3):
    url = f"{BASE_URL}?api-key={API_KEY}&format=json&limit={limit}&offset={offset}"
    for attempt in range(1, max_retries + 1):
        try:
            res = subprocess.run(
                ["curl", "-sk", "--max-time", "45", url],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(res.stdout)
            if "records" in data:
                return data
            else:
                print(f"\nWarning: Attempt {attempt} returned response without 'records': {res.stdout[:200]}")
        except Exception as e:
            print(f"\nError on attempt {attempt} for offset {offset}: {e}")
        time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to fetch chunk at offset {offset} after {max_retries} attempts.")

def main():
    print("=" * 70)
    print("AgroIntel Phase 1 — Nationwide District Crop Production Data Fetch")
    print(f"Resource ID: {RESOURCE_ID}")
    print("=" * 70)

    print("Probing API for total record count...")
    probe_data = fetch_chunk(offset=0, limit=10)
    total_records = probe_data.get("total", 0)
    fields = [f["id"] for f in probe_data.get("field", [])] if "field" in probe_data else []
    print(f"Total Records Reported: {total_records}")
    print(f"Fields Discovered: {fields}")

    all_records = []
    limit = 10000
    offset = 0
    pages_fetched = 0

    print(f"\nStarting batch download (limit={limit})...")
    t0 = time.time()

    while offset < total_records:
        pages_fetched += 1
        print(f"Fetching page {pages_fetched} (offset={offset} / {total_records})...", end="", flush=True)
        chunk_t0 = time.time()
        data = fetch_chunk(offset=offset, limit=limit)
        records = data.get("records", [])
        chunk_time = time.time() - chunk_t0
        all_records.extend(records)
        print(f" Received {len(records)} records in {chunk_time:.2f}s (Total accumulated: {len(all_records)})")

        if not records or len(records) < limit:
            print("Reached end of records.")
            break
        offset += limit
        time.sleep(0.5)

    elapsed = time.time() - t0
    print(f"\nCompleted fetch of {len(all_records)} records in {elapsed:.2f} seconds ({pages_fetched} API pages).")

    print(f"Saving raw records to {RAW_CACHE_FILE}...")
    with open(RAW_CACHE_FILE, "w") as f:
        json.dump(all_records, f, indent=2)

    metadata = {
        "resource_id": RESOURCE_ID,
        "title": probe_data.get("title", "District-wise, season-wise crop production statistics from 1997"),
        "total_records_api": total_records,
        "records_retrieved": len(all_records),
        "pages_retrieved": pages_fetched,
        "fetch_time_seconds": round(elapsed, 2),
        "fields": fields,
        "api_catalog_uuid": probe_data.get("catalog_uuid", ""),
        "created_date": probe_data.get("created_date", ""),
        "updated_date": probe_data.get("updated_date", "")
    }
    with open(META_CACHE_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    print("Raw data collection complete!")

if __name__ == "__main__":
    main()
