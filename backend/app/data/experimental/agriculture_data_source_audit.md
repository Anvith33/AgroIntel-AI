# Agriculture Data Source Audit & Integration Strategy

**Phase 1 — Official Agriculture Data Discovery & Verification Report**
*Generated: 2026-08-11 | Branch: `agriculture-api-testing`*

---

## 1. Primary Official Source: Government of India (data.gov.in)

* **Catalog**: District-wise, season-wise crop production statistics from 1997
* **Resource ID**: `35be999b-0208-4354-b557-f6ca9a5355de`
* **API Endpoint**: `https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de`
* **Authentication**: `api-key` query parameter (configured via `MARKET_DATA_API_KEY` in `app/core/config.py`)
* **Pagination**: Limit & Offset (`limit=10000`, `offset=N`)
* **Total Records Discovered**: 246,091
* **Records Retrieved**: 246,091
* **Total API Pages Retrieved**: 25
* **API Response Time**: 196.61 seconds for full download
* **API Fields Discovered**:
  - `state_name` (String)
  - `district_name` (String)
  - `crop_year` (Integer)
  - `season` (String — Kharif, Rabi, Summer, Whole Year, Autumn, Winter)
  - `crop` (String)
  - `area_` (Float — Hectares)
  - `production_` (Float — Tonnes / Bales / Nuts)
* **Dataset Temporal Range**: **1997 to 2015**
* **Primary Role**: **AUTHORITATIVE CULTIVATION EVIDENCE** for district-level crop production.

---

## 2. Secondary Official Source: DES APY Query Report Portal

* **Official Portal**: `https://data.desagri.gov.in/website/apy-query-report-web`
* **Directorate**: Directorate of Economics & Statistics (DES), Department of Agriculture & Farmers Welfare.
* **Portal Architecture Assessment**:
  - Web interface with dynamic session-based query forms (DataTables / Select2 frontend).
  - **Public REST API Endpoint Status**: No publicly documented open REST API endpoint exists for programmatically querying raw records directly without browser/session state.
  - **Data Access Mechanism**: Web-based reporting engine with interactive table generation and export capabilities.
* **Integration Strategy**: The `data.gov.in` resource `35be999b-0208-4354-b557-f6ca9a5355de` originates directly from DES APY statistics. Therefore, `data.gov.in` serves as the programmatic API pipeline while DES web reports serve as an official manual validation benchmark.

---

## 3. Separation of Mandi Market Data vs Cultivation Data

* **Mandi Resource ID**: `9ef84268-d588-465a-a308-a864a43d0070` (`app/services/mandi_service.py`)
* **Strict Functional Boundaries**:
  - **Mandi Data**: Market prices, modal prices, daily arrival volumes, price forecasting, SELL/HOLD advisory.
  - **APY Cultivation Data (`35be999b`)**: Authoritative district crop cultivation evidence (Area, Production, Yield, Years of Cultivation).
* **Architectural Rule**: Mandi record volume is **NEVER** treated as proof of crop cultivation in a district. Market arrivals reflect trading Hubs (e.g. trading of crops transported across district boundaries), whereas APY data reflects actual agricultural land production.

---

## 4. Legacy District Mapping Status

* **Legacy File**: `app/data/region_crop_mapping.json`
* **Status**: Retained completely intact and unchanged during Phase 1 for rollback and comparison benchmarking.
* **New Pipeline Files**: Created entirely in `app/data/experimental/` to ensure zero disruption to main production code.
