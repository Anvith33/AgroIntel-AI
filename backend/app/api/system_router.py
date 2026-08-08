"""
system_router.py — System Metadata, Diagnostics & Demo Endpoints for AgroIntel v4.0.

Endpoints:
  GET /api/version     — Return system version config
  GET /api/models      — Return trained price & crop models with metrics
  GET /api/system/info — System diagnostics (Python/library versions, CPU/memory usage, uptime)
  GET /api/demo        — Populates frontend dropdowns (crops, states, districts, seasons, horizons)
"""

import json
import logging
import os
import platform
import sys
import time
from pathlib import Path

import fastapi
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.constants import (
    CROP_SEASONS,
    PRICE_PREDICTION_CROPS,
    SEASONS,
)
from app.api.schemas import SystemVersionResponse
from app.services.region_service import _load_region_map

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["System & Diagnostics"])

CONFIG_PATH = settings.BASE_DIR / "app" / "core" / "system_config.json"
REGISTRY_PATH = settings.MODELS_DIR / "model_registry.json"
CROP_METRICS_PATH = settings.MODELS_DIR / "crop_recommender_metrics.json"

START_TIME = time.time()


def _load_system_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {
        "project": "AgroIntel",
        "project_version": "4.0.0",
        "api_version": "v1",
        "ml_pipeline_version": "1.0.0",
        "feature_version": "4.0.0",
        "dataset_version": "2019-2024-v1",
        "weather_version": "open-meteo-monthly-v1",
    }


@router.get("/version", response_model=SystemVersionResponse, summary="Get System Version Metadata")
def get_system_version():
    """Return project version, API version, model registry version, feature version, dataset version, and weather version."""
    cfg = _load_system_config()
    return SystemVersionResponse(**cfg)


@router.get("/models", summary="Get Trained Models & Performance Metrics")
def get_model_registry_details():
    """Return trained price prediction models and crop recommendation model status, MAE, RMSE, and artifacts."""
    if not REGISTRY_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Model registry file not found. Ensure models have been trained."
        )

    with open(REGISTRY_PATH, "r") as f:
        registry_data = json.load(f)

    crop_rf_metrics = {}
    if CROP_METRICS_PATH.exists():
        with open(CROP_METRICS_PATH, "r") as f:
            crop_rf_metrics = json.load(f)

    return {
        "status": "success",
        "price_prediction_models": registry_data.get("registry", {}),
        "crop_recommendation_model": crop_rf_metrics,
        "models_directory": str(settings.MODELS_DIR),
    }


@router.get("/system/info", summary="Get Real-Time System Diagnostics")
def get_system_diagnostics():
    """
    Return Python environment details, ML library versions, CPU/Memory usage,
    loaded model file counts, cached file counts, and server uptime.
    """
    # 1. Package Version Inspection
    prophet_ver = "installed"
    try:
        import prophet
        prophet_ver = getattr(prophet, "__version__", "installed")
    except Exception:
        prophet_ver = "unavailable"

    xgboost_ver = "installed"
    try:
        import xgboost
        xgboost_ver = getattr(xgboost, "__version__", "installed")
    except Exception:
        xgboost_ver = "unavailable"

    tf_available = False
    try:
        import tensorflow as tf
        tf_available = True
    except Exception:
        tf_available = False

    # 2. Resource & Memory Usage (via psutil or os)
    mem_info = {"rss_mb": 0.0, "vsz_mb": 0.0}
    cpu_percent = 0.0
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        mem_info = {
            "rss_mb": round(mem.rss / (1024 * 1024), 2),
            "vsz_mb": round(mem.vms / (1024 * 1024), 2),
            "memory_percent": round(proc.memory_percent(), 2),
        }
        cpu_percent = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        pass

    # 3. Model Files & Artifact Counts
    model_files = list(settings.MODELS_DIR.glob("*.*"))
    data_files = list(settings.DATA_DIR.glob("*.*"))

    uptime_sec = round(time.time() - START_TIME, 2)

    return {
        "application": "AgroIntel v4.0",
        "python_version": sys.version.split()[0],
        "fastapi_version": fastapi.__version__,
        "prophet_version": prophet_ver,
        "xgboost_version": xgboost_ver,
        "tensorflow_available": tf_available,
        "system_os": f"{platform.system()} {platform.release()}",
        "cpu_usage_percent": cpu_percent,
        "memory_usage": mem_info,
        "loaded_models_count": len(model_files),
        "cached_data_files_count": len(data_files),
        "server_uptime_seconds": uptime_sec,
    }


@router.get("/demo", summary="Get Frontend Demo Dropdown Options")
def get_demo_metadata():
    """
    Return supported crops, states, districts, seasons, and forecast horizons
    to populate frontend user selection controls.
    """
    region_data = _load_region_map()
    states = sorted(list(region_data.get("states", {}).keys()))
    districts = sorted(list(region_data.get("districts", {}).keys()))

    return {
        "supported_crops": sorted(PRICE_PREDICTION_CROPS),
        "supported_states": states,
        "supported_districts": districts[:50],  # Return top 50 for quick selector
        "supported_seasons": ["Kharif", "Rabi", "Zaid"],
        "prediction_horizons": [7, 15, 30, 60, 90],
    }
