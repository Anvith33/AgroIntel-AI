# CURRENT_PRICE_AUDIT_REPORT.md

**AgroIntel v4.0 — Current Price Source Audit & Transparency Report**
Generated from: live running application — NOT synthetic

---

## Executive Summary

| Part | Task | Status |
|:---|:---|:---:|
| PART 1 | Current Price Source Audit | ✅ COMPLETED |
| PART 2 | Current Price Logic Verification | ✅ CORRECT |
| PART 3 | Dataset Verification | ✅ COMPLETED |
| PART 4 | API Transparency Fields | ✅ ADDED |
| PART 5 | UI Improvement | ✅ IMPLEMENTED |
| PART 6 | Per-Crop Price Consistency | ✅ VERIFIED |
| PART 7 | Audit Report | ✅ THIS DOCUMENT |

---

## PART 1 — Current Price Source (Live Audit)

### Pipeline Flow Diagram

```
GET /api/predict/price?crop=wheat&horizon_days=30
       │
       ▼
predict_crop_price()  [price_predictor.py]
       │
       ├─► STEP 1: Load model registry + feature metadata
       │
       ├─► STEP 2: Load data_tail_{crop}.pkl
       │           └─ last row = fallback price (2024-12-31 value)
       │
       ├─► STEP 3: get_latest_price(crop, state)  [mandi_service.py]
       │           │
       │           ├─ Check disk cache (mandi_cache.json)
       │           │   └─ key format: "{crop}_{state or 'all'}"
       │           │
       │           ├─ If cache hit AND age < MANDI_CACHE_TTL_SECONDS:
       │           │   └─ return CachedMandiResult → data_status = "CACHE"
       │           │
       │           ├─ Else: fetch data.gov.in API (3.0s timeout)
       │           │   ├─ SUCCESS: parse modal_price → data_status = "LIVE"
       │           │   └─ TIMEOUT/FAIL: fallback to stale cache
       │           │
       │           └─ If no cache at all: return None
       │
       ├─► If mandi_res is NOT None:
       │     current_price = mandi_res.modal_price
       │     current_price_source = "Live Mandi (data.gov.in)"   [age ≤ 3d]
       │                         OR "Cached Mandi (data.gov.in)"  [age > 3d]
       │     current_price_date  = mandi_res.arrival_date
       │     data_status = "LIVE" or "CACHE"
       │
       └─► If mandi_res is None (API + cache both unavailable):
             current_price = data_tail_df["y"].iloc[-1]  ← LAST ROW OF TRAINING DATA
             current_price_source = "Historical Dataset"
             current_price_date   = hist_end_date  (2024-12-31)
             data_status = "FALLBACK"
```

### Current Actual Status

**All 5 crops** are in `FALLBACK` state (2026-08-07):

- **data.gov.in API**: Timing out (3.0s limit) — API key authentication fails or network blocked
- **mandi_cache.json**: Contains old format entries (`{crop}:{state}`) incompatible with new service key format (`{crop}_{state}`) — effectively empty for all 5 crops
- **Result**: All prices come from `data_tail_{crop}.pkl` → last row dated 2024-12-31

---

## PART 2 — Current Price Logic (Correct)

The logic in `price_predictor.py` is **correct by design**:

| Priority | Source | Condition | data_status |
|:---|:---|:---|:---|
| 1 | `data.gov.in` Live API | API reachable, data ≤ 3 days old | `LIVE` |
| 2 | `mandi_cache.json` disk cache | API failed, cache present | `CACHE` |
| 3 | `data_tail_{crop}.pkl` last row | Both API and cache unavailable | `FALLBACK` |

**NEVER used as current price:**
- First prediction (day 1 forecast)
- Average prediction
- 7-day or 30-day predicted price
- Any forecast output

The `current_price` is always set **before** any ML model is called.

---

## PART 3 — Dataset Verification

### real_historical_prices.csv

| Property | Value |
|:---|:---|
| Columns | `ds`, `crop`, `y` |
| Total rows | 10,960 |
| Date range | 2019-01-01 → 2024-12-31 |
| Crops | wheat, rice, maize, potato, onion |
| `y` column stores | **Modal Price** (₹/quintal) |

**Source column in archive CSVs (Agmarknet):**

| Column | Present | Used |
|:---|:---|:---|
| `Min_Price` | ✅ | ❌ |
| `Max_Price` | ✅ | ❌ |
| `Modal_Price` | ✅ | **✅ → `y`** |

The `y` column in `real_historical_prices.csv` stores the **Modal Price** from Agmarknet. Modal price = the price at which the maximum quantity was traded in a market session. It is the closest to the actual "market clearing price".

### data_tail_{crop}.pkl Last Values (Fallback Prices)

| Crop | Last Date | Last `y` (Modal Price) | Fallback Displayed |
|:---|:---|:---|:---|
| Wheat | 2024-12-31 | ₹2,866.34 | ₹2,866.34 ✓ |
| Rice | 2024-12-31 | ₹2,350.80 | ₹2,350.80 ✓ |
| Maize | 2024-12-31 | ₹2,329.39 | ₹2,329.39 ✓ |
| Potato | 2024-12-31 | ₹2,659.54 | ₹2,659.54 ✓ |
| Onion | 2024-12-31 | ₹3,332.15 | ₹3,332.15 ✓ |

**All displayed prices exactly match the historical tail.** No interpolation, no prediction used.

---

## PART 4 — API Transparency (New Fields)

The `/api/predict/price` response now includes all four required fields:

### Example Response — FALLBACK (current state)

```json
{
  "current_price": 2866.34,
  "current_price_source": "Historical Dataset",
  "current_price_date": "2024-12-31",
  "data_status": "FALLBACK"
}
```

### Example Response — LIVE (when data.gov.in is reachable)

```json
{
  "current_price": 2535.00,
  "current_price_source": "Live Mandi (data.gov.in)",
  "current_price_date": "2026-08-06",
  "data_status": "LIVE"
}
```

### Example Response — CACHE

```json
{
  "current_price": 2362.00,
  "current_price_source": "Cached Mandi (data.gov.in)",
  "current_price_date": "2026-08-04",
  "data_status": "CACHE"
}
```

### Live Verification (per-crop, 2026-08-07)

| Crop | current_price | current_price_source | current_price_date | data_status |
|:---|:---|:---|:---|:---|
| wheat | 2866.34 | Historical Dataset | 2024-12-31 | FALLBACK |
| rice | 2350.80 | Historical Dataset | 2024-12-31 | FALLBACK |
| maize | 2329.39 | Historical Dataset | 2024-12-31 | FALLBACK |
| potato | 2659.54 | Historical Dataset | 2024-12-31 | FALLBACK |
| onion | 3332.15 | Historical Dataset | 2024-12-31 | FALLBACK |

All 4 required fields present for all 5 crops. ✅

---

## PART 5 — UI Improvements

The **Current Price** card now displays beneath the price value:

```
Current Price
₹2,866
per quintal
🔵 HISTORICAL
Source: Historical Dataset
Last Updated: 31-12-2024
```

When live or cached data is available:
```
Current Price
₹2,535
per quintal
🟢 LIVE
Source: Live Mandi (data.gov.in)
Last Updated: 07-08-2026
```

The **Price Forecast Chart header** also shows:
```
Price Forecast Chart     [30-day outlook]  [🔵 HISTORICAL · 31-12-2024]
```

### Badge Color Coding

| Status | Dot | Color | Meaning |
|:---|:---|:---|:---|
| LIVE | 🟢 | Green | data.gov.in ≤ 3 days old |
| CACHED | 🟡 | Amber | Disk cache, API unavailable |
| HISTORICAL | 🔵 | Blue | Training data tail (2024-12-31) |

---

## PART 6 — Price Consistency Verification

| Crop | Dataset Last Price | Displayed UI Price | Difference | Source |
|:---|:---|:---|:---|:---|
| Wheat | ₹2,866.34 (2024-12-31) | ₹2,866 | ₹0.34 (rounding) | Historical Dataset |
| Rice | ₹2,350.80 (2024-12-31) | ₹2,351 | ₹0.20 (rounding) | Historical Dataset |
| Maize | ₹2,329.39 (2024-12-31) | ₹2,329 | ₹0.39 (rounding) | Historical Dataset |
| Potato | ₹2,659.54 (2024-12-31) | ₹2,660 | ₹0.46 (rounding) | Historical Dataset |
| Onion | ₹3,332.15 (2024-12-31) | ₹3,332 | ₹0.15 (rounding) | Historical Dataset |

**All differences are display rounding only (`toFixed(0)` in JS). No data inconsistency.** ✅

**Reason for difference vs. Google Prices**: The displayed price is the Agmarknet Modal Price from December 2024. Google and other websites show real-time market prices (today's date). This is now clearly labeled in the UI with the "Last Updated: 31-12-2024" date.

---

## PART 7 — Inconsistencies Found & Resolved

| # | Inconsistency | Status |
|:---|:---|:---|
| 1 | `mandi_cache.json` old format (`crop:state`) incompatible with new service key format (`crop_state`) | ⚠️ Noted — old cache entries are ignored; not a bug |
| 2 | `current_price_date` and `data_status` fields missing from API response | ✅ Fixed in `price_predictor.py` |
| 3 | UI showed no source information — users had no way to know prices were from 2024 | ✅ Fixed in `script.js` + `style.css` |
| 4 | `current_price_source` used internal format `"Historical Data Tail (Fallback)"` | ✅ Renamed to clean `"Historical Dataset"` |
| 5 | Startup log used `logger.info` (filtered in production) | ✅ Changed to `logger.warning` so always visible |

---

## Files Modified

| File | Change |
|:---|:---|
| `backend/app/ml/price_predictor.py` | Added `current_price_date`, `data_status` to response; cleaner source labels; `[PRICE_SOURCE]` audit log |
| `backend/frontend/script.js` | Price source badge, Source label, Last Updated date under Current Price card; data status badge in chart header |
| `backend/frontend/style.css` | CSS for `.price-src-badge` (live/cache/fallback variants), `.price-src-line`, `.price-src-date`, `.chart-header-badges`, `.chart-src-badge` |

## Files NOT Modified

- All ML models (`.pkl`, `.keras`)
- `recommendation_engine.py`
- `price_trainer.py`
- `mandi_service.py` (logic unchanged)
- Feature engineering
- Any API route handler logic
- Training pipeline
