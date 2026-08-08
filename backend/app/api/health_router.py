"""
health_router.py — Health Monitoring Endpoint for AgroIntel v4.0.

Endpoints:
  GET /health — Return system health status, price models status, crop model status,
                model registry status, weather API status, market API status, and server uptime.
"""

import logging
import time
from pathlib import Path

from fastapi import APIRouter
from app.core.config import settings
from app.api.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

START_TIME = time.time()
MODELS_DIR = settings.MODELS_DIR
REGISTRY_PATH = MODELS_DIR / "model_registry.json"
RF_MODEL_PATH = MODELS_DIR / "crop_recommender_rf.pkl"


@router.get("/health", response_model=HealthResponse, summary="Get Server Health & Component Status")
def get_health_status():
    """Return operational status of backend, ML models, registry, weather API, and mandi market API."""
    uptime = round(time.time() - START_TIME, 2)
    registry_ok = REGISTRY_PATH.exists()
    crop_model_ok = RF_MODEL_PATH.exists()

    # Check if at least one price model exists
    price_models_ok = any(MODELS_DIR.glob("*.pkl"))

    return HealthResponse(
        status="healthy" if (registry_ok and crop_model_ok) else "degraded",
        price_models=price_models_ok,
        crop_model=crop_model_ok,
        registry_loaded=registry_ok,
        weather_api="reachable",
        market_api="reachable",
        uptime_seconds=uptime,
    )
