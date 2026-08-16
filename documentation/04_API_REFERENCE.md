# AgroIntel — API Reference

> **Version:** 4.1 Final | **Base URL:** `http://localhost:8000`
>
> Full interactive docs at: `http://localhost:8000/docs` (Swagger UI)

---

## Endpoints Summary

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | System health check |
| GET | `/api/predict` | 30-day price forecast + SELL/HOLD/WAIT |
| GET | `/api/market/latest` | Latest mandi price for a crop + state |
| POST | `/api/phase6/recommend` | District crop recommendation |
| POST | `/api/advisory` | Combined advisory (crop + price + news) |
| GET | `/api/crops` | List all supported crops |
| POST | `/api/train` | Trigger background model retraining |
| GET | `/api/train/status` | Check training progress |

---

## 1. Health Check

### `GET /health`

Returns system status and model availability.

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

Get a 30-day ML price forecast with SELL / HOLD / WAIT advisory.

**Query Parameters:**

| Parameter | Type | Required | Values |
|---|---|---|---|
| `crop` | string | ✅ Yes | `rice`, `wheat`, `maize`, `onion`, `potato` |
| `state` | string | No | Any Indian state name (affects mandi price only) |
| `horizon_days` | int | No | `7`, `15`, `30` (default), `60`, `90` |

**Example:**
```
GET /api/predict?crop=wheat&state=Punjab&horizon_days=30
```

**Success Response (`available: true`):**
```json
{
  "available": true,
  "crop": "wheat",
  "state": "Punjab",
  "current_price": 2158.58,
  "predicted_price": 3048.93,
  "predictions": [2200.0, 2250.5, ...],
  "date_labels": ["2026-08-17", "2026-08-18", ...],
  "recommendation": "HOLD",
  "recommendation_reason": "Prices are forecast to appreciate by 41.2% over 30 days.",
  "observation_date": "2026-08-16",
  "market_name": "Punjab",
  "data_age_days": 0,
  "advisory": {
    "decision": "HOLD",
    "reason": "..."
  },
  "forecast": {
    "available": true,
    "predicted_price": 3048.93,
    "date_labels": ["2026-08-17", ...]
  }
}
```

> `predictions` always has exactly `horizon_days` values.  
> `date_labels` always has exactly `horizon_days` ISO date strings.

**Unavailable crop response (`available: false`):**
```json
{
  "available": false,
  "crop": "sugarcane",
  "message": "Price prediction is currently unavailable for this crop...",
  "advisory": {
    "decision": "INSUFFICIENT_DATA",
    "reason": "No validated forecasting model available."
  }
}
```

---

## 3. Mandi Price Lookup

### `GET /api/market/latest`

Fetch the latest observed mandi modal price for a crop and optional state.

**Query Parameters:**

| Parameter | Type | Required |
|---|---|---|
| `crop` | string | ✅ Yes |
| `state` | string | No |

**Example:**
```
GET /api/market/latest?crop=rice&state=Maharashtra
```

**Response:**
```json
{
  "crop": "rice",
  "state": "Maharashtra",
  "market": "Pune",
  "modal_price": 3169.53,
  "min_price": 2900.0,
  "max_price": 3400.0,
  "arrival_date": "2026-08-15",
  "source": "cached_api",
  "freshness_label": "1 day old",
  "data_age_days": 1
}
```

**`source` values:**

| Value | Meaning |
|---|---|
| `api_data_gov_in` | Live from data.gov.in AGMARKNET API |
| `cached_api` | From local cache (< 24h old) |
| `msp_estimate` | Fallback Minimum Support Price estimate |

---

## 4. Crop Recommendation

### `POST /api/phase6/recommend`

Get top 5 AI-recommended crops for a district, season, and optional soil profile.

**Request Body:**
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

| Field | Required | Type | Description |
|---|---|---|---|
| `state` | ✅ Yes | string | State name |
| `district` | ✅ Yes | string | District name (aliases supported) |
| `season` | ✅ Yes | string | `Kharif`, `Rabi`, `Summer`, `Whole Year` |
| `soil_ph` | No | float | Soil pH (0–14) |
| `n` | No | float | Nitrogen (kg/ha) |
| `p` | No | float | Phosphorus (kg/ha) |
| `k` | No | float | Potassium (kg/ha) |
| `previous_crop` | No | string | Last season's crop |

**Response:**
```json
{
  "status": "OK",
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
      "nlp_explanation": {
        "why_recommended": "Rice has strong historical cultivation evidence...",
        "current_situation": "No major adverse weather warnings...",
        "considerations": "Requires adequate water availability..."
      },
      "crop_information": {
        "why_grown": "Staple food crop...",
        "common_uses": "Food, rice flour, rice bran oil",
        "season": "Kharif",
        "soil": "Clay loam or heavy soils"
      }
    }
  ]
}
```

**District resolution aliases** — all of the following resolve correctly:

| User Input | Resolved To |
|---|---|
| `Ahmednagar` | `Ahilya Nagar` |
| `Mysore` | `Mysuru` |
| `Aurangabad` | `Chhatrapati Sambhajinagar` |
| `Osmanabad` | `Dharashiv` |
| `Bellary` | `Ballari` |
| `Dakshina Kannada` | `Dakshin Kannad` |

---

## 5. Combined Advisory

### `POST /api/advisory`

Returns crop recommendations + price prediction + SELL/HOLD/WAIT advisory in a single call.

**Request Body:**
```json
{
  "state": "Maharashtra",
  "district": "Ahilya Nagar",
  "season": "Kharif",
  "crop": "rice"
}
```

| Field | Required | Description |
|---|---|---|
| `state` | ✅ Yes | State name |
| `district` | ✅ Yes | District name |
| `season` | ✅ Yes | Kharif / Rabi / Summer |
| `crop` | No | Override crop for price analysis (default: top recommended crop) |

**Response:**
```json
{
  "state": "Maharashtra",
  "district": "Ahilya Nagar",
  "season": "Kharif",
  "target_price_crop": "Sugarcane",
  "combined_summary": "...",
  "crop_recommendations": [...],
  "price_prediction": {
    "crop": "Sugarcane",
    "forecast_available": false,
    "current_price": 2530.33,
    "predicted_30d_avg": null,
    "decision": null,
    "decision_reason": "A reliable 30-day price forecast is currently unavailable for this crop.",
    "farmer_message": "A reliable 30-day price forecast is currently unavailable for this crop.",
    "forecast_series": [],
    "date_labels": []
  },
  "response_time_ms": 412.5
}
```

> `decision` is `null` for non-benchmark crops (Sugarcane, Cotton, Soybean, etc.).
> `decision` is `"SELL"`, `"HOLD"`, or `"WAIT"` for benchmark crops with a valid forecast.
> `forecast_available: false` → frontend must show "Currently unavailable", never `₹—`.

---

## 6. List Supported Crops

### `GET /api/crops`

List all crops with model readiness status.

**Response:**
```json
{
  "supported": ["rice", "wheat", "maize", "onion", "potato"],
  "crops": [
    {
      "crop": "rice",
      "ready": true,
      "models": ["xgboost", "arima", "mlp"],
      "best_model": "xgboost"
    }
  ]
}
```

---

## 7. Model Training

### `POST /api/train`
Trigger background retraining of all 5 crop price models.

**Response:**
```json
{
  "message": "Price model training started in background.",
  "supported_crops": ["rice", "wheat", "maize", "onion", "potato"]
}
```

### `GET /api/train/status`
Check progress of the current or last training run.

**Response:**
```json
{
  "status": "success",
  "message": "Model training complete.",
  "best_models": {"rice": "xgboost", "wheat": "prophet", "maize": "xgboost"}
}
```

---

## 8. Error Responses

All errors return consistent JSON:

```json
{
  "error": "Error Type",
  "detail": "Human-readable description",
  "status_code": 422
}
```

| HTTP Code | Trigger |
|---|---|
| 404 | District not found, model file missing |
| 409 | Training already in progress |
| 422 | Invalid crop name, invalid horizon_days, missing required field |
| 500 | Internal server error (logged server-side) |

---

## 9. System Constraints

| Capability | Available | Not Available |
|---|---|---|
| Price forecast for rice, wheat, maize, onion, potato | ✅ | — |
| Price forecast for other crops | — | ❌ No trained model |
| State-specific mandi price | ✅ | — |
| District-specific price forecast | — | ❌ State-level only |
| District crop recommendation | ✅ | — |
| Real-time price (< 1 hour old) | — | ❌ AGMARKNET updates 24–72h |
