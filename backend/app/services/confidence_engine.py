"""
confidence_engine.py — Confidence Score Calculation & Breakdown Service for AgroIntel.

Calculates composite model confidence based on:
  1. Base Model Quality Score (0–100): derived from MAE / Mean Price
  2. Horizon Penalty Score (0–100): 7d=100, 15d=95, 30d=90, 60d=80, 90d=70
  3. Data Freshness Score (0–100): <1d=100, 1-3d=95, 3-7d=85, >7d=70

Composite score strictly clamped between 40.0% and 95.0%.
"""

import logging
from dataclasses import dataclass, asdict
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    """Structured confidence calculation output with breakdown."""
    confidence_score: float         # Clamped decimal (0.40 to 0.95)
    confidence: float               # Percentage (40.0 to 95.0)
    confidence_breakdown: Dict[str, int]  # Breakdown 0-100 integer scores


def calculate_confidence(
    model_mae: float,
    mean_historical_price: float,
    horizon_days: int = 30,
    data_age_days: int = 0,
) -> ConfidenceResult:
    """
    Calculate composite forecast confidence score and breakdown.

    Args:
        model_mae: Model MAE score on validation set (₹/quintal).
        mean_historical_price: Average historical price for this crop.
        horizon_days: Requested forecast horizon (7, 15, 30, 60, 90).
        data_age_days: Age of the current price in days.

    Returns:
        ConfidenceResult object.
    """
    if mean_historical_price <= 0:
        mean_historical_price = 2000.0

    # 1. Base Model Quality Factor
    error_ratio = min(model_mae / mean_historical_price, 0.50)
    base_conf = max(1.0 - error_ratio, 0.50)
    model_quality_score = int(round(base_conf * 100))

    # 2. Forecast Horizon Factor
    if horizon_days <= 7:
        horizon_factor = 1.00
    elif horizon_days <= 15:
        horizon_factor = 0.95
    elif horizon_days <= 30:
        horizon_factor = 0.90
    elif horizon_days <= 60:
        horizon_factor = 0.80
    else:
        horizon_factor = 0.70
    horizon_score = int(round(horizon_factor * 100))

    # 3. Market Data Freshness Factor
    if data_age_days < 1:
        freshness_factor = 1.00
    elif data_age_days <= 3:
        freshness_factor = 0.95
    elif data_age_days <= 7:
        freshness_factor = 0.85
    else:
        freshness_factor = 0.70
    freshness_score = int(round(freshness_factor * 100))

    # 4. Composite Score & Clamping
    raw_score = base_conf * horizon_factor * freshness_factor
    clamped_score = float(np.clip(raw_score, 0.40, 0.95))
    confidence_pct = round(clamped_score * 100.0, 1)

    breakdown = {
        "model_quality": model_quality_score,
        "horizon_penalty": horizon_score,
        "data_freshness": freshness_score,
    }

    logger.debug(f"Confidence score: {confidence_pct}% (Breakdown: {breakdown})")

    return ConfidenceResult(
        confidence_score=round(clamped_score, 4),
        confidence=confidence_pct,
        confidence_breakdown=breakdown,
    )
