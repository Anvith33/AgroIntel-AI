"""
fetch_mandi.py — Daily Mandi Data Ingestion Job for AgroIntel.

Fetches newly available Mandi prices from data.gov.in AGMARKNET API or official sources.
Normalizes state, crop, and market names.
Validates price bounds, rejects impossible values, deduplicates against historical dataset,
and appends new records to real_historical_prices_state.csv.
"""

import json
import logging
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pandas as pd

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.jobs.fetch_mandi")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
EXP_DIR = DATA_DIR / "experimental"
EXP_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR = BASE_DIR.parent / "audit" / "data"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

STATE_PRICE_CSV = DATA_DIR / "real_historical_prices_state.csv"
AUDIT_JSON_PATH = EXP_DIR / "mandi_ingestion_audit.json"
AUDIT_COPY_PATH = AUDIT_DIR / "mandi_ingestion_audit.json"

# Supported target crops for price forecasting
SUPPORTED_CROPS = ["rice", "wheat", "maize", "onion", "potato"]

# Commodity name mapping to canonical crop
COMMODITY_MAP = {
    "wheat": "wheat",
    "paddy(dhan)(common)": "rice",
    "paddy (dhan)(common)": "rice",
    "paddy(dhan)(a-grade)": "rice",
    "paddy (dhan)(a-grade)": "rice",
    "paddy(dhan)(grade a)": "rice",
    "paddy (dhan)(grade a)": "rice",
    "paddy(common)": "rice",
    "paddy (common)": "rice",
    "rice": "rice",
    "maize": "maize",
    "potato": "potato",
    "onion": "onion",
}

# State name normalization map
STATE_NORM_MAP = {
    "andaman and nicobar islands": "Andaman and Nicobar Islands",
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chandigarh": "Chandigarh",
    "chhattisgarh": "Chhattisgarh",
    "chattisgarh": "Chhattisgarh",
    "dadra and nagar haveli": "Dadra and Nagar Haveli",
    "dadra & nagar haveli": "Dadra and Nagar Haveli",
    "daman and diu": "Daman and Diu",
    "delhi": "Delhi",
    "nct of delhi": "Delhi",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jammu and kashmir": "Jammu and Kashmir",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "lakshadweep": "Lakshadweep",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "puducherry": "Puducherry",
    "pondicherry": "Puducherry",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "uttrakhand": "Uttarakhand",
    "west bengal": "West Bengal",
}

# Price sanity bounds (₹ per quintal)
MIN_PRICE_BOUND = 100.0
MAX_PRICE_BOUND = 45000.0


class MandiIngestionJob:
    """Production Daily Mandi Data Ingestion Job."""

    def __init__(self):
        self.api_key = settings.MARKET_DATA_API_KEY
        self.base_url = settings.MARKET_DATA_BASE_URL

    @staticmethod
    def normalize_state(raw_state: str) -> Optional[str]:
        if not raw_state or not isinstance(raw_state, str):
            return None
        cleaned = raw_state.strip().lower()
        return STATE_NORM_MAP.get(cleaned, raw_state.strip().title())

    @staticmethod
    def normalize_crop(raw_commodity: str) -> Optional[str]:
        if not raw_commodity or not isinstance(raw_commodity, str):
            return None
        cleaned = raw_commodity.strip().lower()
        return COMMODITY_MAP.get(cleaned)

    @staticmethod
    def normalize_date(raw_date: Any) -> Optional[str]:
        if not raw_date:
            return None
        s = str(raw_date).strip()
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"]:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def fetch_live_records(self, limit: int = 1500) -> List[Dict[str, Any]]:
        """Fetch newly published market price records from data.gov.in API."""
        if not self.api_key:
            logger.warning("No MARKET_DATA_API_KEY configured. Falling back to local cache.")
            return []

        params = {
            "api-key": self.api_key,
            "format": "json",
            "limit": limit,
        }
        try:
            logger.info("Connecting to data.gov.in AGMARKNET API...")
            with httpx.Client(timeout=12.0) as client:
                resp = client.get(self.base_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    records = data.get("records", [])
                    logger.info(f"Successfully fetched {len(records)} raw records from API.")
                    return records
                else:
                    logger.warning(f"data.gov.in API returned HTTP {resp.status_code}")
                    return []
        except Exception as e:
            logger.warning(f"Network error during Mandi API fetch: {e}")
            return []

    def validate_record(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and normalize a single mandi price record."""
        # 1. Commodity / Crop
        comm = raw.get("commodity") or raw.get("Commodity") or ""
        crop = self.normalize_crop(comm)
        if not crop or crop not in SUPPORTED_CROPS:
            return None

        # 2. State
        st_raw = raw.get("state") or raw.get("State") or ""
        state = self.normalize_state(st_raw)
        if not state:
            return None

        # 3. Date
        d_raw = raw.get("arrival_date") or raw.get("Arrival_Date") or raw.get("date") or ""
        ds = self.normalize_date(d_raw)
        if not ds:
            return None

        # 4. Prices
        try:
            modal = float(raw.get("modal_price") or raw.get("Modal_Price") or 0.0)
            min_p = float(raw.get("min_price") or raw.get("Min_Price") or modal)
            max_p = float(raw.get("max_price") or raw.get("Max_Price") or modal)
        except (ValueError, TypeError):
            return None

        if modal < MIN_PRICE_BOUND or modal > MAX_PRICE_BOUND:
            return None

        # Correct min/max inversions if any
        if min_p > max_p:
            min_p, max_p = max_p, min_p
        min_p = min(min_p, modal)
        max_p = max(max_p, modal)

        price_range = max_p - min_p

        return {
            "ds": ds,
            "crop": crop,
            "state": state,
            "y": round(modal, 2),
            "min_price": round(min_p, 2),
            "max_price": round(max_p, 2),
            "market_count": 1,
            "price_range": round(price_range, 2),
            "source": "api_data_gov_in",
        }

    def run(self) -> Dict[str, Any]:
        """Execute the full Mandi ingestion job."""
        t_start = time.time()
        logger.info("Starting Daily Mandi Ingestion Job...")

        raw_records = self.fetch_live_records()
        valid_records = []
        rejected_count = 0

        for r in raw_records:
            norm = self.validate_record(r)
            if norm:
                valid_records.append(norm)
            else:
                rejected_count += 1

        # Load existing dataset to check duplicates and append
        existing_df = None
        new_records_added = 0
        duplicate_count = 0

        if STATE_PRICE_CSV.exists():
            existing_df = pd.read_csv(STATE_PRICE_CSV)
            existing_df["ds"] = existing_df["ds"].astype(str)
            existing_keys = set(zip(existing_df["ds"], existing_df["crop"], existing_df["state"]))
        else:
            existing_keys = set()

        records_to_append = []
        for v in valid_records:
            key = (v["ds"], v["crop"], v["state"])
            if key in existing_keys:
                duplicate_count += 1
            else:
                existing_keys.add(key)
                records_to_append.append(v)

        if records_to_append:
            append_df = pd.DataFrame(records_to_append)
            # Add rolling_std_7 default if needed
            if "rolling_std_7" not in append_df.columns:
                append_df["rolling_std_7"] = 0.0

            cols_order = ["ds", "crop", "state", "y", "min_price", "max_price", "market_count", "price_range", "rolling_std_7"]
            for col in cols_order:
                if col not in append_df.columns:
                    append_df[col] = 0.0

            append_df = append_df[cols_order]

            if existing_df is not None:
                updated_df = pd.concat([existing_df, append_df], ignore_index=True)
            else:
                updated_df = append_df

            updated_df.to_csv(STATE_PRICE_CSV, index=False)
            new_records_added = len(records_to_append)
            logger.info(f"Appended {new_records_added} new valid mandi records to {STATE_PRICE_CSV.name}")
        else:
            logger.info("No new unique mandi records to append.")

        elapsed = round(time.time() - t_start, 2)
        total_rows = len(existing_df) + new_records_added if existing_df is not None else new_records_added

        audit_report = {
            "job_name": "fetch_mandi",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_seconds": elapsed,
            "api_status": "SUCCESS" if raw_records else "NO_API_DATA_OR_OFFLINE",
            "raw_records_fetched": len(raw_records),
            "valid_records_extracted": len(valid_records),
            "rejected_records": rejected_count,
            "duplicates_ignored": duplicate_count,
            "new_records_added": new_records_added,
            "total_dataset_rows": total_rows,
            "supported_crops": SUPPORTED_CROPS,
            "target_dataset_path": str(STATE_PRICE_CSV),
        }

        # Write audit logs
        with open(AUDIT_JSON_PATH, "w") as f:
            json.dump(audit_report, f, indent=2)
        with open(AUDIT_COPY_PATH, "w") as f:
            json.dump(audit_report, f, indent=2)

        logger.info(f"Mandi Ingestion Complete in {elapsed}s: +{new_records_added} records (Total: {total_rows}).")
        return audit_report


if __name__ == "__main__":
    job = MandiIngestionJob()
    res = job.run()
    print(json.dumps(res, indent=2))
