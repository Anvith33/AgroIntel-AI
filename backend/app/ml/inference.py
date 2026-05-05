"""
inference.py — Multi-model Price Prediction Inference Engine

Loads all trained models (Prophet, XGBoost, ARIMA, MLP) and their
accuracy metrics, then dynamically selects the best model to generate
price forecasts.
"""

import json
import pickle
import logging
import warnings
import numpy as np
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from app.ml.feature_engineering import (
    BLACK_SWAN_EVENTS,
    FEATURE_COLS,
    build_inference_features,
    is_black_swan_period,
    get_active_black_swan,
)

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"

# ── Supported crops for price prediction ─────────────────────────────────────
CROPS = {
    "wheat":     {"base_price": 2200, "seasonal_amplitude": 180, "trend_per_year": 120, "noise_std": 60},
    "rice":      {"base_price": 2900, "seasonal_amplitude": 220, "trend_per_year": 150, "noise_std": 70},
    "maize":     {"base_price": 1600, "seasonal_amplitude": 130, "trend_per_year": 90,  "noise_std": 50},
    "coconut":   {"base_price": 4500, "seasonal_amplitude": 400, "trend_per_year": 200, "noise_std": 120},
    "banana":    {"base_price": 1800, "seasonal_amplitude": 200, "trend_per_year": 100, "noise_std": 80},
    "arecanut":  {"base_price": 38000, "seasonal_amplitude": 3000, "trend_per_year": 1500, "noise_std": 2000},
    "groundnut": {"base_price": 5200, "seasonal_amplitude": 350, "trend_per_year": 180, "noise_std": 90},
    "mustard":   {"base_price": 5500, "seasonal_amplitude": 300, "trend_per_year": 160, "noise_std": 80},
    "soybean":   {"base_price": 3800, "seasonal_amplitude": 250, "trend_per_year": 140, "noise_std": 70},
    "cotton":    {"base_price": 6000, "seasonal_amplitude": 400, "trend_per_year": 200, "noise_std": 100},
}

# ── Coastal crops — get score boost in coastal regions ───────────────────────
COASTAL_CROPS = {"Coconut", "Banana", "Cashew", "Arecanut", "Rubber", "Black Pepper",
                 "Tapioca (Cassava)", "Paddy (Coastal/Kharif)", "Betel Leaf", "Jute",
                 "Cardamom", "Ginger", "Tea"}

# ── Model cache (loaded once on first use) ────────────────────────────────────
_model_cache: dict = {}


def _load_models(crop: str) -> dict:
    """Load all models and metrics for a crop. Caches in memory."""
    if crop in _model_cache:
        return _model_cache[crop]

    bundle = {"prophet": None, "xgboost": None, "arima": None, "mlp": None,
              "metrics": None, "data_tail": None}

    for model_name in ["prophet", "xgboost", "arima", "mlp"]:
        path = MODELS_DIR / f"{model_name}_{crop}.pkl"
        if path.exists():
            try:
                with open(path, "rb") as f:
                    bundle[model_name] = pickle.load(f)
                logger.info(f"Loaded {model_name} for {crop}")
            except Exception as e:
                logger.warning(f"Could not load {model_name} for {crop}: {e}")

    metrics_path = MODELS_DIR / f"metrics_{crop}.json"
    if metrics_path.exists():
        with open(metrics_path, "r") as f:
            bundle["metrics"] = json.load(f)

    data_path = MODELS_DIR / f"data_tail_{crop}.pkl"
    if data_path.exists():
        with open(data_path, "rb") as f:
            bundle["data_tail"] = pickle.load(f)

    _model_cache[crop] = bundle
    return bundle


def clear_model_cache():
    """Clear the in-memory model cache (call after retraining)."""
    _model_cache.clear()
    logger.info("Model cache cleared.")


def _get_recent_prices(data_tail: pd.DataFrame, n: int = 60) -> list:
    """Extract recent price values from the cached data tail."""
    if data_tail is None:
        return []
    return data_tail["y"].tail(n).tolist()


def _predict_prophet(model, target_date: date, horizon_days: int) -> list:
    """Generate Prophet forecasts for horizon_days starting from target_date."""
    dates = pd.date_range(start=target_date, periods=horizon_days, freq="D")
    future = pd.DataFrame({"ds": dates})
    forecast = model.predict(future)
    return forecast["yhat"].tolist()


def _predict_xgboost(model, recent_prices: list, target_date: date, horizon_days: int) -> list:
    """Generate XGBoost forecasts using rolling feature updates."""
    prices = list(recent_prices)
    predictions = []
    current_date = target_date
    for _ in range(horizon_days):
        if len(prices) >= 30:
            features = build_inference_features(prices, current_date)
            pred = float(model.predict(features)[0])
        else:
            pred = prices[-1] if prices else 2000.0
        predictions.append(pred)
        prices.append(pred)
        current_date += timedelta(days=1)
    return predictions


def _predict_arima(model, horizon_days: int) -> list:
    """Generate ARIMA forecasts (weekly model → daily interpolation)."""
    # ARIMA is weekly; convert horizon to weeks
    weeks = max(1, horizon_days // 7 + 1)
    forecast = model.forecast(steps=weeks)
    # Interpolate back to daily
    daily = []
    for val in forecast.values:
        daily.extend([val] * 7)
    return daily[:horizon_days]


def _predict_mlp(bundle: dict, recent_prices: list, target_date: date, horizon_days: int) -> list:
    """Generate MLP forecasts using rolling feature updates."""
    scaler = bundle["scaler"]
    model = bundle["model"]
    prices = list(recent_prices)
    predictions = []
    current_date = target_date
    for _ in range(horizon_days):
        if len(prices) >= 30:
            features = build_inference_features(prices, current_date)
            features_scaled = scaler.transform(features)
            pred = float(model.predict(features_scaled)[0])
        else:
            pred = prices[-1] if prices else 2000.0
        predictions.append(pred)
        prices.append(pred)
        current_date += timedelta(days=1)
    return predictions


def predict_price(crop: str, state: str = "All", horizon_days: int = 30) -> dict:
    """
    Main inference entry point.

    Args:
        crop: crop name (wheat, rice, maize)
        state: State name for market price fetching
        horizon_days: number of days to forecast ahead

    Returns:
        dict with prediction results, model comparison, and Black Swan context
    """
    crop = crop.lower()
    if crop not in CROPS:
        raise ValueError(f"Unsupported crop: '{crop}'. Choose from: {list(CROPS.keys())}")

    bundle = _load_models(crop)
    target_date = date.today() + timedelta(days=1)
    recent_prices = _get_recent_prices(bundle["data_tail"])
    
    # Fetch Live Data
    from app.data.ingestion import DataIngestion
    live_data = DataIngestion.fetch_live_market_data(crop, state)
    live_current_price = live_data.get("current_price")

    # ── Build predictions from each available model ──────────────────────────
    all_predictions = {}

    if bundle["prophet"]:
        try:
            preds = _predict_prophet(bundle["prophet"], target_date, horizon_days)
            all_predictions["prophet"] = preds
        except Exception as e:
            logger.warning(f"Prophet predict error: {e}")

    if bundle["xgboost"] and len(recent_prices) >= 30:
        try:
            preds = _predict_xgboost(bundle["xgboost"], recent_prices, target_date, horizon_days)
            all_predictions["xgboost"] = preds
        except Exception as e:
            logger.warning(f"XGBoost predict error: {e}")

    if bundle["arima"]:
        try:
            preds = _predict_arima(bundle["arima"], horizon_days)
            all_predictions["arima"] = preds
        except Exception as e:
            logger.warning(f"ARIMA predict error: {e}")

    if bundle["mlp"] and len(recent_prices) >= 30:
        try:
            preds = _predict_mlp(bundle["mlp"], recent_prices, target_date, horizon_days)
            all_predictions["mlp"] = preds
        except Exception as e:
            logger.warning(f"MLP predict error: {e}")

    # ── Select best model ─────────────────────────────────────────────────────
    metrics = bundle.get("metrics") or {}
    model_metrics = metrics.get("models", {})
    best_model = metrics.get("best_model", "prophet")

    # Fallback: pick the first available model if best isn't available
    if best_model not in all_predictions:
        best_model = next(iter(all_predictions), None)

    if not all_predictions or best_model is None:
        # Last resort: return a trend-based estimate
        cfg = CROPS[crop]
        estimated = cfg["base_price"] + cfg["trend_per_year"] * 5
        return {
            "crop": crop,
            "current_price": round(estimated, 2),
            "predicted_price": round(estimated * 1.02, 2),
            "predictions": [round(estimated * 1.02, 2)] * horizon_days,
            "best_model": "fallback",
            "model_comparison": {},
            "error": "No trained models found. Please run training first.",
            "black_swan_warning": None,
        }

    best_predictions = all_predictions[best_model]
    
    # Anchor predictions to live price if available
    base_pred = float(np.mean(best_predictions[:7]))
    current_price = round(live_current_price if live_current_price else (recent_prices[-1] if recent_prices else base_pred), 2)
    
    # Adjust prediction relative to live price gap
    adjustment = current_price - base_pred
    adjusted_predictions = [round(p + adjustment, 2) for p in best_predictions]
    predicted_price = round(float(np.mean(adjusted_predictions[:7])), 2)

    # Calculate Sell/Hold Recommendation based on 15-day trend
    price_in_15_days = adjusted_predictions[14] if len(adjusted_predictions) > 14 else adjusted_predictions[-1]
    expected_change = price_in_15_days - current_price
    percent_change = (expected_change / current_price) * 100
    
    if percent_change > 2.0:
        recommendation = "HOLD"
        reason = f"Prices are expected to rise by {percent_change:.1f}% in the next 15 days."
    elif percent_change < -2.0:
        recommendation = "SELL"
        reason = f"Prices are expected to drop by {abs(percent_change):.1f}% in the next 15 days."
    else:
        recommendation = "HOLD"
        reason = "Prices are expected to remain stable."

    # ── Black Swan context ────────────────────────────────────────────────────
    black_swan_info = None
    active_event = get_active_black_swan(target_date)
    if active_event:
        black_swan_info = {
            "label": active_event["label"],
            "factor": active_event["factor"],
            "message": f"⚠️ Active market disruption: {active_event['label']} "
                       f"(price elevated by ~{int((active_event['factor']-1)*100)}%)",
        }

    # ── Model comparison table ────────────────────────────────────────────────
    comparison = {}
    model_labels = {
        "prophet": "Prophet (Seasonal)",
        "xgboost": "XGBoost (Gradient Boost)",
        "arima": "ARIMA (Statistical)",
        "mlp": "Deep Learning (MLP)",
    }
    for m_name, m_preds in all_predictions.items():
        m_mae = model_metrics.get(m_name, {}).get("mae", None)
        m_rmse = model_metrics.get(m_name, {}).get("rmse", None)
        comparison[m_name] = {
            "label": model_labels.get(m_name, m_name),
            "predicted_price": round(float(np.mean(m_preds[:7])), 2),
            "mae": m_mae,
            "rmse": m_rmse,
            "is_best": m_name == best_model,
        }

    # ── Date labels ──────────────────────────────────────────────────────────
    date_labels = [
        (target_date + timedelta(days=i)).isoformat()
        for i in range(horizon_days)
    ]

    return {
        "crop": crop,
        "state": state,
        "current_price": current_price,
        "predicted_price": predicted_price,
        "predictions": adjusted_predictions,
        "date_labels": date_labels,
        "recommendation": recommendation,
        "recommendation_reason": reason,
        "best_model": best_model,
        "best_model_label": model_labels.get(best_model, best_model),
        "model_comparison": comparison,
        "black_swan_warning": black_swan_info,
        "horizon_days": horizon_days,
        "prediction_start": target_date.isoformat(),
    }

# ── Region-crop mapping cache ─────────────────────────────────────────────────
_region_map_cache: dict = {}

def _load_region_map() -> dict:
    """Load region_crop_mapping.json once and cache it."""
    global _region_map_cache
    if _region_map_cache:
        return _region_map_cache
    path = BASE_DIR / "app" / "data" / "region_crop_mapping.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            _region_map_cache = json.load(f)
        logger.info("Loaded region_crop_mapping.json — "
                    f"{_region_map_cache.get('total_unique_crops', '?')} crops, "
                    f"{_region_map_cache.get('total_districts', '?')} districts")
    else:
        logger.warning("region_crop_mapping.json not found. Run build_region_crop_map.py")
        _region_map_cache = {}
    return _region_map_cache


def predict_crop(location: str) -> dict:
    """
    Predict the best crops for a location using a 3-tier approach:

    TIER 1 (Best) — Data-driven: region_crop_mapping.json
        Real mandi transaction data (2023-2025) tells us which crops
        are ACTUALLY grown in each district/state. Covers 400-600+ crops.

    TIER 2 (Fallback) — Soil + weather scoring: crop_dataset.json
        If region map not built yet, score crops by soil/temp/rain match.

    TIER 3 (Last resort) — Hardcoded defaults by soil type.
    """
    import json
    from app.data.ingestion import DataIngestion

    # ── 1. Live weather ─────────────────────────────────────────────────────
    weather   = DataIngestion.fetch_live_weather(location)
    temp      = weather.get("temperature", 25.0)
    rain      = weather.get("rainfall", 0.0)
    humidity  = weather.get("humidity", 50.0)

    # Effective seasonal rainfall estimate (OWM returns 1h rain, often 0)
    if rain > 0:
        effective_rain = rain
    elif humidity > 75:
        effective_rain = 200.0   # High-humidity / coastal
    elif humidity > 60:
        effective_rain = 150.0   # Moderate humid
    else:
        effective_rain = 40.0    # Semi-arid / dry

    # ── 2. Soil + coastal detection ─────────────────────────────────────────
    soil_type        = "Alluvial Soil"
    is_coastal       = False
    loc_lower        = location.lower().strip()
    coastal_districts = []
    matched_by       = "default"

    try:
        geo_path = BASE_DIR / "app" / "data" / "geo_soil_mapping.json"
        if geo_path.exists():
            with open(geo_path, "r") as f:
                geo = json.load(f)

            coastal_districts = geo.get("coastal_districts", [])

            # District match (most specific)
            for dist_key, soil in geo.get("districts", {}).items():
                if dist_key in loc_lower:
                    soil_type  = soil
                    matched_by = f"district:{dist_key}"
                    break
            else:
                # State match
                for state_key, soil in geo.get("states", {}).items():
                    if state_key in loc_lower:
                        soil_type  = soil
                        matched_by = f"state:{state_key}"
                        break

            is_coastal = (
                soil_type == "Coastal Alluvial Soil"
                or any(cd in loc_lower for cd in coastal_districts)
                or humidity > 78
            )
    except Exception as e:
        logger.warning(f"Geo mapping load failed: {e}")

    # ── 3. TIER 1 — Data-driven region lookup ───────────────────────────────
    region_crops: list[str] = []   # ordered by historical frequency
    data_source  = "manual_dataset"

    try:
        rmap = _load_region_map()
        if rmap:
            districts_db = rmap.get("districts", {})
            states_db    = rmap.get("states", {})

            # Try district match first
            for dist_key, dinfo in districts_db.items():
                if dist_key.lower() in loc_lower or loc_lower in dist_key.lower():
                    region_crops = dinfo.get("top_crops", [])
                    data_source  = f"mandi_data:district:{dist_key}"
                    break

            # Try state match if district not found
            if not region_crops:
                for state_key, sinfo in states_db.items():
                    if state_key.lower() in loc_lower or loc_lower in state_key.lower():
                        region_crops = sinfo.get("top_crops", [])
                        data_source  = f"mandi_data:state:{state_key}"
                        break
    except Exception as e:
        logger.warning(f"Region map lookup failed: {e}")

    # ── 4. TIER 2 — Soil/weather scored dataset (used when region map lacks data) ─
    scored_crops: list[dict] = []   # [{crop: item_dict, score: int}]

    try:
        crop_db_path = BASE_DIR / "app" / "data" / "crop_dataset.json"
        if crop_db_path.exists():
            with open(crop_db_path, "r") as f:
                dataset = json.load(f)

            extended_soils = {soil_type}
            if soil_type == "Coastal Alluvial Soil":
                extended_soils.update(["Laterite Soil", "Sandy Soil", "Alluvial Soil"])

            for item in dataset:
                score = 0
                if soil_type in item["suitable_soils"]:
                    score += 5
                elif extended_soils & set(item["suitable_soils"]):
                    score += 2
                if item["min_temp"] <= temp <= item["max_temp"]:
                    score += 3
                if item["min_rain"] <= effective_rain <= item["max_rain"]:
                    score += 3
                if is_coastal and item["crop"] in COASTAL_CROPS:
                    score += 4
                if humidity > 70 and item["crop"] in (
                    "Coconut", "Banana", "Rice", "Arecanut", "Black Pepper",
                    "Rubber", "Tea", "Cardamom", "Ginger", "Jute"
                ):
                    score += 2
                if score > 0:
                    scored_crops.append({"crop": item, "score": score})

            scored_crops.sort(key=lambda x: x["score"], reverse=True)
    except Exception as e:
        logger.warning(f"Crop dataset load failed: {e}")

    # ── 5. Merge results ────────────────────────────────────────────────────
    # If region_crops from mandi data is available, use it as primary order.
    # Enrich with details from crop_dataset where names match.
    crop_detail_map = {}
    for sc in scored_crops:
        crop_detail_map[sc["crop"]["crop"].lower()] = sc["crop"]

    final_list: list[dict] = []   # [{name, description, water_source, source}]

    if region_crops:
        # TIER 1: use real mandi order (most traded = most relevant)
        # Re-score them to filter out weather-incompatible crops
        for crop_name in region_crops:
            detail = crop_detail_map.get(crop_name.lower())
            if detail:
                # Cross-check weather compatibility via dataset
                temp_ok = detail["min_temp"] <= temp <= detail["max_temp"]
                rain_ok = detail["min_rain"] <= effective_rain <= detail["max_rain"]
                if not (temp_ok or rain_ok):
                    continue   # Skip clearly incompatible crops
                final_list.append({
                    "name":        crop_name,
                    "description": detail.get("description", f"Actively traded in this region's mandis."),
                    "water_source": detail.get("water_source", "Varies"),
                    "source":      "mandi_data",
                })
            else:
                # Crop not in our detail DB — still include from mandi data
                final_list.append({
                    "name":        crop_name,
                    "description": f"Historically traded in local mandis in this region.",
                    "water_source": "Varies by season",
                    "source":      "mandi_data",
                })

    # If TIER 1 produced < 3 results, top up from TIER 2 scored dataset
    existing_names = {c["name"].lower() for c in final_list}
    for sc in scored_crops:
        if len(final_list) >= 20:
            break
        cname = sc["crop"]["crop"]
        if cname.lower() not in existing_names:
            final_list.append({
                "name":        cname,
                "description": sc["crop"].get("description", ""),
                "water_source": sc["crop"].get("water_source", "Varies"),
                "source":      "soil_weather_model",
            })
            existing_names.add(cname.lower())

    # ── 6. TIER 3 — absolute fallback ──────────────────────────────────────
    if not final_list:
        fallback_name = "Coconut" if is_coastal else "Wheat"
        final_list = [{
            "name":        fallback_name,
            "description": "Recommended based on general regional conditions.",
            "water_source": "Rainfed" if is_coastal else "Canal Irrigation",
            "source":      "fallback",
        }]

    primary   = final_list[0]
    alts      = final_list[1:6]    # Up to 5 alternatives

    # ── 7. Soil badge & reasoning ────────────────────────────────────────────
    soil_badge_map = {
        "Coastal Alluvial Soil": "🌊 Coastal Alluvial",
        "Laterite Soil":         "🟤 Laterite",
        "Alluvial Soil":         "🟡 Alluvial",
        "Black Soil":            "⬛ Black (Regur)",
        "Red Soil":              "🔴 Red Soil",
        "Mountain Soil":         "🏔️ Mountain",
        "Desert Soil":           "🏜️ Desert",
        "Sandy Soil":            "🏖️ Sandy",
    }
    soil_badge = soil_badge_map.get(soil_type, soil_type)

    context_parts = []
    if is_coastal:
        context_parts.append(
            f"📍 Coastal region detected (humidity {humidity:.0f}%, "
            f"estimated seasonal rainfall {effective_rain:.0f} mm)."
        )
    if data_source.startswith("mandi_data"):
        context_parts.append(
            f"✅ Based on real mandi trading data for your region — "
            f"{len(region_crops)} crops historically cultivated here."
        )
    context_parts.append(
        f"Top recommendation: {primary['name']} — suited to {soil_badge} soil "
        f"at {temp:.1f}°C. {primary.get('description', '')}"
    )
    reasoning = " ".join(context_parts)

    return {
        "location":          location,
        "inferred_soil":     soil_type,
        "soil_badge":        soil_badge,
        "is_coastal":        is_coastal,
        "recommended_crop":  primary["name"],
        "reasoning":         reasoning,
        "water_source":      primary.get("water_source", "Varies"),
        "weather_data":      weather,
        "effective_rain":    round(effective_rain, 1),
        "data_source":       data_source,
        "total_regional_crops": len(region_crops) if region_crops else len(scored_crops),
        "alternative_crops": [
            {
                "name":   c["name"],
                "reason": (
                    "Grown in local mandis" if c["source"] == "mandi_data"
                    else f"Suits {soil_type}"
                ) + (" 🌊" if is_coastal and c["name"] in COASTAL_CROPS else "")
            }
            for c in alts
        ],
    }


def get_crop_info(crop: str) -> dict:
    """Return basic info and current model status for a crop."""
    crop = crop.lower()
    if crop not in CROPS:
        return {"error": f"Unknown crop: {crop}"}

    bundle = _load_models(crop)
    models_available = [k for k in ["prophet", "xgboost", "arima", "mlp"] if bundle[k] is not None]
    metrics = bundle.get("metrics") or {}

    return {
        "crop": crop,
        "models_trained": models_available,
        "best_model": metrics.get("best_model", "none"),
        "model_metrics": metrics.get("models", {}),
        "ready": len(models_available) > 0,
    }
