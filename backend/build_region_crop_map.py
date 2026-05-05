"""
build_region_crop_map.py
========================
Mines the mandi CSV archive (2001-2026) to build a comprehensive
region → crop mapping based on ACTUAL trading history.

Output: app/data/region_crop_mapping.json

Structure:
{
  "states": {
    "Kerala": {
      "top_crops": ["Coconut", "Banana", "Rice", ...],
      "soil_type": "Coastal Alluvial Soil"
    },
    ...
  },
  "districts": {
    "Kozhikode": {
      "state": "Kerala",
      "top_crops": ["Coconut", "Banana", "Arecanut", ...],
      "soil_type": "Coastal Alluvial Soil",
      "total_records": 12543
    },
    ...
  },
  "generated_at": "2026-05-04",
  "total_unique_crops": 512,
  "total_districts": 680
}
"""

import os
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict, Counter
from datetime import date

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
CSV_DIR    = BASE_DIR / "app" / "data" / "archive" / "csv"
DATA_DIR   = BASE_DIR / "app" / "data"
GEO_MAP    = DATA_DIR / "geo_soil_mapping.json"
OUTPUT     = DATA_DIR / "region_crop_mapping.json"

# ── Config ────────────────────────────────────────────────────────────────────
# Use recent 3 years for fast build — enough to cover all districts
# Change to range(2015, 2026) for a full historical build
USE_YEARS = [2023, 2024, 2025]

# Minimum occurrences for a crop to be considered "grown" in a region
MIN_STATE_OCCURRENCES    = 20
MIN_DISTRICT_OCCURRENCES = 5

# Top N crops to keep per region
TOP_N_STATE    = 40
TOP_N_DISTRICT = 25

# Columns we need (keep memory low)
USE_COLS = ["State", "District", "Commodity"]

# ── Excluded commodities (not crops: livestock, services etc.) ────────────────
EXCLUDE_COMMODITIES = {
    "Bull", "Cow", "Ox", "She Goat", "He Goat", "Sheep", "Buffalo",
    "Horse", "Pig", "Rabbit", "Poultry", "Hen",
    "Firewood", "Bamboo", "Grass", "Straw", "Hay",
    "Sand", "Stone", "Gravel",
}

print("=" * 60)
print("AgroIntel AI — Region Crop Map Builder")
print("=" * 60)

# ── Load geo-soil mapping ─────────────────────────────────────────────────────
with open(GEO_MAP, "r") as f:
    geo = json.load(f)

district_soil = {k.lower(): v for k, v in geo.get("districts", {}).items()}
state_soil    = {k.lower(): v for k, v in geo.get("states", {}).items()}

# ── Accumulators ──────────────────────────────────────────────────────────────
state_crop_counter    = defaultdict(Counter)   # state_name  → Counter(crop → count)
district_crop_counter = defaultdict(Counter)   # district_name → Counter(crop → count)
district_state_map    = {}                     # district_name → state_name
all_crops             = set()

# ── Process CSVs year by year ─────────────────────────────────────────────────
for year in USE_YEARS:
    csv_path = CSV_DIR / f"{year}.csv"
    if not csv_path.exists():
        print(f"  [SKIP] {year}.csv not found")
        continue

    print(f"  Processing {year}.csv ({csv_path.stat().st_size // 1_000_000} MB)...", end=" ", flush=True)

    try:
        total_rows = 0
        for chunk in pd.read_csv(
            csv_path,
            usecols=USE_COLS,
            dtype=str,
            chunksize=300_000,
            low_memory=True,
            on_bad_lines="skip",
        ):
            # Clean
            chunk = chunk.dropna(subset=["State", "District", "Commodity"])
            chunk["State"]     = chunk["State"].str.strip().str.title()
            chunk["District"]  = chunk["District"].str.strip().str.title()
            chunk["Commodity"] = chunk["Commodity"].str.strip().str.title()

            # Exclude non-crop commodities
            chunk = chunk[~chunk["Commodity"].isin(EXCLUDE_COMMODITIES)]

            # Fast aggregation — no iterrows!
            # State → Commodity counts
            sc = chunk.groupby(["State", "Commodity"]).size()
            for (state, crop), cnt in sc.items():
                state_crop_counter[state][crop] += cnt
                all_crops.add(crop)

            # District → Commodity counts + district→state map
            dc = chunk.groupby(["District", "Commodity", "State"]).size()
            for (district, crop, state), cnt in dc.items():
                district_crop_counter[district][crop] += cnt
                district_state_map[district] = state

            total_rows += len(chunk)

        print(f"OK ({total_rows:,} rows)")

    except Exception as e:
        print(f"ERROR — {e}")

# ── Build output ──────────────────────────────────────────────────────────────
print("\nBuilding region_crop_mapping.json ...")

out_states    = {}
out_districts = {}

# States
for state, counter in state_crop_counter.items():
    top = [
        crop for crop, cnt in counter.most_common(TOP_N_STATE * 3)
        if cnt >= MIN_STATE_OCCURRENCES
    ][:TOP_N_STATE]

    if not top:
        continue

    soil = state_soil.get(state.lower(), geo.get("default", "Alluvial Soil"))
    out_states[state] = {
        "top_crops": top,
        "soil_type": soil,
        "total_records": sum(counter.values()),
        "unique_crops": len([c for c, n in counter.items() if n >= MIN_STATE_OCCURRENCES]),
    }

# Districts
for district, counter in district_crop_counter.items():
    top = [
        crop for crop, cnt in counter.most_common(TOP_N_DISTRICT * 3)
        if cnt >= MIN_DISTRICT_OCCURRENCES
    ][:TOP_N_DISTRICT]

    if not top:
        continue

    state = district_state_map.get(district, "Unknown")
    soil  = district_soil.get(district.lower(),
            state_soil.get(state.lower(), geo.get("default", "Alluvial Soil")))

    out_districts[district] = {
        "state": state,
        "top_crops": top,
        "soil_type": soil,
        "total_records": sum(counter.values()),
    }

# Final output
result = {
    "generated_at":     str(date.today()),
    "years_used":       USE_YEARS,
    "total_unique_crops": len(all_crops),
    "total_states":     len(out_states),
    "total_districts":  len(out_districts),
    "states":           out_states,
    "districts":        out_districts,
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"\n✅ Done!")
print(f"   States    : {len(out_states)}")
print(f"   Districts : {len(out_districts)}")
print(f"   Unique crops found: {len(all_crops)}")
print(f"   Output    : {OUTPUT}")
