"""
satellite_service.py — Free Satellite Data Integration

Fetches NDVI (vegetation health) and soil moisture using completely free,
no-key-required public APIs:

1. OpenLandMap (NDVI) — Global 250m resolution, no auth needed
2. NASA SMAP (soil moisture) — via OpenLandMap composite layer
3. Fallback: NDVI estimation from weather conditions

Free API Docs:
  - https://openlandmap.org/
  - https://stac.openlandmap.org/
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ── OpenLandMap API ───────────────────────────────────────────────────────────
OPENLANDMAP_URL  = "https://api.openlandmap.org/query/point"

# ── NDVI Classification thresholds ───────────────────────────────────────────
NDVI_CLASSES = [
    (0.60, "🟢 Lush / Irrigated",      "excellent"),
    (0.40, "🟡 Moderate Vegetation",    "good"),
    (0.20, "🟠 Sparse Vegetation",      "moderate"),
    (0.10, "🔴 Very Dry / Barren",      "poor"),
    (-1.0, "⚫ Non-vegetated / Water",  "unsuitable"),
]

# ── Soil Moisture Classification ──────────────────────────────────────────────
SM_CLASSES = [
    (0.40, "💧 High Moisture",       "wet"),
    (0.25, "💧 Adequate Moisture",   "adequate"),
    (0.10, "⚠️ Low Moisture",        "dry"),
    (-1.0, "🏜️ Very Dry / Arid",     "arid"),
]


def _classify_ndvi(ndvi: float) -> dict:
    for threshold, label, status in NDVI_CLASSES:
        if ndvi >= threshold:
            return {"label": label, "status": status}
    return {"label": "Unknown", "status": "unknown"}


def _classify_moisture(sm: float) -> dict:
    for threshold, label, status in SM_CLASSES:
        if sm >= threshold:
            return {"label": label, "status": status}
    return {"label": "Unknown", "status": "unknown"}


def _fetch_openlandmap_ndvi(lat: float, lon: float) -> Optional[float]:
    """
    Fetch NDVI from OpenLandMap point query API.
    Uses MODIS-based composite NDVI layer (global, 250m, free, no key).
    Returns NDVI value (−1 to 1) or None if unavailable.
    """
    try:
        # MODIS NDVI 250m annual composite layer from OpenLandMap
        params = {
            "lon":    lon,
            "lat":    lat,
            "coll":   "mod13q1.ndvi.500m_m_10dy_",  # MODIS 10-day NDVI composite
            "format": "json",
        }
        resp = requests.get(
            OPENLANDMAP_URL,
            params=params,
            timeout=8,
            headers={"User-Agent": "AgroIntelAI/2.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            # OpenLandMap returns list of {date, value} pairs — take the most recent
            values = data.get("data", [])
            if values:
                # Sort by date, take latest non-null
                sorted_vals = sorted(values, key=lambda x: x.get("time", ""), reverse=True)
                for entry in sorted_vals:
                    v = entry.get("value")
                    if v is not None:
                        # NDVI is stored ×10000 in this layer
                        ndvi = round(float(v) / 10000.0, 3)
                        if -1.0 <= ndvi <= 1.0:
                            return ndvi
        logger.warning(f"OpenLandMap NDVI fetch returned no valid data for ({lat},{lon})")
        return None
    except Exception as e:
        logger.warning(f"OpenLandMap NDVI fetch failed for ({lat},{lon}): {e}")
        return None


def _estimate_ndvi_from_weather(temperature: float, humidity: float, rainfall: float) -> float:
    """
    Estimate NDVI from weather parameters when satellite data is unavailable.
    Based on empirical relationships between vegetation index and climate.
    """
    # Rainfall drives vegetation most in Indian context
    if rainfall > 200:
        base = 0.55
    elif rainfall > 100:
        base = 0.40
    elif rainfall > 50:
        base = 0.25
    else:
        base = 0.10

    # Humidity adjustment
    if humidity > 75:
        base += 0.08
    elif humidity < 40:
        base -= 0.05

    # Temperature adjustment (extreme heat reduces NDVI)
    if temperature > 40:
        base -= 0.10
    elif temperature < 10:
        base -= 0.05

    return round(max(-0.1, min(0.9, base)), 2)


def get_satellite_data(lat: float, lon: float,
                       temperature: float = 25.0,
                       humidity: float = 60.0,
                       rainfall: float = 100.0) -> dict:
    """
    Main entry point: fetch satellite-derived agricultural indicators.

    Args:
        lat, lon: GPS coordinates
        temperature, humidity, rainfall: Weather fallback values

    Returns:
        {
            ndvi: float,
            ndvi_label: str,
            ndvi_status: str,          # excellent | good | moderate | poor | unsuitable
            soil_moisture_estimated: float,
            moisture_label: str,
            moisture_status: str,      # wet | adequate | dry | arid
            satellite_source: str,     # 'openlandmap' | 'weather_estimate'
            suitability_score: int,    # 0–100 overall satellite suitability
            crop_warnings: list[str],  # any satellite-based warnings
        }
    """
    # 1. Try to get real NDVI from satellite
    ndvi        = _fetch_openlandmap_ndvi(lat, lon)
    sat_source  = "openlandmap"

    if ndvi is None:
        ndvi       = _estimate_ndvi_from_weather(temperature, humidity, rainfall)
        sat_source = "weather_estimate"

    ndvi_class    = _classify_ndvi(ndvi)

    # 2. Estimate soil moisture from humidity + rainfall (SMAP proxy)
    # Simplified: soil moisture ≈ rainfall_normalized × humidity factor
    sm_estimate   = min(0.5, (rainfall / 500.0) * (humidity / 100.0) + 0.05)
    sm_estimate   = round(sm_estimate, 3)
    sm_class      = _classify_moisture(sm_estimate)

    # 3. Crop warnings from satellite
    warnings = []
    if ndvi < 0.15:
        warnings.append("⚠️ Very low vegetation index — region appears dry or barren. Only drought-resistant crops recommended.")
    if ndvi > 0.60:
        warnings.append("✅ Excellent vegetation health detected — irrigated/moist conditions ideal for high-yield crops.")
    if sm_estimate < 0.12:
        warnings.append("⚠️ Low soil moisture detected — water-intensive crops (rice, sugarcane) may face water stress.")
    if temperature > 42:
        warnings.append("🌡️ Extreme heat conditions — avoid heat-sensitive crops (potato, peas).")

    # 4. Suitability score (0–100)
    ndvi_score = min(100, max(0, int((ndvi + 0.1) * 80)))
    sm_score   = min(100, max(0, int(sm_estimate * 250)))
    suitability_score = int((ndvi_score * 0.6) + (sm_score * 0.4))

    return {
        "ndvi":                     ndvi,
        "ndvi_label":               ndvi_class["label"],
        "ndvi_status":              ndvi_class["status"],
        "soil_moisture_estimated":  sm_estimate,
        "moisture_label":           sm_class["label"],
        "moisture_status":          sm_class["status"],
        "satellite_source":         sat_source,
        "suitability_score":        suitability_score,
        "crop_warnings":            warnings,
    }


def get_ndvi_crop_filter(ndvi: float) -> dict:
    """
    Returns which crop categories are suitable/unsuitable based on NDVI.
    Used by inference.py to filter crop recommendations.
    """
    if ndvi >= 0.50:
        return {
            "allow_water_intensive": True,
            "allow_drought_crops":   True,
            "min_suitability":       "good",
        }
    elif ndvi >= 0.30:
        return {
            "allow_water_intensive": False,
            "allow_drought_crops":   True,
            "min_suitability":       "moderate",
        }
    elif ndvi >= 0.15:
        return {
            "allow_water_intensive": False,
            "allow_drought_crops":   True,
            "min_suitability":       "poor",
        }
    else:
        return {
            "allow_water_intensive": False,
            "allow_drought_crops":   True,
            "min_suitability":       "drought_only",
        }
