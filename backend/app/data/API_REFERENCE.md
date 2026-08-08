# AgroIntel v4.0 — Complete API Reference & OpenAPI Specification

## Overview

AgroIntel v4.0 exposes a complete RESTful API suite under `/api` and `/health`. Interactive Swagger documentation is accessible at `/docs` and ReDoc at `/redoc`.

---

## 1. Endpoints Summary

### System & Health Routers
- `GET /api/version` — Get system version configuration
- `GET /health` — Get server health and component status
- `GET /api/models` — Get trained price models and crop recommendation metrics
- `GET /api/system/info` — Get real-time system diagnostics (CPU, memory, versions, uptime)
- `GET /api/demo` — Get dropdown options for frontend UI (crops, states, districts, seasons, horizons)

### Price Prediction & Market Routers
- `GET /api/predict/price` — Get multi-horizon price forecast, decision score & graph series
- `GET /api/market/latest` — Get real-time or cached mandi market price from Agmarknet API
- `POST /api/train` — Trigger asynchronous retraining of all price prediction models
- `POST /api/train/{crop}` — Retrain price models for a single crop synchronously

### Crop Recommendation & Combined Advisory Routers
- `POST /api/predict/crop` — Multi-stage crop recommendation engine
- `POST /api/advisory` — Integrated crop recommendation and price forecast advisory

---

## 2. Request & Response Payload Examples

### A. Integrated Advisory (`POST /api/advisory`)
- **Request Payload**:
  ```json
  {
    "state": "Maharashtra",
    "district": "Pune",
    "season": "Kharif",
    "crop": "wheat",
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
    "target_price_crop": "wheat",
    "combined_summary": "Recommended crop for Pune, Maharashtra (Kharif): ONION (Suitability Score: 90.6/100). Price forecast for WHEAT indicates HOLD (30-day predicted avg ₹3,012.21, estimated net gain +3.1%).",
    "crop_recommendations": [
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
        }
      }
    ],
    "price_prediction": {
      "crop": "wheat",
      "production_model": "prophet",
      "current_price": 2866.34,
      "predicted_30d_avg": 3012.21,
      "trend": "UPWARD",
      "decision": "HOLD",
      "confidence": 74.8,
      "decision_score": {
        "current_price": 2866.34,
        "predicted_average_price": 3012.21,
        "expected_change_percent": 5.09,
        "estimated_storage_cost_percent": 2.0,
        "estimated_net_gain_percent": 3.09,
        "decision_reason": "Predicted price increase (+5.1%) significantly exceeds estimated 30-day storage costs (2.0%). Holding inventory is profitable."
      }
    },
    "consolidated_reasons": [
      "High soil suitability for Black Soil (N:55, P:30, K:65, pH:7.8).",
      "Favorable seasonal climate in Kharif (27.2°C avg temp, 278.6mm rainfall).",
      "Historically successful commercial crop in Pune district (Onion).",
      "Validated as agro-climatically compatible with Maharashtra agricultural zones.",
      "Historical trend analysis indicates an UPWARD trajectory (+5.1% expected over 30 days).",
      "Net gain after 30-day storage costs (2.0%) is estimated at +3.1%."
    ],
    "response_time_ms": 12.4
  }
}
```

### B. System Diagnostics (`GET /api/system/info`)
- **Response `200 OK`**:
  ```json
  {
    "application": "AgroIntel v4.0",
    "python_version": "3.11.9",
    "fastapi_version": "0.109.2",
    "prophet_version": "1.1.5",
    "xgboost_version": "2.0.3",
    "tensorflow_available": true,
    "system_os": "Darwin 23.6.0",
    "cpu_usage_percent": 12.4,
    "memory_usage": {
      "rss_mb": 278.09,
      "vsz_mb": 4120.5,
      "memory_percent": 1.72
    },
    "loaded_models_count": 26,
    "cached_data_files_count": 14,
    "server_uptime_seconds": 184.2
  }
  ```

---
*AgroIntel v4.0 Technical Report — API Reference Documentation Complete*
