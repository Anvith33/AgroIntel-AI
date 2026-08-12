# AgroIntel AI — System Architecture & Module Report

**Version:** 4.1 Final  
**Date:** 2026-08-12  
**Repository:** https://github.com/Dhanushkumar4-ai/AgroIntel  

---

## 1. Project Overview

AgroIntel is an end-to-end AI-powered agricultural decision support system for Indian farmers. It provides:

- **Crop Recommendation** — District-level explainable ML recommendation (State + District + Season required)
- **Price Prediction** — Crop-level 30-day ML price forecasting with live Mandi data (State + Crop, no district required)
- **Farmer Advisory** — Integrated sell/hold/wait market decision advisory

The system is built on **FastAPI** (Python backend) + **Vanilla JS** (frontend), served as a single-page app.

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI 0.115+ with Uvicorn ASGI |
| ML Models | XGBoost, Facebook Prophet, ARIMA, MLP Neural Network |
| AI/NLP | Groq Llama 3.3 70B (news extraction, NLP explanations) |
| Mandi Data | data.gov.in AGMARKNET API (live), cached fallback, MSP estimates |
| Recommendation Engine | Phase 6 Evidence Matrix (district × crop × season) |
| Frontend | Vanilla HTML/CSS/JS, Chart.js (price graphs) |
| District Resolution | Dynamic alias normalization with token overlap matching |
| Hosting | Local Uvicorn (development); deployable to cloud |

---

## 3. Module Architecture

```
backend/
├── app/
│   ├── main.py                          # FastAPI app, CORS, static serving
│   ├── api/
│   │   ├── endpoints.py                 # /api/predict, /api/train, /api/crops
│   │   ├── price_router.py              # /api/mandi, /api/market
│   │   └── phase6_router.py             # /api/phase6/recommend, /api/advisory
│   ├── ml/
│   │   ├── inference.py                 # predict_price() — main ML entry point
│   │   └── train.py                     # Model training pipeline
│   ├── data/
│   │   ├── ingestion.py                 # DataIngestion.fetch_live_market_data()
│   │   └── experimental/
│   │       ├── district_master.json     # 700+ canonical district entries + aliases
│   │       ├── nationwide_candidate_matrix_v2.json  # District × crop × season evidence
│   │       ├── market_intelligence.json # Pre-fetched Mandi market data
│   │       ├── news_source_registry.json # 7-tier news source definitions
│   │       ├── news_events.json         # Extracted news intelligence
│   │       ├── current_intelligence.json # Processed news by state/crop
│   │       └── price_model_evaluation.json # Model MAE/RMSE per crop
│   └── services/
│       ├── phase6_integration_service.py  # AgroIntelPhase6Engine (main rec engine)
│       └── nlp_explanation_service.py     # Groq-powered NLP explanations
├── models/                              # Trained model artifacts (.joblib)
│   ├── rice_models.joblib
│   ├── wheat_models.joblib
│   ├── maize_models.joblib
│   ├── onion_models.joblib
│   └── potato_models.joblib
└── frontend/
    ├── index.html                       # Single-page app structure
    ├── script.js                        # All frontend logic
    └── style.css                        # Glassmorphism dark UI
```

---

## 4. Price Prediction Architecture

### Data Flow

```
User selects Crop + State
        ↓
/api/predict?crop=wheat&state=Punjab&horizon_days=30
        ↓
endpoints.py → predict_price(crop, state, horizon_days)
        ↓
DataIngestion.fetch_live_market_data(crop, state)
  → Try data.gov.in AGMARKNET API (cache key: "crop:state")
  → Fallback: cached JSON
  → Fallback: MSP estimate (2024-25)
        ↓
_load_models(crop) → loads from models/crop_models.joblib
  → Prophet model (seasonal, weekly patterns)
  → XGBoost model (gradient boosting, lag features)
  → ARIMA model (statistical time series)
  → MLP model (neural network)
        ↓
Select best model (evaluated per crop):
  Rice=XGBoost, Wheat=Prophet, Maize=XGBoost, Onion=XGBoost, Potato=XGBoost
        ↓
Generate 30-day price series
        ↓
Compute SELL/HOLD/WAIT advisory
        ↓
Return full response including observation_date, market_name, data_age_days
```

### Model Features (11 features)

| Feature | Description |
|---|---|
| `lag_1` | Price 1 day ago |
| `lag_7` | Price 7 days ago |
| `lag_14` | Price 14 days ago |
| `lag_30` | Price 30 days ago |
| `rolling_mean_7` | 7-day rolling average |
| `rolling_mean_30` | 30-day rolling average |
| `month` | Month (1–12) |
| `season` | Season encoding |
| `monthly_avg_temp` | Temperature |
| `monthly_total_rainfall` | Rainfall |
| `black_swan` | Binary event indicator |

> **Note:** State is NOT a model feature. The ML forecast is crop-level (same across states). The current Mandi price varies by state via the API lookup.

---

## 5. Crop Recommendation Architecture

### Data Flow

```
User selects State + District + Season (+ optional NPK/pH/previous crop)
        ↓
/api/phase6/recommend
        ↓
AgroIntelPhase6Engine.evaluate_recommendation()
        ↓
1. canonicalize_district(district, state)
   → Direct exact match in dist_map
   → Normalized match in dist_norm_map
   → Token-overlap fallback (score ≥ 0.4)
        ↓
2. Fetch candidate crops from nationwide_candidate_matrix_v2.json
   (lookup by canonical_id + season)
        ↓
3. Score each candidate (0–100):
   - Evidence score (historical cultivation)
   - Seasonal suitability
   - Soil pH fit (if provided)
   - Weather match
   - Water availability
   - Crop rotation benefit
        ↓
4. NLP explanation via Groq Llama 3.3 70B
        ↓
5. Return ranked recommendations with why_recommended, considerations
```

---

## 6. News Intelligence Architecture

```
News Source Registry (7 tiers, 35+ sources)
        ↓
HTTP/RSS Fetch → Google News RSS queries (topic-specific)
        ↓
Raw text/title/summary extracted
        ↓
Groq Llama 3.3 70B:
  "Extract crop, state, district, event_type, impact_direction, severity,
   confidence, verification_status from this text."
        ↓
Verified events → news_events.json
        ↓
Current intelligence by (state, crop) → current_intelligence.json
        ↓
Used in:
  - Crop Recommendation: Risk signal (news-based risk factor)
  - Price Advisory: Black Swan detection
```

> **Critical rule:** Groq reads retrieved source text only. Groq's internal knowledge is NOT used as current-event evidence.

---

## 7. Advisory Decision Logic

```python
# SELL/HOLD/WAIT thresholds
threshold = 5.0 if crop in {onion, potato} else 3.0

if data_age_days > 14:
    decision = "WAIT"   # Stale data — cannot trust current price
elif abs(change_pct) < threshold:
    decision = "WAIT"   # Within uncertainty bounds
elif change_pct <= -threshold:
    decision = "SELL"   # Price declining
else:
    decision = "HOLD"   # Price rising

if black_swan_active and decision == "HOLD" and change_pct < 8.0:
    decision = "WAIT"   # Uncertainty during major market event
```
