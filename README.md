# AgroIntel AI — Agricultural Decision Support System

> **Phase 6 Final** | End-to-End Explainable Crop Recommendation + Mandi Price Intelligence + ML Price Forecast + News Risk Analysis

---

## Quick Start

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open: **http://127.0.0.1:8000**

---

## System Architecture

```
USER INPUT
  → State / District / Season / Soil (optional) / Previous Crop (optional)
  → Phase 4 Candidate Matrix (652 districts × 122 crops, 31,401 vectors)
  → Phase 1-4 Evidence Scoring (evidence, season, soil, weather, water, rotation, ML, news)
  → RandomForest Ranker (candidate RANKER — never invents new crops)
  → Latest Available Mandi Price (data.gov.in batch, observation_date + data_age_days shown)
  → XGBoost/Prophet 30-day Price Forecast (MAE/RMSE/MAPE from 2024 chronological test)
  → Market Advisory (SELL / HOLD / WAIT / INSUFFICIENT_DATA)
  → News Intelligence (Groq Llama 3.3 70B → Gemini 2.5 Flash fallback)
  → Explainable Final Result
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | System health |
| GET | /api/version | Version info |
| GET | /api/demo | Frontend dropdown data |
| **POST** | **/api/phase6/recommend** | **Primary: Full Phase 6 Intelligence** |
| GET | /api/phase6/status | Phase 6 data asset status |
| GET | /api/phase6/demo | Reproducible 10-district demo |
| GET | /api/phase6/districts | Canonical district list |
| GET | /api/phase6/mandi-live | Live Mandi API status |
| GET | /api/phase6/news-intel | News intelligence signals |
| POST | /api/crop/recommend | RF-only crop recommendation |
| POST | /api/price/predict | Price prediction only |
| POST | /api/advisory/recommend | Advisory only |

---

## Phase 6 Recommend Request

```json
{
  "state": "Punjab",
  "district": "Ludhiana",
  "season": "Rabi",
  "soil_ph": 7.2,
  "n": 90,
  "p": 45,
  "k": 40,
  "previous_crop": "Rice"
}
```

---

## Price Intelligence Rules

1. **current_price** = Latest OBSERVED Mandi modal price (from `market_intelligence.json` fallback)
2. **predicted_price** = ML forecast for 30-day horizon — ALWAYS different from current_price
3. **MAE/RMSE/MAPE** = Model accuracy metrics on unseen 2024 test data — NOT crop prices
4. **data_age_days** = today − observation_date (computed dynamically)
5. **source_type**: `BATCH_REFERENCE` (has Mandi record) or `REFERENCE_FALLBACK` (no record)

---

## ML Models

| Crop | Production Model | MAE (₹/q) | RMSE (₹/q) | MAPE% |
|---|---|---|---|---|
| Rice | XGBoost | 23.98 | 30.12 | 1.1% |
| Wheat | XGBoost | 62.92 | 67.69 | 2.8% |
| Maize | XGBoost | 23.79 | 35.88 | 1.4% |
| Onion | XGBoost | 156.63 | 212.63 | 8.5% |
| Potato | XGBoost | 93.54 | 156.35 | 7.2% |

**Crop Recommender**: RandomForestClassifier — 99.55% accuracy
**Evaluation**: Chronological train 2019–2023, test 2024 (no future leakage)

---

## Design Rules

- ✅ Water suitability **UNKNOWN** is **NEVER** converted to SUITABLE
- ✅ **current_price** (observed) **≠** **predicted_price** (ML forecast) — always distinct
- ✅ No hardcoded district logic — 100% data-driven across 652 canonical districts
- ✅ No invented crops — all candidates strictly from evidence matrix
- ✅ No API keys in frontend, responses, or Git
- ✅ MAE/RMSE/MAPE are model accuracy metrics — never displayed as prices
- ✅ LLM uses only retrieved article text — LLM internal knowledge not used as ground truth
- ✅ Mandi labeled `LATEST_AVAILABLE_MARKET_PRICE` — never `LIVE_PRICE`

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app
│   ├── api/
│   │   ├── phase6_router.py             # Phase 6 — primary endpoint
│   │   ├── system_router.py             # Health, version, demo
│   │   ├── crop_router.py               # RF crop recommendation
│   │   ├── price_router.py              # Price prediction
│   │   └── advisory_router.py           # Advisory
│   ├── services/
│   │   ├── phase6_integration_service.py  # Phase 6 engine (primary)
│   │   ├── mandi_service.py             # Mandi price service
│   │   ├── price_service.py             # ML price predictor
│   │   ├── news_service.py              # News intelligence
│   │   └── ...
│   └── data/experimental/
│       ├── nationwide_candidate_matrix_v2.json  # 31,401 candidates
│       ├── market_intelligence.json             # 700 Mandi records
│       ├── current_intelligence.json            # 3,956 news signals
│       ├── district_master.json                 # 652 canonical districts
│       ├── price_model_evaluation.json          # ML evaluation metrics
│       ├── final_system_capabilities.json       # System capabilities
│       ├── phase6_validation_report.md          # Validation report
│       └── phase6_demo_results.json             # 10-district demo
├── models/                              # Trained ML models (.pkl)
├── frontend/
│   ├── index.html                       # Single-page UI
│   ├── script.js                        # Frontend logic
│   ├── style.css                        # Dark theme styling
│   └── indian_districts.json            # State/district data
├── scripts/
│   ├── execute_phase6_final_engine.py   # Validation runner
│   └── run_random_district_e2e_test.py  # E2E test runner
└── .env                                 # API keys (not in Git)
```

---

## Environment Variables

```
MARKET_DATA_API_KEY=...    # data.gov.in Mandi API
GEMINI_API_KEY=...         # Google Gemini 2.5 Flash (news fallback LLM)
GROQ_API_KEY=...           # Groq Llama 3.3 70B (primary news LLM)
AGRICULTURE_DATA_API_KEY=... # Agriculture data API
```

---

## Phase History

| Phase | Description |
|---|---|
| Phase 1 | Historical APY data (246,091 records, 652 districts, 122 crops) |
| Phase 2 | Crop season calendar, soil/weather requirements, rotation rules |
| Phase 3 | Recent cultivation evidence, source comparison |
| Phase 4 | Nationwide candidate matrix (31,401 vectors), RF adapter |
| Phase 5 | Mandi API integration, XGBoost/Prophet price models |
| Phase 5.1 | Mandi accuracy validation, nationwide random district test |
| Phase 5.2 | Groq Llama 3.3 70B LLM fallback (quota exhausted Gemini) |
| Phase 5.3 | News pipeline quality, freshness, geographic weighting |
| **Phase 6** | **End-to-end integration, explainable advisory, frontend, final cleanup** |

---

*AgroIntel AI — Final Year Engineering Project*
