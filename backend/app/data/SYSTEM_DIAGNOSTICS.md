# AgroIntel v4.0 — System Diagnostics & Infrastructure Audit Report

## Executive Summary

The AgroIntel v4.0 system diagnostics endpoint (`GET /api/system/info`) provides operational visibility into machine learning library dependencies, OS resource utilization, model artifact memory footprints, cached datasets, and application uptime.

---

## 1. System Diagnostics Specification (`GET /api/system/info`)

### Response Structure

```json
{
  "application": "AgroIntel v4.0",
  "python_version": "3.11.9",
  "fastapi_version": "0.109.2",
  "prophet_version": "1.1.5",
  "xgboost_version": "2.0.3",
  "tensorflow_available": true,
  "system_os": "Darwin 23.6.0",
  "cpu_usage_percent": 12.4,
  "memory_usage": {
    "rss_mb": 278.09,
    "vsz_mb": 4120.50,
    "memory_percent": 1.72
  },
  "loaded_models_count": 26,
  "cached_data_files_count": 14,
  "server_uptime_seconds": 184.2
}
```

---

## 2. Infrastructure & ML Dependency Matrix

| Component | Library / Binary | Version | Status | Operational Role |
| :--- | :--- | :---: | :---: | :--- |
| **Web Server** | FastAPI / Uvicorn | `0.109.2` | **ACTIVE** | Asynchronous HTTP routing, OpenAPI documentation, and request validation |
| **TimeSeries Baseline** | Prophet | `1.1.5` | **ACTIVE** | Additive seasonal trend forecasting for Wheat, Rice, and Maize |
| **Gradient Boosting** | XGBoost | `2.0.3` | **ACTIVE** | Production recursive feature predictor across all 5 crop commodities |
| **Deep Learning** | TensorFlow / Keras | `2.15.0` | **ACTIVE** | Sequential LSTM neural network model execution |
| **Random Forest** | Scikit-Learn | `1.4.1` | **ACTIVE** | Multi-stage crop recommendation classifier (99.55% test accuracy) |

---

## 3. Resource Memory Footprint Analysis

- **Base Process RSS Memory**: **~278.09 MB**
- **Model Registry Footprint**: 26 trained model files (`.pkl` and `.keras`) occupy under 45 MB on disk.
- **In-Memory Caching Strategy**: Lifespan startup manager caches model registry metadata, region crop mappings, weather history, and soil profiles into RAM, eliminating per-request disk reads.

---
*AgroIntel v4.0 Technical Report — System Diagnostics Complete*
