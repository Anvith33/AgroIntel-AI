"""
mandi_service.py — Government Mandi price service (display only).

Fetches the latest available market price from data.gov.in API.

IMPORTANT DESIGN CONSTRAINT:
  - This price is used ONLY for:
      1. Displaying the latest available market price in the UI
      2. Appending to historical tail if data is FRESH (< 3 days old)
      3. Sell/Hold comparison against ML predictions
  - This price is NEVER fed as a primary model input.
  - Forecast curves are NEVER manually shifted based on this price.

FRESHNESS POLICY (AGMARKNET / data.gov.in):
  - AGMARKNET typically publishes data with a 3–6 day delay (sometimes up to 7 days).
  - Any successful API response with valid records is ACCEPTED regardless of record age.
  - Fallback to historical dataset ONLY on: timeout, HTTP error, no records, invalid response.
  - Freshness label:
      Fresh    : 0–3 days old
      Recent   : 4–7 days old
      Historical: > 7 days old (API data, still preferred over CSV fallback)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CACHE_FILE = settings.DATA_DIR / "mandi_cache.json"

# ── Mandi commodity name map (crop name → API commodity name) ────────────────
CROP_TO_COMMODITY: dict[str, str] = {
    "wheat": "Wheat",
    "rice": "Rice",
    "maize": "Maize",
    "onion": "Onion",
    "potato": "Potato",
}

# ── Freshness thresholds (AGMARKNET publishes 3–6 days late) ─────────────────
FRESHNESS_FRESH_DAYS    = 3   # 0–3  days → Fresh
FRESHNESS_RECENT_DAYS   = 7   # 4–7  days → Recent
# > 7 days → Historical (still preferred over CSV fallback if from API)


@dataclass
class MandiPriceResult:
    """Result from mandi price lookup."""
    crop: str
    modal_price: float           # ₹ per quintal
    min_price: float
    max_price: float
    arrival_date: str            # ISO date string (YYYY-MM-DD)
    market: str
    state: str
    data_age_days: int           # How old the data is in days
    from_api: bool               # True = came from live/cached API; False = historical CSV
    source: str = "Government Mandi Data (data.gov.in)"
    freshness_label: str = field(init=False)

    def __post_init__(self):
        """Set freshness label based on data_age_days."""
        if self.data_age_days <= FRESHNESS_FRESH_DAYS:
            self.freshness_label = "Fresh"
        elif self.data_age_days <= FRESHNESS_RECENT_DAYS:
            self.freshness_label = "Recent"
        else:
            self.freshness_label = "Historical"

    @property
    def is_fresh(self) -> bool:
        return self.data_age_days <= FRESHNESS_FRESH_DAYS


def _load_cache() -> dict:
    """Load the persisted mandi price cache from disk."""
    try:
        if _CACHE_FILE.exists():
            with open(_CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not read mandi cache: {e}")
    return {}


def _save_cache(cache: dict) -> None:
    """Persist the mandi price cache to disk."""
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not write mandi cache: {e}")


def _parse_date(date_str: str) -> Optional[date]:
    """Parse date strings from the mandi API (DD/MM/YYYY or YYYY-MM-DD)."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _build_result(entry: dict, from_api: bool) -> "MandiPriceResult":
    """Build a MandiPriceResult from a cache/API entry dict."""
    return MandiPriceResult(
        crop=entry["crop"],
        modal_price=entry["modal_price"],
        min_price=entry.get("min_price", 0.0),
        max_price=entry.get("max_price", 0.0),
        arrival_date=entry["arrival_date"],
        market=entry.get("market", "Unknown"),
        state=entry.get("state", "All"),
        data_age_days=entry.get("data_age_days", 999),
        from_api=from_api,
    )


def get_latest_price(crop: str, state: Optional[str] = None) -> Optional["MandiPriceResult"]:
    """
    Fetch the latest available mandi price for a crop.

    STRATEGY:
      1. Check in-memory disk cache (fast, avoids redundant API calls within TTL).
      2. Fetch from data.gov.in API (8.0s timeout).
         - ANY successful response with records is accepted, regardless of record age.
         - AGMARKNET data is typically 3–6 days behind — this is NORMAL and NOT a failure.
      3. If API call fails (timeout / HTTP error / no records):
         - Return stale disk cache if available.
         - Return None if no cache exists (triggers historical CSV fallback in caller).

    FALLBACK DECISION (logs all details):
      fallback_used = True ONLY when HTTP fails / timeout / no records / invalid JSON.
      fallback_used = False for ANY successful API response (even 7-day-old data).
    """
    crop_lower = crop.lower()
    commodity = CROP_TO_COMMODITY.get(crop_lower)
    if not commodity:
        logger.warning(f"[MANDI] No commodity mapping for crop='{crop}'")
        return None

    cache = _load_cache()
    cache_key = f"{crop_lower}_{(state or 'all').lower()}"

    today = date.today()
    request_time = datetime.now().isoformat(timespec="seconds")

    # ── 1. Disk cache check (within TTL) ────────────────────────────────────
    cached_entry = cache.get(cache_key)
    if cached_entry:
        fetched_at = cached_entry.get("fetched_at", 0)
        cache_age_s = time.time() - fetched_at
        if cache_age_s < settings.MANDI_CACHE_TTL_SECONDS:
            rec_date_str = cached_entry.get("arrival_date", "")
            rec_date = _parse_date(rec_date_str) or today
            data_age = (today - rec_date).days
            logger.info(
                f"[MANDI] CACHE HIT for {cache_key} | "
                f"record_date={rec_date_str} | data_age={data_age}d | "
                f"cache_age={round(cache_age_s/3600,1)}h | fallback_used=No"
            )
            cached_entry["data_age_days"] = data_age
            return _build_result(cached_entry, from_api=True)

RESOURCE_1_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
RESOURCE_2_URL = "https://api.data.gov.in/resource/35be999b-0b15-465f-b964-1e582e0e0129"

def _normalize_api_record(rec: dict) -> dict:
    """Normalize records from Resource 1 or Resource 2 with various field naming conventions."""
    arr_str = rec.get("arrival_date") or rec.get("date") or ""
    
    modal_val = rec.get("modal_price") or rec.get("modal_price_rs_qtl") or 0.0
    min_val   = rec.get("min_price") or rec.get("min_price_rs_qtl") or 0.0
    max_val   = rec.get("max_price") or rec.get("max_price_rs_qtl") or 0.0

    return {
        "commodity": rec.get("commodity") or rec.get("commodity_name") or rec.get("crop") or "Unknown",
        "state": rec.get("state") or rec.get("state_name") or "All",
        "district": rec.get("district") or rec.get("district_name") or "Unknown",
        "market": rec.get("market") or rec.get("market_name") or "Unknown Mandi",
        "arrival_date": str(arr_str),
        "modal_price": float(modal_val) if modal_val else 0.0,
        "min_price": float(min_val) if min_val else 0.0,
        "max_price": float(max_val) if max_val else 0.0,
    }


def get_latest_price(crop: str, state: Optional[str] = None) -> Optional["MandiPriceResult"]:
    """
    Fetch the latest available mandi price for a crop using Resource 1 and Resource 2 APIs.
    """
    crop_lower = crop.lower()
    commodity = CROP_TO_COMMODITY.get(crop_lower, crop.capitalize())

    cache = _load_cache()
    cache_key = f"{crop_lower}_{(state or 'all').lower()}"

    today = date.today()
    request_time = datetime.now().isoformat(timespec="seconds")

    # ── 1. Disk cache check (within TTL) ────────────────────────────────────
    cached_entry = cache.get(cache_key)
    if cached_entry:
        fetched_at = cached_entry.get("fetched_at", 0)
        cache_age_s = time.time() - fetched_at
        if cache_age_s < settings.MANDI_CACHE_TTL_SECONDS:
            rec_date_str = cached_entry.get("arrival_date", "")
            rec_date = _parse_date(rec_date_str) or today
            data_age = (today - rec_date).days
            logger.info(
                f"[MANDI] CACHE HIT for {cache_key} | "
                f"record_date={rec_date_str} | data_age={data_age}d | "
                f"cache_age={round(cache_age_s/3600,1)}h | fallback_used=No"
            )
            cached_entry["data_age_days"] = data_age
            return _build_result(cached_entry, from_api=True)

    # ── 2. Live API fetch (Resource 1 then Resource 2) ─────────────────────
    t_api_start = time.time()

    for res_name, res_url in [("Resource 1 (9ef84268)", RESOURCE_1_URL), ("Resource 2 (35be999b)", RESOURCE_2_URL)]:
        try:
            params: dict = {
                "api-key": settings.MARKET_DATA_API_KEY,
                "format": "json",
                "filters[commodity]": commodity,
                "limit": 50,
                "sort[arrival_date]": "desc",
            }
            if state:
                params["filters[state]"] = state

            response = httpx.get(res_url, params=params, timeout=0.5)
            api_elapsed_ms = round((time.time() - t_api_start) * 1000, 1)

            if response.status_code == 200:
                api_data = response.json()
                raw_records = api_data.get("records", [])
                if raw_records:
                    rec = _normalize_api_record(raw_records[0])
                    arrival_str = rec["arrival_date"]
                    arrival = _parse_date(arrival_str)
                    data_age_days = (today - arrival).days if arrival else 999
                    arrival_iso = arrival.isoformat() if arrival else arrival_str

                    if data_age_days <= FRESHNESS_FRESH_DAYS:
                        freshness = "Fresh"
                    elif data_age_days <= FRESHNESS_RECENT_DAYS:
                        freshness = "Recent"
                    else:
                        freshness = "Historical"

                    entry = {
                        "crop": crop_lower,
                        "modal_price": rec["modal_price"],
                        "min_price": rec["min_price"],
                        "max_price": rec["max_price"],
                        "arrival_date": arrival_iso,
                        "market": rec["market"],
                        "state": rec["state"],
                        "data_age_days": data_age_days,
                        "fetched_at": time.time(),
                        "source": f"data.gov.in — {res_name}"
                    }

                    # Persist to cache
                    cache[cache_key] = entry
                    _save_cache(cache)

                    logger.warning(
                        f"[MANDI] API SUCCESS via {res_name} | crop={commodity} | "
                        f"record_date={arrival_iso} | modal=₹{entry['modal_price']}/q"
                    )
                    return _build_result(entry, from_api=True)
        except Exception as e:
            logger.debug(f"[MANDI] {res_name} call failed: {e}")
            continue

    # ── 3. Stale cache fallback ─────────────────────────────────────────────
    stale_entry = cache.get(cache_key)
    if stale_entry:
        rec_date_str = stale_entry.get("arrival_date", "")
        rec_date = _parse_date(rec_date_str) or today
        data_age = (today - rec_date).days
        stale_entry["data_age_days"] = data_age
        return _build_result(stale_entry, from_api=True)

    return None

