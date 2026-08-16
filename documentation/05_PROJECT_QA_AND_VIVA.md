# AgroIntel — Project Q&A, Viva Reference & Verification Report

> **Version:** 4.1 Final | **Date:** 2026-08-16

---

## 1. 30-Second Viva Summary

> *"AgroIntel AI is an explainable agricultural decision-support platform designed for Indian farmers and policy analysts. It integrates 27+ years of historical production data across 652 canonical districts, real-time Mandi market rates from data.gov.in, live news intelligence via Groq Llama-3.3 and Gemini 2.5 Flash, and machine learning models (Random Forest, XGBoost, Prophet) to deliver personalized Kharif/Rabi crop recommendations, 30-day price trend forecasts, and actionable SELL/HOLD/WAIT advisories without black-box opacity."*

---

## 2. Core Viva Questions & Answers

### Q1: What problem does AgroIntel solve?

Indian agriculture suffers from severe information asymmetry. Farmers traditionally choose crops based on past habit or local hearsay rather than multi-layered agronomic evidence, real-time market data, or emerging climate risks. AgroIntel acts as an integrated intelligence engine that combines:
- 27+ years of APY cultivation records
- Soil NPK / pH compatibility checks
- Real-time mandi market prices from AGMARKNET (data.gov.in)
- Live news risk intelligence (pest outbreaks, floods, export bans, MSP changes)
- ML time-series forecasting for 5 major commodities

### Q2: Why XGBoost for price prediction?

XGBoost was chosen because it:
1. Handles non-linear interactions between features (weather + lag prices + seasonal patterns)
2. Captures crop-specific price spikes that statistical models (ARIMA) miss
3. Supports multi-step recursive forecasting (Day N predictions feed into Day N+1)
4. Outperformed Prophet, ARIMA, and MLP on MAE for Rice, Maize, Onion, Potato in holdout testing

**Why Prophet for Wheat?**  
Wheat follows a highly consistent seasonal pattern — Rabi harvest (March–April) causes a reliable price drop every year. Prophet's seasonal decomposition captures this better than tree-based models.

### Q3: What is the SELL / HOLD / WAIT decision logic?

```
If (predicted - current) / current ≤ −3.0%  →  SELL
If (predicted - current) / current ≥ +3.0%  →  HOLD
If |change| < 3.0%                           →  WAIT
If data_age_days > 14                        →  WAIT (override, stale data)

For Onion and Potato: threshold is ±5.0% (high volatility)

For unsupported crops (Sugarcane, Cotton, etc.):
  decision = null   ← NEVER defaults to HOLD
  forecast_available = false
```

### Q4: How does the crop recommendation engine work?

5-stage pipeline:
1. **District canonicalization** — alias resolution (e.g., "Ahmednagar" → "Ahilya Nagar")
2. **Candidate generation** — from the nationwide crop-district-season evidence matrix
3. **Hard agronomic filtering** — season, soil pH, NPK, temperature, rainfall
4. **Random Forest scoring** — 22-class classifier gives suitability probabilities
5. **News intelligence adjustment** — bounded ±pts (cannot override agronomic rejection)

### Q5: How do you handle district name aliases?

`location_normalizer.py` maintains a canonical alias map with 700+ district entries.  
Examples:
- `"Mysore"` → `"Mysuru"` (Karnataka official rename)
- `"Aurangabad"` → `"Chhatrapati Sambhajinagar"` (Maharashtra rename)
- `"Ahmednagar"`, `"Ahmed Nagar"`, `"Ahmadnagar"`, `"Ahilyanagar"` → `"Ahilya Nagar"`

The normalizer applies:
1. Exact alias match (case-insensitive, unicode-normalized)
2. Token overlap matching (fuzzy)
3. State-scoped fallback

### Q6: What data sources do you use? Are they real?

| Source | Data | Real? |
|---|---|---|
| data.gov.in AGMARKNET API | Live mandi prices | ✅ Real government API |
| APY (Agriculture Production Information) | Crop cultivation history | ✅ Real government dataset |
| Open-Meteo | Weather (temperature, rainfall) | ✅ Real open API |
| Google News RSS + Groq/Gemini | News intelligence | ✅ Real AI extraction |
| FAO, ICAR, IMD | Context and verification | ✅ Official sources |

**No fabricated data. No artificial state multipliers. No hardcoded fallback prices.**

### Q7: What are the honest limitations?

1. Price forecast is crop-level, not state-specific (state only affects Mandi price lookup)
2. District-level price data is not available — model is trained on state-level data
3. Training data ends 2024 — cannot learn from newer events
4. Onion/Potato have high MAE (₹150–230) due to volatility — advisory uses wider thresholds
5. AGMARKNET API updates every 24–72 hours — not truly real-time
6. News intelligence is bounded: cannot override agronomic rejection of a crop

### Q8: How many crops/states/districts does it support?

| Dimension | Count |
|---|---|
| Price forecasting crops | 5 (Rice, Wheat, Maize, Onion, Potato) |
| Crop recommendation crops | 122 |
| States | 28 |
| Canonical districts | 652 |
| District aliases handled | 700+ |
| News sources | 37 (4 tiers) |

### Q9: What ML evaluation metrics do you use?

- **MAE (Mean Absolute Error)** — primary metric; interpretable in ₹/quintal
- **RMSE (Root Mean Square Error)** — penalizes large errors more heavily
- **R² (Coefficient of Determination)** — proportion of variance explained
- **Chronological holdout** — 80% train / 20% test, strictly time-ordered (no data leakage)

Anti-leakage measures:
- All lag features use `shift(1)` to ensure Day N only sees Day N−1 data
- Test set is strictly from the last 20% of the chronological timeline
- No future data contamination in rolling statistics

### Q10: How do you validate the system end-to-end?

```bash
cd backend
python -m pytest ../tests/ -v
```

| Test Suite | Coverage |
|---|---|
| `test_system_health.py` | Health endpoint + frontend mount |
| `test_price_forecasting_140.py` | 140 state × crop combinations (5 crops × 28 states) |
| `test_crop_recommendation_50.py` | 50 district recommendation scenarios |
| `test_advisory_and_location.py` | Advisory logic + alias resolution |
| `test_regression_bugs.py` | 10 regression tests — all critical bugs |

**All 17 tests pass with 0 failures.**

---

## 3. Verification Test Results

### 3.1 Price Prediction — 5 Crop Verification

| Crop | State | Current ₹ | Forecast ₹ | Decision | Status |
|---|---|---|---|---|---|
| Rice | Maharashtra | 3,170 | 2,365 | SELL | ✅ |
| Wheat | Punjab | 2,159 | 3,049 | HOLD | ✅ |
| Maize | Punjab | 1,690 | 2,325 | HOLD | ✅ |
| Onion | Maharashtra | 1,966 | 3,287 | HOLD | ✅ |
| Potato | Punjab | 1,155 | 2,583 | HOLD | ✅ |

### 3.2 Crop Recommendation — 20 District Verification

All 20 districts resolved correctly and returned valid recommendations:

| District | State | Season | Top Crop |
|---|---|---|---|
| Dakshina Kannada | Karnataka | Kharif | Rice |
| Ludhiana | Punjab | Rabi | Barley |
| Ahilya Nagar (Ahmednagar) | Maharashtra | Kharif | Sugarcane |
| Agra | Uttar Pradesh | Rabi | Wheat |
| Coimbatore | Tamil Nadu | Kharif | Pigeonpea |
| Karnal | Haryana | Rabi | Wheat |
| Ranchi | Jharkhand | Kharif | Pigeonpea |
| Cuttack | Odisha | Kharif | Finger Millet |
| Nalgonda | Telangana | Kharif | Rice |
| Mysuru | Karnataka | Rabi | Wheat |

### 3.3 SELL / HOLD / WAIT Logic Verification

| Scenario | Input | Expected | Actual | Status |
|---|---|---|---|---|
| Declining price (−25.4%) | Rice Maharashtra | SELL | SELL | ✅ |
| Rising price (+41.2%) | Wheat Punjab | HOLD | HOLD | ✅ |
| Stable price (<3%) | Simulated | WAIT | WAIT | ✅ |
| Stale data (>14 days) | Simulated | WAIT | WAIT | ✅ |
| Unsupported crop (Sugarcane) | Maharashtra | null | null | ✅ |

### 3.4 Regression Bugs — All 10 Fixed

| Bug | Test | Status |
|---|---|---|
| 500 error on Ahilya Nagar / Kharif | `test_crop_recommendation_runtime_error` | ✅ Fixed |
| HOLD returned for Sugarcane | `test_advisory_without_price_model` | ✅ Fixed |
| Non-forecast crops return HOLD/SELL/WAIT | `test_no_default_hold_when_prediction_missing` | ✅ Fixed |
| Wheat/Rice price cross-contamination | `test_no_cross_crop_prediction` | ✅ Fixed |
| Forecast not exactly 30 days | `test_exactly_30_forecast_days` | ✅ Fixed |
| Advisory/predict price mismatch | `test_advisory_price_matches_predict_endpoint` | ✅ Fixed |
| Ahmednagar aliases not resolved | `test_ahilya_nagar_aliases` | ✅ Fixed |
| Weather failure causes 500 | `test_weather_provider_failure` | ✅ Fixed |
| Fake weather defaults (temp=25) | `test_no_fake_weather_defaults` | ✅ Fixed |
| Technical scores in farmer UI | `test_no_technical_scores_in_farmer_response` | ✅ Fixed |

---

## 4. Bug History (Resolved)

| Bug | Before Fix | After Fix |
|---|---|---|
| Forecast shows `₹—` for predicted price | `priceData.decision \|\| "HOLD"` hardcoded | `decision = null` returned; frontend shows "Currently unavailable" |
| 500 error on Ahilya Nagar + Kharif | Crash in mandi_service import | Fixed: null guard + try/except |
| Confidence: 0% shown to farmer | `confidence` field returned to frontend | Field removed from farmer-facing response |
| `25.0/25` raw scores shown | NLP template exposed internal scores | `why_recommended` text uses plain language only |
| 30-day label on 31-day array | Observation date included in forecast array | Now exactly 30 future points, 29-day span |
| HOLD for unsupported crops | `_derive_price_advisory` defaulted to HOLD | Returns `null` if `forecast_available = false` |

---

## 5. Technology & Design Decisions

| Decision | Rationale |
|---|---|
| FastAPI over Django/Flask | Async-native, automatic OpenAPI docs, type safety via Pydantic |
| Vanilla JS frontend (no React) | Zero build toolchain, fast load, accessible to non-JS developers |
| XGBoost over LSTM | XGBoost trains faster, more interpretable, same or better accuracy on tabular agricultural data |
| Prophet for Wheat | Strong seasonal decomposition outperforms tree models for wheat's Rabi harvest cycle |
| Groq Llama 3.3 + Gemini fallback | Groq: fast inference; Gemini: fallback for complex extraction |
| Bounded news adjustment (−5 to +3) | Prevents news from overriding agronomic science; positive bias is smaller than negative |
| Null decision (not HOLD) for unsupported crops | Honest information is better than a false signal |
| 3% advisory threshold | Matches typical mandi price measurement error + transport cost margin |

---

## 6. GitHub Repository

**URL:** https://github.com/Dhanushkumar4-ai/AgroIntel

```bash
# Clone and run
git clone https://github.com/Dhanushkumar4-ai/AgroIntel.git
cd AgroIntel/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
