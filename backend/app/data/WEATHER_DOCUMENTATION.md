# Weather Feature Engineering & Reference Location Documentation

## Executive Summary

In AgroIntel v4.0, historical weather features (`monthly_avg_temp` and `monthly_total_rainfall`) are constructed using historical climate data backfilled from the **Open-Meteo Archive API** for the geographical reference location of **Nagpur, Maharashtra, India** (Latitude: 21.1458° N, Longitude: 79.0882° E).

This document details the architectural rationale, scientific justification, limitations, and future scalability path for this design choice.

---

## 1. Selection of Nagpur as the National Reference Location

### Rationale
1. **Geographical Centrality**: Nagpur is recognized as the geographical center of India (indicated by the historical *Zero Mile Marker*). It sits at the intersection of Northern, Peninsular, and Central agricultural belts.
2. **Alignment with National Price Dataset**: The primary price dataset (`real_historical_prices.csv`) contains daily modal prices aggregated at the **national macro level** across major Indian mandis for 5 strategic crops (Wheat, Rice, Maize, Potato, Onion).
3. **Macro-Climate Representation**: Central India experiences distinct, representative monsoon (Kharif), winter (Rabi), and summer (Zaid) climate transitions that correlate strongly with nationwide crop production cycles and seasonal arrival volumes.

---

## 2. Weather as a Generalized Seasonal Climate Feature

In macro-economic price prediction, daily hyper-local weather fluctuations (e.g. today's local rain in a single district) do not directly drive national wholesale mandi price movements.

Instead, commodity price dynamics are governed by:
- **Macro-Seasonal Climate Trends**: Overall monsoon intensity, seasonal temperature curves, and cumulative monthly precipitation.
- **Seasonality & Crop Harvesting Windows**: Major harvest arrivals occur during specific climatic transitions across major producing belts.

Therefore, `monthly_avg_temp` and `monthly_total_rainfall` serve as **generalized macro-climate proxies** in the 11-feature time-series model rather than micro-local inputs.

---

## 3. Operational Guarantee: Zero Live API Latency During Training & Inference

- **Training Pipeline**: Reads historical monthly weather directly from the pre-computed `weather_history.csv` (72 months, 2019–2024). **Zero API calls** occur during model training.
- **Inference Pipeline**: Obtains live 7-day forecast aggregates via `weather_service.py` to populate current month features for real-time model prediction.

---

## 4. Limitations of the Current Approach

1. **Regional Variation Blending**: Highly localized climatic shocks (e.g., flash floods in Himachal Pradesh affecting apple/tomato prices or coastal cyclones in Odisha) are smoothed out when using a single central reference coordinate.
2. **Crop-Specific Production Belt Mismatch**: Wheat production is heavily concentrated in Northern India (Punjab, Haryana, UP), whereas Rice spans Eastern/Southern coastal belts. A central India reference captures macro monsoon trends but not state-specific micro-variations.

---

## 5. Future Extension: State-Level and District-Level Weather Feature Store

To extend AgroIntel in production environments, the architecture supports a seamless upgrade path:

1. **Multi-Location Weather Backfill**: Expand `backfill_weather.py` to store monthly historical weather indexed by `(state_code, year, month)` or `(district_id, year, month)`.
2. **Feature Store Integration**: Store spatial weather series in a centralized feature store (e.g., BigQuery, Feast, or PostgreSQL/TimescaleDB).
3. **State-Weighted Feature Engineering**: Modify `feature_engineering.py` to join price records with weighted state weather based on major crop production share (e.g., Punjab weather weighted for Wheat, West Bengal weather for Rice).

---
*AgroIntel v4.0 Technical Documentation — Phase 3*
