"""
endpoints.py — API routes for AgroIntel AI
"""

import logging
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from app.ml.inference import predict_price, predict_crop, get_crop_info, clear_model_cache
from app.ml.train import train_all_crops, train_price_prediction_model, CROPS

class CropRequest(BaseModel):
    location: str
    season: str = "Auto"  # Auto | Kharif | Rabi | Zaid
    lat: float = None     # Optional GPS latitude  (enables satellite soil detection)
    lon: float = None     # Optional GPS longitude (enables satellite soil detection)

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_CROPS = list(CROPS.keys())

# ── Models are already training in background ─────────────────────────────────
_training_status = {"status": "idle", "message": "No training run yet."}


def _run_training_task():
    """Background task that trains all crop models."""
    global _training_status
    _training_status = {"status": "running", "message": "Training in progress…"}
    try:
        results = train_all_crops()
        clear_model_cache()
        best_models = {c: r.get("best_model", "?") for c, r in results.items() if r.get("status") == "success"}
        _training_status = {
            "status": "success",
            "message": "Training complete.",
            "results": results,
            "best_models": best_models,
        }
        logger.info("Background training complete: %s", best_models)
    except Exception as e:
        _training_status = {"status": "error", "message": str(e)}
        logger.error("Training failed: %s", e)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/train")
def trigger_training(background_tasks: BackgroundTasks):
    """Trigger retraining of all models in the background."""
    if _training_status.get("status") == "running":
        raise HTTPException(status_code=409, detail="Training is already in progress.")
    background_tasks.add_task(_run_training_task)
    return {"message": "Training started in background.", "crops": SUPPORTED_CROPS,
            "note": "Includes COVID-19 (2020) and Russia-Ukraine war (2022) data."}


@router.get("/train/status")
def training_status():
    """Get the status of the last training run."""
    return _training_status


@router.post("/train/{crop}")
def train_single_crop(crop: str):
    """Train models for a single crop synchronously."""
    crop = crop.lower()
    if crop not in SUPPORTED_CROPS:
        raise HTTPException(status_code=400, detail=f"Unsupported crop '{crop}'. Choose: {SUPPORTED_CROPS}")
    try:
        result = train_price_prediction_model(crop)
        clear_model_cache()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/crop")
def predict_crop_endpoint(request: CropRequest):
    """Predict the best crop to grow based on location, weather, satellite soil, and season."""
    try:
        result = predict_crop(
            request.location,
            request.season,
            lat=request.lat,
            lon=request.lon,
        )
        return result
    except Exception as e:
        logger.error("Crop prediction error for %s: %s", request.location, e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/predict")
def predict(
    crop: str = Query(default="wheat", description="Crop name"),
    state: str = Query(default="All", description="State name for accurate local price"),
    horizon_days: int = Query(default=30, ge=1, le=90, description="Forecast horizon in days"),
):
    """Get price prediction for a crop using the best available model."""
    crop = crop.lower()
    if crop not in SUPPORTED_CROPS:
        raise HTTPException(status_code=400, detail=f"Unsupported crop. Choose from: {SUPPORTED_CROPS}")
    try:
        result = predict_price(crop, state, horizon_days)
        return result
    except Exception as e:
        logger.error("Prediction error for %s in %s: %s", crop, state, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crops")
def list_crops():
    """List all supported crops and their model status."""
    crops_info = []
    for crop in SUPPORTED_CROPS:
        try:
            info = get_crop_info(crop)
        except Exception:
            info = {"crop": crop, "ready": False}
        crops_info.append(info)
    return {"crops": crops_info, "supported": SUPPORTED_CROPS}


@router.get("/crops/{crop}")
def crop_info(crop: str):
    """Get model status and metrics for a specific crop."""
    crop = crop.lower()
    if crop not in SUPPORTED_CROPS:
        raise HTTPException(status_code=400, detail=f"Unknown crop: {crop}")
    try:
        return get_crop_info(crop)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
