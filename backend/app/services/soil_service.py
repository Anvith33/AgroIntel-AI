"""
soil_service.py — Soil profile resolution service.

Priority:
  1. User-provided NPK + pH (used directly — most accurate)
  2. geo_soil_mapping.json (district → soil type → default NPK values)
  3. Default fallback values
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import settings
from app.core.constants import DEFAULT_SOIL_VALUES, DEFAULT_SOIL_FALLBACK

logger = logging.getLogger(__name__)

# ── Load geo soil mapping once at module level ───────────────────────────────
_GEO_SOIL_PATH = settings.DATA_DIR / "geo_soil_mapping.json"
_geo_soil_data: Optional[dict] = None


def _load_geo_soil() -> dict:
    """Load and cache geo_soil_mapping.json."""
    global _geo_soil_data
    if _geo_soil_data is None:
        try:
            with open(_GEO_SOIL_PATH, "r") as f:
                _geo_soil_data = json.load(f)
            logger.info(f"Loaded geo_soil_mapping with {len(_geo_soil_data.get('districts', {}))} districts")
        except Exception as e:
            logger.error(f"Failed to load geo_soil_mapping.json: {e}")
            _geo_soil_data = {"districts": {}}
    return _geo_soil_data


@dataclass
class SoilProfile:
    """Resolved soil profile for a district."""
    nitrogen: float       # N (mg/kg)
    phosphorus: float     # P (mg/kg)
    potassium: float      # K (mg/kg)
    ph: float             # Soil pH
    soil_type: str        # Human-readable soil type name
    source: str           # "user_provided" | "geo_mapping" | "fallback"


def get_soil_profile(
    district: str,
    nitrogen: Optional[float] = None,
    phosphorus: Optional[float] = None,
    potassium: Optional[float] = None,
    ph: Optional[float] = None,
) -> SoilProfile:
    """
    Resolve soil profile for a given district.
    """
    # 1. Priority 1: All user values present
    user_npk_provided = all(
        v is not None for v in [nitrogen, phosphorus, potassium, ph]
    )
    if user_npk_provided:
        logger.debug(f"Using user-provided soil values for district='{district}'")
        return SoilProfile(
            nitrogen=float(nitrogen),
            phosphorus=float(phosphorus),
            potassium=float(potassium),
            ph=float(ph),
            soil_type="User Provided",
            source="user_provided",
        )

    # 2. Priority 2: Geo soil mapping
    geo_data = _load_geo_soil()
    district_key = district.strip().lower()
    districts_map: dict = geo_data.get("districts", {})

    soil_type: Optional[str] = None
    if district_key in districts_map:
        soil_type = districts_map[district_key]
    else:
        for key, val in districts_map.items():
            if district_key in key or key in district_key:
                soil_type = val
                break

    if soil_type:
        defaults = DEFAULT_SOIL_VALUES.get(soil_type, DEFAULT_SOIL_FALLBACK)
        return SoilProfile(
            nitrogen=defaults["N"],
            phosphorus=defaults["P"],
            potassium=defaults["K"],
            ph=defaults["pH"],
            soil_type=soil_type,
            source="geo_mapping",
        )

    # 3. Priority 3: Fallback
    return SoilProfile(
        nitrogen=DEFAULT_SOIL_FALLBACK["N"],
        phosphorus=DEFAULT_SOIL_FALLBACK["P"],
        potassium=DEFAULT_SOIL_FALLBACK["K"],
        ph=DEFAULT_SOIL_FALLBACK["pH"],
        soil_type="Unknown",
        source="fallback",
    )


def get_soil_data(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    district: str = "Unknown",
) -> Dict[str, Any]:
    """
    Convenience wrapper function for recommendation engine.
    """
    prof = get_soil_profile(district)
    return {
        "N": prof.nitrogen,
        "P": prof.phosphorus,
        "K": prof.potassium,
        "pH": prof.ph,
        "soil_type": prof.soil_type,
        "source": prof.source,
    }
