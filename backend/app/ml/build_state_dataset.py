"""
build_state_dataset.py — Build real_historical_prices_state.csv

Reads archive/csv/{year}.csv files (2001–2026, AGMARKNET data).
Preserves State column. Aggregates by (Date, Crop, State).
Outputs: real_historical_prices_state.csv

Columns: ds, crop, state, y (modal price ₹/qtl), 
         min_price, max_price, market_count, arrival_qtl
"""

import csv
import os
import json
import logging
import collections
from pathlib import Path
from datetime import datetime, date

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
ARCHIVE    = BASE_DIR / "app" / "data" / "archive" / "csv"
OUTPUT_CSV = BASE_DIR / "app" / "data" / "real_historical_prices_state.csv"
AUDIT_JSON = BASE_DIR / "app" / "data" / "experimental" / "state_crop_data_audit.json"

# Target years for state-aware training
TARGET_YEARS = list(range(2019, 2025))  # 2019–2024

# Commodity → crop name mapping
CROP_MAP = {
    "wheat":                         "wheat",
    "paddy(dhan)(common)":            "rice",
    "paddy (dhan)(common)":           "rice",
    "paddy(dhan)(a-grade)":           "rice",
    "paddy (dhan)(a-grade)":          "rice",
    "paddy(dhan)(grade a)":           "rice",
    "paddy (dhan)(grade a)":          "rice",
    "paddy(common)":                  "rice",
    "paddy (common)":                 "rice",
    "maize":                          "maize",
    "potato":                         "potato",
    "onion":                          "onion",
}

# State name normalization — AGMARKNET uses varied spellings
STATE_NORM = {
    "andaman and nicobar islands":   "Andaman and Nicobar Islands",
    "andhra pradesh":                "Andhra Pradesh",
    "arunachal pradesh":             "Arunachal Pradesh",
    "assam":                         "Assam",
    "bihar":                         "Bihar",
    "chandigarh":                    "Chandigarh",
    "chhattisgarh":                  "Chhattisgarh",
    "chattisgarh":                   "Chhattisgarh",
    "dadra and nagar haveli":        "Dadra and Nagar Haveli",
    "dadra & nagar haveli":          "Dadra and Nagar Haveli",
    "daman and diu":                 "Daman and Diu",
    "delhi":                         "Delhi",
    "nct of delhi":                  "Delhi",
    "goa":                           "Goa",
    "gujarat":                       "Gujarat",
    "haryana":                       "Haryana",
    "himachal pradesh":              "Himachal Pradesh",
    "jammu and kashmir":             "Jammu and Kashmir",
    "jharkhand":                     "Jharkhand",
    "karnataka":                     "Karnataka",
    "kerala":                        "Kerala",
    "lakshadweep":                   "Lakshadweep",
    "madhya pradesh":                "Madhya Pradesh",
    "maharashtra":                   "Maharashtra",
    "manipur":                       "Manipur",
    "meghalaya":                     "Meghalaya",
    "mizoram":                       "Mizoram",
    "nagaland":                      "Nagaland",
    "odisha":                        "Odisha",
    "orissa":                        "Odisha",
    "puducherry":                    "Puducherry",
    "pondicherry":                   "Puducherry",
    "punjab":                        "Punjab",
    "rajasthan":                     "Rajasthan",
    "sikkim":                        "Sikkim",
    "tamil nadu":                    "Tamil Nadu",
    "telangana":                     "Telangana",
    "tripura":                       "Tripura",
    "uttar pradesh":                 "Uttar Pradesh",
    "uttarakhand":                   "Uttarakhand",
    "uttrakhand":                    "Uttarakhand",
    "west bengal":                   "West Bengal",
}

# 28 official states + 8 UTs (AgroIntel covers all)
ALL_STATES = sorted(set(STATE_NORM.values()))
FIVE_CROPS = ["rice", "wheat", "maize", "onion", "potato"]


def _norm_state(raw: str) -> str:
    return STATE_NORM.get(raw.lower().strip(), raw.strip())


def _norm_commodity(raw: str) -> str | None:
    s = raw.lower().strip()
    for key, crop in CROP_MAP.items():
        if key in s:
            return crop
    return None


def build_dataset():
    logger.info("=== Building state-level historical price dataset ===")

    # Accumulate: {(date_str, crop, state): [modal_prices, min_prices, max_prices, arrivals]}
    Accum = collections.defaultdict(lambda: {"modals": [], "mins": [], "maxs": [], "arrivals": []})

    total_raw = 0
    skipped   = 0

    for year in TARGET_YEARS:
        fpath = ARCHIVE / f"{year}.csv"
        if not fpath.exists():
            logger.warning(f"  Missing: {fpath}")
            continue

        logger.info(f"  Processing {year}.csv ...")
        with open(fpath, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_raw += 1

                # State
                raw_state = row.get("State", "").strip()
                if not raw_state:
                    skipped += 1; continue
                state = _norm_state(raw_state)

                # Commodity → crop
                raw_comm = row.get("Commodity", "")
                crop = _norm_commodity(raw_comm)
                if crop is None:
                    skipped += 1; continue

                # Modal price
                raw_modal = row.get("Modal_Price", "").strip()
                try:
                    modal = float(raw_modal)
                    if modal <= 0:
                        skipped += 1; continue
                except (ValueError, TypeError):
                    skipped += 1; continue

                # Date
                raw_date = row.get("Arrival_Date", "").strip()
                if not raw_date:
                    skipped += 1; continue
                # Normalise date format
                try:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                        try:
                            dt = datetime.strptime(raw_date, fmt)
                            date_str = dt.strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            continue
                    else:
                        skipped += 1; continue
                except Exception:
                    skipped += 1; continue

                # Optional fields
                try:
                    min_p = float(row.get("Min_Price", 0) or 0)
                except Exception:
                    min_p = 0.0
                try:
                    max_p = float(row.get("Max_Price", 0) or 0)
                except Exception:
                    max_p = 0.0
                try:
                    arr = float(row.get("Arrivals", 0) or row.get("Arrivals_Qty", 0) or 0)
                except Exception:
                    arr = 0.0

                key = (date_str, crop, state)
                Accum[key]["modals"].append(modal)
                if min_p > 0:  Accum[key]["mins"].append(min_p)
                if max_p > 0:  Accum[key]["maxs"].append(max_p)
                if arr   > 0:  Accum[key]["arrivals"].append(arr)

    logger.info(f"Raw rows processed: {total_raw:,}  Skipped: {skipped:,}")
    logger.info(f"Unique (date, crop, state) keys: {len(Accum):,}")

    # Write CSV
    rows_written = 0
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ds", "crop", "state", "y",
                          "min_price", "max_price",
                          "market_count", "arrival_qtl"])
        for (date_str, crop, state), v in sorted(Accum.items()):
            modals   = v["modals"]
            mins     = v["mins"]
            maxs     = v["maxs"]
            arrivals = v["arrivals"]

            y          = round(sum(modals) / len(modals), 2)
            min_p      = round(sum(mins)   / len(mins),   2) if mins   else 0.0
            max_p      = round(sum(maxs)   / len(maxs),   2) if maxs   else 0.0
            mkt_count  = len(modals)
            arr_total  = round(sum(arrivals), 2)

            writer.writerow([date_str, crop, state, y,
                              min_p, max_p, mkt_count, arr_total])
            rows_written += 1

    logger.info(f"Written {rows_written:,} rows to {OUTPUT_CSV}")

    # ── Build audit JSON ─────────────────────────────────────────────────────
    logger.info("Building state_crop_data_audit.json ...")
    audit = {}
    # Re-aggregate from Accum for audit stats
    from collections import defaultdict
    stats = defaultdict(lambda: {"count": 0, "first": "9999-99-99", "last": "0000-00-00"})
    for (date_str, crop, state) in Accum.keys():
        k = f"{state}||{crop}"
        stats[k]["count"]   += len(Accum[(date_str, crop, state)]["modals"])
        stats[k]["first"]    = min(stats[k]["first"], date_str)
        stats[k]["last"]     = max(stats[k]["last"],  date_str)

    audit_records = []
    for state in ALL_STATES:
        for crop in FIVE_CROPS:
            k    = f"{state}||{crop}"
            cnt  = stats[k]["count"]
            first = stats[k]["first"] if cnt > 0 else None
            last  = stats[k]["last"]  if cnt > 0 else None

            if cnt == 0:
                status = "NO_DATA"
            elif cnt < 50:
                status = "INSUFFICIENT"
            elif cnt < 200:
                status = "LIMITED"
            else:
                status = "ADEQUATE"

            audit_records.append({
                "state":           state,
                "crop":            crop,
                "record_count":    cnt,
                "first_date":      first,
                "last_date":       last,
                "coverage_status": status,
            })

    audit_out = {
        "generated_at":     datetime.now().isoformat(),
        "source_years":     TARGET_YEARS,
        "total_records":    rows_written,
        "unique_states":    len(set(r["state"] for r in audit_records if r["record_count"] > 0)),
        "adequate_pairs":   sum(1 for r in audit_records if r["coverage_status"] == "ADEQUATE"),
        "limited_pairs":    sum(1 for r in audit_records if r["coverage_status"] == "LIMITED"),
        "insufficient_pairs": sum(1 for r in audit_records if r["coverage_status"] == "INSUFFICIENT"),
        "no_data_pairs":    sum(1 for r in audit_records if r["coverage_status"] == "NO_DATA"),
        "coverage":         audit_records,
    }

    AUDIT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit_out, f, indent=2)

    logger.info(f"Audit saved to {AUDIT_JSON}")
    logger.info(f"  Adequate pairs:    {audit_out['adequate_pairs']}")
    logger.info(f"  Limited pairs:     {audit_out['limited_pairs']}")
    logger.info(f"  Insufficient pairs:{audit_out['insufficient_pairs']}")
    logger.info(f"  No-data pairs:     {audit_out['no_data_pairs']}")
    return audit_out


if __name__ == "__main__":
    result = build_dataset()
    print(f"\nDataset built successfully: {result['total_records']:,} daily state-crop records")
