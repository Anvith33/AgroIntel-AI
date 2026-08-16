"""
location_normalizer.py — Canonical Location Normalization Layer for AgroIntel.

Standardizes all state and district names across:
- Dropdown inputs
- AGMARKNET mandi records
- APY crop cultivation evidence
- Weather geocoding lookups
- News intelligence queries

Enforces:
- Canonical display name for renamed districts (e.g., Ahilya Nagar, Chhatrapati Sambhajinagar, Dharashiv, Prayagraj, Ayodhya, Mysuru, Ballari, Belagavi, Kalaburagi, Shivamogga, Vijayapura).
- Strict non-destructive alias matching (raw_name -> canonical_name -> canonical_id).
"""

import re
import unicodedata
from typing import Optional, Dict, Any, List

# Primary canonical district overrides and alias mappings
DISTRICT_CANONICAL_ALIASES: Dict[str, Dict[str, Any]] = {
    # Maharashtra
    "ahilya nagar": {
        "canonical_name": "Ahilya Nagar",
        "canonical_id": "Maharashtra::Ahilya Nagar",
        "state": "Maharashtra",
        "aliases": [
            "ahmednagar", "ahmed nagar", "ahmednagar district",
            "ahilyanagar", "ahilya nagar", "ahmadnagar", "ahmad nagar",
            "ahilyanagar district"
        ]
    },
    "chhatrapati sambhajinagar": {
        "canonical_name": "Chhatrapati Sambhajinagar",
        "canonical_id": "Maharashtra::Chhatrapati Sambhajinagar",
        "state": "Maharashtra",
        "aliases": [
            "aurangabad", "aurangabad district", "chhatrapati sambhaji nagar",
            "chhatrapati sambhajinagar", "sambhajinagar", "aurangabad (maharashtra)"
        ]
    },
    "dharashiv": {
        "canonical_name": "Dharashiv",
        "canonical_id": "Maharashtra::Dharashiv",
        "state": "Maharashtra",
        "aliases": [
            "osmanabad", "osmanabad district", "dharashiv", "dharashiv district"
        ]
    },
    # Karnataka
    "dakshina kannada": {
        "canonical_name": "Dakshina Kannada",
        "canonical_id": "Karnataka::Dakshina Kannada",
        "state": "Karnataka",
        "aliases": [
            "dakshina kannada", "dakshin kannad", "south kanara",
            "dakshina kannada (mangalore)", "mangalore district"
        ]
    },
    "uttara kannada": {
        "canonical_name": "Uttara Kannada",
        "canonical_id": "Karnataka::Uttara Kannada",
        "state": "Karnataka",
        "aliases": [
            "uttara kannada", "uttar kannad", "north kanara",
            "uttara kannada (karwar)", "karwar district"
        ]
    },
    "mysuru": {
        "canonical_name": "Mysuru",
        "canonical_id": "Karnataka::Mysuru",
        "state": "Karnataka",
        "aliases": ["mysore", "mysuru", "mysore district", "mysuru district"]
    },
    "ballari": {
        "canonical_name": "Ballari",
        "canonical_id": "Karnataka::Ballari",
        "state": "Karnataka",
        "aliases": ["bellary", "ballari", "bellary district", "ballari district"]
    },
    "belagavi": {
        "canonical_name": "Belagavi",
        "canonical_id": "Karnataka::Belagavi",
        "state": "Karnataka",
        "aliases": ["belgaum", "belagavi", "belgaum district", "belagavi district"]
    },
    "kalaburagi": {
        "canonical_name": "Kalaburagi",
        "canonical_id": "Karnataka::Kalaburagi",
        "state": "Karnataka",
        "aliases": ["gulbarga", "kalaburagi", "gulbarga district", "kalaburagi district"]
    },
    "shivamogga": {
        "canonical_name": "Shivamogga",
        "canonical_id": "Karnataka::Shivamogga",
        "state": "Karnataka",
        "aliases": ["shimoga", "shivamogga", "shimoga district", "shivamogga district"]
    },
    "vijayapura": {
        "canonical_name": "Vijayapura",
        "canonical_id": "Karnataka::Vijayapura",
        "state": "Karnataka",
        "aliases": ["bijapur", "vijayapura", "bijapur district", "vijayapura district"]
    },
    # Uttar Pradesh
    "prayagraj": {
        "canonical_name": "Prayagraj",
        "canonical_id": "Uttar Pradesh::Prayagraj",
        "state": "Uttar Pradesh",
        "aliases": ["allahabad", "prayagraj", "allahabad district", "prayagraj district"]
    },
    "ayodhya": {
        "canonical_name": "Ayodhya",
        "canonical_id": "Uttar Pradesh::Ayodhya",
        "state": "Uttar Pradesh",
        "aliases": ["faizabad", "ayodhya", "faizabad district", "ayodhya district"]
    },
    # West Bengal
    "purba bardhaman": {
        "canonical_name": "Purba Bardhaman",
        "canonical_id": "West Bengal::Purba Bardhaman",
        "state": "West Bengal",
        "aliases": ["burdwan", "bardhaman", "barddhaman", "purba bardhaman", "burdwan district"]
    }
}

# Fast alias-to-canonical lookup dictionary
_ALIAS_LOOKUP: Dict[str, Dict[str, Any]] = {}
for canon_key, entry in DISTRICT_CANONICAL_ALIASES.items():
    _ALIAS_LOOKUP[canon_key] = entry
    _ALIAS_LOOKUP[entry["canonical_name"].lower()] = entry
    _ALIAS_LOOKUP[entry["canonical_id"].lower()] = entry
    for alias in entry["aliases"]:
        _ALIAS_LOOKUP[alias.lower()] = entry
        _ALIAS_LOOKUP[f"{entry['state'].lower()}::{alias.lower()}"] = entry


def clean_text(text: str) -> str:
    """Normalize whitespace and strip non-ASCII accents."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text)).encode("ASCII", "ignore").decode("utf-8")
    return text.strip().lower()


def normalize_location(district_raw: str, state_raw: Optional[str] = None) -> Dict[str, str]:
    """
    Resolve any raw district string (and optional state) to its canonical display name and ID.

    Returns:
        {
            "raw_name": district_raw,
            "canonical_name": "Ahilya Nagar",
            "canonical_id": "Maharashtra::Ahilya Nagar",
            "state": "Maharashtra"
        }
    """
    if not district_raw:
        return {
            "raw_name": "",
            "canonical_name": "Unknown",
            "canonical_id": "Unknown::Unknown",
            "state": state_raw or "Unknown"
        }

    raw_clean = clean_text(district_raw)
    st_clean = clean_text(state_raw) if state_raw else ""

    # 1. Direct match in alias lookup
    if st_clean and f"{st_clean}::{raw_clean}" in _ALIAS_LOOKUP:
        match = _ALIAS_LOOKUP[f"{st_clean}::{raw_clean}"]
        return {
            "raw_name": district_raw,
            "canonical_name": match["canonical_name"],
            "canonical_id": match["canonical_id"],
            "state": match["state"]
        }

    if raw_clean in _ALIAS_LOOKUP:
        match = _ALIAS_LOOKUP[raw_clean]
        if not state_raw or clean_text(match["state"]) == st_clean:
            return {
                "raw_name": district_raw,
                "canonical_name": match["canonical_name"],
                "canonical_id": match["canonical_id"],
                "state": match["state"]
            }

    # 2. General title casing if not in special alias list
    canon_district = district_raw.strip().title()
    # Normalize common abbreviations
    canon_district = re.sub(r"\bDistrict\b", "", canon_district, flags=re.IGNORECASE).strip()
    canon_state = state_raw.strip().title() if state_raw else "India"

    return {
        "raw_name": district_raw,
        "canonical_name": canon_district,
        "canonical_id": f"{canon_state}::{canon_district}",
        "state": canon_state
    }
