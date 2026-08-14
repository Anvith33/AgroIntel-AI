# AGROINTEL — FINAL 140 STATE-CROP PRICE FORECAST AUDIT REPORT

## Executive Summary
- **Total Combinations Evaluated**: 140 (28 States × 5 Crops)
- **Passed Inferences**: 140/140 (100%)
- **Decision Logic Compliance**: 140/140 (100% Match with Change % Thresholds)
- **Decision Breakdown**: **SELL: 26**, **HOLD: 110**, **WAIT: 4**
- **State-Specific Models (`STATE_CROP`)**: 109
- **Crop-Only Fallbacks (`CROP_ONLY_FALLBACK`)**: 31 (sparse state records < 50 rows)

## Crop Diversity & Decision Breakdown

| Crop | States Tested | STATE_CROP | CROP_ONLY Fallback | Unique Prices | SELL | HOLD | WAIT | Audit Status |
|------|---------------|------------|--------------------|---------------|------|------|------|--------------|
| Rice | 28 | 21 | 7 | 22 | **25** | **3** | **0** | **PASSED (100%)** |
| Wheat | 28 | 17 | 11 | 18 | **1** | **25** | **2** | **PASSED (100%)** |
| Maize | 28 | 19 | 9 | 20 | **0** | **27** | **1** | **PASSED (100%)** |
| Onion | 28 | 26 | 2 | 26 | **0** | **27** | **1** | **PASSED (100%)** |
| Potato | 28 | 26 | 2 | 27 | **0** | **28** | **0** | **PASSED (100%)** |

## Complete 28-State × 5-Crop Price Forecast & Decision Matrix

| State | Rice | Wheat | Maize | Onion | Potato |
|-------|------|-------|-------|-------|--------|
| Andhra Pradesh | ₹2456 (SELL) | ₹3045 (HOLD) * | ₹2079 (HOLD) | ₹3091 (HOLD) | ₹2980 (HOLD) |
| Arunachal Pradesh | ₹2365 (SELL) * | ₹3045 (HOLD) * | ₹2325 (HOLD) * | ₹3287 (HOLD) * | ₹2583 (HOLD) * |
| Assam | ₹1863 (SELL) | ₹2391 (HOLD) | ₹1833 (WAIT) | ₹3522 (HOLD) | ₹3395 (HOLD) |
| Bihar | ₹2456 (SELL) | ₹2630 (HOLD) | ₹1916 (HOLD) | ₹3227 (HOLD) | ₹2898 (HOLD) |
| Chhattisgarh | ₹2436 (SELL) | ₹2547 (HOLD) | ₹2082 (HOLD) | ₹2175 (HOLD) | ₹2887 (HOLD) |
| Goa | ₹2365 (SELL) * | ₹3045 (HOLD) * | ₹2325 (HOLD) * | ₹2175 (HOLD) | ₹1708 (HOLD) |
| Gujarat | ₹2363 (SELL) | ₹2688 (HOLD) | ₹2252 (HOLD) | ₹1900 (WAIT) | ₹2193 (HOLD) |
| Haryana | ₹3053 (HOLD) | ₹2570 (HOLD) | ₹2249 (HOLD) | ₹1933 (HOLD) | ₹1454 (HOLD) |
| Himachal Pradesh | ₹2365 (SELL) * | ₹3045 (HOLD) * | ₹2325 (HOLD) * | ₹2777 (HOLD) | ₹1713 (HOLD) |
| Jharkhand | ₹1943 (SELL) | ₹2342 (WAIT) | ₹1879 (HOLD) | ₹2798 (HOLD) | ₹1475 (HOLD) |
| Karnataka | ₹2414 (SELL) | ₹2899 (HOLD) | ₹2227 (HOLD) | ₹2834 (HOLD) | ₹1739 (HOLD) |
| Kerala | ₹2448 (SELL) | ₹3130 (HOLD) | ₹2325 (HOLD) * | ₹5814 (HOLD) | ₹2788 (HOLD) |
| Madhya Pradesh | ₹2677 (SELL) | ₹2721 (HOLD) | ₹2179 (HOLD) | ₹1860 (HOLD) | ₹1338 (HOLD) |
| Maharashtra | ₹2674 (SELL) | ₹2729 (HOLD) | ₹2162 (HOLD) | ₹3356 (HOLD) | ₹1732 (HOLD) |
| Manipur | ₹3051 (HOLD) | ₹3045 (HOLD) * | ₹3034 (HOLD) | ₹5807 (HOLD) | ₹3514 (HOLD) |
| Meghalaya | ₹3262 (HOLD) * | ₹3045 (HOLD) * | ₹2325 (HOLD) * | ₹5765 (HOLD) | ₹3780 (HOLD) |
| Mizoram | ₹2365 (SELL) * | ₹3045 (HOLD) * | ₹2325 (HOLD) * | ₹5730 (HOLD) | ₹3151 (HOLD) |
| Nagaland | ₹2365 (SELL) * | ₹3045 (HOLD) * | ₹7271 (HOLD) | ₹5852 (HOLD) | ₹3081 (HOLD) |
| Odisha | ₹2425 (SELL) | ₹2630 (HOLD) | ₹2140 (HOLD) | ₹3160 (HOLD) | ₹3005 (HOLD) |
| Punjab | ₹2436 (SELL) | ₹2770 (HOLD) | ₹2000 (HOLD) | ₹2350 (HOLD) | ₹1450 (HOLD) |
| Rajasthan | ₹2694 (SELL) | ₹2749 (HOLD) | ₹2303 (HOLD) | ₹1929 (HOLD) | ₹1627 (HOLD) |
| Sikkim | ₹2365 (SELL) * | ₹3045 (HOLD) * | ₹2325 (HOLD) * | ₹3287 (HOLD) * | ₹2583 (HOLD) * |
| Tamil Nadu | ₹2201 (SELL) | ₹3045 (HOLD) * | ₹2883 (HOLD) | ₹5759 (HOLD) | ₹3043 (HOLD) |
| Telangana | ₹2328 (SELL) | ₹2203 (SELL) | ₹2259 (HOLD) | ₹2199 (HOLD) | ₹1715 (HOLD) |
| Tripura | ₹2301 (SELL) | ₹3045 (HOLD) * | ₹2325 (HOLD) * | ₹5540 (HOLD) | ₹3611 (HOLD) |
| Uttar Pradesh | ₹2294 (SELL) | ₹2642 (HOLD) | ₹2260 (HOLD) | ₹2181 (HOLD) | ₹1601 (HOLD) |
| Uttarakhand | ₹2283 (SELL) | ₹2337 (WAIT) | ₹2277 (HOLD) | ₹1931 (HOLD) | ₹1338 (HOLD) |
| West Bengal | ₹2259 (SELL) | ₹2557 (HOLD) | ₹2325 (HOLD) * | ₹2461 (HOLD) | ₹1718 (HOLD) |

*Note: Asterisk (\*) indicates legitimate CROP_ONLY fallback used due to sparse state historical market records (<50 rows).*