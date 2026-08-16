# AgroIntel — Comprehensive Agricultural Intelligence Platform

AgroIntel is an enterprise-grade AI agricultural intelligence platform that provides:
1. **State-Specific Mandi Price Forecasting**: 30-day forward price forecasts with deterministic **SELL / HOLD / WAIT** market advisories across all 28 Indian States and 5 core crops (Rice, Wheat, Maize, Onion, Potato).
2. **Explainable Crop Recommendation**: District-level agro-climatic recommendations across 652 Indian districts, evaluating soil pH, NPK levels, seasonal crop calendars, APY cultivation evidence, and real-time climate signals.
3. **News Intelligence & Cross-Verification**: Multi-tier credibility classification across 37 official, research, market, and national media sources with automated fact extraction and bounded risk scoring.

---

## 1. System Architecture

```
                                  AGROINTEL PLATFORM ARCHITECTURE

           [HISTORICAL MANDI ARCHIVES]              [LIVE DATA.GOV.IN / IMD API]
           178,522 State Records (2019-2024)        Live Prices & Weather
                           │                                   │
                           ▼                                   ▼
                [DATA ENGINEERING ENGINE]           [NEWS INTELLIGENCE SERVICE]
             - Cleaned Modal/Min/Max Spreads         - 37 Credibility Tiers
             - Price Volatility (rolling_std_7)      - Cross-Source Verification
             - Anti-Leakage shift(1) Transforms      - Bounded Risk Adjustments
                           │                                   │
                           ▼                                   │
               [MODEL TRAINING & REGISTRY]                     │
             - 5 State-Aware XGBoost Models                    │
             - 14 Time-Aligned Features                        │
             - Chronological Holdout Partitions                │
                           │                                   │
                           ▼                                   │
                [INFERENCE ENGINE PIPELINE] ◄──────────────────┘
             - 30-Day Autoregressive Forecast
             - State-Specific Data Tail Seeding
             - Deterministic SELL/HOLD/WAIT Decision
                           │
                           ▼
                 [FARMER-FACING REST API]
              GET  /api/predict (Price Outlook)
              POST /api/phase6/recommend (Crop Rec)
                           │
                           ▼
                    [FARMER WEB UI]
             Decoupled, zero internal ML metrics
```

---

## 2. Directory Structure

```
.
├── audit/                          # Scientific audit and quality reports
│   ├── data/                       # Historical data quality & leakage audits
│   ├── models/                     # Model comparison & evaluation reports
│   ├── forecasting/                # 140 state-crop validation & horizon audits
│   ├── news/                       # 37-source news runtime audits
│   ├── recommendation/             # Agronomic & candidate accuracy audits
│   └── system/                     # Master system inventories and audits
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routers & endpoints
│   │   ├── core/                   # System configuration & constants
│   │   ├── data/                   # Clean historical price CSVs & district maps
│   │   ├── ml/                     # ML training, inference & feature engineering
│   │   ├── services/               # Recommendation, news & decision engines
│   │   └── main.py                 # FastAPI application entry point
│   ├── frontend/                   # Farmer web application (HTML/CSS/JS)
│   ├── models/                     # Production model artifacts (.joblib)
│   └── scripts/                    # Pipeline runner scripts & audits
├── documentation/                  # ← 5 consolidated technical documents
│   ├── 01_SETUP_AND_DEPLOYMENT.md  # Installation, config, directory structure
│   ├── 02_SYSTEM_ARCHITECTURE.md   # Pipeline diagrams, module reference, decision logic
│   ├── 03_ML_MODELS_AND_DATA.md    # Model specs, data sources, evaluation metrics
│   ├── 04_API_REFERENCE.md         # All endpoints with request/response examples
│   └── 05_PROJECT_QA_AND_VIVA.md   # Viva Q&A, test results, bug history
├── tests/                          # Automated pytest validation suites
└── README.md                       # Project overview and quick start
```

---

## 3. Core Pipelines

### A. State-Aware Price Prediction Pipeline
- **Inputs**: `crop` (Rice, Wheat, Maize, Onion, Potato) + `state` (28 Indian States) + `horizon_days` (30).
- **Features (14)**: `state_enc`, `lag_1`, `lag_7`, `lag_14`, `lag_30`, `rolling_7`, `rolling_30`, `rolling_std_7`, `price_range`, `day_of_year`, `month`, `day_of_week`, `year`, `black_swan`.
- **Model**: State-Aware XGBoost with discrete state label encodings and 60-day historical state price tails.
- **Decision Engine**:
  - Expected change $\le -3.0\% \rightarrow \textbf{SELL}$ (Minimizes downside crash risk).
  - Expected change $\ge +3.0\% \rightarrow \textbf{HOLD}$ (Captures price appreciation).
  - $|\text{Change}| < 3.0\%$ or Data Age $> 14\text{ days} \rightarrow \textbf{WAIT}$ (Market stability / stale data).

### B. Crop Recommendation Pipeline
- **Inputs**: `state` + `district` + `season` (Kharif, Rabi, Summer, Whole Year) + optional soil pH, NPK, previous crop.
- **Evaluation Order**:
  1. District & season validation.
  2. Hard seasonal calendar & soil pH tolerance filter.
  3. APY historical cultivation evidence (246k records).
  4. 22-class Random Forest suitability scoring.
  5. Bounded news intelligence adjustment ($-5$ to $+3$ pts; cannot override agronomic rejection).

---

## 4. Running the Application

### Start Backend & Frontend Server
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Farmer Web App**: [http://localhost:8000/](http://localhost:8000/)
- **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

### Running Automated Test Suites
```bash
pytest tests/ -v
```

---

## 5. Retraining Production Models
```bash
cd backend
python -m app.ml.build_state_dataset     # Rebuild clean state dataset from AGMARKNET
python -m app.ml.train_state_models      # Retrain all 5 state-aware XGBoost models
python -m app.ml.crop_recommender        # Retrain 22-class crop classifier
```
