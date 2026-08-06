"""
region_service.py — District and state crop lookup service.

Loads region_crop_mapping.json and provides:
  - Top 10 historically grown crops for a given district
  - District soil type and state information
  - State-level fallback if district not found

Data structure of region_crop_mapping.json:
  {
    "states": { "Karnataka": { "top_crops": [...], ... }, ... },
    "districts": { "Mysore": { "top_crops": [...], ... }, ... }
  }

IMPORTANT DESIGN CONSTRAINT:
  - Only crops in the district Top-10 list are valid candidates for
    crop recommendation. The Random Forest ONLY ranks these crops.
  - Never recommend crops outside this list.
"""

import json
import logging
from typing import Dict, List, Optional, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAPPING_PATH = settings.DATA_DIR / "region_crop_mapping.json"
_region_data: Optional[dict] = None


def _load_region_map() -> dict:
    """Load and cache region_crop_mapping.json. Logs absolute path on first load."""
    global _region_data
    if _region_data is None:
        try:
            import os
            abs_path = _MAPPING_PATH.resolve()
            mtime = os.path.getmtime(_MAPPING_PATH)
            import datetime
            mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

            with open(_MAPPING_PATH, "r") as f:
                _region_data = json.load(f)

            total_districts = len(_region_data.get('districts', {}))
            udupi_crops = _region_data.get('districts', {}).get('Udupi', {}).get('top_crops', [])

            # ── STARTUP AUDIT LOG — always visible ──────────────────────────
            logger.warning(
                f"[REGION_MAP LOADED] "
                f"path={abs_path} | "
                f"mtime={mtime_str} | "
                f"districts={total_districts} | "
                f"states={len(_region_data.get('states', {}))}"
            )
            logger.warning(
                f"[REGION_MAP AUDIT] Udupi top_crops={udupi_crops}"
            )
            # ────────────────────────────────────────────────────────────────

        except Exception as e:
            logger.error(f"Failed to load region_crop_mapping.json: {e}")
            _region_data = {"states": {}, "districts": {}}
    return _region_data


def _normalize(name: str) -> str:
    """Lowercase and strip for case-insensitive comparison."""
    return name.strip().lower()


def get_district_info(state: Optional[str], district: str) -> Optional[Dict[str, Any]]:
    """
    Return full district info dict including top_crops and soil_type.

    Args:
        state: State name (optional).
        district: District name (case-insensitive).

    Returns:
        Dict with keys: top_crops, soil_type, state (or None if not found).
    """
    data = _load_region_map()
    dist_key = _normalize(district)
    districts_map: dict = data.get("districts", {})

    # 1. Exact match
    for dname, dinfo in districts_map.items():
        if _normalize(dname) == dist_key:
            return {
                "district_name": dname,
                "top_crops": dinfo.get("top_crops", []),
                "soil_type": dinfo.get("soil_type", "Alluvial Soil"),
                "state": dinfo.get("state", state or "Unknown"),
            }

    # 2. Partial match
    for dname, dinfo in districts_map.items():
        d_norm = _normalize(dname)
        if dist_key in d_norm or d_norm in dist_key:
            return {
                "district_name": dname,
                "top_crops": dinfo.get("top_crops", []),
                "soil_type": dinfo.get("soil_type", "Alluvial Soil"),
                "state": dinfo.get("state", state or "Unknown"),
            }

    # 3. State-level fallback
    if state:
        state_key = _normalize(state)
        states_map: dict = data.get("states", {})
        for sname, sinfo in states_map.items():
            if _normalize(sname) == state_key or state_key in _normalize(sname):
                return {
                    "district_name": district,
                    "top_crops": sinfo.get("top_crops", []),
                    "soil_type": "Alluvial Soil",
                    "state": sname,
                }

    return None


def list_districts_in_state(state: str) -> List[str]:
    """Return list of supported district names for a given state."""
    data = _load_region_map()
    state_key = _normalize(state)
    districts_map: dict = data.get("districts", {})
    
    matches = []
    for dname, dinfo in districts_map.items():
        if dinfo.get("state") and _normalize(dinfo.get("state")) == state_key:
            matches.append(dname)

    if not matches:
        matches = list(districts_map.keys())[:15]
    return matches


def get_top_crops(district: str, state: Optional[str] = None, top_n: int = 10) -> list[str]:
    """Return the top N historically grown crops for a district."""
    info = get_district_info(state, district)
    if info:
        return info.get("top_crops", [])[:top_n]
    return []


def get_state_crops(state: str, top_n: int = 10) -> list[str]:
    """Return top N crops for a state (used as fallback)."""
    data = _load_region_map()
    state_key = _normalize(state)
    for sname, sinfo in data.get("states", {}).items():
        if _normalize(sname) == state_key or state_key in _normalize(sname):
            return sinfo.get("top_crops", [])[:top_n]
    return []
