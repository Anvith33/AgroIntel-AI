# AgroIntel v4.0 — API Integration Guide for Frontend Developers

## Overview

This guide details how `script.js` consumes FastAPI endpoints exposed by the AgroIntel v4.0 backend.

---

## 1. Endpoints & Integration Patterns

### 1. Initial Load & Metadata (`GET /api/demo`)
- **Called On**: Application initialization (`DOMContentLoaded`).
- **Purpose**: Retrieves supported crops, states, districts, seasons, and horizons to populate `<select>` dropdowns dynamically.
- **Handling**:
  ```javascript
  const res = await fetch("/api/demo");
  const data = await res.json();
  // Populates recState, advState, predState dropdowns
  ```

### 2. System Health Monitoring (`GET /health`)
- **Called On**: Periodic check / startup.
- **Purpose**: Checks status of price models, crop recommender, registry, weather API, and market API.
- **Handling**: Updates header status badge to "System Ready" (Green Pulse) or "System Degraded" (Amber Pulse).

### 3. Crop Recommendation (`POST /api/predict/crop`)
- **Payload**:
  ```json
  {
    "state": "Maharashtra",
    "district": "Pune",
    "season": "Kharif",
    "n": 55.0,
    "p": 30.0,
    "k": 65.0,
    "ph": 7.8
  }
  ```
- **Rendering**: Generates recommendation cards for top 3 crops, renders normalized RF probabilities, suitability scores, score breakdowns, and bullet-point reasons.

### 4. Price Prediction & Chart.js (`GET /api/predict/price`)
- **Query Params**: `crop`, `state`, `horizon_days`
- **Rendering**:
  - Updates metric cards with Current Mandi Price, 30-Day Predicted Average, Expected Change %, Storage Cost (2.0%), Net Gain %, and Trend Strength.
  - Passes `daily_prediction_series`, `trend_line`, and `confidence_series` (`upper_bound`, `lower_bound`) to Chart.js context to plot interactive line charts.

### 5. Combined Advisory (`POST /api/advisory`)
- **Payload**: `state`, `district`, `season`, `crop` (optional)
- **Rendering**: Displays unified farmer advisory statement, target price forecast, action recommendation (`HOLD`/`SELL`), and consolidated explainability reasons.

---
*AgroIntel v4.0 API Integration Guide Complete*
