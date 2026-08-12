# AgroIntel AI — News Intelligence & Sources Report

**Version:** 4.1 Final | **Date:** 2026-08-12

---

## 1. Overview

The AgroIntel News Intelligence layer is a backend pipeline that:
- Fetches agricultural news from 35+ sources across 7 tiers
- Classifies and structures news events using Groq Llama 3.3 70B AI
- Integrates news risk signals into the Crop Recommendation advisory
- Detects Black Swan events that trigger WAIT advisories in Price Prediction

The news pipeline does **NOT** make up or invent intelligence. It only uses text retrieved from registered sources.

---

## 2. Tier-by-Tier Source Registry

### Tier 1 — Official Government & Scientific Authorities (Credibility: 1.00)

| Source | Website | RSS/Feed | Topics |
|---|---|---|---|
| ICAR (Indian Council of Agricultural Research) | icar.org.in | ✅ RSS | Crop research, pest/disease advisories, variety releases |
| PIB Agriculture | pib.gov.in | ✅ RSS | MSP policy, government schemes, subsidies, export/import |
| DA&FW (Ministry of Agriculture & Farmers Welfare) | agriwelfare.gov.in | ✅ | Agriculture policy, farmer schemes |
| IMD (India Meteorological Department) | mausam.imd.gov.in | ✅ RSS | Rainfall, cyclone, drought, heatwave, flood warnings |
| Ministry of Earth Sciences | moes.gov.in | ✅ | Climate, extreme events |

**Usage:** Highest priority. ICAR advisories directly inform pest/disease risk scoring. IMD alerts trigger weather-related risk signals.

---

### Tier 1B — State Government Agriculture Departments (Credibility: 0.95, Dynamic)

State departments are selected dynamically based on the user's selected state:

| State | Department | URL |
|---|---|---|
| Karnataka | Raitamitra (Dept. of Agriculture) | raitamitra.karnataka.gov.in |
| Maharashtra | Maharashtra Krishi | krishi.maharashtra.gov.in |
| Punjab | Dept. of Agriculture Punjab | agripb.gov.in |
| Haryana | Agriculture Haryana | agriharyana.gov.in |
| Uttar Pradesh | UP Agriculture | upagriculture.com |
| Rajasthan | Agriculture Rajasthan | agriculture.rajasthan.gov.in |
| Tamil Nadu | TN Agriculture | tn.gov.in/department/2 |
| Andhra Pradesh | AP Agriculture | ap.gov.in/agriculture |
| Telangana | Telangana Agriculture | agri.telangana.gov.in |
| West Bengal | WB Agriculture | wb.gov.in/department-details-27 |
| Bihar | Bihar Agriculture | agriculture.bih.nic.in |
| Madhya Pradesh | MP Krishi | mpkrishi.mp.gov.in |
| Gujarat | Gujarat Agriculture | agri.gujarat.gov.in |
| Odisha | Odisha Agriculture | agri.odisha.gov.in |
| Kerala | Kerala Agriculture | keralaagriculture.gov.in |

---

### Tier 1C — KVK Network & State Agricultural Universities (Credibility: 0.92, Dynamic)

Used for district-level advisory context when district is available (Crop Recommendation module):

| Institution | Type |
|---|---|
| KVK (Krishi Vigyan Kendra) Network | Field-level crop advisories |
| Punjab Agricultural University (PAU) | Research + extension |
| Tamil Nadu Agricultural University (TNAU) | Crop technology advisories |
| UAS Bangalore/Dharwad/Raichur | Karnataka agronomic research |
| ANGRAU | Andhra Pradesh crop science |
| Acharya N.G. Ranga Agri. University | Crop technology |

---

### Tier 2 — Agricultural News Publications (Credibility: 0.80)

| Source | Website | RSS |
|---|---|---|
| Krishi Jagran | krishijagran.com | ✅ |
| Agri Farming | agrifarming.in | ✅ |
| Agriculture World | agriworld.in | — |
| ChiniMandi | chinimandi.com | ✅ (sugarcane/sugar) |
| AgroSpectrum | agrospectrum.in | ✅ |
| Rural Voice | ruralvoice.in | ✅ |
| Agriculture Post | agriculturepost.com | ✅ |

---

### Tier 3 — Business & Financial Market News (Credibility: 0.80)

| Source | Website | RSS |
|---|---|---|
| Economic Times — Agriculture | economictimes.indiatimes.com | ✅ |
| Business Standard — Agriculture | business-standard.com | ✅ |
| The Hindu BusinessLine | thehindubusinessline.com | ✅ |
| Financial Express — Commodities | financialexpress.com | ✅ |
| Moneycontrol — Commodity | moneycontrol.com | — |
| Reuters — Agriculture India | reuters.com | Google News |

---

### Tier 4 — National News Outlets (Credibility: 0.75)

| Source | Website | RSS |
|---|---|---|
| The Hindu | thehindu.com | ✅ |
| The Indian Express | indianexpress.com | ✅ |
| Times of India | timesofindia.indiatimes.com | ✅ |
| Hindustan Times | hindustantimes.com | ✅ |
| India Today | indiatoday.in | ✅ |

---

### Tier 5 — Climate & Environmental Science (Credibility: 0.90)

| Source | Website | RSS |
|---|---|---|
| Down To Earth | downtoearth.org.in | ✅ |
| Mongabay India | india.mongabay.com | ✅ |
| FAO India | fao.org/india | Google News |

---

### Tier 6 — Google News RSS Discovery Layer (Credibility: 0.60)

Google News aggregates from ALL tiers above. Used as a dynamic discovery mechanism with context-specific search queries.

**Query templates for Crop Recommendation:**
```
{state} agriculture
{district} agriculture
{district} farmers
{district} crop
{district} rainfall / flood / drought / pest disease
{district} mandi price
{state} agriculture department advisory
{state} crop damage disaster
```

**Query templates for Price Prediction:**
```
{state} {crop}
{state} {crop} price / mandi
{state} {crop} rainfall / disease
{state} {crop} export restriction
India {crop} market price
India {crop} export restriction
global {crop} commodity price
```

---

## 3. Groq Extraction Schema

**Model:** `llama-3.3-70b-versatile` (via Groq API)

**Input:** Retrieved source text (title + summary + body excerpt)

**Output schema:**
```json
{
  "is_agriculture_related": true/false,
  "crop": "rice",
  "state": "Maharashtra",
  "district": "Nashik",
  "event_type": "HEAVY_RAIN",
  "impact_direction": "NEGATIVE",
  "severity": "HIGH",
  "confidence": 0.87,
  "verification_status": "VERIFIED",
  "supporting_evidence": "Article text confirms flooding in Nashik district...",
  "is_blackswan": false,
  "geographic_scope": "DISTRICT"
}
```

**Event types:**
FLOOD, DROUGHT, HEAVY_RAIN, HEATWAVE, CYCLONE, FROST, HAILSTORM,  
PEST_OUTBREAK, DISEASE_OUTBREAK, MSP_POLICY, EXPORT_RESTRICTION,  
IMPORT_RESTRICTION, FERTILIZER, MARKET_PRICE_EVENT, SUPPLY_SHOCK,  
WAR_CONFLICT, FUEL_SHOCK, GOVERNMENT_POLICY, CROP_DAMAGE, OTHER

---

## 4. Black Swan Detection

A Black Swan is declared when:
1. `is_blackswan = True` from Groq extraction
2. `verification_status` is `VERIFIED` (not PLAUSIBLE or INSUFFICIENT)
3. Source text explicitly confirms the event (not speculation)

**Black swan examples:**
- Confirmed export ban on onion (2023, 2024)
- Russia-Ukraine war impact on wheat prices (2022)
- COVID-19 supply chain disruption (2020)
- Major multi-district flood (confirmed by IMD + state government)

**Effect on Price Advisory:**
- If active black swan detected + recommendation is HOLD + change_pct < 8%:
  → Override to **WAIT** (uncertainty too high for confident HOLD)

---

## 5. Critical Rules

1. **Groq does NOT fetch news.** Groq reads retrieved text only.
2. **Groq's internal knowledge is NOT used as current evidence.**
3. **Only VERIFIED/PLAUSIBLE events affect advisories.**
4. **Black swan requires VERIFIED status** — speculation/opinion is discarded.
5. **Geographic specificity is weighted:** District > State > National > International.
6. **Data freshness matters:** Events older than 60 days are labeled STALE and given reduced weight.
