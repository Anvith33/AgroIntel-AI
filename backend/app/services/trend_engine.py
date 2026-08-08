"""
trend_engine.py — Enhanced Trend Analysis & Statistics Service for AgroIntel v4.0.

Provides statistical trend analysis over 30-day predicted price arrays:
  - Trend direction: UPWARD | DOWNWARD | STABLE
  - Trend strength: LOW | MEDIUM | HIGH
  - Expected change percentage
  - 30-day forecast bounds: average_price, minimum_price, maximum_price
  - Detailed trend_statistics:
      forecast_slope, daily_average_change, forecast_std, forecast_variance, volatility_percent
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrendAnalysisResult:
    """Structured trend analysis output with comprehensive statistics."""
    trend_direction: str          # "UPWARD" | "DOWNWARD" | "STABLE"
    trend_strength: str           # "LOW" | "MEDIUM" | "HIGH"
    expected_change_percent: float # Percentage change over 30 days
    average_price: float          # Mean predicted price over 30 days
    minimum_price: float          # Lowest predicted price over 30 days
    maximum_price: float          # Highest predicted price over 30 days
    volatility_percent: float     # Price volatility (std / mean * 100)
    trend_statistics: Dict[str, float] # Detailed statistical metrics dict


def analyze_trend(current_price: float, predictions_30d: List[float]) -> TrendAnalysisResult:
    """
    Perform statistical trend & strength analysis over a 30-day forecast array.

    Args:
        current_price: Current market price (₹/quintal).
        predictions_30d: Array of predicted daily prices for 30 days.

    Returns:
        TrendAnalysisResult object.
    """
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    if not predictions_30d:
        raise ValueError("predictions_30d cannot be empty")

    arr = np.array(predictions_30d, dtype=float)
    avg_pred = float(np.mean(arr))
    min_pred = float(np.min(arr))
    max_pred = float(np.max(arr))
    std_pred = float(np.std(arr))
    var_pred = float(np.var(arr))

    expected_change = ((avg_pred - current_price) / current_price) * 100.0
    volatility = (std_pred / avg_pred) * 100.0 if avg_pred > 0 else 0.0

    # Trend Direction Rules
    if expected_change > 2.0:
        direction = "UPWARD"
    elif expected_change < -2.0:
        direction = "DOWNWARD"
    else:
        direction = "STABLE"

    # Linear regression slope calculation (days 0..29)
    x = np.arange(len(arr))
    slope, _ = np.polyfit(x, arr, 1)
    daily_slope_pct = (slope / current_price) * 100.0

    # Daily average absolute change
    daily_diffs = np.abs(np.diff(arr))
    daily_avg_change = float(np.mean(daily_diffs)) if len(daily_diffs) > 0 else 0.0

    # Trend Strength Rules
    abs_change = abs(expected_change)
    abs_slope = abs(daily_slope_pct)

    if abs_change >= 8.0 or abs_slope >= 0.25:
        strength = "HIGH"
    elif abs_change >= 3.0 or abs_slope >= 0.08:
        strength = "MEDIUM"
    else:
        strength = "LOW"

    trend_stats = {
        "forecast_slope": round(float(slope), 2),
        "daily_average_change": round(daily_avg_change, 2),
        "forecast_std": round(std_pred, 2),
        "forecast_variance": round(var_pred, 2),
        "volatility_percent": round(volatility, 2),
    }

    logger.debug(
        f"Trend analyzed: current=₹{current_price}, 30d_avg=₹{avg_pred:.2f}, "
        f"change={expected_change:.2f}%, direction={direction}, strength={strength}"
    )

    return TrendAnalysisResult(
        trend_direction=direction,
        trend_strength=strength,
        expected_change_percent=round(expected_change, 2),
        average_price=round(avg_pred, 2),
        minimum_price=round(min_pred, 2),
        maximum_price=round(max_pred, 2),
        volatility_percent=round(volatility, 2),
        trend_statistics=trend_stats,
    )
