"""
nlp_explanation_service.py — AgroIntel Natural Language Explanation & Summarization Layer
"""

import os
import json
import logging
import datetime
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CROP_INFO_PATH = DATA_DIR / "crop_information.json"

_CROP_INFO_DB = {}
if CROP_INFO_PATH.exists():
    with open(CROP_INFO_PATH) as f:
        _CROP_INFO_DB = json.load(f)


def _get_groq_key() -> Optional[str]:
    env_file = BASE_DIR.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                val = line.split("=", 1)[1].strip().strip("\"'")
                if val and val != "your_groq_api_key_here":
                    return val
    return os.environ.get("GROQ_API_KEY")



def get_crop_information(crop_name: str) -> dict:
    """Retrieve verified crop knowledge facts from crop_information.json."""
    if not crop_name:
        return {}
    c_clean = crop_name.lower().strip()
    if c_clean in _CROP_INFO_DB:
        return _CROP_INFO_DB[c_clean]
    for k, v in _CROP_INFO_DB.items():
        if k in c_clean or c_clean in k:
            return v
    return {
        "why_grown": f"{crop_name} is cultivated for regional food security, farm revenue, and seasonal crop rotation.",
        "common_uses": "Consumed as food grain, pulse, oilseed, or industrial agricultural product.",
        "season": "Grown in recommended regional cropping seasons.",
        "soil": "Requires appropriate soil preparation, drainage, and balanced NPK fertilization.",
        "climate": "Thrives under favorable regional seasonal temperature and rainfall.",
        "key_characteristics": "Responds well to recommended agronomic and soil management practices."
    }


def explain_crop_recommendation(
    state: str,
    district: str,
    season: str,
    crop_recommendation: dict,
    current_intelligence: List[dict] = None,
    data_quality: dict = None
) -> dict:
    """Generate natural language explanation for a single crop recommendation."""
    crop = crop_recommendation.get("crop", "Crop")
    score = round(crop_recommendation.get("final_score", 0)) if isinstance(crop_recommendation.get("final_score"), (int, float)) else crop_recommendation.get("final_score", 0)
    reasons = crop_recommendation.get("reasons", [])
    risks = crop_recommendation.get("risks", [])
    sb = crop_recommendation.get("score_breakdown", {})
    water_status = sb.get("water_score", "UNKNOWN")

    relevant_news = []
    if current_intelligence:
        for intel in current_intelligence:
            intel_crop = intel.get("crop", "").lower()
            if intel_crop == crop.lower() or crop.lower() in intel_crop or intel_crop in crop.lower():
                relevant_news.append(intel)

    why_text = f"{crop} is recommended for {district} during the {season} season because historical district cultivation evidence supports the crop and available environmental conditions are suitable."
    if reasons:
        why_text = f"{crop} is recommended because " + "; ".join(reasons[:3]).lower() + "."
        why_text = why_text[0].upper() + why_text[1:]

    considerations_text = ""
    if str(water_status).startswith("UNKNOWN") or water_status == "UNKNOWN":
        considerations_text = "Water suitability could not be fully verified."
    elif risks:
        considerations_text = risks[0]
    else:
        considerations_text = "Standard agronomic practices and field monitoring recommended."

    situation_text = "Current agricultural intelligence does not indicate major adverse weather or pest warnings for this crop."
    if relevant_news:
        n_item = relevant_news[0]
        sig = n_item.get("recommendation_risk_signal", "NEUTRAL")
        headline = n_item.get("headline") or n_item.get("summary") or "agricultural news reported in the region"
        if sig == "RISK_INCREASED":
            situation_text = f"Recent agricultural news indicates elevated risk: {headline}. This is considered as a contextual risk signal."
        else:
            situation_text = f"Recent news report: {headline} ({n_item.get('publication_date', '')})."

    summary_text = f"{crop} ranks #{crop_recommendation.get('rank', 1)} with a suitability score of {score}/100 for {district}, {state} ({season} season). {why_text}"

    deterministic_res = {
        "summary": summary_text,
        "why_recommended": why_text,
        "current_situation": situation_text,
        "considerations": considerations_text,
        "nlp_source": "DETERMINISTIC_RULES"
    }

    groq_key = _get_groq_key()
    if not groq_key:
        return deterministic_res

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        prompt_payload = {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You are AgroIntel's Farmer Advisory NLP Engine. Convert structured ML outputs into natural, simple English explanations. Output strictly JSON with keys: summary, why_recommended, current_situation, considerations. Never invent prices, crops, or facts."
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "district": district,
                        "state": state,
                        "season": season,
                        "crop": crop,
                        "score": score,
                        "reasons": reasons,
                        "water_status": water_status,
                        "news_item": relevant_news[0] if relevant_news else None
                    })
                }
            ]
        }
        req = urllib.request.Request(url, data=json.dumps(prompt_payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
            llm_content = json.loads(raw["choices"][0]["message"]["content"])
            llm_content["nlp_source"] = "GROQ_LLAMA_3.3_70B"
            return llm_content
    except Exception as e:
        logger.debug(f"[NLP_EXPLANATION] Groq unavailable ({e}), using deterministic fallback.")
        return deterministic_res


def explain_price_prediction(
    crop: str,
    district: str,
    state: str,
    market_data: dict,
    forecast_data: dict,
    advisory_data: dict,
    current_intelligence: List[dict] = None
) -> dict:
    """Generate natural language explanation for price prediction & SELL/HOLD market advisory."""
    raw_cur = market_data.get("current_price")
    raw_pred = forecast_data.get("predicted_price")
    horizon = forecast_data.get("forecast_horizon_days", 30)

    is_valid_cur = isinstance(raw_cur, (int, float)) and raw_cur > 0
    is_valid_pred = isinstance(raw_pred, (int, float)) and raw_pred > 0

    cur_price_fmt = f"{round(raw_cur):,}" if is_valid_cur else "—"
    pred_price_fmt = f"{round(raw_pred):,}" if is_valid_pred else "—"

    # Default logic when Mandi price or prediction is unavailable
    if not is_valid_cur or not is_valid_pred:
        decision = "HOLD"
        reason = "Reliable recent Mandi observations are currently unavailable, so there is insufficient market evidence to recommend selling. Please verify the latest local Mandi price before making a transaction."
        outlook = f"{crop} market observations are currently limited for {district}, {state}. Farmers are advised to check local Mandi yards for real-time rates before liquidating produce."
    else:
        change_pct = ((raw_pred - raw_cur) / raw_cur) * 100.0
        abs_change = round(abs(change_pct), 1)

        if change_pct < -3.0:
            decision = "SELL"
            reason = f"The forecast indicates a decline of approximately {abs_change}% over the next {horizon} days, so selling at the current market price may reduce exposure to the expected fall."
            direction_str = f"decrease of about {abs_change}%"
            action_advice = "selling at the current market price is recommended to protect returns"
        elif change_pct > 3.0:
            decision = "HOLD"
            reason = f"Prices are forecast to increase by approximately {abs_change}% over the next {horizon} days, so holding may provide a better expected selling price."
            direction_str = f"increase of about {abs_change}%"
            action_advice = "holding the crop may provide a better expected selling price"
        else:
            decision = "HOLD"
            reason = f"The forecast indicates only a small price movement of about {abs_change}%. The expected change is not large enough to justify immediate selling."
            direction_str = f"stable trend with a minor change of {abs_change}%"
            action_advice = "holding is recommended as prices are expected to remain steady"

        outlook = f"{crop} is currently trading around ₹{cur_price_fmt} per quintal in the latest available Mandi observation in {district}, {state}. The model forecasts approximately ₹{pred_price_fmt} per quintal over the next {horizon} days, indicating an expected {direction_str}. Based on this trend, {action_advice}."

    deterministic_res = {
        "decision": decision,
        "reason": reason,
        "price_outlook": outlook,
        "nlp_source": "DETERMINISTIC_RULES"
    }

    groq_key = _get_groq_key()
    if not groq_key:
        return deterministic_res

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        prompt_payload = {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You are AgroIntel's Market Advisory NLP Engine. Return strictly JSON with keys: decision (must be 'SELL' or 'HOLD'), reason, price_outlook. Never invent prices or facts outside the input."
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "crop": crop,
                        "district": district,
                        "state": state,
                        "current_price": cur_price_fmt,
                        "predicted_price": pred_price_fmt,
                        "horizon_days": horizon,
                        "decision": decision,
                        "reason": reason,
                        "price_outlook": outlook
                    })
                }
            ]
        }
        req = urllib.request.Request(url, data=json.dumps(prompt_payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
            llm_content = json.loads(raw["choices"][0]["message"]["content"])
            llm_content["nlp_source"] = "GROQ_LLAMA_3.3_70B"
            return llm_content
    except Exception:
        return deterministic_res



def summarize_news_intelligence(intel_list: List[dict]) -> str:
    """Generate 2-3 sentence natural language summary of current news intelligence."""
    if not intel_list:
        return "Current agricultural news monitors indicate stable baseline conditions with no major weather or market disruptions reported."

    head_lines = [item.get("headline") or item.get("summary") for item in intel_list if item.get("headline") or item.get("summary")]
    if not head_lines:
        return "Agricultural intelligence monitoring is active for this region."

    summary = f"Recent agricultural reports indicate key updates: {head_lines[0]}."
    if len(head_lines) > 1:
        summary += f" Additionally, {head_lines[1]}."
    summary += " This information is incorporated as contextual risk intelligence."

    return summary
