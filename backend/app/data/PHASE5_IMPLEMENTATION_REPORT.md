# AgroIntel v4.0 — Phase 5: Price Prediction & Decision Engine Implementation Report

## Executive Summary

Phase 5 implements the complete, generic multi-model Price Prediction & Decision Engine for AgroIntel v4.0. The implementation includes:
1. **Generic Prediction Engine (`app/ml/price_predictor.py`)**: Dynamically reads `models/model_registry.json` to load production models (`Prophet`, `XGBoost`, `ARIMA`, `LSTM`) and historical feature tails without hardcoding crop-specific paths.
2. **Trend Analysis Engine (`app/services/trend_engine.py`)**: Computes statistical trend direction (`UPWARD`, `DOWNWARD`, `STABLE`), expected change percentage over 30 days, min/max/average forecast bounds, and price volatility.
3. **Composite Confidence Engine (`app/services/confidence_engine.py`)**: Computes composite forecast confidence combining base model error ratio, forecast horizon penalty factor, and market data freshness factor, strictly clamped between **40.0% and 95.0%**.
4. **Sell/Hold Decision Engine (`app/services/decision_engine.py`)**: Implements the 5% threshold decision rules (`HOLD` when expected increase > +5%; `SELL` when expected decrease > -5% or within ±5% range to avoid storage and quality decay costs) and generates deterministic, model-aligned explainability points.

---

## 1. System Architecture & Component Design

```
                     ┌───────────────────────────┐
                     │    User API Request       │
                     │ (crop, state, horizon_d)  │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │   models/model_registry   │
                     │  (read production_model)  │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
        ┌──────────────────────────┴──────────────────────────┐
        │                                                     │
        ▼                                                     ▼
┌──────────────┐                                    ┌───────────────────┐
│ mandi_service│                                    │  weather_service  │
│(latest price)│                                    │  (Open-Meteo)     │
└───────┬──────┘                                    └─────────┬─────────┘
        │                                                     │
        └──────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │    price_predictor.py     │
                     │ (multi-horizon forecast)  │
                     └─────────────┬─────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
    ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
    │ trend_engine │       │confidence_eng│       │decision_engin│
    └───────┬──────┘       └───────┬──────┘       └───────┬──────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │   Unified Output JSON     │
                     └───────────────────────────┘
```

---

## 2. Decision Logic & Threshold Specifications

### Decision Rule Matrix
- **Expected Change > +5.0%**: `HOLD`
  - *Rationale*: Forecasted price gain significantly exceeds holding costs. Storing inventory is profitable.
- **Expected Change < -5.0%**: `SELL`
  - *Rationale*: Market prices entering a downward trend. Immediate selling locks in current prices.
- **Expected Change between -5.0% and +5.0%**: `SELL`
  - *Rationale*: Flat or marginal price changes do not cover recurring warehouse storage fees, capital lockup, and post-harvest crop shrinkage/decay.

---

## 3. Confidence Formula & Factors

$$\text{Final Confidence} = \text{Clamp}_{0.40}^{0.95} \left( \text{Base Confidence} \times \text{Horizon Factor} \times \text{Freshness Factor} \right)$$

1. **Base Confidence**: $\max(1.0 - \frac{\text{MAE}}{\text{Mean Historical Price}}, 0.50)$
2. **Forecast Horizon Factors**:
   - 7 days: $1.00$
   - 15 days: $0.95$
   - 30 days: $0.90$
   - 60 days: $0.80$
   - 90 days: $0.70$
3. **Data Freshness Factors**:
   - Data age < 1 day: $1.00$
   - 1–3 days: $0.95$
   - 3–7 days: $0.85$
   - > 7 days (or historical fallback): $0.70$

---

## 4. Output Response Schema

```json
{
  "crop": "wheat",
  "production_model": "prophet",
  "current_price": 2866.34,
  "current_price_source": "Historical Data Tail (Fallback)",
  "price_timestamp": "2024-12-31",
  "predictions": {
    "7_day": 2990.68,
    "15_day": 3000.29,
    "30_day": 3012.21,
    "60_day": 3032.45,
    "90_day": 3058.89
  },
  "trend": "UPWARD",
  "expected_change_percent": 5.09,
  "confidence": 0.7478,
  "confidence_percent": 74.8,
  "decision": "HOLD",
  "reason_summary": "Prices expected to increase by 5.1% over the next 30 days (from ₹2866 to ₹3012/quintal). Holding inventory recommended.",
  "reasons": [
    "Historical trend analysis indicates an UPWARD trajectory (+5.1% expected over 30 days).",
    "Wheat exhibits high Rabi season harvest arrival influence on market pricing.",
    "Regional climate proxy conditions (27.9°C avg temp, 268.8mm monthly rainfall) align with standard seasonal supply expectations.",
    "Forecast generated by production-selected PROPHET model with 74.8% confidence."
  ],
  "metrics": {
    "model_mae": 62.92,
    "model_rmse": 67.69
  }
}
```

---

## 5. Phase 5 Code Artifacts Summary

| File | Type | Purpose |
| :--- | :--- | :--- |
| `app/services/trend_engine.py` | New Service | Direction, change %, min/max/avg, volatility |
| `app/services/confidence_engine.py` | New Service | Composite confidence formula & clamping |
| `app/services/decision_engine.py` | New Service | 5% Sell/Hold threshold & deterministic reasons |
| `app/ml/price_predictor.py` | New Engine | Multi-model generic forecaster & unified pipeline |
| `app/services/mandi_service.py` | Updated Service | Fast 3.0s timeout & automatic cache/tail fallback |

---
*AgroIntel v4.0 Technical Documentation — Phase 5 Implementation*
