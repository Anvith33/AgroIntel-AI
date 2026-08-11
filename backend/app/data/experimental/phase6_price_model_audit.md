# AgroIntel AI — Phase 6 Price Model Audit Report

## Executive Summary
This audit addresses the Wheat price prediction model loading issue where selecting **Wheat** in **Ahilya Nagar, Maharashtra** previously displayed the warning *"Price prediction is currently unavailable for this crop because a validated forecasting model is not available."*

Comprehensive inspection of the repository confirmed that all trained forecasting models for **Wheat**, **Rice**, **Maize**, **Onion**, and **Potato** exist in `models/` and load 100% successfully via `joblib.load()`.

---

## 1. Discovered Models Registry Audit

| Crop | Evaluated Best Model | Model File Path | File Exists? | Loadable? | Validation MAE | Baseline Imprv % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Rice** | Prophet (Seasonal) | `models/prophet_rice.pkl` | Yes | Yes | **23.98** | **77.56%** |
| **Wheat** | Prophet (Seasonal) | `models/prophet_wheat.pkl` | Yes | Yes | **62.92** | **55.54%** |
| **Maize** | Prophet (Seasonal) | `models/prophet_maize.pkl` | Yes | Yes | **23.79** | **86.48%** |
| **Onion** | Prophet (Seasonal) | `models/prophet_onion.pkl` | Yes | Yes | **156.63** | **85.83%** |
| **Potato** | Prophet (Seasonal) | `models/potato_prophet.pkl` | Yes | Yes | **93.54** | **92.23%** |

---

## 2. Root Cause Analysis

The bug was caused by three interacting frontend and API response handling issues:

1. **Frontend Key Mismatch**:
   In `frontend/script.js`, `renderPredResults()` checked `predData.average_price`. However, `/api/predict` returns `predicted_price`. This caused `predPriceNum` to evaluate to `null`.
2. **Phase 6 Forecast Availability Leakage**:
   When requesting price prediction for Wheat in Ahilya Nagar for Kharif season, the frontend POSTed to `/api/phase6/recommend`. The recommendation endpoint evaluated top crops for Kharif (top crop: `Horse-gram`), which returned `price_forecast.available = False` because Horse-gram is an unsupported crop. The frontend stored this as `p6Data.price_forecast` and checked `p6Data.price_forecast.available`, erroneously overwriting Wheat's prediction availability.
3. **Chart Format Discrepancy**:
   `renderPriceChart()` expected a dictionary with keys `"7_day"`, `"15_day"`, `"30_day"`. However, `/api/predict` returns an array of 30 daily prediction floats. This caused the chart points filter to evaluate to empty, hiding the 30-day forecast graph.

---

## 3. Five-Crop Verification Matrix

| Crop | State | District | Mandi Observed Price | Market Name | Observation Date | Forecast Model | 30-Day Prediction | Market Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Wheat** | Maharashtra | Ahilya Nagar | **₹2,530.33 / q** | Ahilya Nagar Market Yard | 10-08-2026 | Prophet (Seasonal) | **₹2,387.57 / q** | **HOLD** |
| **Rice** | Punjab | Ludhiana | **₹2,340.82 / q** | Ludhiana Market Yard | 11-08-2026 | Prophet (Seasonal) | **₹2,792.01 / q** | **HOLD** |
| **Maize** | Karnataka | Dakshina Kannada | **₹2,692.44 / q** | Dakshin Kannad Market Yard | 11-08-2026 | Prophet (Seasonal) | **₹1,868.37 / q** | **SELL** |
| **Onion** | Tamil Nadu | Coimbatore | **₹2,375.78 / q** | Coimbatore Market Yard | 08-08-2026 | Prophet (Seasonal) | **₹1,757.75 / q** | **SELL** |
| **Potato** | Bihar | Lakhisarai | **₹2,772.77 / q** | Lakhisarai Market Yard | 10-08-2026 | Prophet (Seasonal) | **₹1,221.17 / q** | **SELL** |

---

## 4. Verification & Testing

- **Backend Health**: `200 OK` on `http://127.0.0.1:8000/health`.
- **Wheat Forecast API**: `/api/predict?crop=wheat&state=Maharashtra&horizon_days=30` returns 30 daily predictions starting from tomorrow (`predicted_price: 2387.57`).
- **Graph Restoration**: `30-Day Price Forecast` line chart restored on localhost interface.
- **Dynamic NLP Explanation**: Generated dynamically from API output values without hardcoded multipliers.
