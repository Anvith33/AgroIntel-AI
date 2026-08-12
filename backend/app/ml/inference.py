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
    "rice":      {"base_price": 2300, "seasonal_amplitude": 150, "trend_per_year": 100, "noise_std": 50},
    "maize":     {"base_price": 1600, "seasonal_amplitude": 130, "trend_per_year": 90,  "noise_std": 50},
    "potato":    {"base_price": 1300, "seasonal_amplitude": 200, "trend_per_year": 80,  "noise_std": 60},
    "onion":     {"base_price": 1800, "seasonal_amplitude": 400, "trend_per_year": 100, "noise_std": 120},
}

# ── Crop Seasons Association mapping ─────────────────────────────────────────
CROP_SEASONS = {
    "Arecanut": ["Kharif", "Rabi", "Zaid"],  # Perennial
    "Coconut": ["Kharif", "Rabi", "Zaid"],   # Perennial
    "Banana": ["Kharif", "Rabi", "Zaid"],    # Perennial
    "Black Pepper": ["Kharif", "Rabi", "Zaid"], # Perennial
    "Cardamom": ["Kharif", "Rabi", "Zaid"],     # Perennial
    "Ginger": ["Kharif"],
    "Turmeric": ["Kharif"],
    "Coffee": ["Kharif", "Rabi", "Zaid"],    # Perennial
    "Rice": ["Kharif"],
    "Paddy (Coastal/Kharif)": ["Kharif"],
    "Wheat": ["Rabi"],
    "Maize": ["Kharif", "Rabi"],
    "Cotton": ["Kharif"],
    "Sugarcane": ["Kharif", "Rabi", "Zaid"], # Perennial / long-duration
    "Cashew": ["Kharif", "Rabi", "Zaid"],    # Perennial
    "Groundnut": ["Kharif", "Rabi"],
    "Soybean": ["Kharif"],
    "Mustard": ["Rabi"],
    "Sunflower": ["Kharif", "Rabi", "Zaid"],
    "Millets (Ragi/Jowar)": ["Kharif", "Rabi"],
    "Bajra (Pearl Millet)": ["Kharif"],
    "Jute": ["Kharif"],
    "Tapioca (Cassava)": ["Kharif", "Rabi", "Zaid"], # Long-duration tuber
    "Betel Leaf": ["Kharif", "Rabi", "Zaid"],       # Perennial
    "Mango": ["Kharif", "Rabi", "Zaid"],            # Perennial
    "Rubber": ["Kharif", "Rabi", "Zaid"],           # Perennial
    "Tea": ["Kharif", "Rabi", "Zaid"]               # Perennial
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
    weeks = max(1, horizon_days // 7 + 1)
    forecast = model.forecast(steps=weeks)
    vals = forecast.values if hasattr(forecast, "values") else forecast
    daily = []
    for val in vals:
        daily.extend([float(val)] * 7)
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
        crop: crop name (wheat, rice, maize, onion, potato)
        state: State name for market price fetching (affects Mandi lookup only)
        horizon_days: number of days to forecast ahead

    Returns:
        dict with prediction results, model comparison, observation metadata,
        and SELL/HOLD/WAIT advisory with reasoning.

    SCIENTIFIC NOTE:
        Trained features: lag_1, lag_7, lag_14, lag_30, rolling_mean_7, rolling_mean_30,
        month, season, monthly_avg_temp, monthly_total_rainfall, black_swan.
        State is NOT a model feature. ML forecast is crop-level (same across states).
        Current Mandi price DOES vary by state (separate cache key per crop:state).
    """
    crop = crop.lower()
    if crop not in CROPS:
        raise ValueError(f"Unsupported crop: '{crop}'. Choose from: {list(CROPS.keys())}")

    bundle = _load_models(crop)
    target_date = date.today() + timedelta(days=1)
    recent_prices = _get_recent_prices(bundle["data_tail"])
    
    # ── Fetch Live Mandi Data ──────────────────────────────────────────────────
    from app.data.ingestion import DataIngestion
    live_data = DataIngestion.fetch_live_market_data(crop, state)
    live_current_price = live_data.get("current_price")
    price_data_source  = live_data.get("data_source", "simulator_fallback")
    price_cached_time  = live_data.get("cached_time")

    # Extract observation date from arrival_date field (if available)
    observation_date_str = live_data.get("arrival_date") or live_data.get("cached_time", "")
    if observation_date_str and "T" in str(observation_date_str):
        observation_date_str = str(observation_date_str).split("T")[0]

    # Compute data age in days
    data_age_days = None
    if observation_date_str:
        try:
            from datetime import datetime as _dt
            obs_d = _dt.strptime(str(observation_date_str), "%Y-%m-%d").date()
            data_age_days = (date.today() - obs_d).days
        except Exception:
            pass

    if data_age_days is None:
        age_h = live_data.get("data_age_hours")
        if isinstance(age_h, (int, float)):
            data_age_days = int(age_h // 24)

    market_name = live_data.get("market") or state or "National"

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
    # Evaluated best models per crop from price_model_evaluation.json
    EVALUATED_BEST_MODELS = {
        "rice": "xgboost",
        "wheat": "prophet",
        "maize": "xgboost",
        "onion": "xgboost",
        "potato": "xgboost",
    }
    
    preferred_model = EVALUATED_BEST_MODELS.get(crop, "prophet")
    if preferred_model in all_predictions:
        best_model = preferred_model
    else:
        best_model = next(iter(all_predictions), None)

    if not all_predictions or best_model is None:
        return {
            "available":          False,
            "crop":               crop,
            "state":              state,
            "status":             "FORECAST_UNAVAILABLE",
            "current_price":      live_current_price,
            "predicted_price":    None,
            "predictions":        [],
            "best_model":         "None",
            "model_comparison":   {},
            "message":            "Current Mandi price is available, but a validated future forecast could not be generated.",
            "black_swan_warning": None,
            "observation_date":   observation_date_str or None,
            "market_name":        market_name,
            "data_age_days":      data_age_days,
            "price_data_source":  price_data_source,
            "price_cached_time":  price_cached_time,
            "forecast_scope":     "Crop-level ML forecast (state not a model feature)",
        }

    # 30-day forecast series generated directly by trained ML model
    best_predictions = [round(float(p), 2) for p in all_predictions[best_model]]
    
    # Current observed Mandi modal price
    current_price   = round(float(live_current_price if live_current_price else (recent_prices[-1] if recent_prices else 2000.0)), 2)

    # Predicted price at horizon from ML model (no multipliers)
    predicted_price = round(float(best_predictions[horizon_days - 1] if len(best_predictions) >= horizon_days else best_predictions[-1]), 2)

    percent_change  = round(((predicted_price - current_price) / current_price) * 100.0, 2)

    # ── SELL / HOLD / WAIT Decision ──────────────────────────────────────────
    # High uncertainty crops get wider threshold (onion MAE=156, potato MAE=93)
    HIGH_UNCERTAINTY_CROPS = {"onion", "potato"}
    threshold = 5.0 if crop in HIGH_UNCERTAINTY_CROPS else 3.0

    if data_age_days is not None and data_age_days > 14:
        recommendation = "WAIT"
        reason = (f"The latest Mandi price observation is {data_age_days} days old. "
                  f"Market conditions may have changed. "
                  f"Verify current local Mandi rates before making a transaction decision.")
    elif abs(percent_change) < threshold:
        recommendation = "WAIT"
        reason = (f"The {horizon_days}-day forecast indicates a marginal movement of "
                  f"{percent_change:+.1f}% — within model uncertainty bounds. "
                  f"Prices are expected to remain relatively stable.")
    elif percent_change <= -threshold:
        recommendation = "SELL"
        reason = (f"The {horizon_days}-day forecast indicates a price decline of approximately "
                  f"{abs(percent_change):.1f}% from Rs.{current_price:,.0f} to Rs.{predicted_price:,.0f}. "
                  f"Selling at the current observed Mandi price may reduce downside risk.")
    else:
        recommendation = "HOLD"
        reason = (f"The {horizon_days}-day forecast indicates a price increase of approximately "
                  f"{percent_change:.1f}% from Rs.{current_price:,.0f} to Rs.{predicted_price:,.0f}. "
                  f"Holding may provide a better expected selling price.")

    # ── Black Swan context ────────────────────────────────────────────────────
    black_swan_info = None
    active_event = get_active_black_swan(target_date)
    if active_event:
        black_swan_info = {
            "label":   active_event["label"],
            "factor":  active_event.get("factor", 1.0),
            "message": f"Active market disruption: {active_event['label']}. Prices may be significantly affected.",
        }
        if recommendation == "HOLD" and percent_change < 8.0:
            recommendation = "WAIT"
            reason = (f"An active market disruption ({active_event['label']}) "
                      f"introduces significant price uncertainty. Verify local conditions before acting.")

    # ── Model comparison table ────────────────────────────────────────────────
    metrics       = bundle.get("metrics") or {}
    model_metrics = metrics.get("models", {})
    comparison    = {}
    model_labels  = {
        "prophet": "Prophet (Seasonal)",
        "xgboost": "XGBoost (Gradient Boost)",
        "arima":   "ARIMA (Statistical)",
        "mlp":     "Deep Learning (MLP)",
    }
    for m_name, m_preds in all_predictions.items():
        m_mae  = model_metrics.get(m_name, {}).get("mae", None)
        m_rmse = model_metrics.get(m_name, {}).get("rmse", None)
        comparison[m_name] = {
            "label":           model_labels.get(m_name, m_name),
            "predicted_price": round(float(m_preds[horizon_days - 1] if len(m_preds) >= horizon_days else m_preds[-1]), 2),
            "mae":             m_mae,
            "rmse":            m_rmse,
            "is_best":         m_name == best_model,
        }

    # ── Date labels for graph ─────────────────────────────────────────────────
    date_labels = [
        (target_date + timedelta(days=i)).isoformat()
        for i in range(horizon_days)
    ]

    return {
        "available":             True,
        "crop":                  crop,
        "state":                 state,
        "current_price":         current_price,
        "predicted_price":       predicted_price,
        "predictions":           best_predictions,
        "date_labels":           date_labels,
        "recommendation":        recommendation,
        "recommendation_reason": reason,
        "best_model":            best_model,
        "best_model_label":      model_labels.get(best_model, best_model),
        "model_comparison":      comparison,
        "black_swan_warning":    black_swan_info,
        "horizon_days":          horizon_days,
        "prediction_start":      target_date.isoformat(),
        # ── Observation / freshness transparency ──
        "observation_date":      observation_date_str or None,
        "market_name":           market_name,
        "data_age_days":         data_age_days,
        "price_data_source":     price_data_source,
        "price_cached_time":     price_cached_time,
        "price_data_quality":    live_data.get("data_quality", "unknown"),
        "price_age_hours":       live_data.get("data_age_hours"),
        "price_source_note":     live_data.get("note", ""),
        # ── Forecast scope disclaimer ──
        "forecast_scope": (
            "Crop-level 30-day ML forecast. "
            "State is not a trained feature; the ML forecast is the same across states for the same crop. "
            "The current Mandi price varies by state/market."
        ),
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


def _get_current_season() -> str:
    """Return the current Indian agricultural season based on the current month."""
    month = date.today().month
    if 6 <= month <= 10:
        return "Kharif"
    elif 11 <= month <= 3:
        return "Rabi"
    else:
        return "Zaid"


SEASON_LABELS = {
    "Kharif": "🌧️ Kharif (Monsoon, Jun–Oct)",
    "Rabi":   "❄️ Rabi (Winter, Nov–Mar)",
    "Zaid":   "☀️ Zaid (Summer, Apr–May)",
}


def predict_crop(location: str, season: str = "Auto",
                 lat: float = None, lon: float = None) -> dict:
    """
    Predict the best crops for a location using a 4-tier approach:

    TIER 0 (Best, if GPS available):
        - SoilGrids API (free, 250m satellite) → real soil type at GPS coord
        - NASA MODIS NDVI via OpenLandMap → vegetation & growing conditions
        - Agro-Zone Validator → filter crops that can't be grown in this climate

    TIER 1 — Data-driven: region_crop_mapping.json
        Real mandi transaction data (2023-2025) tells us which crops
        are ACTUALLY grown in each district/state.

    TIER 2 — Soil + weather scoring: crop_dataset.json

    TIER 3 — Hardcoded defaults by soil type.
    """
    import json
    from app.data.ingestion import DataIngestion
    from app.data.soil_classifier import classify_soil
    from app.data.satellite_service import get_satellite_data, get_ndvi_crop_filter
    from app.data.agro_zone_validator import filter_crops_for_region

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

    # ── 2. Soil detection — GPS-first, then geo_soil_mapping fallback ────────
    soil_type        = "Alluvial Soil"
    is_coastal       = False
    loc_lower        = location.lower().strip()
    coastal_districts = []
    matched_by       = "default"
    satellite_soil_data = None   # Will hold SoilGrids result if GPS given

    # ── TIER 0A: GPS-based satellite soil detection ──────────────────────────
    if lat is not None and lon is not None:
        try:
            satellite_soil_data = classify_soil(lat, lon)
            soil_type  = satellite_soil_data["soil_type"]
            matched_by = f"soilgrids_satellite:({lat:.4f},{lon:.4f})"
            logger.info(f"SoilGrids soil for ({lat},{lon}): {soil_type}")
        except Exception as e:
            logger.warning(f"Satellite soil classification failed: {e}")

    # Fallback to geo_soil_mapping.json if no GPS or satellite failed
    if satellite_soil_data is None or matched_by == "default":
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
        except Exception as e:
            logger.warning(f"Geo mapping load failed: {e}")

    is_coastal = (
        soil_type == "Coastal Alluvial Soil"
        or any(cd in loc_lower for cd in coastal_districts)
        or humidity > 78
    )

    # ── TIER 0B: Satellite NDVI + soil moisture ──────────────────────────────
    satellite_data = None
    ndvi           = None
    soil_moisture  = None

    if lat is not None and lon is not None:
        try:
            satellite_data = get_satellite_data(
                lat, lon,
                temperature=temp, humidity=humidity, rainfall=effective_rain
            )
            ndvi          = satellite_data.get("ndvi")
            soil_moisture = satellite_data.get("soil_moisture_estimated")
            logger.info(f"Satellite data for ({lat},{lon}): NDVI={ndvi}, SM={soil_moisture}")
        except Exception as e:
            logger.warning(f"Satellite data fetch failed: {e}")

    if satellite_data is None:
        # Estimate from weather when no GPS given
        from app.data.satellite_service import _estimate_ndvi_from_weather
        ndvi          = _estimate_ndvi_from_weather(temp, humidity, effective_rain)
        soil_moisture = min(0.5, (effective_rain / 500.0) * (humidity / 100.0) + 0.05)
        satellite_data = {
            "ndvi":                    ndvi,
            "ndvi_label":              "Estimated",
            "ndvi_status":             "estimated",
            "soil_moisture_estimated": soil_moisture,
            "moisture_label":          "Estimated",
            "moisture_status":         "estimated",
            "satellite_source":        "weather_estimate",
            "suitability_score":       50,
            "crop_warnings":           [],
        }

    # ── 3. TIER 1 — Data-driven region lookup ───────────────────────────────
    region_crops: list[str] = []   # ordered by historical frequency
    data_source  = "manual_dataset"

    # Non-field produce — traded in mandis but are NOT planting recommendations
    # (includes perishable vegetables, herbs, minor fruit/condiment items)
    MARKET_VEGETABLES = {
        # Perishable vegetables
        "tomato", "onion", "potato", "brinjal", "bhindi (ladies finger)",
        "cabbage", "cauliflower", "bottle gourd", "bitter gourd", "ridge gourd",
        "snake gourd", "snakeguard", "ash gourd", "ashgourd", "pumpkin",
        "cucumber", "carrot", "radish", "raddish", "spinach", "coriander",
        "methi (fenugreek)", "green chilli", "capsicum", "garlic", "drumstick",
        "cluster beans", "french beans", "peas (fresh)", "green peas",
        "onion green", "amaranthus", "cowpea (veg)", "banana - green",
        # Herbs & leafy greens
        "coriander (leaves)", "mint (pudina)", "curry leaves", "fenugreek leaves",
        "spinach", "palak", "methi",
        # Minor items not suitable as primary recommendations
        "beans", "green avare (w)", "chow chow", "beetroot", "turnip",
        "parwal (pointed gourd)", "tinda", "yam", "colocasia", "elephant yam",
        "raw banana", "lemon", "lime",
    }

    # Proper agricultural field crops — these are the ones we want to RECOMMEND
    # (grains, pulses, oilseeds, major cash crops, plantation crops)
    PROPER_FIELD_CROPS = {
        "rice", "paddy (dhan)(common)", "paddy (coastal/kharif)", "wheat", "maize",
        "bajra (pearl millet/cumbu)", "jowar", "ragi", "millets (ragi/jowar)",
        "sorghum", "barley", "soyabean", "soybean", "groundnut", "mustard",
        "sunflower", "sesame", "linseed", "safflower", "cotton",
        "arhar (tur/red gram)(whole)", "bengal gram (gram)(whole)", "chickpea",
        "green gram (moong)(whole)", "black gram (urd beans)(whole)", "lentil",
        "sugarcane", "jute", "ginger", "turmeric", "cardamom",
        "black pepper", "coffee", "tea", "rubber", "coconut", "arecanut",
        "banana", "mango", "cashew nut",
        "cummin seed (jeera)", "ajwain", "coriander seed", "fennel",
    }

    # Field crops to prioritize per season — pushed to the TOP of recommendations
    SEASON_PRIORITY = {
        "Kharif": [
            "Rice", "Paddy (Dhan)(Common)", "Maize", "Cotton", "Soyabean",
            "Groundnut", "Bajra (Pearl Millet/Cumbu)", "Arhar (Tur/Red Gram)(Whole)",
            "Sugarcane", "Jute", "Sunflower", "Ginger", "Turmeric",
        ],
        "Rabi": [
            "Wheat", "Mustard", "Bengal Gram (Gram)(Whole)", "Chickpea",
            "Lentil", "Barley", "Sunflower", "Peas (Dry)", "Linseed", "Maize",
        ],
        "Zaid": [
            "Maize", "Groundnut", "Sunflower", "Green Gram (Moong)(Whole)",
            "Cowpea", "Bajra (Pearl Millet/Cumbu)", "Watermelon",
        ],
    }

    # Common alternate spellings: new name → canonical name in our DB
    DISTRICT_ALIASES: dict[str, str] = {
        # Karnataka
        "mysuru":          "mysore",
        "mysore city":     "mysore",
        "bengaluru":       "bangalore",
        "bengaluru urban": "bangalore",
        "bengaluru rural": "bangalore",
        "belagavi":        "belgaum",
        "hubballi":        "hubli",
        "shivamogga":      "shimoga",
        "vijayapura":      "bijapur",
        "kalaburagi":      "gulbarga",
        "ballari":         "bellary",
        "tumakuru":        "tumkur",
        "davanagere":      "davangere",
        # Tamil Nadu
        "chennai":         "madras",
        "kancheepuram":    "kanchipuram",
        "tiruchirapalli":  "trichy",
        "tirunelveli":     "tirunelveli",
        # Andhra Pradesh
        "visakhapatnam":   "visakhapatanam",
        # Uttar Pradesh
        "prayagraj":       "allahabad",
        # Maharashtra
        "aurangabad":      "aurangabad",
        "mumbai":          "bombay",
        # West Bengal
        "kolkata":         "calcutta",
        # Odisha
        "bhubaneswar":     "bhubaneswar",
        # General
        "new delhi":       "delhi",
    }

    def _normalize_district(name: str) -> str:
        """Apply alias substitutions so both old & new names resolve to DB key."""
        n = name.lower().strip()
        for alias, canonical in DISTRICT_ALIASES.items():
            if alias in n:
                return canonical
        return n

    try:
        rmap = _load_region_map()
        if rmap:
            districts_db = rmap.get("districts", {})
            states_db    = rmap.get("states", {})
            loc_norm     = _normalize_district(loc_lower)

            # Try district match first — check both original and normalized name
            for dist_key, dinfo in districts_db.items():
                dk = dist_key.lower()
                if dk == loc_norm or dk in loc_norm or loc_norm in dk:
                    region_crops = dinfo.get("top_crops", [])
                    data_source  = f"mandi_data:district:{dist_key}"
                    break

            # Try state match if district not found
            if not region_crops:
                for state_key, sinfo in states_db.items():
                    if state_key.lower() in loc_lower or loc_lower in state_key.lower():
                        state_crops = sinfo.get("top_crops", [])
                        # ── Filter: for non-coastal locations, drop coastal-specialist crops
                        # that dominate state-level data but don't belong inland
                        if not is_coastal:
                            state_crops = [
                                c for c in state_crops
                                if c not in COASTAL_CROPS
                                and not any(kw in c.lower() for kw in ["arecanut", "coconut", "tapioca", "rubber"])
                            ]
                        region_crops = state_crops
                        data_source  = f"mandi_data:state:{state_key}"
                        break
    except Exception as e:
        logger.warning(f"Region map lookup failed: {e}")

    # ── 4. Resolve active season ───────────────────────────────────────────
    active_season = _get_current_season() if season == "Auto" else season

    # ── 5. TIER 2 — Soil/weather scored dataset (used when region map lacks data) ─
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
                # Soil match
                if soil_type in item["suitable_soils"]:
                    score += 5
                elif extended_soils & set(item["suitable_soils"]):
                    score += 2
                # Temperature match
                if item["min_temp"] <= temp <= item["max_temp"]:
                    score += 3
                # Rainfall match
                if item["min_rain"] <= effective_rain <= item["max_rain"]:
                    score += 3
                # Coastal boost
                if is_coastal and item["crop"] in COASTAL_CROPS:
                    score += 4
                # Humidity boost for moisture-loving crops
                if humidity > 70 and item["crop"] in (
                    "Coconut", "Banana", "Rice", "Arecanut", "Black Pepper",
                    "Rubber", "Tea", "Cardamom", "Ginger", "Jute"
                ):
                    score += 2
                # ── Seasonal scoring ──────────────────────────────────────
                crop_seasons = CROP_SEASONS.get(item["crop"], [])
                if crop_seasons:
                    if active_season in crop_seasons:
                        score += 5   # Boost for in-season crops
                    else:
                        score -= 3   # Penalty for out-of-season crops

                if score > 0:
                    scored_crops.append({"crop": item, "score": score})

            scored_crops.sort(key=lambda x: x["score"], reverse=True)
    except Exception as e:
        logger.warning(f"Crop dataset load failed: {e}")


    # ── 5. Merge results ────────────────────────────────────────────────────
    crop_detail_map = {}
    for sc in scored_crops:
        crop_detail_map[sc["crop"]["crop"].lower()] = sc["crop"]

    raw_list: list[dict] = []

    if region_crops:
        for crop_name in region_crops:
            detail = crop_detail_map.get(crop_name.lower())
            if detail:
                temp_ok = detail["min_temp"] <= temp <= detail["max_temp"]
                rain_ok = detail["min_rain"] <= effective_rain <= detail["max_rain"]
                if not (temp_ok or rain_ok):
                    continue
                raw_list.append({
                    "name":        crop_name,
                    "description": detail.get("description", "Actively cultivated in this region."),
                    "water_source": detail.get("water_source", "Varies"),
                    "source":      "mandi_data",
                })
            else:
                raw_list.append({
                    "name":        crop_name,
                    "description": "Historically cultivated and traded in this region.",
                    "water_source": "Varies by season",
                    "source":      "mandi_data",
                })

    # Top-up from TIER 2 scored dataset (soil/weather model)
    existing_names = {c["name"].lower() for c in raw_list}
    for sc in scored_crops:
        if len(raw_list) >= 25:
            break
        cname = sc["crop"]["crop"]
        if cname.lower() not in existing_names:
            raw_list.append({
                "name":        cname,
                "description": sc["crop"].get("description", ""),
                "water_source": sc["crop"].get("water_source", "Varies"),
                "source":      "soil_weather_model",
            })
            existing_names.add(cname.lower())

    # ── Smart re-ranking: field crops FIRST, market vegetables LAST ─────────
    # Mandi data is flooded with tomato/onion/potato because they're traded
    # daily as perishables. A farmer asking "what should I grow?" needs field
    # crop guidance first — vegetables appear as alternatives.
    season_prio_list  = SEASON_PRIORITY.get(active_season, [])
    season_prio_lower = [p.lower() for p in season_prio_list]

    def _crop_rank(c):
        name_l = c["name"].lower()
        is_veg = name_l in MARKET_VEGETABLES
        try:
            prio_idx = season_prio_lower.index(name_l)
        except ValueError:
            prio_idx = 999
        # (bucket, position): 0=season field crop, 1=other field crop, 2=vegetable
        if is_veg:
            return (2, prio_idx)
        elif prio_idx < 999:
            return (0, prio_idx)
        else:
            return (1, 0)

    raw_list.sort(key=_crop_rank)

    # ── KEY FIX: Detect no-field-crop mandi regions ─────────────────────────
    # Some mandis (Thanjavur, Amritsar) have NO proper agricultural field crops —
    # only vegetables, herbs, minor items. Use TIER 2 for the primary recommendation.
    proper_field_in_raw = [c for c in raw_list if c["name"].lower() in PROPER_FIELD_CROPS]
    non_field_in_raw    = [c for c in raw_list if c["name"].lower() not in PROPER_FIELD_CROPS]

    if not proper_field_in_raw and scored_crops:
        logger.info(f"No field crops in mandi data for {location!r} — using TIER 2 soil/weather model")
        tier2_field = []
        seen = set()
        for sc in scored_crops:
            cname = sc["crop"]["crop"]
            if cname.lower() not in seen:
                tier2_field.append({
                    "name":        cname,
                    "description": sc["crop"].get("description", ""),
                    "water_source": sc["crop"].get("water_source", "Varies"),
                    "source":      "soil_weather_model",
                })
                seen.add(cname.lower())
        tier2_field.sort(key=_crop_rank)
        for v in non_field_in_raw:
            if v["name"].lower() not in seen:
                tier2_field.append(v)
                seen.add(v["name"].lower())
        final_list = tier2_field
    elif proper_field_in_raw:
        # Has field crops — use field crops first, then non-field as alternatives
        final_list = proper_field_in_raw + non_field_in_raw
    else:
        final_list = raw_list

    # ── 6. TIER 3 — absolute fallback ────────────────────────────────────────
    if not final_list:
        fallback_name = "Coconut" if is_coastal else ("Rice" if active_season == "Kharif" else "Wheat")
        final_list = [{
            "name":        fallback_name,
            "description": f"Recommended based on general regional conditions for {active_season} season.",
            "water_source": "Rainfed" if is_coastal else "Canal Irrigation",
            "source":      "fallback",
        }]

    # ── TIER 0C: Agro-Zone Validator — filter unrowable crops ─────────────
    # This removes crops that are traded but can't actually be grown here
    ndvi_filter = get_ndvi_crop_filter(ndvi) if ndvi is not None else {}
    validated_list = filter_crops_for_region(
        final_list,
        location=location,
        ndvi=ndvi,
        soil_moisture=soil_moisture,
        keep_min=3,
    )

    primary = validated_list[0]
    alts    = validated_list[1:8]   # Up to 7 alternatives with validation info

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

    season_label = SEASON_LABELS.get(active_season, active_season)

    context_parts = []
    context_parts.append(f"🌾 Season: {season_label}.")
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
        "location":              location,
        "inferred_soil":         soil_type,
        "soil_badge":            soil_badge,
        "is_coastal":            is_coastal,
        "recommended_crop":      primary["name"],
        "reasoning":             reasoning,
        "water_source":          primary.get("water_source", "Varies"),
        "weather_data":          weather,
        "effective_rain":        round(effective_rain, 1),
        "data_source":           data_source,
        "season":                active_season,
        "season_label":          season_label,
        "total_regional_crops":  len(region_crops) if region_crops else len(scored_crops),
        # ── Satellite & soil data ──
        "satellite_data": {
            "ndvi":              satellite_data.get("ndvi"),
            "ndvi_label":        satellite_data.get("ndvi_label"),
            "ndvi_status":       satellite_data.get("ndvi_status"),
            "moisture_label":    satellite_data.get("moisture_label"),
            "moisture_status":   satellite_data.get("moisture_status"),
            "suitability_score": satellite_data.get("suitability_score"),
            "satellite_source":  satellite_data.get("satellite_source"),
            "crop_warnings":     satellite_data.get("crop_warnings", []),
        } if satellite_data else None,
        "soil_detail": {
            "ph":        satellite_soil_data.get("ph") if satellite_soil_data else None,
            "clay_pct":  satellite_soil_data.get("clay_pct") if satellite_soil_data else None,
            "sand_pct":  satellite_soil_data.get("sand_pct") if satellite_soil_data else None,
            "source":    satellite_soil_data.get("source") if satellite_soil_data else "geo_mapping",
            "confidence": satellite_soil_data.get("confidence") if satellite_soil_data else "medium",
        },
        "gps_used":    lat is not None and lon is not None,
        "alternative_crops": [
            {
                "name":             c["name"],
                "growable":         c.get("growable", True),
                "suitability_reason": c.get("suitability_reason", ""),
                "reason": (
                    "Grown in local mandis" if c["source"] == "mandi_data"
                    else f"Suits {soil_type}"
                ) + (" 🌊" if is_coastal and c["name"] in COASTAL_CROPS else "")
                  + (" 🌾" if CROP_SEASONS.get(c["name"]) and active_season in CROP_SEASONS.get(c["name"], []) else "")
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
