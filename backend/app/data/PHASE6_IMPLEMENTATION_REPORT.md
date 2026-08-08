# AgroIntel v4.0 — Phase 6: Crop Recommendation Engine Implementation Report

## Executive Summary

Phase 6 implements the multi-stage, production-grade Crop Recommendation Engine for AgroIntel v4.0. The pipeline combines district-level crop history, agronomic season filtering, Random Forest candidate scoring (trained on 2,200 Kaggle samples with 99.86% accuracy), ICAR agro-climatic zone validation, and dynamic weather fusion.

---

## 1. Multi-Stage Pipeline Architecture

```
                       ┌─────────────────────────┐
                       │    User Request         │
                       │(State, District, Season)│
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   District Resolution   │
                       │(region_service: top 10) │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │      Season Filter      │
                       │ (constants.CROP_SEASONS)│
                       └────────────┬────────────┘
                                    │
                                    ▼
     ┌──────────────────────────────┴──────────────────────────────┐
     │                                                             │
     ▼                                                             ▼
┌──────────────┐                                         ┌───────────────────┐
│Soil Resolution│                                        │  Dynamic Weather  │
│(User>Geo>Def)│                                         │   Fusion Engine   │
└──────┬───────┘                                         └─────────┬─────────┘
       │                                                           │
       └────────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Random Forest Scorer   │
                       │ (predict_probabilities) │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Agro Zone Validation   │
                       │ (agro_zone_validator)   │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   Suitability Scoring   │
                       │  (0 - 100 Composite)    │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   Top 3 Recommendations │
                       │    + Explainability     │
                       └─────────────────────────┘
```

---

## 2. Key Components & Implementation Details

### A. Random Forest Classifier (`app/ml/crop_recommender.py`)
- **Dataset**: Kaggle Crop Recommendation Dataset (`app/data/crop_recommendation.csv`, 2,200 rows, 22 classes).
- **Accuracy**: **99.86%** training accuracy across 100 decision trees (`RandomForestClassifier(n_estimators=100, max_depth=12)`).
- **Artifacts Saved**: `models/crop_recommender_rf.pkl`, `models/crop_recommender_encoder.pkl`, `models/crop_recommender_metrics.json`.

### B. Dynamic Weather Fusion Engine (`recommendation_engine.py`)
- **Dynamic Weighting**: Replaced static weights with an adaptive fusion mechanism:
  $$\text{Fused Weather} = (1 - w_{\text{live}}) \times \text{Climate}_{\text{historical}} + w_{\text{live}} \times \text{Weather}_{\text{live}}$$
  - Fresh live forecast (<3 days old): $w_{\text{live}} = 0.40$ (40% live forecast, 60% historical 6-year climate).
  - Stale live forecast (>3 days old or offline): $w_{\text{live}} = 0.10$ (10% live forecast, 90% historical 6-year climate).

### C. Soil Resolution Priority
1. **Priority 1 (User Input)**: Direct user `n`, `p`, `k`, `ph` values (`soil_source: "user"`).
2. **Priority 2 (Geo Mapping)**: `app/services/soil_service.py` via `geo_soil_mapping.json` (`soil_source: "geo_mapping"`).
3. **Priority 3 (Default Mapping)**: `DEFAULT_SOIL_VALUES` for district soil type (`soil_source: "default"`).

### D. Suitability Scoring Formula (0 to 100)
$$\text{Score} = \left[ (\text{RF\_Prob} \times 40) + (\text{Weather\_Match} \times 25) + (\text{Soil\_Match} \times 20) + (\text{District\_Rank} \times 10) + (\text{Season\_Match} \times 5) \right] \times \text{Agro\_Penalty}$$

- If `not agro_zone_valid`, $\text{Agro\_Penalty} = 0.50$ (50% reduction for climate-incompatible crops).

---

## 3. Response Schema & Metadata

```json
{
  "state": "Maharashtra",
  "district": "Pune",
  "season": "Kharif",
  "soil_type": "Black Soil",
  "soil_source": "geo_mapping",
  "soil": { "N": 55.0, "P": 30.0, "K": 65.0, "pH": 7.8 },
  "weather": { "temperature": 27.2, "humidity": 68.0, "rainfall": 278.6 },
  "recommendation_metadata": {
    "generated_at": "2026-08-03T23:25:29.916323",
    "model_version": "4.0.0",
    "feature_version": "4.0.0",
    "weather_source": "Dynamic Weather Fusion (Historical Climate 90% + Open-Meteo Live 10%)",
    "soil_source": "geo_mapping",
    "district": "Pune",
    "state": "Maharashtra",
    "season": "Kharif",
    "dataset_version": "Kaggle-Crop-22-v1"
  },
  "candidate_crops": ["onion"],
  "recommended_crops": [
    {
      "crop": "onion",
      "rank": 1,
      "suitability_score": 51.0,
      "soil_match": 84.0,
      "weather_match": 69.0,
      "district_match": 100.0,
      "season_match": 100.0,
      "agro_zone_valid": true,
      "probability": 0.0455,
      "reasons": [
        "High soil suitability for Black Soil (N:55, P:30, K:65, pH:7.8).",
        "Favorable seasonal climate in Kharif (27.2°C avg temp, 278.6mm rainfall).",
        "Historically successful commercial crop in Pune district (Onion).",
        "Validated as agro-climatically compatible with Maharashtra agricultural zones."
      ]
    }
  ],
  "response_time_ms": 5.49
}
```

---

## 4. Phase 6 Code Artifacts

| File Path | Purpose |
| :--- | :--- |
| `app/ml/crop_recommender.py` | Random Forest classifier trainer & candidate probability scorer |
| `app/services/recommendation_engine.py` | Multi-stage recommendation engine with dynamic weather fusion & suitability scoring |
| `app/services/recommendation_logger.py` | Audit logger recording request parameters to `app/data/recommendation_history.json` |

---
*AgroIntel v4.0 Technical Report — Phase 6 Implementation Complete*
