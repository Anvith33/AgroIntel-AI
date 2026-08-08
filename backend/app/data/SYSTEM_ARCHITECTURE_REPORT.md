# AgroIntel v4.0 — System Architecture Report

## Executive Summary

AgroIntel v4.0 is an enterprise-grade AI/ML software system engineered for national-scale agricultural intelligence in India. The platform integrates time-series commodity price forecasting, real-time market data retrieval, multi-source dynamic weather fusion, and multi-stage crop recommendation into a FastAPI microservices framework.

---

## 1. High-Level System Architecture

```
                               ┌─────────────────────────────┐
                               │   FastAPI Web Application   │
                               │          (main.py)          │
                               └──────────────┬──────────────┘
                                              │
         ┌──────────────────┬─────────────────┼─────────────────┬──────────────────┐
         │                  │                 │                 │                  │
         ▼                  ▼                 ▼                 ▼                  ▼
┌──────────────────┐┌───────────────┐┌─────────────────┐┌────────────────┐┌─────────────────┐
│  system_router   ││ health_router ││  price_router   ││  crop_router   ││    endpoints    │
│ (/api/version,   ││   (/health)   ││ (/api/predict,  ││ (/api/predict/ ││ (legacy compat) │
│  /api/models)    ││               ││  /api/market)   ││  crop)         ││                 │
└────────┬─────────┘└───────┬───────┘└────────┬────────┘└───────┬────────┘└────────┬────────┘
         │                  │                 │                 │                  │
         └──────────────────┴─────────────────┼─────────────────┴──────────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │       Business Core         │
                               ├─────────────────────────────┤
                               │ • price_predictor.py        │
                               │ • recommendation_engine.py  │
                               │ • decision_engine.py        │
                               │ • confidence_engine.py      │
                               │ • trend_engine.py           │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │    Data & Model Layer       │
                               ├─────────────────────────────┤
                               │ • Prophet / XGBoost / ARIMA │
                               │ • RandomForestClassifier    │
                               │ • weather_service.py        │
                               │ • mandi_service.py          │
                               │ • soil_service.py           │
                               │ • region_service.py         │
                               └─────────────────────────────┘
```

---

## 2. Core Subsystems

### A. Price Prediction & Decision Engine
- **Models**: Prophet, XGBoost, ARIMA(1,1,1), LSTM (Keras). Selected automatically per crop based on lowest MAE on chronological 60-day validation set.
- **Features (11)**: Lags (`lag_1`, `lag_7`, `lag_14`, `lag_30`), Rolling Averages (`rolling_7`, `rolling_30`), Calendar (`month`, `season`), Weather (`monthly_avg_temp`, `monthly_total_rainfall`), Event (`black_swan`).
- **Decision Engine**: Computes net 30-day gain percentage after subtracting an estimated 2.0% monthly holding & decay cost. Outputs deterministic `HOLD` or `SELL` recommendation with explainability strings.

### B. Multi-Stage Crop Recommendation Engine
- **District Top 10 Resolution**: Restricts candidate crops to historically proven regional crops.
- **Season Filter**: Removes out-of-season crops prior to Random Forest scoring.
- **Dynamic Weather Fusion Engine**: Blends 6-year historical climate data with live Open-Meteo forecasts dynamically based on data age.
- **Random Forest Scorer**: 100 decision trees trained on 2,200 Kaggle samples with 99.55% unseen test accuracy.
- **Probability Normalization**: Normalizes RF output probabilities over candidate crop subset ($\sum P = 1.0$).
- **Suitability Score (0–100)**: Composite index of RF Probability (40%), Soil Match (20%), Weather Match (20%), District Match (10%), Season Match (10%), with a 50% penalty if non-viable per ICAR agro-climatic zone rules.

---

## 3. Data Integrity & Security Standards

1. **Stack Trace Suppression**: All production 500 exceptions suppress Python tracebacks and return sanitized JSON error messages.
2. **Audit Logging**: Prediction and recommendation requests are stored in `prediction_history.json` and `recommendation_history.json` for monitoring without mutating model training weights.
3. **Pydantic Validation**: Strict boundary checks on NPK values ($0-300$), pH ($1.0-14.0$), latitude ($\pm 90$), longitude ($\pm 180$), and crop names.

---
*AgroIntel v4.0 System Architecture Overview*
