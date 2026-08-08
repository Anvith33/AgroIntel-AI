"""
prediction_logger.py — Enhanced Audit Logging Service for AgroIntel v4.0.

Stores prediction request audit logs into app/data/prediction_history.json:
  - timestamp (ISO string)
  - crop (string)
  - production_model (string)
  - current_price (float)
  - forecast_horizon (int)
  - predicted_price (float)
  - expected_change_percent (float)
  - confidence (float)
  - decision ("HOLD" | "SELL")
  - response_time_ms (float)
  - prediction_source (string)

Used exclusively for monitoring, performance analysis, and audit history.
NOT used for model training.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

LOG_FILE = settings.DATA_DIR / "prediction_history.json"


def log_prediction(
    crop: str,
    production_model: str,
    current_price: float,
    forecast_horizon: int,
    predicted_price: float,
    expected_change_percent: float,
    confidence: float,
    decision: str,
    response_time_ms: float,
    prediction_source: str,
) -> Dict[str, Any]:
    """
    Log a prediction request to prediction_history.json.

    Args:
        crop: Crop name.
        production_model: Production model name (e.g. "prophet", "xgboost").
        current_price: Current market price (₹/quintal).
        forecast_horizon: Horizon in days (7, 15, 30, 60, 90).
        predicted_price: Average predicted price over 30 days.
        expected_change_percent: Expected change percentage.
        confidence: Confidence score or percentage.
        decision: "HOLD" or "SELL".
        response_time_ms: Execution time in milliseconds.
        prediction_source: "live_api" | "cache" | "historical_tail".

    Returns:
        Dict of the logged entry.
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "crop": crop.lower(),
        "production_model": production_model.lower(),
        "current_price": round(float(current_price), 2),
        "forecast_horizon": forecast_horizon,
        "predicted_price": round(float(predicted_price), 2),
        "expected_change_percent": round(float(expected_change_percent), 2),
        "confidence": round(float(confidence), 1),
        "decision": decision,
        "response_time_ms": round(float(response_time_ms), 2),
        "prediction_source": prediction_source,
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

        # Retain last 1000 records
        if len(history) > 1000:
            history = history[-1000:]

        with open(LOG_FILE, "w") as f:
            json.dump(history, f, indent=2)

        logger.info(
            f"Logged prediction: crop='{crop}', model='{production_model}', "
            f"decision='{decision}', latency={response_time_ms:.1f}ms"
        )
    except Exception as e:
        logger.warning(f"Could not write prediction log entry: {e}")

    return entry
