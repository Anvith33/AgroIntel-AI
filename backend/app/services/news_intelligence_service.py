"""
news_intelligence_service.py — AgroIntel Tiered News Intelligence & Cross-Verification Pipeline
==================================================================================================
Key Principles:
  1. Source Credibility Tiers (Tier 1 Official = 1.0, Tier 2 Ag = 0.8, Tier 3 Market = 0.6, Tier 4 Media = 0.4, Discovery = 0.2)
  2. Dynamic Search Queries: Local/State for Crop Recommendation (State+District+Crop+Season); State+Crop for Price Prediction.
  3. Groq Fact Grounding: Strictly extract facts from source text. No ungrounded hallucinations.
  4. Cross-Source Verification: VERIFIED (2+ sources), SINGLE_SOURCE, CONFLICTING, UNVERIFIED, STALE.
  5. Bounded Risk Adjustment (-5.0 to +3.0 max): News CANNOT select crops or override hard agronomic rejections.
"""

import json
import logging
import os
import re
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
EXP_DIR = BASE_DIR / "app" / "data" / "experimental"

# ── Source Credibility Tiers ──────────────────────────────────────────────────

SOURCE_TIERS = {
    "TIER_1_OFFICIAL": {
        "label": "Official Government & Scientific Authorities",
        "credibility_weight": 1.0,
        "keywords": [
            "icar", "pib", "department of agriculture", "ministry of agriculture",
            "imd", "ministry of earth sciences", "kvk", "apmc", "state agriculture department",
            "state horticulture department", "disaster management authority", "agricultural university"
        ]
    },
    "TIER_2_AGRI_RESEARCH": {
        "label": "Agricultural Research & Dedicated Media",
        "credibility_weight": 0.8,
        "keywords": [
            "krishi jagran", "rural voice", "agrospectrum", "agriwatch",
            "krishak jagat", "agriculture world", "fao", "down to earth"
        ]
    },
    "TIER_3_BUSINESS_MARKET": {
        "label": "Business & Financial Media",
        "credibility_weight": 0.6,
        "keywords": [
            "reuters", "economic times", "business standard", "financial express",
            "businessline", "moneycontrol", "bloomberg"
        ]
    },
    "TIER_4_GENERAL_MEDIA": {
        "label": "General Media Publishers",
        "credibility_weight": 0.4,
        "keywords": [
            "the hindu", "indian express", "times of india", "hindustan times",
            "deccan herald", "tribune", "matrubhumi", "dinakaran", "lokmat"
        ]
    },
    "DISCOVERY_ONLY": {
        "label": "Search Aggregator / Discovery Only",
        "credibility_weight": 0.2,
        "keywords": ["google news", "news aggregator", "rss feed"]
    }
}


def classify_source_credibility(source_name: str, url: str = "") -> dict:
    """Classify an article's source into Credibility Tiers 1-4 or Discovery."""
    src_clean = (source_name or "").lower() + " " + (url or "").lower()

    for tier_key, tier_info in SOURCE_TIERS.items():
        if tier_key == "DISCOVERY_ONLY":
            continue
        for kw in tier_info["keywords"]:
            if kw in src_clean:
                return {
                    "tier": tier_key,
                    "label": tier_info["label"],
                    "credibility_weight": tier_info["credibility_weight"],
                    "is_official": tier_key == "TIER_1_OFFICIAL"
                }

    # Default if no match
    if "google" in src_clean or "feed" in src_clean:
        return {
            "tier": "DISCOVERY_ONLY",
            "label": SOURCE_TIERS["DISCOVERY_ONLY"]["label"],
            "credibility_weight": 0.2,
            "is_official": False
        }

    return {
        "tier": "TIER_4_GENERAL_MEDIA",
        "label": SOURCE_TIERS["TIER_4_GENERAL_MEDIA"]["label"],
        "credibility_weight": 0.4,
        "is_official": False
    }


def generate_local_search_queries(state: str, district: str, crop: str = None, season: str = None) -> List[str]:
    """Generate dynamic local and state-level agricultural search query terms."""
    queries = []
    st = state.strip() if state else ""
    dt = district.strip() if district else ""
    cr = crop.strip() if crop else ""

    if dt:
        queries.append(f"{dt} agriculture")
        queries.append(f"{dt} crop news")
        queries.append(f"{dt} rainfall flood drought")
        queries.append(f"{dt} pest disease advisory")
        if cr:
            queries.append(f"{dt} {cr}")

    if st:
        queries.append(f"{st} agriculture department")
        queries.append(f"{st} crop advisory")
        queries.append(f"{st} mandi market news")
        if cr:
            queries.append(f"{st} {cr} crop")

    return queries


def generate_price_search_queries(state: str, crop: str) -> List[str]:
    """Generate state and commodity search query terms for Price Prediction (NO district)."""
    cr = crop.strip() if crop else "crop"
    st = state.strip() if state else "India"

    return [
        f"{st} {cr} price news",
        f"{st} {cr} mandi rates",
        f"{st} {cr} market arrival",
        f"{cr} export import policy India",
        f"{cr} MSP weather risk {st}"
    ]


def verify_cross_source(events: List[dict]) -> str:
    """
    Determine cross-source verification status across multiple independent sources:
    - VERIFIED: 2+ independent sources reporting matching event/direction
    - SINGLE_SOURCE: 1 credible source
    - CONFLICTING: sources disagree on impact direction
    - UNVERIFIED: weak or unconfirmed source
    - STALE: article > 60 days old
    """
    if not events:
        return "NO_INTELLIGENCE"

    fresh_events = [e for e in events if e.get("freshness_status") != "STALE" and e.get("age_days", 0) <= 60]
    if not fresh_events:
        return "STALE"

    directions = set()
    sources = set()

    for e in fresh_events:
        src = e.get("source_name") or e.get("source_id") or "unknown"
        sources.add(src)
        dir_val = e.get("impact_direction") or e.get("risk_signal") or "NEUTRAL"
        if dir_val != "NEUTRAL":
            directions.add(dir_val)

    if len(directions) > 1 and ("RISK_INCREASED" in directions or "POSITIVE" in directions) and ("NEGATIVE" in directions or "RISK_DECREASED" in directions):
        return "CONFLICTING"

    if len(sources) >= 2:
        return "VERIFIED"
    elif len(sources) == 1:
        top_tier = fresh_events[0].get("source_credibility", {}).get("tier", "")
        if top_tier in ["TIER_1_OFFICIAL", "TIER_2_AGRI_RESEARCH"]:
            return "SINGLE_SOURCE"
        return "UNVERIFIED"

    return "UNVERIFIED"


def calculate_bounded_news_adjustment(events: List[dict]) -> tuple[float, str, str]:
    """
    Calculate bounded news risk score adjustment for crop recommendation:
    - Range: STRICTLY bounded between -5.0 and +3.0
    - UNVERIFIED / CONFLICTING / STALE news = 0.0 adjustment
    """
    if not events:
        return 0.0, "NO_SIGNIFICANT_SIGNAL", "NO_INTELLIGENCE"

    verification_status = verify_cross_source(events)

    if verification_status in ["UNVERIFIED", "STALE", "CONFLICTING", "NO_INTELLIGENCE"]:
        return 0.0, "NEUTRAL_SIGNAL", verification_status

    # Filter to fresh, credible events
    fresh_events = [e for e in events if e.get("age_days", 0) <= 60]
    if not fresh_events:
        return 0.0, "NEUTRAL_SIGNAL", "STALE"

    top_event = fresh_events[0]
    cred_weight = top_event.get("source_credibility", {}).get("credibility_weight", 0.5)
    sig = top_event.get("recommendation_risk_signal") or top_event.get("impact_direction", "NEUTRAL")

    adjustment = 0.0
    if sig in ["RISK_INCREASED", "HIGH_RISK", "NEGATIVE"]:
        adjustment = round(-3.0 * cred_weight - 2.0 * (1.0 if verification_status == "VERIFIED" else 0.5), 1)
        adjustment = max(-5.0, adjustment)
    elif sig in ["RISK_ELEVATED", "MODERATE_RISK"]:
        adjustment = round(-2.0 * cred_weight, 1)
        adjustment = max(-3.0, adjustment)
    elif sig in ["RISK_DECREASED", "POSITIVE", "FAVORABLE"]:
        adjustment = round(+2.0 * cred_weight + (1.0 if verification_status == "VERIFIED" else 0.0), 1)
        adjustment = min(+3.0, adjustment)

    return adjustment, sig, verification_status
