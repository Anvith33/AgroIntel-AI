# AgroIntel AI — Viva / Presentation Reference

**Version:** 4.1 Final | **Date:** 2026-08-12  
**Repository:** https://github.com/Dhanushkumar4-ai/AgroIntel

---

## WHAT IS AGROINTEL?

AgroIntel is an **AI-powered agricultural decision support system** for Indian farmers and agricultural officers. It integrates:
- Machine learning crop price forecasting
- Evidence-based district-level crop recommendation
- Real-time Mandi market data
- News intelligence from 35+ agricultural sources
- SELL / HOLD / WAIT market advisory

The system helps farmers make **data-driven decisions** about what to grow (Crop Recommendation) and when to sell (Price Prediction).

---

## WHY IS THIS A MAJOR PROJECT?

| Feature | Complexity |
|---|---|
| 4 ML model architectures per crop | XGBoost, Prophet, ARIMA, MLP |
| 5 supported crops | Rice, Wheat, Maize, Onion, Potato |
| 700+ district resolution with aliases | Dynamic normalization + token-overlap |
| Real-time Mandi data integration | data.gov.in AGMARKNET API |
| 7-tier news intelligence pipeline | 35+ sources + Groq Llama 3.3 70B |
| 15-point scoring recommendation engine | Evidence × Season × Soil × Weather × Rotation |
| Black Swan detection | Binary event feature in ML training |
| NLP explanations for every recommendation | Groq-powered explainability |
| Honest limitations | District price = not a feature; labeled clearly |

---

## KEY TECHNICAL DECISIONS (for viva Q&A)

### Q: Why XGBoost for Rice but Prophet for Wheat?

**A:** Based on actual model evaluation (MAE/RMSE on 20% holdout test set):
- Wheat follows a very strong, consistent seasonal pattern (Rabi harvest → price drop every April). Prophet's additive seasonal decomposition captures this pattern extremely well (MAE ~₹38).
- Rice and other crops have more complex interactions with lagged prices, weather, and supply shocks. XGBoost's gradient boosting with lag features handles these non-linearities better.

### Q: Why does the ML forecast show the same value regardless of State?

**A:** By scientific design. The trained model's 11 features do not include state as a variable. Training was done on national-average price data. The ML forecast is therefore **crop-level, not state-level**. The system is honest about this — the UI shows: *"Crop-level 30-day ML forecast. State is not a trained feature."*

What DOES vary by state is the **current Mandi price** — that comes from the live data.gov.in API with a separate cache key per `crop:state`.

### Q: How does SELL/HOLD/WAIT work?

**A:** The advisory uses 3 inputs:
1. **Current Mandi price** (from data.gov.in API)
2. **ML forecast at 30 days** (from best model)
3. **Data freshness** (observation_date, data_age_days)

Decision rules:
- If data > 14 days old → **WAIT** (stale, cannot trust comparison)
- If forecast change < threshold → **WAIT** (within model uncertainty)
- If forecast drops > threshold → **SELL** (downside risk)
- If forecast rises > threshold → **HOLD** (better price coming)

Thresholds: ±3% for Rice/Wheat/Maize (low MAE), ±5% for Onion/Potato (high MAE = high uncertainty).

### Q: How does district resolution work?

**A:** 5-step resolution:
1. Direct exact match (case-insensitive)
2. Normalized match (remove diacritics, punctuation)
3. State + district combined normalized match
4. Parenthetical removal (e.g., "Bangalore (Urban)" → "bangalore urban")
5. Token-overlap Jaccard similarity fallback (threshold ≥ 0.4)

This means "Dakshina Kannada", "DAKSHINA KANNADA", "South Canara" all resolve to `Karnataka::Dakshin Kannad`.

### Q: What news sources does AgroIntel use?

**A:** 7 tiers, 35+ sources. Key ones:
- **Tier 1 Official:** ICAR, PIB, IMD, Ministry of Agriculture
- **Tier 1B Dynamic:** State agriculture department (selected by user's state)
- **Tier 2 Agriculture:** Krishi Jagran, Rural Voice, AgroSpectrum
- **Tier 3 Business:** Economic Times, Business Standard, Reuters
- **Tier 6 Discovery:** Google News RSS with dynamic crop + state queries

Groq Llama 3.3 70B classifies retrieved text → crop, state, district, event_type, severity, confidence, verification_status. Groq does NOT use its internal knowledge as current evidence.

### Q: What are the limitations of AgroIntel?

**A:** Honest limitations documented in the system:
1. **Price forecast is crop-level, not district-level** — models were not trained with district data
2. **5 crops only** — Rice, Wheat, Maize, Onion, Potato. Other crops show "forecast unavailable"
3. **Mandi data is 24–72 hours delayed** — data.gov.in AGMARKNET updates cycle
4. **Training data ends at 2024** — model cannot learn from post-2024 events
5. **Weather features use historical normals** — future weather cannot be precisely predicted
6. **Black swan events are approximated** — binary feature; actual magnitude may differ

### Q: How does Crop Recommendation work without district price data?

**A:** The recommendation engine uses a **15-point scoring system** based on:
1. Historical cultivation evidence (from candidate matrix — what crops were actually grown in this district)
2. Seasonal suitability (from crop season calendar)
3. Soil pH fit (if user provides pH)
4. Weather match (historical temperature/rainfall vs crop requirements)
5. Water availability
6. Crop rotation benefit (if previous crop provided)

The Mandi price from market_intelligence.json provides a supplementary price advisory — but the primary recommendation is based on evidence, not price alone.

---

## HOW TO RUN THE PROJECT

```bash
# Navigate to backend
cd /path/to/projectphase2/backend

# Activate virtual environment (if set up)
source venv/bin/activate

# Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Open browser
http://127.0.0.1:8000
```

---

## WORKFLOW DEMONSTRATION (for viva)

### Demo 1: Price Prediction
1. Click **Price Prediction** in nav
2. Select **Wheat** as crop, **Punjab** as state
3. Click **Generate Price Forecast**
4. System shows:
   - Latest Mandi price from Punjab (data.gov.in)
   - 30-day ML forecast by Prophet model
   - HOLD recommendation with reasoning
   - Price trend chart
   - Model comparison table

### Demo 2: Crop Recommendation
1. Click **Crop Recommendation**
2. Select **Karnataka** → **Dakshin Kannad** → **Kharif**
3. Click **Get Recommendation**
4. System shows:
   - Top 5 crops ranked by 15-point score
   - Why each crop is recommended (historical evidence, season match)
   - Current situation from news intelligence
   - Crop information card

### Demo 3: Different States Same Crop
1. Predict **Rice** for **Maharashtra** → note current price
2. Predict **Rice** for **Punjab** → different Mandi price, same forecast trend
3. Explain: "ML forecast is crop-level; Mandi price is state-specific"

---

## GITHUB REPOSITORY

**URL:** https://github.com/Dhanushkumar4-ai/AgroIntel  
**Branch:** main  
**Latest Commit:** e894262 — *feat: Final AgroIntel v4.1*  

**Key files for viva reference:**
- `backend/app/ml/inference.py` — ML prediction engine
- `backend/app/services/phase6_integration_service.py` — Recommendation engine
- `backend/app/data/docs/` — All 7 documentation reports
- `backend/frontend/script.js` — Frontend logic
- `backend/models/*.joblib` — Trained ML models
