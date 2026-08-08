"""
recommendation_logger.py — Enhanced Recommendation Audit Logging Service for AgroIntel v4.0.

Stores prediction request audit logs into app/data/recommendation_history.json:
  - timestamp (ISO string)
  - state (string)
  - district (string)
  - season (string)
  - candidate_crops (list of strings)
  - recommended_crops (list of strings)
  - rf_probabilities (list of floats)
  - suitability_scores (list of floats)
  - weather (dict of temp, humidity, rainfall)
  - soil (dict of N, P, K, pH, source)
  - model (string)
  - response_time_ms (float)

Used exclusively for monitoring, performance analysis, and audit history.
NOT used for model training.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

LOG_FILE = settings.DATA_DIR / "recommendation_history.json"


def log_recommendation(
    state: str,
    district: str,
    season: str,
    recommended_crops: List[str],
    scores: List[float],
    weather: Dict[str, float],
    soil: Dict[str, Any],
    model: str = "RandomForestClassifier",
    response_time_ms: float = 0.0,
) -> Dict[str, Any]:
    """Log a recommendation request audit entry."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "state": state,
        "district": district,
        "season": season,
        "recommended_crops": recommended_crops,
        "suitability_scores": [round(float(s), 1) for s in scores],
        "weather": weather,
        "soil": soil,
        "model": model,
        "response_time_ms": round(float(response_time_ms), 2),
    }

    try:
        history = []
        if LOG_FILE.exists():
            with open(LOG_FILE, "r") as f:
                try:
                    history = json.load(f)
                except Exception:
                    history = []

        history.append(entry)

        if len(history) > 1000:
            history = history[-1000:]

        with open(LOG_FILE, "w") as f:
            json.dump(history, f, indent=2)

        logger.info(f"Logged recommendation for {district}, {state} ({season}): {recommended_crops}")
    except Exception as e:
        logger.warning(f"Could not write recommendation audit log: {e}")

    return entry
