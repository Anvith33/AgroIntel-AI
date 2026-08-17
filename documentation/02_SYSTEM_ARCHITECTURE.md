# AgroIntel — System Architecture & Module Reference

> **Version:** 4.1 Final | **Date:** 2026-08-16

---

## 1. Platform Overview

AgroIntel is an end-to-end AI-powered agricultural decision support system for Indian farmers. It delivers:

| Feature | Description |
|---|---|
| **Crop Recommendation** | District-level explainable ML recommendation using soil, climate & historical evidence |
| **Price Prediction** | 30-day ML price forecast for 5 major commodities across 28 states |
| **Farmer Advisory** | Integrated SELL / HOLD / WAIT market decision with real-time mandi data |
| **News Intelligence** | Multi-tier credibility news scoring for 37 official and research sources |

**Tech Stack:**

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.115+ / Python 3.13 / Uvicorn ASGI |
| ML Models | XGBoost, Facebook Prophet, ARIMA, MLP Neural Network, Random Forest |
| AI / NLP | Groq Llama 3.3 70B + Google Gemini 2.5 Flash |
| Mandi Data | data.gov.in AGMARKNET API (live) + cached fallback + MSP estimates |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript ES6+ / Chart.js |
| District Resolution | Canonical alias normalization (700+ district entries) |

---

## 2. Complete Pipeline Architecture

```
USER INPUT (State + District + Season + optional Soil NPK/pH)
       │
       ▼
[1. LOCATION CANONICALIZATION]
   location_normalizer.py + district_master.json (652 canonical districts)
   → Resolves aliases: "Ahmednagar" → "Ahilya Nagar", "Mysore" → "Mysuru"
       │
       ▼
[2. CANDIDATE CROP GENERATION]
   nationwide_candidate_matrix_v2.json (122 crops × 652 districts × 3 seasons)
   → Returns crops with verified regional agronomic feasibility
       │
       ▼
[3. AGRONOMIC FILTER]
   Hard-boundary validation: season, soil pH, NPK, temperature, rainfall
   → Removes agronomically impossible crops for this location
       │
       ▼
[4. RANDOM FOREST INFERENCE]
   crop_recommendation_rf.pkl (22-class classifier)
   → Outputs suitability probability scores per crop
       │
       ▼
[5. NEWS INTELLIGENCE ADJUSTMENT]
   Google News RSS → Groq Llama 3.3 / Gemini 2.5 Flash extraction
   → Applies bounded risk weight (−5 to +3 pts; cannot override agronomic rejection)
       │
       ▼
[6. MANDI PRICE FETCH]
   data.gov.in AGMARKNET API → mandi_service.py
   → Latest modal price (₹/quintal) for state + crop
       │
       ▼
[7. ML PRICE FORECAST]
   predict_price() in inference.py
   → 30-day autoregressive forecast array (state-aware XGBoost / Prophet)
       │
       ▼
[8. ADVISORY DECISION ENGINE]
   3% threshold rule: SELL / HOLD / WAIT
   → NULL decision if no validated model exists (no fake defaults)
       │
       ▼
[9. NLP EXPLANATION ENGINE]
   nlp_explanation_service.py + crop_information.json
   → Farmer-friendly text (no internal scores, model names, or technical jargon)
       │
       ▼
[10. FARMER FRONTEND DASHBOARD]
   frontend/script.js + Chart.js
   → Single-page app with price graph, crop cards, decision badge
```

---

## 3. Key Module Reference

### Backend — API Layer (`backend/app/api/`)

| File | Endpoints | Purpose |
|---|---|---|
| `endpoints.py` | `GET /api/predict` | Main price prediction endpoint (farmer-facing) |
| `price_router.py` | `GET /api/predict/price`, `GET /api/market/latest` | Detailed price + mandi lookup |
| `phase6_router.py` | `POST /api/phase6/recommend`, `POST /api/advisory` | Crop recommendation + combined advisory |
| `advisory_router.py` | `POST /api/advisory` | Integrated advisory (crop rec + price + news) |
| `health_router.py` | `GET /health` | System health check |
| `system_router.py` | `GET /api/system/*` | Version and system info |

### Backend — ML Layer (`backend/app/ml/`)

| File | Purpose |
|---|---|
| `inference.py` | `predict_price()` — unified price forecast entry point |
| `price_predictor.py` | Detailed price prediction with model comparison |
| `price_trainer.py` | Training pipeline for XGBoost + Prophet + ARIMA + MLP |
| `train.py` | Legacy training entry point |
| `build_state_dataset.py` | Builds clean state-level price dataset from AGMARKNET |
| `train_state_models.py` | Trains all 5 state-aware XGBoost models |

### Backend — Services Layer (`backend/app/services/`)

| File | Purpose |
|---|---|
| `phase6_integration_service.py` | `AgroIntelPhase6Engine` — main recommendation orchestrator |
| `mandi_service.py` | Live mandi price fetch + caching + MSP fallback |
| `location_normalizer.py` | District alias resolution + canonicalization |
| `weather_service.py` | Open-Meteo weather data fetch + rainfall/temp summaries |
| `nlp_explanation_service.py` | Farmer-friendly NLP text generator |
| `news_intelligence_service.py` | News RSS ingestion + Groq/Gemini extraction |

### Data Files (`backend/app/data/`)

| File | Description |
|---|---|
| `experimental/district_master.json` | 700+ canonical district entries with aliases |
| `experimental/nationwide_candidate_matrix_v2.json` | District × crop × season evidence matrix |
| `experimental/crop_requirements.json` | Soil/climate requirements per crop |
| `experimental/crop_information.json` | NLP explanation templates per crop |
| `experimental/market_intelligence.json` | Cached mandi market data |
| `experimental/news_events.json` | Extracted news intelligence events |

### Model Artifacts (`backend/models/`)

| File | Contents |
|---|---|
| `xgboost_state_{crop}.pkl` | State-Aware XGBoost production models (Rice, Wheat, Maize, Onion, Potato) |
| `prophet_{crop}.pkl` | Facebook Prophet seasonal models |
| `arima_{crop}.pkl` | Statistical ARIMA baseline models |
| `mlp_{crop}.pkl` | Deep Learning MLP Neural Network models |
| `state_encoder_{crop}.pkl` | Scikit-Learn LabelEncoders for 28 Indian States |
| `data_tail_state_{crop}.pkl` | 60-day historical state price data tails for lag features |
| `crop_recommender_rf.pkl` | 22-class Random Forest crop recommendation model |
| `model_registry.json` | Registry of all model metadata, metrics, and best model selection |

---

## 4. Advisory Decision Logic

### Price Advisory (SELL / HOLD / WAIT)

```
If forecast unavailable → decision = null (NEVER fake HOLD)

Else if (predicted - current) / current ≤ −3.0% → SELL
     if (predicted - current) / current ≥ +3.0% → HOLD
     else                                          → WAIT

For Onion and Potato: threshold is ±5.0% (high volatility crops)
```

### Stale Data Rule
```
If data_age_days > 14 → WAIT
  (Market conditions may have changed; verify current local mandi rates)
```

### Non-Benchmark Crops (Sugarcane, Cotton, Soybean, etc.)
```
forecast_available = false
decision           = null  ← NEVER "HOLD"
farmer_message     = "A reliable 30-day price forecast is currently
                      unavailable for this crop."
```

---

## 5. Data Flow — Price Prediction

```
Request: GET /api/predict?crop=wheat&state=Punjab&horizon_days=30
    │
    ├── 1. Validate crop ∈ {rice, wheat, maize, onion, potato}
    │
    ├── 2. predict_price(crop="wheat", state="Punjab", horizon_days=30)
    │        └── Load wheat_models.joblib
    │        └── Fetch latest mandi price for Punjab via mandi_service.py
    │        └── Build 14-feature input vector (lags + rolling means + weather + black_swan)
    │        └── Run XGBoost (or Prophet for wheat) → 30 price points
    │        └── Compute recommendation: SELL / HOLD / WAIT
    │
    └── 3. Return clean farmer response (no model names, MAE, RMSE, internal scores)
```

---

## 6. Crop Recommendation Flow

```
Request: POST /api/phase6/recommend {state, district, season, n, p, k, soil_ph}
    │
    ├── 1. normalize_location(district, state) → canonical_id
    │
    ├── 2. Load candidate crops from nationwide_candidate_matrix_v2.json
    │
    ├── 3. Apply hard agronomic filters (season, soil pH, NPK bounds)
    │
    ├── 4. Run Random Forest inference → suitability scores
    │
    ├── 5. Apply news intelligence adjustment (±bounded)
    │
    ├── 6. Rank and select top 5 crops
    │
    └── 7. Generate NLP explanation (farmer-friendly, no raw scores)
```

---

## 7. System Constraints (Honest Disclosure)

| Capability | Available | Not Available |
|---|---|---|
| Price forecast: rice, wheat, maize, onion, potato | ✅ | — |
| Price forecast: other crops (sugarcane, cotton, etc.) | — | ❌ No validated model |
| State-specific mandi price | ✅ | — |
| District-specific price forecast | — | ❌ Not a model feature |
| District-level crop recommendation | ✅ | — |
| Crop recommendation without district | — | ❌ District required |
| Live mandi price (< 3 hours old) | — | ❌ AGMARKNET updates every 24–72h |
| District-level price data | — | ❌ Only state-level in training data |
