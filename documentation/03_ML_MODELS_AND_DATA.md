# AgroIntel — ML Models & Data Sources

> **Version:** 4.1 Final | **Date:** 2026-08-16

---

## 1. Price Forecasting Models

AgroIntel trains 4 competing model architectures per crop. The best performer (lowest MAE on holdout) is selected as the production model.

### 1.1 Model Selection Results

| Crop | Production Model | MAE (₹/qtl) | RMSE | R² |
|---|---|---|---|---|
| Rice | XGBoost | ~45 | ~67 | ~0.89 |
| Wheat | Prophet (Facebook) | ~38 | ~55 | ~0.91 |
| Maize | XGBoost | ~52 | ~78 | ~0.86 |
| Onion | XGBoost | ~156 | ~230 | ~0.74 |
| Potato | XGBoost | ~93 | ~140 | ~0.81 |

> **Note on Onion/Potato:** Higher MAE is expected — these are volatile commodities subject to supply shocks, weather events, and export decisions. The advisory threshold for these crops is widened to ±5% to avoid false signals.

---

### 1.2 Model 1: State-Aware XGBoost (Primary — Rice, Maize, Onion, Potato)

**Library:** `xgboost` (gradient boosted decision trees)

**Input Features (14 total):**

| Feature | Type | Description |
|---|---|---|
| `state_enc` | int | Encoded state label (LabelEncoder) |
| `lag_1` | float | Price 1 day ago |
| `lag_7` | float | Price 7 days ago |
| `lag_14` | float | Price 14 days ago |
| `lag_30` | float | Price 30 days ago |
| `rolling_mean_7` | float | 7-day rolling mean |
| `rolling_mean_30` | float | 30-day rolling mean |
| `rolling_std_7` | float | 7-day price volatility |
| `price_range` | float | Max − Min over window |
| `month` | int | Calendar month (1–12) |
| `day_of_year` | int | Day of year (1–365) |
| `day_of_week` | int | Day of week (0–6) |
| `year` | int | Calendar year |
| `black_swan` | int | Binary (1 = active market disruption) |

**Hyperparameters:**
```
n_estimators  = 200
max_depth     = 6
learning_rate = 0.05
subsample     = 0.8
```

**Inference Method:** Multi-step recursive forecasting
- Uses its own Day N prediction as lag input for Day N+1
- Generates exactly 30 daily prices

**Why XGBoost:** Handles non-linear price spikes, captures weather-price interactions, robust on Indian agricultural data patterns.

---

### 1.3 Model 2: Prophet (Primary — Wheat)

**Library:** Facebook Prophet

**Architecture:** Additive decomposition
```
y(t) = trend(t) + seasonality(t) + holidays(t) + ε(t)
```

**Configuration:**
- `yearly_seasonality = True` — Indian crop prices follow annual harvest cycles
- `weekly_seasonality = False` — monthly data; not applicable
- Custom changepoints for monsoon onset and harvest periods
- Black swan events added as holiday regressors

**Why Prophet for Wheat:** Wheat follows a very consistent seasonal pattern — Rabi harvest (March–April) causes a reliable price drop. Prophet's seasonal decomposition captures this better than XGBoost for this crop.

---

### 1.4 Model 3: ARIMA (Statistical Baseline)

**Library:** `statsmodels`

**Order:** ARIMA(p, d, q) — auto-selected via AIC/BIC minimization

```
p (AR terms):  1–3 lags based on autocorrelation
d (diff order): 1 (prices are non-stationary)
q (MA terms):  0–2
```

**Limitation:** Does not incorporate external weather or event features. Used as a benchmark/ensemble component only.

---

### 1.5 Model 4: MLP Neural Network

**Library:** `sklearn.neural_network.MLPRegressor`

**Architecture:**
```
Input (14 features) → [128] → [64] → [32] → Output (1 price)
Activation: ReLU
Normalization: StandardScaler on all inputs
```

**Note:** Requires StandardScaler fitted during training. Minor `InconsistentVersionWarning` from sklearn version mismatch is safe to ignore.

---

## 2. Crop Recommendation Model

### 2.1 Random Forest Classifier

**Library:** `sklearn.ensemble.RandomForestClassifier`

**Task:** 22-class classification (crop type) given soil + climate features

**Training Data:** Nationwide district × crop × season candidate matrix  
(246,000+ APY historical cultivation records across 652 districts, 1997–2024)

**Input Features:**
```
N, P, K        — soil nutrient levels (kg/ha)
soil_pH        — soil acidity
temperature    — monthly average (°C)
rainfall       — monthly total (mm)
season_enc     — Kharif=0, Rabi=1, Zaid=2
state_enc      — encoded state label
```

**Output:** Probability scores per candidate crop (used as `suitability_score`)

**Why Random Forest:** Handles complex non-linear interactions between soil, climate, and crop success. Naturally provides class probabilities. Robust to missing features.

---

## 3. Advisory Decision Rules

```
Supported crops (rice, wheat, maize, onion, potato):
  forecast_available = True
  If (pred - curr) / curr <= −3.0%  → SELL
  If (pred - curr) / curr >= +3.0%  → HOLD
  Else                              → WAIT
  If data_age_days > 14            → WAIT (override)

  For Onion and Potato: threshold = ±5.0%

Unsupported crops (sugarcane, cotton, soybean, etc.):
  forecast_available = False
  decision           = null   ← NEVER "HOLD"
  farmer_message     = "A reliable 30-day price forecast is currently unavailable..."
```

---

## 4. Data Sources

### 4.1 Historical Price Data — AGMARKNET (Primary)

| Property | Value |
|---|---|
| Source | data.gov.in — Agriculture Market Data (AGMARKNET) |
| Records | 178,522 state-level daily mandi records |
| Period | 2019–2024 |
| Coverage | 28 Indian states × 5 crops |
| Fields | min_price, max_price, modal_price, arrival_date, market_name |
| Update Frequency | Every 24–72 hours via API |
| API | `https://api.data.gov.in/resource/...` (requires API key) |
| Fallback | Cached JSON → MSP (Minimum Support Price) estimates |

**Data Cleaning applied:**
- Remove duplicates and zero-price records
- Clip outliers beyond ±3σ of rolling 30-day mean
- Fill short gaps with linear interpolation
- Anti-leakage: `shift(1)` on all lag features
- Black swan binary flag for known disruption periods

### 4.2 Live Mandi Price — API Fetch

```python
mandi_service.get_latest_price(crop, state)
  → Tries AGMARKNET API first
  → Falls back to cached market_intelligence.json
  → Falls back to MSP estimate if both unavailable
  → Returns: modal_price, market_name, arrival_date, data_age_days, source
```

### 4.3 Weather Data — Open-Meteo

| Property | Value |
|---|---|
| API | `https://api.open-meteo.com/v1/forecast` |
| Variables | temperature_2m, precipitation, relative_humidity_2m |
| Coverage | Any GPS coordinate (lat/lon) |
| Rate Limit | Free tier — sufficient for normal use |
| Fallback | UNAVAILABLE status; recommendation still proceeds |

### 4.4 APY Cultivation Evidence

| Property | Value |
|---|---|
| Source | Agriculture Production Information (APY), Government of India |
| Records | 246,000+ historical cultivation records |
| Period | 1997–2024 |
| Coverage | 652 canonical districts × 122 crop types × 3 seasons |
| Format | Nationwide candidate matrix JSON |

### 4.5 News Intelligence Sources — 37 Sources, 4 Tiers

| Tier | Sources | Weight | Status |
|---|---|---|---|
| TIER 1 — Official | ICAR, PIB, Ministry of Agriculture, IMD, KVK, State Agriculture Dept | 1.00 | OFFICIAL |
| TIER 2 — Research | Krishi Jagran, Rural Voice, AgroSpectrum, AgriWatch, FAO | 0.80 | AGRI_RESEARCH |
| TIER 3 — Business | Reuters, Economic Times, Business Standard, Financial Express | 0.60 | BUSINESS_MARKET |
| TIER 4 — National | The Hindu, Indian Express, Times of India, Hindustan Times | 0.40 | NATIONAL_MEDIA |

**News Processing Pipeline:**
```
Google News RSS → Groq Llama 3.3 70B / Gemini 2.5 Flash
    → Extract 21 agricultural event categories
       (droughts, floods, pest outbreaks, export bans, MSP changes, etc.)
    → Compute bounded risk weight (−5 to +3 points)
    → Apply to recommendation score ONLY if crop is agronomically valid
```

---

## 5. Black Swan Events Registry

Events that affect price forecasts via the `black_swan` binary feature:

| Period | Event | Impact |
|---|---|---|
| Jun–Sep 2019 | 2019 Drought | Supply reduction → price spike |
| Mar–Jun 2020 | COVID-19 Lockdown | Transport disruption → price spike |
| Jul–Dec 2020 | COVID-19 Recovery | Demand normalization |
| Feb–Jun 2022 | Russia–Ukraine War | Fertilizer/wheat supply shock |
| Jul–Dec 2022 | War Supply Disruption | Ongoing supply chain impact |
| Jan–Sep 2023 | Post-War Inflation | Lingering price elevation |

---

## 6. Model Limitations (Honest Disclosure)

1. **State is used for Mandi price lookup only** — it is NOT a trained feature in the ML model. Two states may show different current prices but the same forecast trajectory.
2. **District-level price forecasting is not available** — no district-level price data was used in training.
3. **Models do not incorporate:** fuel prices, transport costs, export policy changes — these are approximated via the news intelligence layer only.
4. **Training data ends at 2024** — the model cannot learn from events after its training cutoff.
5. **30-day uncertainty increases with horizon** — Day 1 predictions are more accurate than Day 30.
6. **Onion and Potato are highly volatile** — MAE > ₹90/qtl; advisory threshold widened to ±5%.
