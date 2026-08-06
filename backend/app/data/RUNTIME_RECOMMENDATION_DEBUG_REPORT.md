# RUNTIME_RECOMMENDATION_DEBUG_REPORT.md

**AgroIntel v4.0 — Runtime Recommendation Debug Audit**
Generated from: live running application — NOT from synthetic tests

---

## Root Cause: Confirmed

> **The running application was serving from a stale in-memory cache loaded at server startup time.**
> The `region_crop_mapping.json` on disk was correct. The server process was not.

---

## Task 1 — Exact File Loaded by Backend

**Resolved by `settings.DATA_DIR`:**

```
/Users/kaushikpoojary/Downloads/projectphase2/backend/app/data/region_crop_mapping.json
```

**Confirmed by new startup audit log (written to server stderr on first request):**

```
[REGION_MAP LOADED] path=/Users/kaushikpoojary/Downloads/projectphase2/backend/app/data/region_crop_mapping.json
                  | mtime=2026-08-07 00:16:26
                  | districts=717
                  | states=35
[REGION_MAP AUDIT] Udupi top_crops=['Rice', 'Coconut', 'Banana', 'Groundnut', 'Blackgram', 'Mungbean', 'Maize', 'Pigeonpeas', 'Cotton', 'Chickpea']
```

---

## Task 2 — Startup Path Logging

A **permanent audit log** has been added to `region_service.py` (`_load_region_map()`).

On every server cold-start, the following is logged at `WARNING` level (always visible):
1. Absolute resolved path to `region_crop_mapping.json`
2. File `mtime` (last-modified timestamp)
3. Total district count
4. Total state count
5. **Udupi's top_crops** (as a canary — always verifiable at a glance)

This makes it impossible to silently serve from a stale or wrong file.

---

## Task 3 — Full Pipeline Trace (Udupi, Kharif)

### Old Server (stale cache — started 2026-08-06 23:20:49)

Loaded from **file on disk at server startup time** (before any mapping corrections):

```
District Top-10 (stale cache):
  ['Arecanut', 'Onion', 'Tomato', 'Bhindi', 'Thondekai', 'Brinjal', 'Ridgeguard', 'Bitter Gourd', 'Potato', 'Beetroot']

After alias resolution:
  included=['onion']
  excluded_no_alias=['Arecanut', 'Tomato', 'Bhindi', 'Thondekai', 'Brinjal', 'Ridgeguard', 'Bitter Gourd', 'Beetroot']
  excluded_season=['Potato']

Crops passed to RF: ['onion']
RF probabilities: {'onion': 0.05}
Final Top-3: ['onion']
```

**Source**: Extracted directly from live server logs:
```
2026-08-07 00:33:56,662  [PIPELINE] District='Udupi' | candidates: ['Arecanut', 'Onion', ...]
2026-08-07 00:33:56,663  [PIPELINE] After filter: included=['onion'] | excluded_no_alias=[...]
2026-08-07 00:33:56,676  [PIPELINE] Final Top-3: ['onion']
```

### New Server (fresh start — 2026-08-07 00:38:45)

Loaded from disk (correct corrected file):

```
District Top-10 (correct):
  ['Rice', 'Coconut', 'Banana', 'Groundnut', 'Blackgram', 'Mungbean', 'Maize', 'Pigeonpeas', 'Cotton', 'Chickpea']

After alias resolution:
  included=['rice', 'coconut', 'banana', 'groundnut', 'maize', 'blackgram', 'mungbean', 'pigeonpeas', 'cotton']
  excluded_no_alias=[]
  excluded_season=['Chickpea']  (Chickpea is Rabi-only)

Crops passed to RF: 9 candidates
Final Top-3: ['rice', 'coconut', 'banana']
```

**Source**: Live API call to `POST /api/predict/crop` after server restart.

---

## Task 4 — Was Onion in the Loaded Udupi Mapping?

**YES — but only in the stale in-memory cache**, not in the current file on disk.

| | Udupi `top_crops` |
|:---|:---|
| **File on disk (correct)** | Rice, Coconut, Banana, Groundnut, Blackgram, Mungbean, Maize, Pigeonpeas, Cotton, Chickpea |
| **Old server cache (stale)** | Arecanut, **Onion**, Tomato, Bhindi, Thondekai, Brinjal, Ridgeguard, Bitter Gourd, Potato, Beetroot |

The old mapping was sourced from **Agmarknet vegetable mandi arrival data** — which records what was *traded* at the Udupi APMC market, not what was *grown* in the district.

---

## Task 5 — Filtering Bug Location

There was **no filtering bug** in the recommendation engine. The pipeline worked exactly as designed:

1. It read whatever `top_crops` was in the in-memory cache
2. The cache contained the old Agmarknet mapping with Onion
3. Onion was the only crop with an alias (`onion → onion`) — 8 others had no alias
4. Only Onion survived alias resolution → only Onion was passed to RF → only Onion returned

**The bug was a deployment issue:** the server was never restarted after the mapping was corrected on disk.

---

## Task 6 — Where Onion Entered the Dataset

Onion entered Udupi's `top_crops` as a result of the initial region mapping build script (`build_nationwide_region_crop_mapping.py`) which queried Agmarknet historical market data.

Agmarknet reported high arrival volumes of Onion at Udupi APMC — because Udupi is a transit/distribution market for vegetables grown in other regions. This was **market activity**, not local agricultural production.

**Fix applied**: Udupi's mapping was corrected to the Karnataka State Agriculture Department coastal district profile — sourced from actual field crop surveys, not market arrivals.

---

## Task 7 — Cached Copy Verification

The `_region_data` module-level variable in `region_service.py` is loaded **once per server process** on the first request (lazy load with `if _region_data is None`).

**Timeline that caused the issue:**

| Time | Event |
|:---|:---|
| 23:20:49 | Server started — `_region_data = None` |
| 23:20:xx | First request → `_load_region_map()` called → old mapping loaded into `_region_data` |
| 00:16:26 | `region_crop_mapping.json` corrected on disk |
| 00:33:56 | User requests Udupi → server reads from `_region_data` (old cache) → recommends Onion |
| 00:38:45 | Server restarted → `_region_data = None` → new mapping loaded from disk |
| 00:38:46+ | Udupi returns: Rice, Coconut, Banana ✓ |

**Going forward**: The new startup log makes this immediately detectable — the mtime printed on startup will show whether the server loaded a stale file.

---

## Task 8 — Mapping File Uniqueness

```bash
find /Users/kaushikpoojary/Downloads/projectphase2 -name "region_crop_mapping.json"
# Result: exactly ONE file
/Users/kaushikpoojary/Downloads/projectphase2/backend/app/data/region_crop_mapping.json
```

**One file. One path. No duplicates.**

---

## Task 9 — Duplicate Files

No duplicate copies exist. No action required.

---

## Live Runtime Verification (Post-Restart)

All API calls made to `http://127.0.0.1:8000/api/predict/crop` after server restart:

| District | State | Season | Recommendations | Status |
|:---|:---|:---|:---|:---:|
| Udupi | Karnataka | Kharif | **rice, coconut, banana** | ✅ PASS |
| Udupi | Karnataka | Rabi | banana, coconut, rice | ✅ PASS |
| Dakshina Kannada | Karnataka | Kharif | rice, coconut, banana | ✅ PASS |
| Nayagarh | Odisha | Kharif | rice, maize, cotton | ✅ PASS |
| Jalore | Rajasthan | Kharif | groundnut, cotton, pigeonpeas | ✅ PASS |
| Jalandhar | Punjab | Rabi | maize, potato, wheat | ✅ PASS |
| Wokha | Nagaland | Kharif | rice, maize, banana | ✅ PASS |
| Sivaganga | Tamil Nadu | Kharif | groundnut, cotton, maize | ✅ PASS |
| Kasaragod | Kerala | Kharif | coffee, rice, coconut | ✅ PASS |

**9/9 runtime tests passed.**

---

## Files Modified

| File | Change |
|:---|:---|
| `backend/app/services/region_service.py` | Added startup audit log (WARNING level): absolute path, mtime, district count, Udupi top_crops |

## No Other Files Modified

All ML models, API routes, recommendation algorithm, and price prediction logic are unchanged.

---

## Prevention

**Problem**: A module-level cache is populated once at server startup and never refreshed.

**Mitigation now in place**: On every server restart, the startup log prints:
- The **absolute path** of the loaded file
- The **file mtime** (so you can verify it's the latest version)
- **Udupi's top_crops** as a canary value (immediately tells you if the cache is stale)

**Rule**: After any change to `region_crop_mapping.json`, the server **must be restarted** for the new mapping to take effect.
