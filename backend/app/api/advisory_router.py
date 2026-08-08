"""
advisory_router.py — Combined Agricultural Advisory Router for AgroIntel v4.0.

Endpoints:
  POST /api/advisory — Integrated Crop Recommendation & Price Forecast Advisory Engine
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.constants import PRICE_PREDICTION_CROPS
from app.ml.price_predictor import predict_crop_price
from app.services.recommendation_engine import recommend_crops

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Combined Advisory"])


class AdvisoryRequest(BaseModel):
    state: str = Field(..., description="Target state", example="Maharashtra")
    district: str = Field(..., description="Target district", example="Pune")
    season: Optional[str] = Field("Kharif", description="Season", example="Kharif")
    crop: Optional[str] = Field(None, description="Optional target crop for price prediction", example="wheat")
    n: Optional[float] = Field(None, description="Nitrogen content (kg/ha)")
    p: Optional[float] = Field(None, description="Phosphorus content (kg/ha)")
    k: Optional[float] = Field(None, description="Potassium content (kg/ha)")
    ph: Optional[float] = Field(None, description="Soil pH")
    lat: Optional[float] = Field(None, description="Latitude")
    lon: Optional[float] = Field(None, description="Longitude")


@router.post("/advisory", summary="Get Integrated Crop Recommendation & Price Forecast Advisory")
def get_combined_advisory(request: AdvisoryRequest):
    """
    Generate combined agricultural advisory:
      1. Run Multi-Stage Crop Recommendation for target region & soil.
      2. Predict 30-day Price Forecast & Sell/Hold Decision for target/top crop.
      3. Output unified advisory response with combined explainability reasons.
    """
    t_start = time.perf_counter()

    # 1. Step 1: Crop Recommendation Pipeline
    rec_result = recommend_crops(
        state=request.state,
        district=request.district,
        season=request.season,
        user_n=request.n,
        user_p=request.p,
        user_k=request.k,
        user_ph=request.ph,
        lat=request.lat,
        lon=request.lon,
    )

    top_recommended = rec_result.get("recommended_crops", [])
    top_crop_name = top_recommended[0]["crop"] if top_recommended else "wheat"

    # 2. Step 2: Target Crop Selection for Price Prediction
    target_price_crop = "wheat"
    if request.crop and request.crop.lower().strip() in PRICE_PREDICTION_CROPS:
        target_price_crop = request.crop.lower().strip()
    elif top_crop_name.lower().strip() in PRICE_PREDICTION_CROPS:
        target_price_crop = top_crop_name.lower().strip()

    # 3. Step 3: Price Forecast & Decision Pipeline
    price_result = predict_crop_price(
        crop=target_price_crop,
        state=request.state,
        horizon_days=30,
        lat=request.lat or 18.52,
        lon=request.lon or 73.85,
    )

    # 4. Consolidated Decision & Reasons
    rec_top1 = top_recommended[0] if top_recommended else {}
    decision_action = price_result.get("decision", "HOLD")
    net_gain = price_result.get("decision_score", {}).get("estimated_net_gain_percent", 0.0)

    combined_summary = (
        f"Recommended crop for {request.district}, {request.state} ({request.season}): "
        f"{rec_top1.get('crop', '').upper()} (Suitability Score: {rec_top1.get('suitability_score', 0)}/100). "
        f"Price forecast for {target_price_crop.upper()} indicates {decision_action} "
        f"(30-day predicted avg ₹{price_result.get('average_price', 0):.2f}, estimated net gain {net_gain:+.1f}%)."
    )

    consolidated_reasons = rec_top1.get("reasons", []) + price_result.get("reasons", [])

    t_end = time.perf_counter()
    latency_ms = round((t_end - t_start) * 1000.0, 2)

    return {
        "state": request.state,
        "district": request.district,
        "season": rec_result.get("season"),
        "target_price_crop": target_price_crop,
        "combined_summary": combined_summary,
        "crop_recommendations": top_recommended,
        "price_prediction": {
            "crop": price_result.get("crop"),
            "production_model": price_result.get("production_model"),
            "current_price": price_result.get("current_price"),
            "predicted_30d_avg": price_result.get("average_price"),
            "trend": price_result.get("trend"),
            "decision": decision_action,
            "confidence": price_result.get("confidence"),
            "decision_score": price_result.get("decision_score"),
        },
        "consolidated_reasons": consolidated_reasons,
        "response_time_ms": latency_ms,
    }
