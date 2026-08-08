# Wheat Price Model Validation & Prophet Selection Analysis

## Executive Summary

During the Phase 4 model training and evaluation process over the 60-day chronological validation holdout set (`2024-11-02` to `2024-12-31`), **Prophet** achieved superior prediction accuracy compared to XGBoost and ARIMA for Wheat price forecasting.

### Model Evaluation Summary (Wheat)

| Model | MAE (₹/quintal) | RMSE (₹/quintal) | Selection Result |
| :--- | :---: | :---: | :--- |
| **Prophet** | **62.92** | **67.69** | **SELECTED PRODUCTION MODEL** |
| **ARIMA(1,1,1)** | 82.65 | 90.64 | Baseline |
| **XGBoost** | 84.73 | 93.29 | Candidate (`max_depth=3, lr=0.1, n_estimators=100`) |
| **LSTM** | — | — | Skipped (isolated environment) |

---

## 1. Pipeline & Leakage Audit

A comprehensive audit of the Wheat training pipeline was performed:

1. **Feature Ordering & Selection**: All 11 feature columns (`lag_1`, `lag_7`, `lag_14`, `lag_30`, `rolling_mean_7`, `rolling_mean_30`, `month`, `season`, `monthly_avg_temp`, `monthly_total_rainfall`, `black_swan`) are correctly specified.
2. **Data Leakage Check**:
   - `lag` features use `shift(1)`, `shift(7)`, etc. (Strictly past prices).
   - `rolling_mean` features use `shift(1).rolling(...)` (No future lookahead).
   - Weather features join on past historical monthly averages.
3. **Split Integrity**: Chronological holdout of the final 60 days (`train_df`: 2,102 samples, `val_df`: 60 samples). No random shuffling (`train_test_split`) was used.
4. **Hyperparameter Grid Search**: XGBoost underwent an exhaustive grid search across 27 parameter combinations (`max_depth` ∈ {3, 5, 7}, `learning_rate` ∈ {0.03, 0.05, 0.1}, `n_estimators` ∈ {100, 150, 200}). The optimal configuration achieved MAE = 84.73.

---

## 2. Scientific Justification: Why Prophet Outperforms XGBoost on Wheat

### A. Annual Rabi Agronomic Seasonality
Wheat in India is a major **Rabi (winter) crop**. Sowing begins in November–December, and harvesting takes place in March–April. The wholesale price curve follows a highly structured, smooth annual seasonal cycle.

### B. Prophet's Fourier Seasonality vs. Tree Step-Functions
- **Prophet**: Models time-series as $y(t) = g(t) + s(t) + h(t) + \epsilon_t$, where $s(t)$ uses Fourier series to fit smooth, continuous annual seasonality curves. During the November–December validation period, Prophet accurately captures the continuous seasonal curvature.
- **XGBoost**: Decision tree ensembles partition feature space into hyper-rectangular regions. When evaluating over a 60-day forecast horizon where prices transition across non-linear seasonal boundaries, tree models predict step-wise piece-wise constants. Without continuous extrapolation, XGBoost suffers higher error on Wheat's smooth seasonal transitions.

### C. Decision Rule Compliance
Per the AgroIntel v4.0 specification:
```
best_baseline = min(ARIMA, Prophet, LSTM) by MAE  --> Prophet (MAE = 62.92)
XGBoost MAE = 84.73

Since XGBoost MAE (84.73) is NOT lower than Best Baseline MAE (62.92):
--> Production Model = Prophet
```

---

## 3. Recommendation

**Keep Prophet as the production model for Wheat.** The pipeline operates correctly, without data leakage or feature mismatch. Prophet's mathematical formulation is inherently superior for Wheat's annual harvest seasonality.

---
*AgroIntel v4.0 Technical Documentation — Wheat Model Validation*
