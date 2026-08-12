# AgroIntel AI — Data Sources & Pipeline Documentation

**Version:** 4.1 Final | **Date:** 2026-08-12

---

## 1. Price Data Source: data.gov.in AGMARKNET

**API:** `https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070`

**What it provides:**
- Daily Mandi arrival prices (min, modal, max) per commodity per market per state
- Coverage: 3,000+ markets across India
- Fields: `commodity`, `state`, `market`, `arrival_date`, `min_price`, `modal_price`, `max_price`

**How AgroIntel uses it:**
```python
# Cache key: f"{crop}:{state}"
# Cache duration: 72 hours (3-day cycle)
live_data = DataIngestion.fetch_live_market_data(crop, state)
```

**Fallback chain:**
1. Try AGMARKNET API for latest `modal_price` for crop in state
2. On API failure/no data → use cached JSON file
3. On cache miss → use MSP 2024-25 estimate (labeled as "msp_estimate")

**Price returned:** `modal_price` (the most frequently traded price at market) in ₹/quintal.

**What `observation_date` means:**
The `arrival_date` field from AGMARKNET — the actual date of the market observation. This is NOT the date of the API call. It can be 1–3 days behind real-time.

---

## 2. Historical Price Data (Model Training)

**Source:** Curated dataset from multiple government sources:
- AGMARKNET historical archives (2000–2024)
- CACP (Commission for Agricultural Costs & Prices) price data
- State Directorate of Agriculture price bulletins
- FAO India crop price indices

**Dataset characteristics:**
- Frequency: Monthly (aggregated from daily Mandi data)
- Time range: 2000–2024 (24 years)
- Coverage: 5 crops (Rice, Wheat, Maize, Onion, Potato)
- Price unit: ₹/quintal (modal price, national average)
- Augmentation: COVID-19 2020 period, Russia-Ukraine war 2022 marked as black_swan=1

**Where stored:** `backend/app/data/` as CSV files processed during training.

---

## 3. Weather Data (Training Features)

**Source:** IMD historical climate data + World Weather Online API

**Training features:**
- `monthly_avg_temp` — monthly average temperature (°C) by crop zone
- `monthly_total_rainfall` — monthly total rainfall (mm) by crop zone

**Inference:** Weather features for future predictions use historical monthly averages (climatological normals) since future weather cannot be precisely predicted.

---

## 4. Mandi Market Data (Phase 6 / Crop Recommendation)

**File:** `backend/app/data/experimental/market_intelligence.json`

**Contents:** Pre-fetched Mandi price records per district × commodity  
**Source:** data.gov.in API (fetched during initialization, cached)  
**Use:** Price advisory within the Crop Recommendation engine (Phase 6)

**Lookup hierarchy in `_get_mandi_vector()`:**
1. Exact match by `(state, district, commodity)`
2. Canonical state/district match
3. Source alias match
4. Live Mandi Service (if `mandi_service` is available)
5. Return empty if all fail (no fabricated prices)

---

## 5. News Data Pipeline

### 5.1 Source Registry

**File:** `backend/app/data/experimental/news_source_registry.json`

7-tier architecture (see Report 6 for full details):

| Tier | Type | Examples |
|---|---|---|
| 1 | Official Government | ICAR, PIB, IMD, MoES |
| 1B | State Agriculture Depts | Karnataka Raitamitra, Maharashtra Krishi |
| 1C | KVK & Universities | KVK network, PAU, TNAU |
| 2 | Agricultural News | Krishi Jagran, Rural Voice |
| 3 | Business/Market | Economic Times, Business Standard |
| 4 | National News | The Hindu, Indian Express |
| 5 | Climate/Science | Down to Earth, Mongabay India |
| 6 | Google News RSS | Dynamic query templates |

### 5.2 Extraction Pipeline

```
RSS Feed / HTTP Fetch
    ↓
HTML → text extraction (title + summary + publication date)
    ↓
Deduplication (URL + headline similarity)
    ↓
Groq Llama 3.3 70B:
  Input: retrieved source text
  Output: {crop, state, district, event_type, impact_direction,
           severity, confidence, verification_status, is_blackswan}
    ↓
Filtered by verification_status ∈ {VERIFIED, PLAUSIBLE}
    ↓
news_events.json → grouped by (state, crop) → current_intelligence.json
```

**Critical rule:** Groq is used as a text classifier/extractor on retrieved content ONLY. Groq's internal knowledge about "current events" is NOT used as evidence.

### 5.3 Verification Status

| Status | Meaning | Used for |
|---|---|---|
| `VERIFIED` | Source text explicitly confirms event | Price advisory, Black Swan trigger |
| `PLAUSIBLE` | Source text implies event with high probability | Risk signal |
| `INSUFFICIENT` | Event mentioned but too vague | Discarded |

---

## 6. District Master Data

**File:** `backend/app/data/experimental/district_master.json`

**Contents:** 700+ district entries, each with:
```json
{
  "canonical_id": "Karnataka::Dakshin Kannad",
  "state": "Karnataka",
  "district": "Dakshin Kannad",
  "source_names": [
    "DAKSHIN KANNAD",
    "DAKSHINA KANNADA",
    "DAKSHINA KANNAD",
    "SOUTH CANARA",
    "SOUTH KANARA",
    "MANGALORE DISTRICT"
  ]
}
```

**Source:** Census 2011 district codes + AGMARKNET market district names + LGD (Local Government Directory) codes + manually curated aliases for common variants.

**Resolution algorithm:**
1. Direct exact match (case-insensitive)
2. Normalized match (remove diacritics, special chars, extra spaces)
3. Normalized state + district match
4. Parenthetical removal (e.g., "Bangalore (Urban)" → "bangalore urban")
5. Token-overlap Jaccard similarity fallback (threshold: score ≥ 0.4)

---

## 7. Candidate Matrix (Crop Recommendation Evidence)

**File:** `backend/app/data/experimental/nationwide_candidate_matrix_v2.json`

**Contents:** Evidence-based crop × district × season candidate lists

**Source:** Built from:
- ICRISAT village-level crop production data
- APEDA district-wise crop export data
- State Agriculture Department annual area/production reports
- National Horticulture Board district data

**Each candidate entry contains:**
```json
{
  "crop": "Rice",
  "evidence_score": 0.85,
  "area_ha": 45000,
  "dominant_season": ["Kharif"],
  "soil_types": ["Clay loam", "Silty clay"],
  "water_requirement": "HIGH"
}
```

**What "evidence" means:** The candidate matrix ONLY includes crops where there is documented historical cultivation evidence for that district. AgroIntel does NOT recommend crops based on theoretical suitability alone.
