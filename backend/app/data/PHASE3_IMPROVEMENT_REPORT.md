# AgroIntel v4.0 — Phase 3 Comprehensive Dataset & Feature Report

## 1. Executive Summary

This report documents the completion of all Phase 3 improvements for AgroIntel v4.0 prior to model training. All datasets, feature extraction logic, crop name normalization dictionaries, black swan event configurations, and weather documentation have been verified.

---

## 2. Dataset Validation Summary

| Dataset Name | Rows | Columns | Missing Values | Duplicates | Date Range / Target | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`real_historical_prices.csv`** | 10,960 | 3 (`ds`, `crop`, `y`) | 0 | 0 | 2019-01-01 to 2024-12-31 | **100% Clean** |
| **`weather_history.csv`** | 72 | 4 (`year`, `month`, `avg_temp`, `total_rainfall`) | 0 | 0 | 2019-01 to 2024-12 | **100% Clean** |
| **`crop_recommendation.csv`** | 2,200 | 8 (`N`,`P`,`K`,`temp`,`humidity`,`pH`,`rainfall`,`label`) | 0 | 0 | 22 unique crop labels | **100% Clean** |

### Crop Distribution (`real_historical_prices.csv`)
- `maize`: 2,192 daily records (mean: ₹1,857 / quintal)
- `onion`: 2,192 daily records (mean: ₹2,351 / quintal)
- `potato`: 2,192 daily records (mean: ₹1,580 / quintal)
- `rice`: 2,192 daily records (mean: ₹1,887 / quintal)
- `wheat`: 2,192 daily records (mean: ₹2,130 / quintal)
- **Continuity**: 0 missing dates per crop across all 6 years (2019–2024).

---

## 3. Crop Name Normalization & Alias Dictionary (`crop_aliases.json`)

### Improvements Made
1. **Normalization Pipeline**:
   - Lowercasing and strip space
   - Bracketed text removal (e.g. `(Common)`, `(Grade A)`, `(Loss Green)`)
   - Processing suffix & filler word stripping (`(Whole)`, `(Split)`, `Dal`, `Pulses`, `Veg`)
   - Special character stripping (`-`, `/`, `.`)
2. **`crop_aliases.json`**: Created a centralized lookup containing **116 alias patterns** mapping regional, vernacular, and mandi terms directly to canonical machine learning targets.

### Mapping Statistics
- **Total Unique District Crops**: `248`
- **Successfully Mapped District Crops**: `59` (up from initial 27)
- **Remaining Unmapped Crops**: `189`

### Why Unmapped Crops Cannot Be Mapped to the Random Forest Model
The Random Forest classifier is trained on the Kaggle 22-class agronomic dataset:
`[apple, banana, blackgram, chickpea, coconut, coffee, cotton, grapes, jute, kidneybeans, lentil, maize, mango, mothbeans, mungbean, muskmelon, orange, papaya, pigeonpeas, pomegranate, rice, watermelon]`

The 189 unmapped district crops belong to commodity categories not present in the 22-class agronomic dataset:
1. **Vegetables & Greens** (e.g., Brinjal, Tomato, Bhindi, Bitter Gourd, Bottle Gourd, Cabbage, Cauliflower, Amaranthus) — 84 crops.
2. **Spices & Condiments** (e.g., Black Pepper, Cardamom, Turmeric, Ginger, Garlic, Coriander, Ajwan, Cumin) — 38 crops.
3. **Tree & Plantation Crops** (e.g., Arecanut, Cashewnut, Rubber, Tea, Amla, Apricot, Jackfruit) — 35 crops.
4. **Millets & Coarse Grains** (e.g., Bajra, Jowar, Ragi, Barley) — 18 crops.
5. **Processed Goods & Non-Farm Commodities** (e.g., Gur/Jaggery, Butter, Ghee, Broomstick, Wood) — 14 items.

> **System Behavior**: Unmapped crops are **never deleted or ignored**. They remain valid district crop candidates. At inference time, if a district top-10 list contains unmapped crops, they are passed through as secondary recommendations, while the Random Forest ranks all mapped candidates.

---

## 4. Deterministic Black Swan Configuration (`black_swan_config.json`)

Created `app/data/black_swan_config.json` defining exact historical market disruption windows:
1. **2019 Drought Window**: `2019-06-01` to `2019-09-30` (Monsoon deficit supply shock).
2. **COVID-19 Lockdown Window**: `2020-03-15` to `2021-12-31` (Mandi closures & transport disruptions).
3. **Russia–Ukraine War Window**: `2022-02-24` to `2023-12-31` (Fertilizer price spikes & grain export bans).

`feature_engineering.py` reads this JSON dynamically. **Zero hardcoded dates exist in the code.**

---

## 5. Weather Documentation (`WEATHER_DOCUMENTATION.md`)

Created `app/data/WEATHER_DOCUMENTATION.md` detailing:
- **Reference Location**: Nagpur (`21.1458°N, 79.0882°E`) as the geographical center of India matching national average price trends.
- **Role**: Macro-seasonal climate proxy (`monthly_avg_temp`, `monthly_total_rainfall`).
- **Guarantees**: Zero live API latency during training; pre-computed `weather_history.csv` (72 months) is joined offline.
- **Future Extension**: Path for multi-location state-weighted feature stores.

---

## 6. Verification Results

| Check | Result | Verification Detail |
| :--- | :--- | :--- |
| **Exact Feature Count** | **11** | `['lag_1', 'lag_7', 'lag_14', 'lag_30', 'rolling_mean_7', 'rolling_mean_30', 'month', 'season', 'monthly_avg_temp', 'monthly_total_rainfall', 'black_swan']` |
| **Weather Join** | **PASS** | `(year, month)` inner lookup joins perfectly for all 2,192 rows per crop |
| **Black Swan Flags** | **PASS** | Deterministic 0/1 binary series generated matching config windows |
| **Null/NaN Count** | **0** | `df.isnull().sum()` = 0 across all engineered feature columns |
| **Training Pipeline** | **PASS** | `add_features(df)` converts raw price series (2,192 rows) into 2,162 feature rows |
| **Inference Pipeline** | **PASS** | `build_inference_features(price_tail, target_date, temp, rain)` outputs `(1, 11)` DataFrame |

---

## 7. Phase 3 Deliverables Created / Updated
1. `app/data/crop_aliases.json` (New)
2. `app/data/black_swan_config.json` (New)
3. `app/data/WEATHER_DOCUMENTATION.md` (New)
4. `app/ml/feature_engineering.py` (Updated to read `black_swan_config.json`)
5. `app/core/constants.py` (Updated with standardized column names & alias loader)
6. `app/data/validate_crop_dataset.py` (Updated with alias-aware mapping report)

---
*Phase 3 Improvements Complete. Awaiting approval to proceed to Phase 4 (Model Training).*
