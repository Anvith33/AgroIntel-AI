"""
crop_router.py — Crop Recommendation API Router for AgroIntel v4.0.

Endpoints:
  POST /api/predict/crop — Multi-stage Crop Recommendation Engine with Suitability Scoring & Explainability
"""

import logging

from fastapi import APIRouter, HTTPException
from app.api.schemas import CropRecommendationRequest
from app.services.recommendation_engine import recommend_crops

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Crop Recommendation"])


@router.post("/predict/crop", summary="Recommend Best Crops for Region, Soil & Season")
def predict_crop_recommendation(request: CropRecommendationRequest):
    """
    Execute multi-stage crop recommendation pipeline:
      1. District Resolution (top 10 historical crops)
      2. Season Filter (constants.CROP_SEASONS)
      3. Soil Resolution (User input > geo_soil_mapping > default values)
      4. Dynamic Weather Fusion Engine (70-90% historical climate + 10-40% Open-Meteo live)
      5. Random Forest Candidate Scoring & Probability Normalization
      6. ICAR Agro-Climatic Zone Validation
      7. Composite Suitability Scoring (0 to 100)
      8. Top 3 Selection with Deterministic Explainability & Visualization Support
    """
    try:
        result = recommend_crops(
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
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Crop recommendation error for district='{request.district}', state='{request.state}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal recommendation error: {str(e)}")
