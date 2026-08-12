# AgroIntel AI — API Reference & Endpoint Documentation

**Version:** 4.1 Final | **Date:** 2026-08-12  
**Base URL:** `http://127.0.0.1:8000` (local development)

---

## 1. Health Check

### `GET /health`

Check system status and model availability.

**Response:**
```json
{
  "status": "healthy",
  "price_models": true,
  "crop_model": true,
  "registry_loaded": true,
  "weather_api": "reachable",
  "market_api": "reachable",
  "uptime_seconds": 2808.99
}
```

---

## 2. Price Prediction

### `GET /api/predict`

Get a 30-day ML price forecast for a crop.

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `crop` | string | Yes | One of: `rice`, `wheat`, `maize`, `onion`, `potato` |
| `state` | string | No | State name (affects Mandi price lookup only) |
| `horizon_days` | int | No | Forecast horizon (default: 30, max: 90) |

**Example:**
```
GET /api/predict?crop=wheat&state=Punjab&horizon_days=30
```

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `available` | bool | True if forecast was generated |
| `crop` | string | Crop name (lowercase) |
| `state` | string | State used for Mandi lookup |
| `current_price` | float | Latest observed Mandi modal price (₹/quintal) |
| `predicted_price` | float | ML forecast at horizon_days (₹/quintal) |
| `predictions` | array[float] | Day-by-day forecast series (length = horizon_days) |
| `date_labels` | array[str] | ISO dates for each forecast day |
| `recommendation` | string | `SELL`, `HOLD`, or `WAIT` |
| `recommendation_reason` | string | Human-readable rationale |
| `best_model` | string | `prophet`, `xgboost`, `arima`, `mlp` |
| `best_model_label` | string | Human-readable model name |
| `model_comparison` | object | Per-model predictions and metrics |
| `black_swan_warning` | object or null | Active disruption event details |
| `observation_date` | string or null | Date of Mandi price observation (YYYY-MM-DD) |
| `market_name` | string | Market/state for the price |
| `data_age_days` | int or null | Days since price observation |
| `price_data_source` | string | `api_data_gov_in`, `cached_api`, `msp_estimate` |
| `forecast_scope` | string | Scope disclaimer |
| `advisory` | object | `{decision, reason}` — same as recommendation |
| `forecast` | object | Nested: `{available, model, predicted_price, date_labels}` |
| `market` | object | Nested: `{current_price, observation_date, market_name, source}` |
| `horizon_days` | int | Actual horizon used |
| `prediction_start` | string | First forecast date (ISO) |

**Example response (partial):**
```json
{
  "available": true,
  "crop": "wheat",
  "state": "Punjab",
  "current_price": 2158.58,
  "predicted_price": 3048.93,
  "recommendation": "HOLD",
  "recommendation_reason": "The 30-day forecast indicates a price increase of approximately 41.2%...",
  "best_model": "prophet",
  "best_model_label": "Prophet (Seasonal)",
  "observation_date": "2026-08-12",
  "market_name": "Punjab",
  "data_age_days": 0,
  "price_data_source": "cached_api",
  "forecast_scope": "Crop-level 30-day ML forecast. State is not a trained feature...",
  "advisory": {"decision": "HOLD", "reason": "..."},
  "predictions": [2200.0, 2250.0, ...],
  "date_labels": ["2026-08-13", "2026-08-14", ...]
}
```

**When `available = false`:**
```json
{
  "available": false,
  "crop": "horse-gram",
  "message": "Price prediction is currently unavailable for this crop...",
  "forecast": {"available": false, "status": "FORECAST_UNAVAILABLE", "reason": "..."}
}
```

---

## 3. Crop Recommendation

### `POST /api/phase6/recommend`

Get district-level AI crop recommendations.

**Request body:**
```json
{
  "state": "Karnataka",
  "district": "Dakshina Kannada",
  "season": "Kharif",
  "soil_ph": 6.2,
  "n": 80,
  "p": 40,
  "k": 40,
  "previous_crop": "Rice"
}
```

| Field | Required | Description |
|---|---|---|
| `state` | Yes | State name |
| `district` | Yes | District name (aliases supported) |
| `season` | Yes | `Kharif`, `Rabi`, `Summer`, `Whole Year` |
| `soil_ph` | No | Soil pH value |
| `n`, `p`, `k` | No | NPK values (kg/ha) |
| `previous_crop` | No | Last season's crop |

**Response:**
```json
{
  "location": {
    "state": "Karnataka",
    "district": "Dakshin Kannad",
    "canonical_id": "Karnataka::Dakshin Kannad"
  },
  "season": "Kharif",
  "recommendations": [
    {
      "rank": 1,
      "crop": "Rice",
      "final_score": 95.2,
      "score_breakdown": {
        "evidence_score": 16.0,
        "season_score": 20.0,
        "soil_score": 15.0,
        "weather_score": 15.0
      },
      "explanation": {
        "why_recommended": "Rice has strong historical cultivation evidence...",
        "current_situation": "...",
        "considerations": "..."
      },
      "crop_information": {
        "why_grown": "...",
        "common_uses": "...",
        "season": "Kharif",
        "soil": "Clay loam"
      }
    }
  ],
  "rejected_crops": [...]
}
```

**Error response (district not found):**
```json
{
  "status": "ERROR",
  "message": "District 'XYZ' could not be resolved to canonical master.",
  "canonical_id": "UNRESOLVED_LOCATION"
}
```

---

## 4. List Supported Crops

### `GET /api/crops`

List all crops with model status.

**Response:**
```json
{
  "supported": ["rice", "wheat", "maize", "onion", "potato"],
  "crops": [
    {"crop": "rice", "ready": true, "models": ["xgboost", "arima", "mlp"], "best_model": "xgboost"},
    ...
  ]
}
```

---

## 5. Retrain Models

### `POST /api/train`

Trigger background model retraining for all crops.

**Response:**
```json
{
  "message": "Training started in background.",
  "crops": ["rice", "wheat", "maize", "onion", "potato"]
}
```

### `GET /api/train/status`

Check training progress.

---

## 6. Static Frontend

### `GET /`
Serves `frontend/index.html` — the main single-page application.

### `GET /indian_districts.json`
Serves the states/districts data for the frontend dropdowns.

---

## 7. Scope Constraints

| Capability | Available | Not Available |
|---|---|---|
| Price forecast for rice, wheat, maize, onion, potato | ✅ | — |
| Price forecast for other crops | — | ❌ No trained model |
| State-specific Mandi price | ✅ | — |
| District-specific price forecast | — | ❌ Not a model feature |
| District-level crop recommendation | ✅ | — |
| Crop recommendation without district | — | ❌ District required |
| News intelligence integration | ✅ | — |
| Real-time price (< 3 hours old) | — | ❌ Data.gov.in updates every 24–72h |
