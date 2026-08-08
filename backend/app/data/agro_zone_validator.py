"""
agro_zone_validator.py — Prevent Unrowable Crop Recommendations

Validates whether a crop can actually be grown in a given agro-climatic zone.
Based on ICAR Agro-Ecological Zones for India (20 zones) and satellite NDVI data.

This prevents the "traded but not grown" problem where mandi transaction data
includes imported commodities that can't be grown locally.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Indian Agro-Climatic Zone Classification ──────────────────────────────────
# Maps district/state identifiers to agro-climate zone.
# Source: ICAR National Academy of Agricultural Sciences (NAAS) zones.

AGRO_ZONE_MAP = {
    # ── Zone 1: Western Himalayan (J&K, Himachal) ──
    "jammu": "himalayan", "kashmir": "himalayan", "leh": "himalayan",
    "himachal": "himalayan", "shimla": "himalayan", "kullu": "himalayan",
    "lahaul": "himalayan", "spiti": "himalayan",

    # ── Zone 2: Eastern Himalayan (Uttarakhand, NE) ──
    "uttarakhand": "himalayan", "dehradun": "himalayan", "nainital": "himalayan",
    "arunachal": "himalayan", "sikkim": "himalayan", "darjeeling": "himalayan",

    # ── Zone 3: Lower Gangetic Plains (WB, Bihar east) ──
    "west bengal": "humid_subtropical", "kolkata": "humid_subtropical",
    "nadia": "humid_subtropical", "murshidabad": "humid_subtropical",
    "patna": "humid_subtropical", "bhagalpur": "humid_subtropical",

    # ── Zone 4: Middle Gangetic Plains (UP, Bihar west) ──
    "uttar pradesh": "sub_humid", "lucknow": "sub_humid",
    "kanpur": "sub_humid", "varanasi": "sub_humid", "agra": "sub_humid",
    "allahabad": "sub_humid", "prayagraj": "sub_humid", "bihar": "sub_humid",

    # ── Zone 5: Upper Gangetic Plains (Punjab, Haryana) ──
    "punjab": "sub_humid", "haryana": "sub_humid", "delhi": "sub_humid",
    "chandigarh": "sub_humid", "ludhiana": "sub_humid", "amritsar": "sub_humid",

    # ── Zone 6: Trans Gangetic Plains (Rajasthan north) ──
    "jaipur": "semi_arid", "jodhpur": "arid", "bikaner": "arid",
    "jaisalmer": "arid", "barmer": "arid", "nagpur": "semi_arid",

    # ── Zone 7: Eastern Plateau / Hill (MP, Chhattisgarh) ──
    "madhya pradesh": "semi_arid", "chhattisgarh": "semi_arid",
    "bhopal": "semi_arid", "indore": "semi_arid", "raipur": "semi_arid",

    # ── Zone 8: Central Plateau / Hills (Bundelkhand) ──
    "bundelkhand": "semi_arid", "gwalior": "semi_arid", "sagar": "semi_arid",

    # ── Zone 9: Western Plateau / Hills (Maharashtra inland) ──
    "maharashtra": "semi_arid", "pune": "semi_arid", "nashik": "semi_arid",
    "aurangabad": "semi_arid", "nagpur": "semi_arid", "solapur": "arid",

    # ── Zone 10: Southern Plateau / Hills (Karnataka, AP Deccan) ──
    "karnataka": "semi_arid", "bangalore": "semi_arid", "bengaluru": "semi_arid",
    "mysore": "semi_arid", "bijapur": "arid", "gulbarga": "arid",
    "bellary": "semi_arid", "andhra pradesh": "semi_arid",
    "hyderabad": "semi_arid", "telangana": "semi_arid",

    # ── Zone 11: East Coast Plains / Hills (Andhra coast) ──
    "visakhapatnam": "humid_tropical", "east godavari": "humid_tropical",
    "west godavari": "humid_tropical", "krishna": "humid_tropical",
    "guntur": "humid_tropical", "nellore": "humid_tropical",

    # ── Zone 12: West Coast Plains (Kerala, Coastal Karnataka, Goa) ──
    "kerala": "humid_tropical", "thiruvananthapuram": "humid_tropical",
    "kozhikode": "humid_tropical", "ernakulam": "humid_tropical",
    "goa": "humid_tropical", "udupi": "humid_tropical",
    "dakshina kannada": "humid_tropical", "north goa": "humid_tropical",

    # ── Zone 13: Gujarat Plains / Hills ──
    "gujarat": "semi_arid", "ahmedabad": "semi_arid", "surat": "semi_arid",
    "vadodara": "semi_arid", "rajkot": "arid", "kutch": "arid",

    # ── Zone 14: Western Dry Region (Rajasthan desert) ──
    "rajasthan": "arid",

    # ── Zone 15: Tamil Nadu (varied) ──
    "tamil nadu": "semi_arid", "chennai": "semi_arid", "coimbatore": "semi_arid",
    "madurai": "semi_arid", "thanjavur": "humid_tropical",
    "tiruchirapalli": "semi_arid",

    # ── Zone 16: Northeast Hills (Meghalaya, Manipur, etc.) ──
    "assam": "humid_subtropical", "meghalaya": "humid_subtropical",
    "manipur": "humid_subtropical", "mizoram": "humid_subtropical",
    "nagaland": "humid_subtropical", "tripura": "humid_subtropical",

    # ── Zone 17: Odisha / Jharkhand ──
    "odisha": "sub_humid", "jharkhand": "sub_humid",

    # ── Zone 18: Western Rajasthan (extreme arid) ──
    "jaisalmer": "arid", "barmer": "arid",
}

# ── Crop suitability per agro-climate zone ────────────────────────────────────
# Values: list of growable crop names (case-insensitive match)
ZONE_CROP_SUITABILITY = {
    "arid": {
        "allowed": [
            "bajra", "bajra (pearl millet)", "jowar", "millets", "millets (ragi/jowar)",
            "groundnut", "mustard", "castor", "guar", "moth bean", "cluster bean",
            "sesame", "sunflower", "cotton", "date palm",
        ],
        "blocked": [
            "rice", "sugarcane", "jute", "rubber", "tea", "coconut", "cardamom",
            "ginger", "banana", "arecanut", "black pepper", "tapioca", "betel leaf",
        ],
    },
    "semi_arid": {
        "allowed": [
            "cotton", "groundnut", "sorghum", "bajra", "maize", "soybean",
            "sunflower", "wheat", "jowar", "toor dal", "chickpea", "lentil",
            "mustard", "onion", "tomato", "millets (ragi/jowar)", "bajra (pearl millet)",
            "sugarcane",  # with irrigation
        ],
        "blocked": [
            "rubber", "tea", "jute", "coconut", "arecanut", "cardamom", "tapioca",
            "black pepper",
        ],
    },
    "sub_humid": {
        "allowed": [
            "wheat", "rice", "maize", "sugarcane", "potato", "mustard",
            "soybean", "lentil", "chickpea", "banana", "mango",
            "cotton", "onion", "garlic",
        ],
        "blocked": [
            "rubber", "tea", "cardamom", "coconut", "arecanut",
        ],
    },
    "humid_subtropical": {
        "allowed": [
            "rice", "jute", "tea", "sugarcane", "banana", "potato", "maize",
            "mustard", "lentil", "ginger", "turmeric",
        ],
        "blocked": [
            "rubber",  # Only in true tropical humid zones
            "coconut",  # Only coastal
        ],
    },
    "humid_tropical": {
        "allowed": [
            "rice", "coconut", "banana", "rubber", "arecanut", "black pepper",
            "cardamom", "ginger", "turmeric", "cashew", "tapioca (cassava)",
            "betel leaf", "sugarcane", "paddy (coastal/kharif)",
            "mango", "coffee", "tea",
        ],
        "blocked": [
            "wheat",  # Not suitable in true humid tropics
            "bajra (pearl millet)",
        ],
    },
    "himalayan": {
        "allowed": [
            "wheat", "potato", "apple", "barley", "buckwheat", "maize",
            "ginger", "cardamom", "tea",
        ],
        "blocked": [
            "cotton", "sugarcane", "rice",  # lowland crops
            "coconut", "rubber", "arecanut", "tapioca (cassava)",
            "bajra (pearl millet)", "jute",
        ],
    },
}

# ── NDVI-based crop filter ─────────────────────────────────────────────────────
WATER_INTENSIVE_CROPS = {
    "rice", "sugarcane", "banana", "jute", "coconut", "rubber",
    "tea", "paddy (coastal/kharif)", "ginger", "turmeric",
}

DROUGHT_TOLERANT_CROPS = {
    "bajra", "bajra (pearl millet)", "jowar", "millets (ragi/jowar)",
    "groundnut", "castor", "sorghum", "guar", "cotton", "mustard",
}


STATE_KEYS = {
    "jammu", "kashmir", "himachal", "uttarakhand", "west bengal", "uttar pradesh",
    "bihar", "punjab", "haryana", "delhi", "rajasthan", "madhya pradesh",
    "chhattisgarh", "maharashtra", "karnataka", "andhra pradesh", "telangana",
    "kerala", "goa", "gujarat", "tamil nadu", "assam", "meghalaya", "manipur",
    "mizoram", "nagaland", "tripura", "odisha", "jharkhand"
}


def _get_agro_zone(location: str) -> Optional[str]:
    """Resolve location string to agro-climate zone (districts prioritized over states)."""
    loc = location.lower().strip()
    # 1. District/city match (more specific)
    best_key = None
    best_len = 0
    for key, zone in AGRO_ZONE_MAP.items():
        if key not in STATE_KEYS and key in loc and len(key) > best_len:
            best_key = key
            best_len = len(key)
    if best_key:
        return AGRO_ZONE_MAP[best_key]

    # 2. State match
    for key, zone in AGRO_ZONE_MAP.items():
        if key in STATE_KEYS and key in loc and len(key) > best_len:
            best_key = key
            best_len = len(key)
    if best_key:
        return AGRO_ZONE_MAP[best_key]

    return None


def validate_crop_for_region(
    crop_name: str,
    location: str,
    ndvi: Optional[float] = None,
    soil_moisture: Optional[float] = None,
) -> dict:
    """
    Validate if a crop can actually be grown in the given location.

    Args:
        crop_name:      Name of the crop to validate
        location:       Location string (village, district, state)
        ndvi:           NDVI value (−1 to 1), optional
        soil_moisture:  Soil moisture estimate (0–1), optional

    Returns:
        {
            growable: bool,
            reason: str,
            agro_zone: str | None,
            confidence: str,   # 'high' | 'medium' | 'low'
        }
    """
    crop_lower   = crop_name.lower().strip()
    agro_zone    = _get_agro_zone(location)
    confidence   = "high" if agro_zone else "low"

    # ── Zone-based validation ─────────────────────────────────────────────────
    if agro_zone and agro_zone in ZONE_CROP_SUITABILITY:
        zone_data = ZONE_CROP_SUITABILITY[agro_zone]
        blocked   = [c.lower() for c in zone_data.get("blocked", [])]
        allowed   = [c.lower() for c in zone_data.get("allowed", [])]

        if crop_lower in blocked:
            return {
                "growable":  False,
                "reason":    f"❌ {crop_name} cannot be grown in {agro_zone.replace('_', ' ').title()} climate zones.",
                "agro_zone": agro_zone,
                "confidence": confidence,
            }

        if allowed and crop_lower not in allowed:
            # Soft block: crop not in explicit allowed list — flag it
            return {
                "growable":  False,
                "reason":    f"⚠️ {crop_name} is not typically cultivated in {agro_zone.replace('_', ' ').title()} climate. May be traded but not grown locally.",
                "agro_zone": agro_zone,
                "confidence": "medium",
            }

    # ── NDVI-based validation ─────────────────────────────────────────────────
    if ndvi is not None:
        if ndvi < 0.15 and crop_lower in WATER_INTENSIVE_CROPS:
            return {
                "growable":  False,
                "reason":    f"📡 Satellite data shows very dry conditions (NDVI={ndvi:.2f}). {crop_name} needs high water availability.",
                "agro_zone": agro_zone,
                "confidence": "high",
            }

    # ── Soil moisture validation ──────────────────────────────────────────────
    if soil_moisture is not None:
        if soil_moisture < 0.10 and crop_lower in WATER_INTENSIVE_CROPS:
            return {
                "growable":  False,
                "reason":    f"💧 Very low soil moisture detected. {crop_name} is water-intensive and unsuitable for current conditions.",
                "agro_zone": agro_zone,
                "confidence": "high",
            }

    # ── Default: pass ─────────────────────────────────────────────────────────
    return {
        "growable":  True,
        "reason":    f"✅ {crop_name} is suitable for this region's agro-climate conditions.",
        "agro_zone": agro_zone,
        "confidence": confidence,
    }


def filter_crops_for_region(
    crops: list,
    location: str,
    ndvi: Optional[float] = None,
    soil_moisture: Optional[float] = None,
    keep_min: int = 3,
) -> list:
    """
    Filter a list of crop dicts, removing truly unrowable crops.
    Always keeps at least `keep_min` crops even if validation fails.

    Args:
        crops: List of crop dicts with 'name' key
        location: Location string
        ndvi, soil_moisture: Satellite data (optional)
        keep_min: Minimum crops to always return

    Returns:
        List of crop dicts enriched with 'growable' and 'suitability_reason'
    """
    enriched = []
    for crop in crops:
        name = crop.get("name", "")
        validation = validate_crop_for_region(name, location, ndvi, soil_moisture)
        enriched.append({
            **crop,
            "growable":          validation["growable"],
            "suitability_reason": validation["reason"],
            "agro_zone":         validation.get("agro_zone"),
        })

    # Separate growable vs blocked
    growable = [c for c in enriched if c["growable"]]
    blocked  = [c for c in enriched if not c["growable"]]

    # Always keep at least keep_min crops
    if len(growable) < keep_min and blocked:
        # Add least-bad blocked crops to make up the minimum
        needed = keep_min - len(growable)
        for crop in blocked[:needed]:
            crop["growable"]          = None   # None = "uncertain" (not False)
            crop["suitability_reason"] = "⚠️ Climate match uncertain — local expert advice recommended."
        growable.extend(blocked[:needed])

    return growable
