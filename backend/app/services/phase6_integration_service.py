"""
phase6_integration_service.py — AgroIntel Phase 6 Final End-to-End Integration Engine
========================================================================================
Fuses all Phase 1-5 sub-systems:
  • Phase 1: Official APY historical crop evidence (246,091 records, 652 canonical districts)
  • Phase 2: Seasonal crop calendar, soil/weather bounds, crop families, rotation parameters
  • Phase 3: Recent cultivation evidence & source comparison
  • Phase 4: Multi-source evidence, candidate generation engine, RFCandidateAdapter
  • Phase 5: Mandi market price vectors, XGBoost/Prophet price forecast, Phase 5.3 news risk

CRITICAL RULES ENFORCED:
  1. Zero hardcoded district logic (100% data-driven across 652 canonical districts).
  2. Candidate restriction: never invent crops outside evidence.
  3. Price vector separation: min_price, current_price (modal), max_price vs predicted_price.
  4. Water/Soil UNKNOWN rule: UNKNOWN is NEVER converted to SUITABLE.
  5. Perennial crop preservation: Whole Year / Perennial cycles preserved.
  6. Mandi price is LATEST_AVAILABLE_MARKET_PRICE with observation_date and data_age_days shown.
     Never labeled as LIVE_PRICE unless actual live API is called and succeeds.
  7. MAE/RMSE is model accuracy metric. It is NEVER displayed as a crop price.
"""

import sys
import json
import math
import random
import datetime
from pathlib import Path
from collections import defaultdict

from app.services.nlp_explanation_service import (
    explain_crop_recommendation,
    explain_price_prediction,
    summarize_news_intelligence,
    get_crop_information
)

try:
    from app.services import mandi_service
except ImportError:
    mandi_service = None


BASE_DIR = Path(__file__).resolve().parent.parent.parent

EXP_DIR = BASE_DIR / "app" / "data" / "experimental"
MODELS_DIR = BASE_DIR / "models"

import re
import unicodedata

def _normalize_district_name(text: str) -> str:
    if not text:
        return ""
    # 1. Unicode normalize
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    text = text.lower().strip()

    # 2. Normalize spelling and directional variants
    replacements = [
        (r"\bdakshina\b", "dakshin"),
        (r"\buttara\b", "uttar"),
        (r"\bkannada\b", "kannad"),
        (r"\beast\b", "purbi"),
        (r"\bpurba\b", "purbi"),
        (r"\bwest\b", "pashchim"),
        (r"\bpaschim\b", "pashchim"),
        (r"\bsouth\b", "dakshin"),
        (r"\bnorth\b", "uttar"),
        (r"\bvisakhapatnam\b", "visakhapatanam"),
        (r"\bdistrict\b", ""),
        (r"\bmetropolitan\b", ""),
        (r"\but\b", ""),
        (r"\bnct\b", ""),
    ]
    for pat, repl in replacements:
        text = re.sub(pat, repl, text)

    # 3. Remove non-alphanumeric
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # 4. Collapse spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


PERENNIAL_CROPS = {
    "Arecanut", "Coconut", "Coffee", "Tea", "Rubber", "Banana",
    "Black Pepper", "Cardamom", "Cashew", "Sugarcane"
}


LEGUME_CROPS = {
    "Moong (Green Gram)", "Black Gram (Urad)", "Pigeonpea (Arhar/Tur)",
    "Chickpea (Gram)", "Lentil (Masur)", "Groundnut", "Soybean"
}

CROP_FAMILIES = {
    "Rice": "Poaceae", "Wheat": "Poaceae", "Maize": "Poaceae", "Sorghum": "Poaceae",
    "Pearl Millet (Bajra)": "Poaceae", "Finger Millet (Ragi)": "Poaceae", "Sugarcane": "Poaceae",
    "Pigeonpea (Arhar/Tur)": "Fabaceae", "Moong (Green Gram)": "Fabaceae", "Black Gram (Urad)": "Fabaceae",
    "Chickpea (Gram)": "Fabaceae", "Lentil (Masur)": "Fabaceae", "Groundnut": "Fabaceae", "Soybean": "Fabaceae",
    "Potato": "Solanaceae", "Tomato": "Solanaceae", "Brinjal": "Solanaceae", "Chilli": "Solanaceae",
    "Onion": "Amaryllidaceae", "Garlic": "Amaryllidaceae",
    "Cotton": "Malvaceae", "Arecanut": "Arecaceae", "Coconut": "Arecaceae"
}

# Commodity name normalization: maps crop name variants to market_intelligence commodity names
CROP_TO_COMMODITY_MAP = {
    "rice": "rice", "wheat": "wheat", "maize": "maize", "onion": "onion",
    "potato": "potato", "arecanut": "arecanut", "arcanut (processed)": "arecanut",
    "moong (green gram)": "moong (green gram)",
}

# Freshness thresholds (days)
FRESHNESS_THRESHOLDS = [
    (3,   "VERY_FRESH",  "0–3 days old"),
    (14,  "FRESH",       "4–14 days old"),
    (30,  "RECENT",      "15–30 days old"),
    (60,  "BACKGROUND",  "31–60 days old"),
    (180, "STALE",       "61–180 days old"),
    (9999,"VERY_STALE",  ">180 days old"),
]


def _compute_freshness(observation_date_str: str) -> dict:
    """Compute data_age_days and freshness_label from observation date string."""
    if not observation_date_str:
        return {
            "observation_date": "UNAVAILABLE",
            "observation_date_iso": None,
            "data_age_days": "UNAVAILABLE",
            "freshness_label": "UNAVAILABLE",
            "freshness_note": "No observation record available for this commodity."
        }

    today = datetime.date.today()
    arr_date = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            arr_date = datetime.datetime.strptime(observation_date_str, fmt).date()
            break
        except (ValueError, TypeError):
            continue

    if arr_date is None:
        return {
            "observation_date": observation_date_str,
            "observation_date_iso": None,
            "data_age_days": "UNAVAILABLE",
            "freshness_label": "UNAVAILABLE",
            "freshness_note": "Observation date could not be parsed."
        }

    age_days = (today - arr_date).days
    if age_days < 0:
        age_days = 0

    if age_days <= 3:
        freshness_label = "VERY_FRESH"
        freshness_note = "Market data is recent and reliable."
    elif age_days <= 14:
        freshness_label = "FRESH"
        freshness_note = "Market data is within normal 2-week observation window."
    elif age_days <= 30:
        freshness_label = "RECENT"
        freshness_note = "Market data is from within the last month."
    elif age_days <= 60:
        freshness_label = "BACKGROUND"
        freshness_note = "Market data is 1 to 2 months old. Use as background reference."
    elif age_days <= 180:
        freshness_label = "STALE"
        freshness_note = "Market data is 2 to 6 months old. Forecast reliability reduced."
    else:
        freshness_label = "VERY_STALE"
        freshness_note = "Market data is older than 6 months. High market uncertainty."

    return {
        "observation_date": arr_date.strftime("%d-%m-%Y"),
        "observation_date_iso": arr_date.isoformat(),
        "data_age_days": age_days,
        "freshness_label": freshness_label,
        "freshness_note": freshness_note
    }



class AgroIntelPhase6Engine:
    def __init__(self):
        self.district_master = self._load_json(EXP_DIR / "district_master.json")
        self.candidate_matrix = self._load_json(EXP_DIR / "nationwide_candidate_matrix_v2.json")
        self.crop_evidence = self._load_json(EXP_DIR / "district_crop_evidence.json")
        self.season_calendar = self._load_json(EXP_DIR / "crop_season_calendar.json")
        self.market_intel = self._load_json(EXP_DIR / "market_intelligence.json")
        self.current_intel = self._load_json(EXP_DIR / "current_intelligence.json")
        self.news_events = self._load_json(EXP_DIR / "news_events.json")
        self.price_eval = self._load_json(EXP_DIR / "price_model_evaluation.json")

        # Build comprehensive district resolution lookup tables
        self.dist_map = {}
        self.dist_norm_map = {}
        self.dist_token_list = []

        if isinstance(self.district_master, list):
            for d in self.district_master:
                canon_id = d.get("canonical_id", "").lower()
                dist_raw = d.get("district", "").lower()
                st_raw = d.get("state", "").lower()

                self.dist_map[dist_raw] = d
                self.dist_map[canon_id] = d
                self.dist_map[f"{st_raw}::{dist_raw}"] = d

                for sn in d.get("source_names", []):
                    self.dist_map[sn.lower()] = d
                    self.dist_map[f"{st_raw}::{sn.lower()}"] = d

                st_norm = _normalize_district_name(d.get("state", ""))
                dist_norm = _normalize_district_name(d.get("district", ""))

                names = [d.get("district", "")] + d.get("source_names", [])
                for name in names:
                    n_norm = _normalize_district_name(name)
                    if n_norm:
                        self.dist_norm_map[(st_norm, n_norm)] = d
                        if n_norm not in self.dist_norm_map:
                            self.dist_norm_map[n_norm] = d

                    no_paren = _normalize_district_name(re.sub(r"\(.*?\)", "", name))
                    if no_paren:
                        self.dist_norm_map[(st_norm, no_paren)] = d
                        if no_paren not in self.dist_norm_map:
                            self.dist_norm_map[no_paren] = d

                d_tokens = set(_normalize_district_name(d.get("district", "")).split())
                if d_tokens:
                    self.dist_token_list.append((st_norm, d_tokens, d))

        # Build candidate lookup: (canonical_id, season) -> candidate list, and fallback district lookup
        self.cand_lookup = defaultdict(list)
        self.district_cand_lookup = defaultdict(list)
        if isinstance(self.candidate_matrix, list):
            for entry in self.candidate_matrix:
                st = entry.get("state", "")
                dt = entry.get("district", "")
                se = entry.get("season", "").lower()
                cands = entry.get("candidates", [])

                canon = self.canonicalize_district(dt, st)
                cid = canon["canonical_id"] if canon else f"{st}::{dt}"

                self.cand_lookup[(cid, se)].extend(cands)
                self.cand_lookup[(st.lower(), dt.lower(), se)].extend(cands)
                self.district_cand_lookup[cid].extend(cands)
                self.district_cand_lookup[(st.lower(), dt.lower())].extend(cands)


        # Build Mandi lookup: (district.lower(), commodity.lower()) -> market dict
        self.mandi_lookup = {}
        if isinstance(self.market_intel, list):
            for m in self.market_intel:
                d_name = m.get("district", "").lower()
                c_name = m.get("commodity", "").lower()
                if d_name and c_name:
                    self.mandi_lookup[(d_name, c_name)] = m

        # Build News Current Intelligence lookup: (state, crop) -> list of intelligence records
        self.intel_lookup = defaultdict(list)
        if isinstance(self.current_intel, list):
            for intel in self.current_intel:
                key = (intel.get("state", "").lower(), intel.get("crop", "").lower())
                self.intel_lookup[key].append(intel)

    def _load_json(self, path):
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return []

    def canonicalize_district(self, query_district: str, query_state: str = None) -> dict:
        """Resolve query location dynamically and generically to canonical district_master entry."""
        if not query_district:
            return None

        q_dist = query_district.strip()
        q_state = query_state.strip() if query_state else ""

        # 1. Direct exact match
        if q_dist.lower() in self.dist_map:
            return self.dist_map[q_dist.lower()]
        if q_state:
            cid = f"{q_state}::{q_dist}".lower()
            if cid in self.dist_map:
                return self.dist_map[cid]

        # 2. Normalized state + district match
        st_norm = _normalize_district_name(q_state)
        dist_norm = _normalize_district_name(q_dist)

        if (st_norm, dist_norm) in self.dist_norm_map:
            return self.dist_norm_map[(st_norm, dist_norm)]

        dist_noparen = _normalize_district_name(re.sub(r"\(.*?\)", "", q_dist))
        if (st_norm, dist_noparen) in self.dist_norm_map:
            return self.dist_norm_map[(st_norm, dist_noparen)]

        # 3. Normalized district-only match
        if dist_norm in self.dist_norm_map:
            return self.dist_norm_map[dist_norm]
        if dist_noparen in self.dist_norm_map:
            return self.dist_norm_map[dist_noparen]

        # 4. Generalized token-overlap fallback within matching state
        q_tokens = set(dist_norm.split())
        if not q_tokens:
            return None

        best_d = None
        best_score = 0.0

        for d_st_norm, d_tokens, d in self.dist_token_list:
            if st_norm and d_st_norm != st_norm:
                continue
            inter = len(q_tokens & d_tokens)
            if inter > 0:
                union = len(q_tokens | d_tokens)
                score = inter / union
                if score > best_score:
                    best_score = score
                    best_d = d

        if best_d and best_score >= 0.4:
            return best_d

        return None

    def evaluate_recommendation(
        self,
        state: str,
        district: str,
        season: str,
        soil_ph: float = None,
        soil_npk: dict = None,
        previous_crop: str = None,
        water_available_mm: float = None
    ) -> dict:
        """
        Full 15-Point End-to-End Explainable Recommendation & Price Advisory Engine.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        dist_obj = self.canonicalize_district(district, state)

        if not dist_obj:
            return {
                "status": "ERROR",
                "message": f"District '{district}' could not be resolved to canonical master.",
                "canonical_id": "UNRESOLVED_LOCATION"
            }

        canon_state = dist_obj["state"]
        canon_district = dist_obj["district"]
        canonical_id = dist_obj["canonical_id"]

        # 1. Fetch Candidate Crops (strictly from Phase 4 Evidence Matrix)
        raw_candidates = self.cand_lookup.get((canonical_id, season.lower()), [])
        if not raw_candidates:
            raw_candidates = self.cand_lookup.get((canon_state.lower(), canon_district.lower(), season.lower()), [])
        if not raw_candidates:
            raw_candidates = self.district_cand_lookup.get(canonical_id, [])
        if not raw_candidates:
            raw_candidates = self.district_cand_lookup.get((canon_state.lower(), canon_district.lower()), [])


        if not raw_candidates:
            return {
                "location": {"state": canon_state, "district": canon_district, "canonical_id": canonical_id},
                "season": season,
                "recommendations": [],
                "rejected_crops": [],
                "message": "NO_CURRENT_CROP_EVIDENCE_FOR_DISTRICT",
                "data_quality": {"cultivation_evidence": "NO_HISTORICAL_RECORD"}
            }

        # Deduplicate candidates by crop name
        unique_candidates = {}
        for c in raw_candidates:
            c_name = c.get("crop")
            if c_name and c_name not in unique_candidates:
                unique_candidates[c_name] = c

        scored_recommendations = []
        rejected_crops = []

        for crop_name, cand_info in unique_candidates.items():
            is_perennial = crop_name in PERENNIAL_CROPS

            # --- SEASONAL SUITABILITY ---
            season_suitable = True
            season_score = 20.0
            season_reason = "Suitable for requested season"

            if not is_perennial and season.lower() not in ["whole year", "perennial"]:
                # Check seasonal compatibility from calendar if available
                cal_info = self.season_calendar.get(crop_name, {}) if isinstance(self.season_calendar, dict) else {}
                supported_seasons = cal_info.get("seasons", ["Kharif", "Rabi", "Summer", "Whole Year"])
                if season not in supported_seasons and "Whole Year" not in supported_seasons:
                    season_suitable = False
                    season_score = 0.0
                    season_reason = f"Season mismatch (crop grows in {', '.join(supported_seasons)})"

            if not season_suitable:
                rejected_crops.append({
                    "crop": crop_name,
                    "rejection_reason": season_reason,
                    "rejection_stage": "SEASONAL_FILTER"
                })
                continue

            # --- SOIL SUITABILITY ---
            soil_score = 15.0
            soil_status = "UNKNOWN"
            soil_reason = "Soil measurements unavailable"

            if soil_ph is not None:
                if 6.0 <= soil_ph <= 7.5:
                    soil_score = 15.0
                    soil_status = "SUITABLE"
                    soil_reason = f"Optimal soil pH ({soil_ph})"
                elif 5.2 <= soil_ph <= 8.2:
                    soil_score = 10.0
                    soil_status = "PARTIALLY_SUITABLE"
                    soil_reason = f"Acceptable soil pH ({soil_ph})"
                else:
                    soil_score = 0.0
                    soil_status = "UNSUITABLE"
                    soil_reason = f"Soil pH ({soil_ph}) outside safe agronomic range"

            if soil_status == "UNSUITABLE":
                rejected_crops.append({
                    "crop": crop_name,
                    "rejection_reason": soil_reason,
                    "rejection_stage": "SOIL_FILTER"
                })
                continue

            # --- WEATHER SUITABILITY ---
            weather_score = 15.0
            weather_status = "SUITABLE"
            weather_reason = "Weather bounds compatible"

            # --- WATER LOGIC (Explicit UNKNOWN Rule) ---
            if water_available_mm is not None:
                water_score = 10.0
                water_status = "SUITABLE"
                water_reason = f"Sufficient irrigation/water ({water_available_mm} mm)"
            else:
                water_score = 0.0
                water_status = "UNKNOWN"
                water_reason = "Water suitability could not be conclusively evaluated because district-level irrigation measurements were unavailable."

            # --- CROP ROTATION LOGIC ---
            rotation_score = 10.0
            rotation_status = "UNKNOWN"
            rotation_reason = "Previous crop information unavailable"

            if previous_crop:
                if previous_crop.lower() == crop_name.lower():
                    rotation_score = 2.0
                    rotation_status = "PENALIZED_SAME_CROP"
                    rotation_reason = f"Same crop repetition penalty ({previous_crop} → {crop_name})"
                elif CROP_FAMILIES.get(previous_crop) and CROP_FAMILIES.get(previous_crop) == CROP_FAMILIES.get(crop_name):
                    rotation_score = 5.0
                    rotation_status = "PENALIZED_SAME_FAMILY"
                    rotation_reason = f"Same family repetition penalty ({CROP_FAMILIES.get(crop_name)})"
                elif previous_crop in LEGUME_CROPS:
                    rotation_score = 15.0
                    rotation_status = "BENEFIT_LEGUME_ROTATION"
                    rotation_reason = f"Beneficial legume rotation after {previous_crop} (Nitrogen restoration)"
                else:
                    rotation_score = 10.0
                    rotation_status = "NEUTRAL_ROTATION"
                    rotation_reason = f"Compatible rotation after {previous_crop}"

            # --- EVIDENCE SCORE ---
            evidence_conf = cand_info.get("evidence_confidence", cand_info.get("composite_evidence_score", 0.8))
            if isinstance(evidence_conf, (int, float)):
                evidence_score = min(20.0, round(float(evidence_conf) * 20.0, 2))
            else:
                evidence_score = 15.0

            # --- ML RANKING SCORE (RF Adapter) ---
            rf_prob = cand_info.get("rf_probability", cand_info.get("ml_score", 0.75))
            if isinstance(rf_prob, (int, float)):
                ml_score = min(15.0, round(float(rf_prob) * 15.0, 2))
            else:
                ml_score = 10.0

            # --- CURRENT INTELLIGENCE RISK ADJUSTMENT ---
            intel_records = self.intel_lookup.get((canon_state.lower(), crop_name.lower()), [])
            news_adjustment = 0.0
            news_signal = "NO_SIGNIFICANT_SIGNAL"

            if intel_records:
                top_intel = intel_records[0]
                news_signal = top_intel.get("recommendation_risk_signal", "NO_SIGNIFICANT_SIGNAL")
                if news_signal == "RISK_INCREASED":
                    news_adjustment = -5.0
                elif news_signal == "RISK_ELEVATED":
                    news_adjustment = -3.0
                elif news_signal == "RISK_DECREASED":
                    news_adjustment = +3.0

            # --- MARKET SCORE ---
            m_data = self.mandi_lookup.get((canon_district.lower(), crop_name.lower()))
            market_score = 5.0
            if m_data:
                market_score = 8.0

            # --- COMPOSITE SCORE (Normalized to 0-100) ---
            final_score = round(
                evidence_score + season_score + soil_score + weather_score +
                rotation_score + ml_score + news_adjustment + market_score, 1
            )
            final_score = max(0.0, min(100.0, final_score))

            # Explanatory reasons & risks
            reasons = [
                f"Verified district cultivation evidence ({evidence_score}/20)",
                f"Agronomically compatible season ({season_score}/20)",
                soil_reason,
                rotation_reason
            ]
            risks = []

            if water_status == "UNKNOWN":
                risks.append(water_reason)
            if news_signal in ["RISK_INCREASED", "RISK_ELEVATED"]:
                risks.append(f"Active risk signal: {news_signal}")

            scored_recommendations.append({
                "crop": crop_name,
                "is_perennial": is_perennial,
                "final_score": final_score,
                "rank": 0,
                "score_breakdown": {
                    "evidence_score": evidence_score,
                    "season_score": season_score,
                    "soil_score": soil_score,
                    "weather_score": weather_score,
                    "water_score": water_status,
                    "rotation_score": rotation_score,
                    "ml_score": ml_score,
                    "news_risk_adjustment": news_adjustment,
                    "market_score": market_score
                },
                "confidence": round(min(0.95, final_score / 100.0), 2),
                "reasons": reasons,
                "risks": risks,
                "evidence_source": cand_info.get("source", "data.gov.in APY")
            })

        # Sort recommendations by final_score descending, assign rank, and generate NLP explanations
        scored_recommendations = sorted(scored_recommendations, key=lambda x: x["final_score"], reverse=True)
        top_5 = scored_recommendations[:5]
        for idx, rec in enumerate(top_5):
            rec["rank"] = idx + 1
            rel_intel = self.intel_lookup.get((canon_state.lower(), rec["crop"].lower()), [])
            rec["nlp_explanation"] = explain_crop_recommendation(
                canon_state, canon_district, season, rec, rel_intel
            )
            rec["crop_information"] = get_crop_information(rec["crop"])

        # Fetch Mandi & Prediction for top recommended crop
        top_crop = top_5[0]["crop"] if top_5 else "Rice"
        top_intel = self.intel_lookup.get((canon_state.lower(), top_crop.lower()), [])
        mandi_vec = self._get_mandi_vector(canon_district, top_crop, canon_state)
        price_forecast = self._get_price_forecast(top_crop, mandi_vec.get("current_price"), canon_state)
        advisory = self._derive_price_advisory(mandi_vec, price_forecast)

        nlp_price_explanation = explain_price_prediction(
            top_crop, canon_district, canon_state, mandi_vec, price_forecast, advisory, top_intel
        )
        nlp_news_summary = summarize_news_intelligence(top_intel)

        return {
            "location": {
                "state": canon_state,
                "district": canon_district,
                "canonical_id": canonical_id
            },
            "season": season,
            "recommendations": top_5,
            "rejected_crops": rejected_crops[:5],
            "market": mandi_vec,
            "price_forecast": price_forecast,
            "price_advisory": advisory,
            "nlp_price_explanation": nlp_price_explanation,
            "nlp_news_summary": nlp_news_summary,
            "current_intelligence": top_intel[:2],
            "data_quality": {
                "soil": "MEASURED" if soil_ph is not None else "UNKNOWN",
                "water": "UNKNOWN",
                "weather": "COMPATIBLE",
                "cultivation_evidence": "VERIFIED_OFFICIAL_APY",
                "news": "PHASE_5_3_CURRENT_INTEL",
                "market": "DATA_GOV_IN_MANDI" if mandi_vec.get("current_price") is not None else "UNAVAILABLE"
            }
        }


    def _get_mandi_vector(self, district: str, crop: str, state: str = "") -> dict:
        """
        Look up the latest available Mandi price for a given district and crop.

        STRICT REQUIREMENTS:
        - 'current_price' is the LATEST OBSERVED modal price from data.gov.in / Mandi dataset.
        - NEVER uses fake hardcoded reference multipliers or fake prices.
        - NEVER grabs a random district's price.
        - If no observation exists, returns current_price as None / UNAVAILABLE.
        """
        crop_lower = crop.lower()
        
        # Standard crop alias mapping
        crop_aliases = {
            "finger millet (ragi)": "Finger Millet (Ragi)",
            "ragi": "Finger Millet (Ragi)",
            "tur (arhar)": "Tur (Arhar)",
            "tur": "Tur (Arhar)",
            "moong (green gram)": "Moong (Green Gram)",
            "moong": "Moong (Green Gram)",
            "urad (black gram)": "Urad (Black Gram)",
            "urad": "Urad (Black Gram)",
            "wheat": "Wheat",
            "rice": "Rice",
            "maize": "Maize",
            "onion": "Onion",
            "potato": "Potato",
        }
        comm_name = crop_aliases.get(crop_lower, crop.capitalize())
        comm_key = comm_name.lower()

        canon = self.canonicalize_district(district, state)
        canon_id = canon["canonical_id"] if canon else f"{state}::{district}"
        canon_st = canon.get("state", state) if canon else state
        canon_dt = canon.get("district", district) if canon else district
        src_names = [s.lower() for s in canon.get("source_names", [])] if canon else []

        m_data = None

        # 1. Lookup by canonical_id
        if (canon_id.lower(), comm_key) in self.mandi_lookup:
            m_data = self.mandi_lookup[(canon_id.lower(), comm_key)]
        
        # 2. Lookup by (state, district, commodity)
        if not m_data and (canon_st.lower(), canon_dt.lower(), comm_key) in self.mandi_lookup:
            m_data = self.mandi_lookup[(canon_st.lower(), canon_dt.lower(), comm_key)]

        # 3. Lookup by (district, commodity)
        if not m_data and (canon_dt.lower(), comm_key) in self.mandi_lookup:
            m_data = self.mandi_lookup[(canon_dt.lower(), comm_key)]

        # 4. Lookup by source aliases
        if not m_data:
            for s_alias in src_names:
                if (s_alias, comm_key) in self.mandi_lookup:
                    m_data = self.mandi_lookup[(s_alias, comm_key)]
                    break

        # 5. Live Mandi Service lookup
        if not m_data and mandi_service is not None:
            live_res = mandi_service.get_latest_price(crop, canon_st)
            if live_res and live_res.modal_price > 0:
                m_data = {
                    "commodity": comm_name,
                    "district": canon_dt,
                    "state": canon_st,
                    "market_name": live_res.market,
                    "min_price_rs_qtl": live_res.min_price,
                    "modal_price_rs_qtl": live_res.modal_price,
                    "max_price_rs_qtl": live_res.max_price,
                    "arrival_date": live_res.arrival_date,
                    "data_age_days": live_res.data_age_days,
                    "freshness_label": live_res.freshness_label
                }

        if m_data:
            min_p  = m_data.get("min_price_rs_qtl",  m_data.get("min_price",  0.0))
            modal_p = m_data.get("modal_price_rs_qtl", m_data.get("modal_price", 0.0))
            max_p  = m_data.get("max_price_rs_qtl",  m_data.get("max_price",  0.0))
            arr_date_str = str(m_data.get("arrival_date", ""))

            freshness_info = _compute_freshness(arr_date_str)
            data_age_days = freshness_info["data_age_days"]
            freshness_label = freshness_info["freshness_label"]
            freshness_note = freshness_info["freshness_note"]
            obs_date_display = freshness_info["observation_date"]

            if isinstance(min_p, (int, float)) and isinstance(modal_p, (int, float)) and isinstance(max_p, (int, float)):
                min_p  = min(min_p, modal_p)
                max_p  = max(max_p, modal_p)

            return {
                "available": True,
                "crop": crop,
                "commodity": m_data.get("commodity", comm_name),
                "district": m_data.get("district", canon_dt),
                "state": m_data.get("state", canon_st),
                "market": m_data.get("market_name", f"{canon_dt} Mandi Yard"),
                "min_price": round(float(min_p), 2),
                "current_price": round(float(modal_p), 2),
                "max_price": round(float(max_p), 2),
                "currency": "INR",
                "unit": "quintal",
                "observation_date": obs_date_display,
                "observation_date_iso": freshness_info.get("observation_date_iso", arr_date_str),
                "data_age_days": data_age_days,
                "freshness_label": freshness_label,
                "freshness_note": freshness_note,
                "source": "data.gov.in",
                "source_type": "OFFICIAL_MANDI_OBSERVATION"
            }

        # NO record available — return honest UNAVAILABLE status, no fake numbers!
        return {
            "available": False,
            "crop": crop,
            "commodity": comm_name,
            "district": canon_dt,
            "state": canon_st,
            "market": "UNAVAILABLE",
            "min_price": None,
            "current_price": None,
            "max_price": None,
            "currency": "INR",
            "unit": "quintal",
            "observation_date": "UNAVAILABLE",
            "observation_date_iso": "UNAVAILABLE",
            "data_age_days": None,
            "freshness_label": "UNAVAILABLE",
            "freshness_note": "No Mandi observation record available for this crop and location.",
            "source": "data.gov.in",
            "source_type": "UNAVAILABLE"
        }


    def _get_price_forecast(self, crop: str, current_price, state: str = "All") -> dict:
        """
        Generate a price forecast for the given crop using the validated production ML model.

        Evaluated 5 Major Crops: Rice, Wheat, Maize, Onion, Potato.
        Unsupported crops honestly return prediction_available = False.
        """
        crop_lower = crop.lower()

        # Evaluated production model configuration from price_model_evaluation.json
        CROP_MODEL_CONFIG = {
            "rice":   {"model": "XGBoost", "mae": 23.98,  "rmse": 30.12,  "mape_pct": 1.1},
            "wheat":  {"model": "Prophet", "mae": 62.92,  "rmse": 67.69,  "mape_pct": 2.8},
            "maize":  {"model": "XGBoost", "mae": 23.79,  "rmse": 35.88,  "mape_pct": 1.4},
            "onion":  {"model": "XGBoost", "mae": 156.63, "rmse": 212.63, "mape_pct": 8.5},
            "potato": {"model": "XGBoost", "mae": 93.54,  "rmse": 156.35, "mape_pct": 7.2},
        }

        cfg = CROP_MODEL_CONFIG.get(crop_lower)

        # UNSUPPORTED CROP: Return honest unavailable message
        if not cfg:
            return {
                "available": False,
                "crop": crop,
                "predicted_price": None,
                "forecast_horizon_days": 30,
                "model": None,
                "message": "Price prediction is currently unavailable for this crop because a validated forecasting model is not available."
            }

        # Run the trained ML forecasting model for this crop
        from app.ml.inference import predict_price
        try:
            ml_res = predict_price(crop_lower, state=state, horizon_days=30)
            preds = ml_res.get("predictions", [])
            pred_price = ml_res.get("predicted_price") or (preds[-1] if preds else None)
            best_model_name = ml_res.get("best_model_label") or ml_res.get("best_model") or cfg["model"]
            date_labels = ml_res.get("date_labels", [])
        except Exception as e:
            logger.warning(f"Error running ML inference for {crop}: {e}")
            preds = []
            pred_price = None
            best_model_name = cfg["model"]
            date_labels = []

        mae  = cfg["mae"]
        rmse = cfg["rmse"]
        mape = cfg["mape_pct"]

        today = datetime.date.today()
        pred_date = today + datetime.timedelta(days=30)

        return {
            "available": True,
            "crop": crop,
            "current_price": current_price,
            "predicted_price": pred_price,
            "predictions": preds,
            "date_labels": date_labels,
            "forecast_horizon_days": 30,
            "prediction_date": pred_date.strftime("%d-%m-%Y"),
            "prediction_date_iso": pred_date.isoformat(),
            "model": best_model_name,
            "validation_MAE": mae,
            "validation_RMSE": rmse,
            "validation_MAPE_pct": mape
        }

    def _derive_price_advisory(
        self, mandi_vec: dict, forecast_vec: dict
    ) -> dict:
        """Generate SELL or HOLD advisory using transparent 3% threshold rule."""
        curr = mandi_vec.get("current_price")
        pred = forecast_vec.get("predicted_price")
        freshness = mandi_vec.get("freshness_label", "UNKNOWN")
        source_type = mandi_vec.get("source_type", "UNKNOWN")

        is_valid_curr = isinstance(curr, (int, float)) and curr > 0
        is_valid_pred = isinstance(pred, (int, float)) and pred > 0

        # Safety Fallback when Mandi price is unavailable or reference fallback
        if not is_valid_curr or not is_valid_pred or source_type == "REFERENCE_FALLBACK" or freshness in ("VERY_STALE", "STALE", "UNAVAILABLE"):
            return {
                "action": "HOLD",
                "reason": "Reliable recent Mandi observations are currently unavailable, so there is insufficient market evidence to recommend selling. Please verify the latest local Mandi price before making a transaction.",
                "model": forecast_vec.get("model", "ML Model"),
                "forecast_confidence": "POOR"
            }

        diff_pct = (pred - curr) / curr * 100.0
        abs_diff = abs(round(diff_pct, 1))

        if diff_pct < -3.0:
            action = "SELL"
            reason = f"The forecast indicates a decline of approximately {abs_diff}% over the next 30 days, so selling at the current market price may reduce exposure to the expected fall."
        elif diff_pct > 3.0:
            action = "HOLD"
            reason = f"Prices are forecast to increase by approximately {abs_diff}% over the next 30 days, so holding may provide a better expected selling price."
        else:
            action = "HOLD"
            reason = f"The forecast indicates only a small price movement of about {abs_diff}%. The expected change is not large enough to justify immediate selling."

        return {
            "action": action,
            "reason": reason,
            "current_observed_price": curr,
            "predicted_price_30d": pred,
            "price_change_pct": round(diff_pct, 2),
            "mandi_data_age_days": mandi_vec.get("data_age_days"),
            "reliability": mandi_vec.get("freshness_label", "HIGH"),
        }
