# AgroIntel v4.0 — API Endpoint Documentation

## Overview

AgroIntel v4.0 exposes a RESTful FastAPI backend for crop price forecasting, Mandi market lookup, system health monitoring, and multi-stage crop recommendations.

---

## 1. System & Health Endpoints

### `GET /api/version`
- **Description**: Returns dynamic system version configuration.
- **Response `200 OK`**:
  ```json
  {
    "project": "AgroIntel",
    "project_version": "4.0.0",
    "api_version": "v1",
    "ml_pipeline_version": "1.0.0",
    "feature_version": "4.0.0",
    "dataset_version": "2019-2024-v1",
    "weather_version": "open-meteo-monthly-v1",
    "model_registry_version": "4.0.0",
    "random_forest_version": "RandomForestClassifier-100-trees-v4.0.0"
  }
  ```

### `GET /health`
- **Description**: Health status monitoring endpoint.
- **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "price_models": true,
    "crop_model": true,
    "registry_loaded": true,
    "weather_api": "reachable",
    "market_api": "reachable",
    "uptime_seconds": 124.5
  }
  ```

### `GET /api/models`
- **Description**: Returns model registry metadata and trained performance metrics (MAE, RMSE, training dates).

---

## 2. Price Prediction & Market Endpoints

### `GET /api/predict/price`
- **Query Parameters**:
  - `crop` (required): `wheat` | `rice` | `maize` | `potato` | `onion`
  - `state` (optional): Indian state name
  - `horizon_days` (optional): `7` | `15` | `30` | `60` | `90` (default 30)
- **Response `200 OK`**:
  ```json
  {
    "crop": "wheat",
    "production_model": "prophet",
    "current_price": 2866.34,
    "forecast_horizon": 30,
    "average_price": 3012.21,
    "trend": "UPWARD",
    "trend_strength": "MEDIUM",
    "confidence": 74.8,
    "decision": "HOLD",
    "decision_score": {
      "current_price": 2866.34,
      "predicted_average_price": 3012.21,
      "expected_change_percent": 5.09,
      "estimated_storage_cost_percent": 2.0,
      "estimated_net_gain_percent": 3.09,
      "decision_reason": "Predicted price increase (+5.1%) significantly exceeds estimated 30-day storage costs (2.0%). Holding inventory is profitable."
    },
    "daily_predictions": [
      { "day": 1, "predicted_price": 2989.83, "lower_bound": 2908.6, "upper_bound": 3071.06 }
    ]
  }
  ```

---

## 3. Crop Recommendation Endpoint

### `POST /api/predict/crop`
- **Request Body (`application/json`)**:
  ```json
  {
    "state": "Maharashtra",
    "district": "Pune",
    "season": "Kharif",
    "n": 55.0,
    "p": 30.0,
    "k": 65.0,
    "ph": 7.8
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "state": "Maharashtra",
    "district": "Pune",
    "season": "Kharif",
    "soil_source": "geo_mapping",
    "recommended_crops": [
      {
        "crop": "onion",
        "rank": 1,
        "raw_rf_probability": 0.05,
        "normalized_rf_probability": 1.0,
        "suitability_score": 90.6,
        "score_breakdown": {
          "random_forest": 40.0,
          "soil": 16.8,
          "weather": 13.8,
          "district": 10.0,
          "season": 10.0,
          "total": 90.6
        },
        "reasons": [
          "High soil suitability for Black Soil.",
          "Favorable seasonal climate in Kharif.",
          "Historically successful commercial crop in Pune district."
        ]
      }
    ]
  }
  ```

---
*AgroIntel v4.0 API Endpoint Reference*
