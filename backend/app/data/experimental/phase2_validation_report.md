# AgroIntel Phase 2 — Nationwide Intelligence & Suitability Validation Report

**Executive Summary & Agronomic Suitability Verification**
*Audit Date: 2026-08-11 | Branch: `agriculture-api-testing` | Scope: ALL INDIA*

---

## 1. Multi-Dimensional Data Distinction (Historical vs Current vs Suitable)

AgroIntel Phase 2 strictly maintains the three fundamental agronomic principles:
1. **WHAT WAS GROWN HISTORICALLY**: 246,091 official APY records (1997–2015) in `district_crop_evidence.json`.
2. **WHAT IS CURRENTLY GROWN**: Discovered current/recent official evidence (2023–2026) in `current_crop_evidence.json`.
3. **WHAT IS SUITABLE TO GROW NOW**: Multi-factor agronomic suitability (Soil pH/NPK, Season, Water, Temperature, Duration Window, and Crop Rotation) in `crop_requirements.json` & `experimental_candidate_dataset.json`.

> **Data Integrity Constraint**: "Not found" is NEVER converted into "not grown", and "historical evidence" is NEVER converted into "currently grown". Districts lacking 2024-2026 records maintain `current_data_status = "insufficient"`.

---

## 2. Summary of Phase 2 Datasets Created

| Dataset File | Description | Records / Coverage |
|:---|:---|:---|
| `current_crop_evidence.json` | Nationwide current crop evidence & status classification | **652 Districts** across **33 States/UTs** |
| `crop_season_calendar.json` | `DISTRICT + SEASON + CROP` seasonal mapping | **Kharif, Rabi, Summer, Whole Year** |
| `crop_family_mapping.json` | Agronomic crop families, categories & rotation groups | **122 Canonical Crops** |
| `crop_requirements.json` | Soil pH, NPK, Water, Temp, Duration requirements | **122 Canonical Crops** |
| `current_agriculture_sources.json` | Official current data sources & freshness policies | **5 Official Source Registries** |
| `news_source_registry.json` | News hierarchy, credibility & geo relevance weights | **Tier 1 (1.0), Tier 2 (0.80), Tier 3 (0.0)** |
| `news_intelligence_schema.json` | Market shock & news impact extraction schema | **12 Event Types, Severity & Impact Vectors** |
| `experimental_candidate_dataset.json` | Integrated experimental candidate matrix | **1,464 Candidate Evaluation Vectors** |

---

## 3. Crop Seasonality & Seasonal Calendar Metrics

- **Kharif Season Observations**: 11,135 crop-district mappings
- **Rabi Season Observations**: 8,167 crop-district mappings
- **Summer / Zaid Season Observations**: 1,613 crop-district mappings
- **Whole Year / Perennial Observations**: 10,582 crop-district mappings

---

## 4. Crop Rotation Engine Architecture

The crop rotation evaluation module measures candidate suitability using 5 agronomic dimensions:
1. **Same Crop Monoculture Penalty**: Severe score penalty (0.35) if repeating the exact same heavy feeder (e.g. Rice after Rice).
2. **Legume Nitrogen Restoration**: High bonus (0.95) for leguminous pulse crops (Moong, Urad, Chickpea) following heavy cereal nitrogen feeders (Rice, Wheat).
3. **Nutrient Habit Balance**: Alternating heavy N/K feeders with light feeders or deep taproot soil restorers.
4. **Disease Cycle Break**: Rotating crop families (e.g., Poaceae -> Fabaceae -> Brassicaceae) breaks host-specific soil pathogen cycles.
5. **Cultivation Window Duration Compatibility**: Matching crop `duration_days` window with the seasonal window.

---

## 5. News Intelligence & Market Shock Layer

- **Hierarchy**: Tier 1 Government/IMD/PIB (1.0 weight) > Tier 2 Business/Agri Media (0.80 weight). Tier 3 unverified web content is assigned **0.0 weight** and excluded from ML inference.
- **Geographical Relevance Weighting**:
  - District-level event: **1.00**
  - State-level event: **0.80**
  - National-level event: **0.50**
  - International trade event: **0.30**
- **Impact Analysis Vectors**: Production Impact %, Supply Impact, Demand Impact, Expected Price Direction (BULLISH / BEARISH / STABLE).
- **Freshness Decay**: Time-decay half-life based on event type (e.g., Weather Warning = 7 days half-life; Export Policy = 90 days half-life).

---

## 6. Phase 2 Verification Checklist

- [x] All 8 Phase 2 experimental datasets generated cleanly in `app/data/experimental/`.
- [x] Applied nationwide across all 652 districts and 33 states/UTs (Zero state/district hardcoding).
- [x] Preserved strict separation between Historical, Current, and Suitable evidence.
- [x] Retained `app/services/mandi_service.py` and `app/data/region_crop_mapping.json` untouched.
- [x] Zero changes to production ML models, recommendation engine, price predictor, or frontend.
- [x] Verified on branch `agriculture-api-testing`.
