"""
soil_classifier.py — Village-Level Soil Detection via SoilGrids API

Uses the free ISRIC SoilGrids REST API (250m resolution, no API key required)
to fetch real soil properties at any GPS coordinate, then classifies them
into Indian agricultural soil types.

Free API Docs: https://rest.isric.org/soilgrids/v2.0/properties/query
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ── SoilGrids API endpoint ────────────────────────────────────────────────────
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# We request: phh2o (soil pH), clay (clay %), sand (sand %), soc (organic carbon)
SOIL_PROPERTIES = ["phh2o", "clay", "sand", "soc"]
SOIL_DEPTH      = "0-5cm"   # Topsoil layer relevant for agriculture


def _fetch_soilgrids(lat: float, lon: float) -> Optional[dict]:
    """
    Query the SoilGrids REST API for soil properties at a given coordinate.
    Returns: {ph, clay_pct, sand_pct, soc} or None if fetch fails.
    """
    try:
        params = {
            "lon":      lon,
            "lat":      lat,
            "property": SOIL_PROPERTIES,
            "depth":    SOIL_DEPTH,
            "value":    "mean",
        }
        response = requests.get(
            SOILGRIDS_URL,
            params=params,
            timeout=10,
            headers={"User-Agent": "AgroIntelAI/2.0 (agricultural advisory)"},
        )
        if response.status_code != 200:
            logger.warning(f"SoilGrids API returned {response.status_code} for {lat},{lon}")
            return None

        data = response.json()
        layers = data.get("properties", {}).get("layers", [])

        result = {}
        for layer in layers:
            name   = layer.get("name", "")
            depths = layer.get("depths", [])
            if not depths:
                continue
            # Get value for the target depth
            val_raw = depths[0].get("values", {}).get("mean")
            if val_raw is None:
                continue
            # SoilGrids returns values in units × 10 (e.g. pH × 10, clay % × 10)
            if name == "phh2o":
                result["ph"]       = round(val_raw / 10.0, 1)
            elif name == "clay":
                result["clay_pct"] = round(val_raw / 10.0, 1)
            elif name == "sand":
                result["sand_pct"] = round(val_raw / 10.0, 1)
            elif name == "soc":
                result["soc"]      = round(val_raw / 10.0, 2)   # g/kg

        if result:
            logger.info(f"SoilGrids data for ({lat},{lon}): {result}")
        return result if result else None

    except Exception as e:
        logger.warning(f"SoilGrids API call failed for ({lat},{lon}): {e}")
        return None


def _classify_indian_soil(ph: float, clay_pct: float, sand_pct: float, soc: float, lat: float, lon: float) -> str:
    """
    Classify GPS-derived soil properties into Indian agricultural soil types.

    Rules based on ICAR soil classification guidelines:
    - Black Soil (Regur):  clay > 40%, pH 7.5–8.5, low sand
    - Red Soil:            clay 20–35%, pH 5.5–7.0, high iron indicators (low SoC)
    - Laterite Soil:       pH < 5.5, medium clay, high Fe (tropical humid regions)
    - Alluvial Soil:       clay 15–30%, pH 6.5–8.0, high SoC
    - Sandy/Desert Soil:   sand > 70%, very low SoC
    - Mountain Soil:       lat > 28 AND elevation proxy (approximated)
    - Coastal Alluvial:    near coast proxy + alluvial properties
    """
    # Mountain soil proxy: high latitudes + hilly indicators
    if lat >= 28.5 and (clay_pct < 25 and sand_pct < 50):
        return "Mountain Soil"

    # Desert / Sandy soil
    if sand_pct > 68:
        return "Desert Soil" if (lat > 24 and lon < 76) else "Sandy Soil"

    # Black Cotton Soil (Vertisol / Regur)
    if clay_pct > 38 and 7.2 <= ph <= 8.8:
        return "Black Soil"

    # Laterite Soil — acidic, humid tropics
    if ph < 5.5 and clay_pct > 20:
        return "Laterite Soil"

    # Coastal Alluvial — near coasts, similar to alluvial but slightly salty
    if ph >= 7.0 and clay_pct < 30 and lon > 78 and lat < 18:
        return "Coastal Alluvial Soil"

    # Red Soil — Deccan plateau signature
    if 5.5 <= ph <= 7.2 and 15 <= clay_pct <= 35 and soc < 5:
        return "Red Soil"

    # Default: Alluvial Soil (most common in plains)
    return "Alluvial Soil"


def classify_soil(lat: float, lon: float) -> dict:
    """
    Main entry point: given GPS coordinates, return classified soil info.

    Returns:
        {
            soil_type: str,     # Indian soil classification
            ph: float,
            clay_pct: float,
            sand_pct: float,
            soc: float,         # Soil Organic Carbon g/kg
            source: str,        # 'soilgrids_api' | 'fallback'
            confidence: str,    # 'high' | 'medium' | 'low'
        }
    """
    raw = _fetch_soilgrids(lat, lon)

    if raw and "clay_pct" in raw and "sand_pct" in raw and "ph" in raw:
        ph       = raw.get("ph", 7.0)
        clay_pct = raw.get("clay_pct", 20.0)
        sand_pct = raw.get("sand_pct", 40.0)
        soc      = raw.get("soc", 5.0)

        soil_type = _classify_indian_soil(ph, clay_pct, sand_pct, soc, lat, lon)

        return {
            "soil_type":  soil_type,
            "ph":         ph,
            "clay_pct":   clay_pct,
            "sand_pct":   sand_pct,
            "soc":        soc,
            "source":     "soilgrids_satellite",
            "confidence": "high",
            "lat":        lat,
            "lon":        lon,
        }
    else:
        # Fallback: rough classification from coordinates only
        soil_type = _coord_based_fallback(lat, lon)
        return {
            "soil_type":  soil_type,
            "ph":         None,
            "clay_pct":   None,
            "sand_pct":   None,
            "soc":        None,
            "source":     "coordinate_fallback",
            "confidence": "low",
            "lat":        lat,
            "lon":        lon,
        }


def _coord_based_fallback(lat: float, lon: float) -> str:
    """
    Rough soil type estimate from coordinates when SoilGrids API is unavailable.
    Based on known Indian agro-ecological zone boundaries.
    """
    # Northeast / Assam — Alluvial
    if lat >= 24 and lon >= 88 and lon <= 97:
        return "Alluvial Soil"
    # Himalayan belt
    if lat >= 28 and (lon < 80 or lon > 88):
        return "Mountain Soil"
    # Rajasthan / Gujarat desert
    if lat >= 22 and lat <= 30 and lon >= 68 and lon <= 77:
        return "Desert Soil"
    # Deccan plateau
    if lat >= 13 and lat <= 22 and lon >= 73 and lon <= 80:
        return "Black Soil"
    # Western Ghats coastal strip
    if lon < 77 and lat < 20:
        return "Laterite Soil"
    # Coastal Andhra / Tamil Nadu
    if lon > 79 and lat < 18:
        return "Coastal Alluvial Soil"
    # Indo-Gangetic plains default
    return "Alluvial Soil"
