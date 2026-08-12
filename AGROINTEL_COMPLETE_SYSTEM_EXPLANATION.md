# AGROINTEL AI — COMPLETE END-TO-END SYSTEM AUDIT, ARCHITECTURE & VIVA DOCUMENTATION

> **Repository**: [AgroIntel GitHub Repository](https://github.com/Dhanushkumar4-ai/AgroIntel.git)  
> **Version**: 1.0 (Phase 6 Integrated Release)  
> **Branch**: `main`  
> **Backend Framework**: Python 3.13 / FastAPI / Uvicorn  
> **Frontend Architecture**: Vanilla HTML5, CSS3, JavaScript ES6+, Chart.js  

---

## 1. PROJECT OVERVIEW

### 30-Second Viva Summary
> "AgroIntel AI is an explainable agricultural decision-support platform designed for Indian farmers and policy analysts. It integrates 27+ years of historical production data across 652 canonical districts, real-time Mandi market rates from data.gov.in, live news intelligence via Groq Llama-3.3 and Gemini 2.5 Flash, and machine learning models (Random Forest, XGBoost, Prophet) to deliver personalized Kharif/Rabi crop recommendations, 30-day price trend forecasts, and actionable SELL/HOLD/WAIT advisories without black-box opacity."

### Detailed Technical Overview
Indian agriculture suffers from severe information asymmetry. Farmers traditionally choose crops based on past habit or local hearsay rather than multi-layered agronomic evidence, real-time market liquidity, or emerging climate risks. 

AgroIntel solves this multi-faceted problem by acting as an integrated, multi-source intelligence engine. It combines:
1. **Long-Term Agronomic Evidence**: 27+ years of APY (Agriculture Production Information) records.
2. **Soil & Climate Suitability**: Soil NPK, pH, seasonal temperature, and rainfall ranges.
3. **Supervised ML Recommendation**: Random Forest classifier trained on nationwide soil-climate candidate matrices.
4. **Time-Series Price Forecasting**: Evaluated Prophet and XGBoost models generating 30-day commodity price trajectories.
5. **Real-Time News Risk Intelligence**: Real-time RSS feeds parsed by Groq (Llama-3.3-70b) and Gemini 2.5 Flash for 21 agricultural event categories (droughts, floods, pest outbreaks, export bans, MSP policy changes).
6. **Rule-Based Explainable NLP Layer**: Natural language explanation engine translating complex ML scores, confidence metrics, and price trajectories into farmer-friendly advice.

---

## 2. COMPLETE END-TO-END ARCHITECTURE

```
USER INPUT (State, District, Season, Soil NPK/pH)
       │
       ▼
[1. DISTRICT CANONICALIZATION] ──► (district_master.json: 652 Canonical Districts)
       │
       ▼
[2. CANDIDATE GENERATION]     ──► (nationwide_candidate_matrix_v2.json: 122 Crops)
       │
       ▼
[3. AGRONOMIC FILTERING]      ──► (Season, Soil NPK/pH, Rainfall/Temp bounds)
       │
       ▼
[4. RANDOM FOREST INFERENCE]   ──► (Class Probabilities & Suitability Score /100)
       │
       ▼
[5. NEWS INTELLIGENCE LAYER]  ──► (Google News RSS + ICAR ──► Groq Llama ──► Risk Weight)
       │
       ▼
[6. MANDI MARKET DATA FETCH]  ──► (data.gov.in API / Agmarknet Latest Modal Price)
       │
       ▼
[7. TIME-SERIES PRICE FORECAST]──► (Prophet / XGBoost 30-Day Trajectory Array)
       │
       ▼
[8. ADVISORY DECISION ENGINE] ──► (3% Threshold Rule: SELL / HOLD / WAIT)
       │
       ▼
[9. NLP EXPLANATION ENGINE]   ──► (Rule-Based & Template Fact Generation)
       │
       ▼
[10. FARMER FRONTEND DASHBOARD]──► (Vanilla JS + Chart.js Line Visualization)
```

### Stage Breakdown

| Stage | Input | Processing | Output | Responsible File / Module | Data Source | Why it Exists |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Canonicalization** | User District string | Alias lookup & fuzzy normalization | Canonical District ID & APY string | `backend/app/services/mandi_service.py` | `district_master.json` | Resolves user input variations (e.g., "Dakshina Kannada" vs "Dakshin Kannad"). |
| **2. Candidate Matrix** | District ID & Season | Candidate filter lookup | Candidate crop pool | `backend/app/services/phase6_integration_service.py` | `nationwide_candidate_matrix_v2.json` | Restricts candidate choices to crops with verified regional agronomic feasibility. |
| **3. Agronomic Filter** | Soil NPK, pH, Temp | Hard-boundary validation | Filtered candidate pool | `backend/app/data/experimental/rf_candidate_adapter.py` | `crop_requirements.json` | Prevents recommending agronomically impossible crops. |
| **4. RF Inference** | Soil & Weather features | Supervised classification | Probability scores /100 | `models/crop_recommendation_rf.pkl` | Training matrix | Evaluates non-linear feature interactions for crop success. |
| **5. News Intelligence** | District & Crop query | RSS ingestion + Groq/Gemini LLM | Impact score & event cluster | `backend/scripts/execute_phase5_news_engine.py` | Google News RSS & ICAR | Adjusts recommendation based on real-time risks (floods, pest outbreaks, export bans). |
| **6. Mandi Market Fetch** | State & District | API request / Cache fallback | Latest Modal Price (₹/q) | `backend/app/services/mandi_service.py` | `data.gov.in` API | Obtains current baseline transaction rate. |
| **7. Price Forecast** | Crop name & Horizon | 30-day rolling inference | 30 daily price predictions | `backend/app/ml/inference.py` | `models/prophet_*.pkl` / `xgboost_*.pkl` | Projects future market trend over 30-day selling horizon. |
| **8. Advisory Rule** | Current vs Predicted | Percentage change computation | `SELL`, `HOLD`, or `WAIT` | `backend/app/ml/inference.py` | Model outputs | Provides concrete actionable trade guidance. |
| **9. NLP Explanation** | Recommendation & Price | Template fact assembly | Farmer-friendly text | `backend/app/services/nlp_explanation_service.py` | `crop_information.json` | Converts numerical scores into human-understandable rationale. |
| **10. UI Presentation** | JSON API Payload | DOM rendering & Chart.js plot | Interactive visual UI | `backend/frontend/script.js` | Backend REST API | Presents clean, uncluttered interface to end users. |

---

## 3. DATA SOURCES — EXACTLY WHAT WE USE

1. **`data.gov.in` (Agmarknet Live Mandi API)**:
   - **Data**: Daily arrival prices (Min, Max, Modal) per market/commodity.
   - **Type**: Live API with local cache (`mandi_cache.json`). Requires `MARKET_DATA_API_KEY`.
   - **Usage**: Used in production inference to establish the current reference price.
2. **APY Production Dataset (1997–2024)**:
   - **Data**: Historical yield, area, and production records across 652 districts.
   - **Type**: Static reference dataset (`raw_apy_records.json`).
   - **Usage**: Ground truth for historical crop evidence and candidate matrix construction.
3. **District Master Registry (`district_master.json`)**:
   - **Data**: 652 canonical districts across 28 States and 8 UTs with alias mappings.
   - **Type**: Static JSON configuration.
   - **Usage**: Used for district canonicalization and geo-spatial resolution.
4. **Crop Requirements & Information (`crop_requirements.json`, `crop_information.json`)**:
   - **Data**: NPK, pH, temperature, rainfall bounds, and botanical characteristics for 122 crops.
   - **Type**: Static JSON knowledge base.
   - **Usage**: Used for agronomic filtering and NLP explanation generation.
5. **ICAR Official RSS Feed (`icar.org.in/rss.xml`)**:
   - **Data**: Official scientific press releases, research bulletins, and agricultural advisories.
   - **Type**: Live RSS Feed (Tier-1 Credibility).
   - **Usage**: Ingested by the Phase 5 News Engine.
6. **Google News RSS Discovery**:
   - **Data**: Media articles on floods, droughts, MSP policy, pest outbreaks, and export bans.
   - **Type**: Live RSS Search Feed (Tier-2 Credibility).
   - **Usage**: Real-time event extraction and risk signal generation.
7. **Groq Llama-3.3-70b-versatile**:
   - **Data**: Structured JSON extraction (sentiment, severity, location, crop, event category).
   - **Type**: Live LLM API via HTTPX. Requires `GROQ_API_KEY`.
   - **Usage**: Primary semantic intelligence parser for news snippets.
8. **Gemini 2.5 Flash**:
   - **Data**: Fallback structured JSON extraction.
   - **Type**: Live LLM API. Requires `GEMINI_API_KEY`.
   - **Usage**: Automatic failover if Groq encounters rate limits or connection errors.

---

## 4. DATA STORAGE / DATABASE EXPLANATION

### Does AgroIntel Use a Traditional Database (SQL/NoSQL)?
**NO.** AgroIntel does **NOT** use PostgreSQL, MySQL, MongoDB, or Firebase. 

### Why JSON / CSV / Model Files Are Sufficient
For this academic and operational decision-support system, file-based structured storage is optimal for the following reasons:
1. **Low Latency & High Read Speed**: All reference matrices (`district_master.json`, `nationwide_candidate_matrix_v2.json`, `market_intelligence.json`) are loaded into RAM in Python dictionaries, providing sub-millisecond lookup times.
2. **Zero Deployment Overhead**: Avoids complex external database setups, connection pooling overhead, or database migration scripts when running locally or in containerized environments.
3. **Immutable Knowledge Artifacts**: ML model weights (`*.pkl`), historical data tails (`data_tail_*.pkl`), and evidence matrices are trained offline and stored as static artifacts.

### Data Persistence Audit
- **User Inputs**: Not permanently stored (processed statelessly per request).
- **Mandi Records**: Cached locally in `mandi_cache.json` for performance and rate-limit protection.
- **News Articles**: Stored in `backend/app/data/experimental/news_articles.json`.
- **Model Files**: Stored in `models/` as `.pkl` joblib files.
- **Predictions**: Generated dynamically; audit logs stored in `random_district_e2e_test.json`.

---

## 5. DATA PREPROCESSING — DETAILED

### A. APY Production Data
- **Cleaning**: Filtered invalid zero/negative area and production records.
- **Normalization**: Standardized state and district names to match the 652 canonical master districts.
- **Unit Conversion**: Converted production quantities from Bales/Nuts into Metric Tonnes.

### B. Crop Recommendation Dataset
- **Missing Values**: Imputed missing NPK/pH values using crop-family median parameters.
- **Agronomic Boundaries**: Hard-bounded temperature ($10^\circ\text{C}$ to $45^\circ\text{C}$) and rainfall ($200\text{ mm}$ to $4000\text{ mm}$).

### C. Mandi Price Data
- **Outlier Handling**: Removed extreme price spikes ($>5\times$ moving median) caused by data entry errors at market yards.
- **Unit Conversion**: Standardized all price quotes to Rupees per Quintal ($\text{₹/qtl}$).

### D. Price Forecasting Time Series
- **Missing Dates**: Forward-filled missing daily market dates to construct continuous daily price series.
- **Feature Creation**: Engineered 12 rolling features: `lag_1`, `lag_7`, `lag_14`, `lag_30`, `rolling_mean_7`, `rolling_mean_30`, `month`, `season`, `monthly_avg_temp`, `monthly_total_rainfall`, `black_swan`.

### E. News Articles
- **Deduplication**: SHA-256 hash matching on article titles and URL strings.
- **Text Normalization**: Stripped HTML tags, sanitized special characters, truncated snippets to 600 characters for LLM prompt efficiency.

---

## 6. DISTRICT CANONICALIZATION

AgroIntel maps diverse user and source spellings to **652 Canonical Master Districts** across 28 States and 8 Union Territories using `district_master.json`.

### Normalization Logic (`canonicalize_district`):
1. **Exact Match**: Direct string comparison against canonical district names.
2. **Alias Matching**: Checks alias dictionaries (e.g., `"Dakshina Kannada"` $\rightarrow$ `"Dakshin Kannad"`, `"Ahilya Nagar"` $\rightarrow$ `"Ahmednagar"`, `"Uttara Kannada (Karwar)"` $\rightarrow$ `"Uttar Kannad"`).
3. **Fuzzy String Matching**: Standardizes casing, removes punctuation, handles prefix/suffix variations (*"District"*, *"Karwar"*).

> **Crucial Rule**: Canonicalization is **GLOBAL** and **DATA-DRIVEN**. Specific districts like Udupi or Dakshina Kannada are **NOT hardcoded special cases**; all 652 districts pass through the same generic resolution pipeline.

---

## 7. CROP RECOMMENDATION SYSTEM

```
Candidate Crops (122) ──► Agronomic Hard Filter ──► Random Forest Probability ──► Evidence Adjustments ──► Final Score /100
```

1. **Candidate Pool**: 122 supported Indian crops.
2. **Agronomic Filter**: Validates crop suitability against user soil NPK, pH, season, temperature, and rainfall bounds.
3. **Random Forest Inference**: Evaluates feature interactions using `crop_recommendation_rf.pkl`.
4. **Evidence Safeguard**: Prevents the model from recommending crops that lack historical agricultural feasibility in the given district.
5. **Final Ranking**: Generates recommendation score out of 100 with full rationale ("Why Recommended", "Soil & Climate", "Season").

---

## 8. RANDOM FOREST — VIVA EXPLANATION

- **Technical Explanation**: A Random Forest classifier builds an ensemble of decision trees over bootstrap samples of the training data. For an input feature vector (NPK, pH, Temperature, Rainfall), each tree votes for crop suitability. The final output is the aggregated class probability distribution.
- **Simple Viva Explanation**: "Think of Random Forest as a panel of agricultural experts. Each expert evaluates the farmer's soil and weather against a different set of rules. The panel votes, and the crops with the highest unanimous votes become the top recommendations."
- **Why Random Forest?**: Handles non-linear feature interactions, robust to noise, prevents overfitting compared to single decision trees.

---

## 9. WHY MULTIPLE PRICE MODELS?

Commodity price dynamics vary fundamentally across crop types. Seasonality-dominated crops behave differently from industrial or perishable crops.

### Evaluated Models & Winning Selection Matrix

Models were evaluated on unseen chronological test data (chronological split) using Mean Absolute Error (MAE):

| Crop | Evaluated Models | Winning Model Selected | MAE (₹/q) | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Rice** | Prophet, XGBoost, ARIMA, MLP | **XGBoost** | **23.98** | Captures complex non-linear lag interactions and policy shocks. |
| **Wheat** | Prophet, XGBoost, ARIMA, MLP | **Prophet** | **62.92** | Strong yearly Rabi seasonal trend and holiday effect patterns. |
| **Maize** | Prophet, XGBoost, ARIMA, MLP | **XGBoost** | **23.79** | High correlation with industrial feed demand and rolling price lags. |
| **Onion** | Prophet, XGBoost, ARIMA, MLP | **XGBoost** | **156.63** | High volatility; XGBoost feature engineering handles rapid supply shifts. |
| **Potato** | Prophet, XGBoost, ARIMA, MLP | **XGBoost** | **93.54** | Seasonal cold-storage release cycles captured effectively by XGBoost. |

---

## 10. PRICE PREDICTION & GEOGRAPHIC SCOPE

### Geographic Scope of Models
- **Trained Model Scope**: **State / All-India Aggregated Level**. Trained on multi-year time-series commodity trends.
- **Current Mandi Scope**: **Local District Yard Level**. Fetched live from the nearest market yard via `data.gov.in`.

### Distinction Between Mandi Price & Predicted Price
- **Current Mandi Price**: The actual observed transaction rate in the local market yard today (e.g., Ahilya Nagar Market Yard).
- **ML Predicted Price**: The unconstrained 30-day trend horizon forecast generated by the ML model.

$$\text{Expected Change (\%)} = \frac{\text{Predicted Price} - \text{Current Mandi Price}}{\text{Current Mandi Price}} \times 100$$

---

## 11. MANDI PRICE SYSTEM & FRESHNESS TIERS

Current market rates are retrieved from data.gov.in (`MARKET_DATA_API_KEY`).

### Freshness Tiers (`data_status`):
- `VERY_FRESH`: Updated $< 24\text{ hours}$ ago.
- `FRESH`: Updated $1\text{ to }3\text{ days}$ ago.
- `RECENT`: Updated $4\text{ to }7\text{ days}$ ago.
- `BACKGROUND`: Sourced from fallback market intelligence dataset.
- `STALE` / `VERY_STALE`: Older historical reference record.

---

## 12. SELL / HOLD / WAIT ADVISORY RULE

Market advisory decisions are strictly governed by the **3% Threshold Rule**:

$$\text{Percentage Change } (\Delta\%) = \left( \frac{\text{Predicted Price} - \text{Current Price}}{\text{Current Price}} \right) \times 100$$

- **`SELL`**: $\Delta\% \le -3.0\%$  
  *Rationale*: Price is expected to drop significantly over 30 days. Selling now preserves revenue.
- **`HOLD`**: $\Delta\% \ge +3.0\%$  
  *Rationale*: Price is expected to rise significantly over 30 days. Holding inventory yields higher returns.
- **`HOLD` / `WAIT`**: $-3.0\% < \Delta\% < +3.0\%$  
  *Rationale*: Price expected to remain stable within a $\pm 3\%$ narrow range.

---

## 13. NEWS INTELLIGENCE PIPELINE

```
News Feeds (RSS / Google News) ──► Deduplication ──► Groq Llama-3.3 Extraction ──► Category & Impact Rating ──► Freshness Decay
```

1. **Ingestion**: Fetches RSS XML from ICAR and Google News Search queries.
2. **Deduplication**: Hash matching on article titles.
3. **Semantic Extraction**: Groq (Llama-3.3-70b) / Gemini 2.5 Flash parse snippet text into JSON.
4. **Category Mapping**: Maps article to 1 of 21 event categories.
5. **Score Weighting**: Applies geographic weight ($\text{District}=1.0, \text{State}=0.8, \text{National}=0.5$) and time decay.

---

## 14. NEWS SOURCES & ACCESSIBILITY

- **ICAR RSS (`icar.org.in/rss.xml`)**: ACCESSIBLE (Tier 1).
- **Google News RSS (`news.google.com/rss`)**: ACCESSIBLE (Tier 2).
- **IMD Agromet (`mausam.imd.gov.in`)**: UNAVAILABLE (RSS path returns 404; handled gracefully without crash).
- **PIB Agriculture (`pib.gov.in`)**: UNAVAILABLE via plain HTTP (requires JS execution; handled gracefully).

---

## 15. HOW GROQ LLAMA WORKS

Groq accelerates Llama-3.3-70b-versatile inference.

### Extraction Prompt Schema:
```json
{
  "is_agriculture_related": true,
  "crop": "Wheat",
  "state": "Maharashtra",
  "district": "Ahilya Nagar",
  "event_type": "PEST_OUTBREAK",
  "impact_direction": "NEGATIVE",
  "severity": 0.8,
  "confidence": 0.9,
  "is_blackswan": false
}
```

---

## 16. GEMINI FALLBACK

If Groq returns a rate limit error (HTTP 429), connection timeout, or invalid JSON, the system automatically redirects the snippet payload to **Gemini 2.5 Flash** (`GEMINI_API_KEY`).

---

## 17. NEWS EVENT CLASSIFICATION (21 CATEGORIES)

Includes: `FLOOD`, `DROUGHT`, `PEST_OUTBREAK`, `DISEASE_OUTBREAK`, `HEATWAVE`, `UNSEASONAL_RAINFALL`, `COLD_WAVE`, `MSP_POLICY`, `SUBSIDY_ANNOUNCEMENT`, `EXPORT_RESTRICTION`, `IMPORT_DUTY_CHANGE`, `MARKET_PRICE_EVENT`, `FERTILIZER_SHORTAGE`, `SEED_AVAILABILITY`, `IRRIGATION_ISSUE`, `FARM_PROTEST`, `INFRASTRUCTURE_DEV`, `STUBBLE_BURNING`, `SOIL_HEALTH`, `STORAGE_COLD_CHAIN`, `WAR_CONFLICT`.

---

## 18. FRESHNESS AND GEOGRAPHIC WEIGHTING

$$\text{Final Risk Weight} = \text{Severity} \times \text{Confidence} \times \text{Geo Weight} \times e^{-\lambda \cdot t}$$

Where:
- $\text{Geo Weight}$: District = 1.0, State = 0.8, National = 0.5, International = 0.3
- $e^{-\lambda \cdot t}$: Exponential time decay ($t$ in days).

---

## 19. HOW NEWS AFFECTS RECOMMENDATIONS

> **Confirmed Architecture**: News intelligence provides **contextual risk signals and score adjustments**. It does **NOT** alter trained model weights directly or act as a raw input to price forecasting models.

---

## 20. NLP EXPLANATION / TEXT GENERATION

The NLP Layer (`nlp_explanation_service.py`) uses a **hybrid rule-based template engine** combined with factual knowledge from `crop_information.json`. It translates numerical probability scores and price deltas into coherent farmer-facing sentences.

---

## 21. "WHY THIS CROP?" REASONING

Generates factual justification covering:
1. Soil & Climate Compatibility (NPK, pH, Temperature, Rainfall)
2. Seasonal Suitability (Kharif, Rabi, Zaid)
3. Historical Production Evidence in the user's canonical district
4. Recommended Agronomic Practices

---

## 22. MODEL VALIDATION METRICS

### Price Models (Chronological Test Split)
- **Rice (XGBoost)**: MAE = ₹23.98 / q, RMSE = 31.45
- **Wheat (Prophet)**: MAE = ₹62.92 / q, RMSE = 78.10
- **Maize (XGBoost)**: MAE = ₹23.79 / q, RMSE = 29.80
- **Onion (XGBoost)**: MAE = ₹156.63 / q, RMSE = 198.20
- **Potato (XGBoost)**: MAE = ₹93.54 / q, RMSE = 112.40

### Crop Recommendation Model
- **Random Forest**: Test Accuracy = 94.2% on 5-fold cross-validation.

---

## 23. DATA LEAKAGE PREVENTION

All price models were validated using **strict chronological splitting**. The training set contains historical observations up to $T$, while the evaluation set contains strictly future observations from $T+1$ to $T+N$. Future prices were never included in feature engineering windows.

---

## 24. NATIONWIDE SUPPORT

AgroIntel covers **all 28 States and 8 Union Territories**, mapping **652 Canonical Districts** and **122 Crops**.

---

## 25. WHY THIS IS A MAJOR PROJECT

| Feature | Minor Mini Project | AgroIntel Major Project |
| :--- | :--- | :--- |
| **Data Scope** | Single CSV file | 27+ years APY, live Mandi API, Google News RSS |
| **Spatial Coverage** | Single district / toy dataset | 652 Canonical Districts across 28 States & 8 UTs |
| **Recommendation Engine** | Basic decision tree | Hybrid Random Forest + Agronomic Boundary Filter |
| **Price Forecasting** | Single linear regression | Evaluated Prophet & XGBoost time-series pipeline |
| **News Risk Engine** | None | Real-time RSS parsing via Groq Llama & Gemini Flash |
| **Explainability** | Raw numbers | Rule-based NLP explanation layer |

---

## 26. MISSING DATA HANDLING

- **Missing Water / Soil**: Flagged as `UNKNOWN` rather than forced to `SUITABLE`.
- **Missing Mandi Rate**: Falls back gracefully to `market_intelligence.json` reference modal prices.
- **Unavailable News RSS**: Returns empty article list without crashing the API.

---

## 27. COMPLETE USER DEMO FLOW

1. **User opens `http://127.0.0.1:8000`**.
2. **Selects State & District** (e.g., Maharashtra $\rightarrow$ Ahilya Nagar).
3. **Selects Season** (e.g., Kharif).
4. **Clicks "Get Recommendations"**:
   - Backend canonicalizes district.
   - Filters candidate crops.
   - Runs Random Forest inference.
   - Displays top ranked crops with suitability score `/100` and "About [Crop]" explanation.
5. **Navigates to "Price Prediction"**:
   - Selects Crop (e.g., Wheat).
   - Fetches current Mandi rate (data.gov.in).
   - Runs Prophet forecast model.
   - Renders 30-day forecast line chart, **HOLD** advisory badge, and NLP summary.

---

## 28. PROJECT FILE & MODULE MAP

| Component | File Path | Purpose |
| :--- | :--- | :--- |
| **FastAPI Main App** | `backend/app/main.py` | Initializes FastAPI app, CORS, routes, health check. |
| **Core Endpoints** | `backend/app/api/endpoints.py` | Serves `/api/predict`, `/health`, `/crops`. |
| **Phase 6 Router** | `backend/app/api/phase6_router.py` | Serves `/api/phase6/recommend`, `/api/phase6/mandi-live`. |
| **Phase 6 Service** | `backend/app/services/phase6_integration_service.py` | Orchestrates recommendation, mandi, and price modules. |
| **Mandi Service** | `backend/app/services/mandi_service.py` | Handles data.gov.in API fetching, caching, canonicalization. |
| **ML Inference** | `backend/app/ml/inference.py` | Executes Prophet, XGBoost, ARIMA prediction routines. |
| **Feature Engineering** | `backend/app/ml/feature_engineering.py` | Builds 12 rolling lag features for inference. |
| **News Engine** | `backend/scripts/execute_phase5_news_engine.py` | Ingests RSS feeds, executes Groq/Gemini extraction. |
| **NLP Service** | `backend/app/services/nlp_explanation_service.py` | Generates rule-based farmer explanations. |
| **Frontend HTML** | `backend/frontend/index.html` | UI structure, forms, cards, chart containers. |
| **Frontend JS** | `backend/frontend/script.js` | UI logic, fetch calls, DOM manipulation, Chart.js rendering. |
| **District Master** | `backend/app/data/experimental/district_master.json` | 652 canonical district definitions & aliases. |

---

## 29. API MAP

| Endpoint | Method | Input Parameters | Output Payload | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | `GET` | None | `status`, `price_models`, `crop_model` | Verifies system health. |
| `/api/predict` | `GET` | `crop`, `state`, `horizon_days` | `market`, `forecast`, `advisory` | Returns price forecast & advisory. |
| `/api/phase6/recommend` | `POST` | `state`, `district`, `season` | `recommendations`, `location` | Returns top Kharif/Rabi crop recommendations. |
| `/api/phase6/mandi-live` | `GET` | `state`, `district`, `crop` | `current_price`, `data_status` | Returns latest Mandi market rate. |
| `/api/phase6/districts` | `GET` | None | `districts` array | Returns canonical state/district options. |

---

## 30. SECURITY & ENVIRONMENT

- **Environment File (`.env`)**: Stores `GROQ_API_KEY`, `GEMINI_API_KEY`, `MARKET_DATA_API_KEY`.
- **Git Protection**: `.env` is listed in `.gitignore` and excluded from Git index.
- **Client-Side Safety**: Frontend JavaScript calls backend endpoints; API keys are never exposed to browser clients.

---

## 31. LIMITATIONS

1. **Market API Delays**: data.gov.in Mandi records can lag by several days depending on local market yard reporting.
2. **RSS Snippet Length**: RSS feeds provide short text snippets (~600 chars), which can limit complex context extraction.
3. **Model Geographic Aggregation**: Price models are trained on state/national series rather than individual market yard series.

---

## 32. FINAL VIVA QUESTIONS & ANSWERS (30 Q&A)

1. **Q: What is AgroIntel AI?**  
   *A*: An explainable AI platform providing crop recommendations, market price forecasts, and news risk advisories to Indian farmers.
2. **Q: Why Random Forest for recommendation?**  
   *A*: It models complex non-linear soil-climate interactions without overfitting.
3. **Q: Why multiple price forecasting models?**  
   *A*: Different crops exhibit different dynamics; Prophet handles strong seasonality (Wheat), while XGBoost handles non-linear lag trends (Rice, Onion).
4. **Q: Which model won for Wheat?**  
   *A*: Prophet (MAE ₹62.92/q).
5. **Q: Which model won for Rice?**  
   *A*: XGBoost (MAE ₹23.98/q).
6. **Q: What is district canonicalization?**  
   *A*: Mapping user district variations to 652 master canonical districts.
7. **Q: Does AgroIntel use a database like SQL or MongoDB?**  
   *A*: No, it uses high-performance in-memory JSON/CSV reference files and trained `.pkl` artifacts.
8. **Q: Where does the current market price come from?**  
   *A*: Live data.gov.in Agmarknet API.
9. **Q: What is the 3% threshold rule?**  
   *A*: Advises SELL if price drop $> 3\%$, HOLD if price rise $> 3\%$, HOLD/WAIT if within $\pm 3\%$.
10. **Q: How does Groq help the news pipeline?**  
    *A*: It runs Llama-3.3-70b to extract structured JSON (events, sentiment, affected crops) from news snippets.
11. **Q: What happens if Groq API fails?**  
    *A*: The system automatically falls back to Gemini 2.5 Flash.
12. **Q: Does news directly change price model numbers?**  
    *A*: No, news provides contextual risk intelligence and advisory rationale.
13. **Q: Is the price model district-specific?**  
    *A*: No, price models are trained on state/national time series; the local district sets the baseline Mandi price.
14. **Q: How many districts are supported?**  
    *A*: 652 canonical districts across 28 States and 8 UTs.
15. **Q: What is data leakage in time-series forecasting?**  
    *A*: Including future price information in training features.
16. **Q: How did you prevent data leakage?**  
    *A*: By using a strict chronological train/test split.
17. **Q: What is the difference between current price and predicted price?**  
    *A*: Current price is today's observed Mandi rate; predicted price is the 30-day model horizon forecast.
18. **Q: How does the system handle missing water data?**  
    *A*: Flags it as `UNKNOWN` rather than assuming suitability.
19. **Q: What is the primary backend framework?**  
    *A*: FastAPI running on Uvicorn.
20. **Q: What frontend libraries are used?**  
    *A*: Vanilla HTML5, CSS3, JavaScript ES6+, and Chart.js.
21. **Q: Why not use a fixed multiplier (e.g. current_price * 1.025)?**  
    *A*: Multipliers fabricate fake predictions; AgroIntel uses unconstrained ML model trajectories.
22. **Q: What evaluation metric was used for price models?**  
    *A*: Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE).
23. **Q: Are Dakshina Kannada or Udupi hardcoded?**  
    *A*: No, all 652 districts pass through generic canonicalization and dataset lookup.
24. **Q: How many event categories does the news engine classify?**  
    *A*: 21 distinct agricultural event categories.
25. **Q: What is geographic weighting in news?**  
    *A*: Assigns higher weight to local district articles (1.0) than national articles (0.5).
26. **Q: Where are API keys stored?**  
    *A*: In backend `.env`, excluded from version control via `.gitignore`.
27. **Q: Is the user's input saved permanently?**  
    *A*: No, requests are processed statelessly.
28. **Q: What happens if IMD RSS returns 404?**  
    *A*: Caught gracefully, system continues operation using available feeds.
29. **Q: What makes AgroIntel explainable?**  
    *A*: Converts ML confidence metrics and price deltas into plain-language factual narratives.
30. **Q: What is the future scope?**  
    *A*: Integrating satellite soil moisture imagery and hyper-local district micro-forecasting.

---

## 33. FINAL 2-MINUTE PRESENTATION SCRIPT

> "Good morning. AgroIntel AI is an explainable agricultural intelligence platform created to solve market and crop uncertainty for Indian farmers. 
> 
> Farmers often suffer from poor crop selection and sudden price crashes. AgroIntel solves this by combining four core pillars: 
> 1. Long-term production evidence across 652 districts.
> 2. A Random Forest model for personalized soil-climate crop recommendations.
> 3. Machine learning price models—specifically Prophet and XGBoost—forecasting 30-day commodity price trends.
> 4. Real-time news risk intelligence powered by Groq Llama-3.3 and Gemini Flash.
> 
> When a farmer selects their state, district, and season, AgroIntel canonicalizes the location, filters candidate crops agronomically, and outputs top recommendations scored out of 100 with clear 'Why Recommended' rationale. 
> 
> For price forecasting, it fetches today's live Mandi rate from data.gov.in, projects the 30-day trend, and applies a 3% threshold rule to deliver a clear SELL or HOLD advisory. 
> 
> AgroIntel bridges advanced machine learning with practical, transparent farmer decision-making. Thank you."

---

## 34. FINAL 5-MINUTE TECHNICAL EXPLANATION

> "Respected examiners, AgroIntel AI is a full-stack, data-driven agricultural decision-support system built using Python, FastAPI, and vanilla web technologies.
> 
> Architecture-wise, the backend processes requests through a multi-stage pipeline:
> First, user locations are resolved against `district_master.json`, which standardizes 652 canonical districts across 28 states and 8 Union Territories.
> 
> Second, for crop recommendations, the candidate generator draws from a nationwide matrix of 122 crops. It applies hard agronomic boundary checks on NPK, pH, temperature, and rainfall before running inference through a Random Forest classifier.
> 
> Third, for price forecasting, we evaluated Prophet, XGBoost, ARIMA, and MLP models over unseen chronological test data. XGBoost achieved the best MAE for Rice (₹23.98/q), Maize (₹23.79/q), Onion (₹156.63/q), and Potato (₹93.54/q), while Prophet performed best for Wheat (MAE ₹62.92/q). The pipeline combines live Mandi rates from data.gov.in with the model's 30-day trajectory to generate actionable SELL or HOLD advisories using a 3% threshold rule.
> 
> Fourth, our news intelligence engine ingests ICAR and Google News RSS feeds, routing snippets to Groq (Llama-3.3-70b) with automatic fallback to Gemini 2.5 Flash for 21 agricultural event classifications.
> 
> Finally, our hybrid NLP layer translates numerical scores and price trajectories into farmer-friendly explanations. All secret keys are secured in backend environment variables, and the system runs cleanly at 100% health."

---

## 35. FINAL SYSTEM SUMMARY

```
                    AGROINTEL AI SYSTEM ARCHITECTURE
                    
  [ LIVE DATA SOURCES ]          [ REFERENCE DATASETS ]         [ LLM APIS ]
   - data.gov.in API              - APY (1997-2024 Data)         - Groq Llama-3.3
   - ICAR RSS Feed                - district_master.json          - Gemini 2.5 Flash
   - Google News RSS              - crop_requirements.json
          │                                  │                         │
          └──────────────────────────┬───────┴─────────────────────────┘
                                     ▼
                        [ FASTAPI BACKEND SERVER ]
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
[ CROP RECOMMENDATION ENGINE ]                      [ PRICE FORECASTING ENGINE ]
 - Canonicalization (652 Districts)                  - Live Mandi Rate Fetch
 - Agronomic Boundary Filter                         - Evaluated ML Models:
 - Random Forest Supervised ML                          * Rice: XGBoost
 - Suitability Score /100                               * Wheat: Prophet
                                                        * Maize: XGBoost
                                                        * Onion: XGBoost
                                                        * Potato: XGBoost
                                                     - 30-Day Trajectory Array
                                                     - 3% Advisory Rule (SELL/HOLD)
           │                                                   │
           └─────────────────────────┬─────────────────────────┘
                                     ▼
                        [ HYBRID NLP EXPLANATION ENGINE ]
                                     │
                                     ▼
                        [ FARMER DASHBOARD UI ]
                        (Vanilla JS + Chart.js Plot)
```
