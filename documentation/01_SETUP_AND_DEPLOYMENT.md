# AgroIntel — Setup & Deployment Guide

> **Version:** 4.1 Final | **Repository:** https://github.com/Dhanushkumar4-ai/AgroIntel

---

## 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 or 3.13 |
| pip | latest |
| Git | any recent version |

---

## 2. Clone & Install

```bash
git clone https://github.com/Dhanushkumar4-ai/AgroIntel.git
cd AgroIntel/backend
pip install -r requirements.txt
```

---

## 3. Environment Configuration

Create `backend/.env` with the following keys:

```env
# API Keys
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Data.gov.in Agmarknet API (for live mandi prices)
AGMARKNET_API_KEY=your_data_gov_in_api_key_here

# Application
APP_ENV=production
LOG_LEVEL=INFO
```

> **Note:** The app runs without API keys (falls back to cached data), but live mandi prices and news intelligence require valid keys.

---

## 4. Start the Server

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

| URL | Purpose |
|---|---|
| http://localhost:8000/ | Farmer Web Application |
| http://localhost:8000/docs | Swagger API Documentation |
| http://localhost:8000/redoc | ReDoc API Documentation |

---

## 5. Run Tests

```bash
# From the project root
cd backend
python -m pytest ../tests/ -v
```

**Test suites:**

| File | Coverage |
|---|---|
| `test_system_health.py` | Health endpoint + frontend mount |
| `test_price_forecasting_140.py` | 140 state × crop forecast combinations |
| `test_crop_recommendation_50.py` | 50 district recommendation scenarios |
| `test_advisory_and_location.py` | Advisory logic + location alias resolution |
| `test_regression_bugs.py` | 10 regression tests for all critical bugs |

---

## 6. Retrain Models

If you want to retrain the ML models from scratch:

```bash
cd backend

# Step 1: Rebuild the state-level price dataset from AGMARKNET
python -m app.ml.build_state_dataset

# Step 2: Retrain all 5 state-aware XGBoost price models
python -m app.ml.train_state_models

# Step 3: Retrain the 22-class Random Forest crop recommender
python -m app.ml.crop_recommender
```

> Trained models are saved to `backend/models/`. The file `model_registry.json` is updated automatically.

---

## 7. Directory Structure

```
projectphase2/
├── audit/                     # Scientific audit reports (read-only reference)
│   ├── data/                  # Data quality & leakage audits
│   ├── models/                # Model comparison & evaluation
│   ├── forecasting/           # 140 state-crop validation
│   ├── news/                  # 37-source news audit reports
│   ├── recommendation/        # Agronomic accuracy audits
│   └── system/                # Master system inventory
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI routers & endpoints
│   │   ├── core/              # Config, constants, settings
│   │   ├── data/              # Historical price CSVs, district maps, JSON data
│   │   ├── ml/                # ML training, inference, feature engineering
│   │   └── services/          # Recommendation, news, decision engines
│   ├── frontend/              # Farmer web UI (HTML + CSS + JS)
│   ├── models/                # Production model artifacts (.joblib)
│   └── scripts/               # Pipeline runner scripts
├── documentation/             # ← You are here (5 consolidated docs)
├── tests/                     # Automated pytest validation suites
├── README.md                  # Project overview and quick start
└── requirements.txt           # Python dependencies
```

---

## 8. Supported Crops & States

**Price Forecasting (5 crops):**
Rice, Wheat, Maize, Onion, Potato

**Crop Recommendation (122 crops):**
All major Kharif, Rabi, and Summer crops across 652 Indian districts

**Supported States (28):**
Andhra Pradesh, Arunachal Pradesh, Assam, Bihar, Chhattisgarh, Goa, Gujarat, Haryana, Himachal Pradesh, Jharkhand, Karnataka, Kerala, Madhya Pradesh, Maharashtra, Manipur, Meghalaya, Mizoram, Nagaland, Odisha, Punjab, Rajasthan, Sikkim, Tamil Nadu, Telangana, Tripura, Uttar Pradesh, Uttarakhand, West Bengal

---

## 9. Common Issues

| Problem | Cause | Fix |
|---|---|---|
| `Address already in use` on port 8000 | Old server still running | `lsof -i :8000` → `kill -9 <PID>` |
| `ModuleNotFoundError: app` in tests | Running pytest from wrong dir | Run `pytest` from `backend/` directory |
| `InconsistentVersionWarning` for sklearn | Model was trained on sklearn 1.8 | Safe to ignore; or retrain models locally |
| Mandi price returns `null` | API key missing / rate limited | Check `.env`; app falls back to cached prices |
| `Weather status: UNAVAILABLE` | Open-Meteo API temporarily down | Safe to ignore; recommendation still works |
