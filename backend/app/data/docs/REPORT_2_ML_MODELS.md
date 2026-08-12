# AgroIntel AI — ML Model Documentation

**Version:** 4.1 Final | **Date:** 2026-08-12

---

## 1. Overview

AgroIntel trains and deploys 4 price-forecasting model architectures per crop. For each crop, models compete and the best is selected based on validated MAE/RMSE from holdout testing.

### Supported Crops

| Crop | Best Model | Training Horizon |
|---|---|---|
| Rice | XGBoost | 2000–2024 monthly + augmented |
| Wheat | Prophet | 2000–2024 monthly + seasonal |
| Maize | XGBoost | 2000–2024 monthly |
| Onion | XGBoost | 2000–2024 monthly (high volatility) |
| Potato | XGBoost | 2000–2024 monthly |

---

## 2. Model 1: XGBoost (Primary for Rice/Maize/Onion/Potato)

**Library:** `xgboost` (gradient boosted decision trees)

**Features (11 features):**
```
lag_1, lag_7, lag_14, lag_30       — price history lags
rolling_mean_7, rolling_mean_30    — smoothed trend
month                              — seasonal month (1–12)
season                             — season encoding (Kharif=0, Rabi=1, Summer=2)
monthly_avg_temp                   — average temperature (°C)
monthly_total_rainfall             — monthly rainfall (mm)
black_swan                         — binary (1 = active market disruption)
```

**Training:**
- Input: 11 features from historical price dataset (2000–2024)
- Output: Predicted price (₹/quintal)
- Validation: 80/20 train-test split
- Hyperparameters: n_estimators=200, max_depth=6, learning_rate=0.05

**Inference:**
- Multi-step recursive: uses its own predictions as lags for next-day prediction
- Generates 30 daily prices iteratively

**Why XGBoost:** Handles non-linear price spikes, crop-specific patterns, captures interaction between weather and price lags.

---

## 3. Model 2: Prophet (Primary for Wheat)

**Library:** `prophet` by Facebook/Meta

**Architecture:** Additive decomposition model
```
y(t) = trend(t) + seasonality(t) + holidays(t) + ε(t)
```

**Configuration:**
- `yearly_seasonality=True` — Indian crop price cycles follow annual patterns
- `weekly_seasonality=False` — monthly data; weekly pattern not applicable
- Custom India-specific changepoints for monsoon onset, harvest periods
- Black swan holidays added as regressors

**Training:**
- Input: (ds: date, y: price) time series from 2000–2024
- Output: Forecast with uncertainty intervals (yhat, yhat_lower, yhat_upper)

**Why Prophet for Wheat:** Wheat follows a very strong, consistent seasonal pattern (Rabi harvest March–April → price drop). Prophet's seasonal decomposition captures this reliably.

---

## 4. Model 3: ARIMA (Statistical Baseline)

**Library:** `statsmodels`

**Order:** ARIMA(p, d, q) — auto-selected via AIC/BIC minimization per crop

**Configuration:**
- Differencing order (d): typically 1 (prices are non-stationary)
- AR terms (p): 1–3 lags depending on autocorrelation
- MA terms (q): 0–2

**Limitation:** Does not incorporate external features (temperature, rainfall, black swan). Used as ensemble component.

---

## 5. Model 4: MLP Neural Network (Deep Learning)

**Library:** `sklearn.neural_network.MLPRegressor`

**Architecture:**
- Input: 11 features (same as XGBoost)
- Hidden layers: (128, 64, 32)
- Activation: ReLU
- Output: Single price prediction

**Training:**
- Requires ≥30 recent observations for reliable inference
- StandardScaler normalization on inputs
- Early stopping with validation fraction

---

## 6. Model Evaluation Results (from price_model_evaluation.json)

| Crop | Best Model | MAE (₹/quintal) | RMSE | R² |
|---|---|---|---|---|
| Rice | XGBoost | ~45 | ~67 | ~0.89 |
| Wheat | Prophet | ~38 | ~55 | ~0.91 |
| Maize | XGBoost | ~52 | ~78 | ~0.86 |
| Onion | XGBoost | ~156 | ~230 | ~0.74 |
| Potato | XGBoost | ~93 | ~140 | ~0.81 |

> **Note:** Onion and Potato have higher MAE due to extreme price volatility (supply shocks, weather events, export decisions). This is why the SELL/HOLD advisory uses ±5% threshold for these crops.

---

## 7. Advisory Decision Thresholds

| Crop | Threshold | Rationale |
|---|---|---|
| Rice, Wheat, Maize | ±3.0% | Lower volatility; model error < ±3% of market movement |
| Onion, Potato | ±5.0% | High volatility; MAE > ₹90. 3% threshold would generate too many false signals |

---

## 8. Model Limitations (Honest Disclosure)

1. **State is NOT a model feature.** The ML forecast is crop-level. Two states may show different current Mandi prices, but the same 30-day forecast trajectory.
2. **District-level price prediction is NOT available.** No district-level price data was used in training.
3. **Models do not incorporate:** fuel prices, transport costs, export policy changes (these are captured in the news intelligence layer but not in the ML features).
4. **Training data ends at 2024.** The model cannot learn from events after its training cutoff.
5. **30-day forecast uncertainty increases** with horizon. Day 1 predictions are more accurate than Day 30.
6. **Black swan events** (wars, pandemics, export bans) are approximated via a binary feature. Actual magnitude may differ.

---

## 9. Model Files

All models stored in `backend/models/`:

```
rice_models.joblib      — {xgboost, arima, mlp, data_tail, metrics}
wheat_models.joblib     — {prophet, xgboost, arima, mlp, data_tail, metrics}
maize_models.joblib     — {xgboost, arima, mlp, data_tail, metrics}
onion_models.joblib     — {xgboost, arima, mlp, data_tail, metrics}
potato_models.joblib    — {xgboost, arima, mlp, data_tail, metrics}
```

Each bundle contains the serialized model objects + a data_tail (recent 60 days of prices for lag features) + metrics dict.
