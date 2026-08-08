# AgroIntel v4.0 — Frontend Architecture Report

## Executive Summary

The AgroIntel v4.0 Frontend is a modern, responsive Single-Page Application (SPA) built using Vanilla HTML5, CSS3, and JavaScript (ES6+) with **Chart.js** integration and a **Glassmorphism Green Agriculture Theme**. The application communicates with FastAPI backend endpoints (`/api/version`, `/health`, `/api/demo`, `/api/models`, `/api/predict/price`, `/api/predict/crop`, `/api/advisory`).

---

## 1. Single-Page Application View Architecture

```
                               ┌───────────────────────────┐
                               │   AgroIntel Single-Page   │
                               │        App Shell          │
                               └─────────────┬─────────────┘
                                             │
         ┌──────────────────┬────────────────┼─────────────────┐
         │                  │                │                 │
         ▼                  ▼                ▼                 ▼
┌──────────────────┐┌───────────────┐┌───────────────┐┌────────────────┐
│ View 1: Dashboard││    View 2:    ││    View 3:    ││    View 4:     │
│ (Landing/Metrics)││ Recommendation││Price Forecast ││Combined Advisory│
└──────────────────┘└───────────────┘└───────────────┘└────────────────┘
```

### Views Description
1. **View 1: Dashboard (`#view-dashboard`)**:
   - Hero banner, system status metrics (RF 99.55% accuracy, ~5.5ms API latency, 585 districts, Prophet/XGBoost models), and key feature highlights.
2. **View 2: Crop Recommendation (`#view-recommendation`)**:
   - State & District cascading selectors, season options (`Kharif`, `Rabi`, `Zaid`), optional soil NPK + pH input controls.
   - Renders Top 3 Crop Cards, Normalized RF Probabilities, Suitability Scores, Score Breakdowns, and Explainability Reasons.
3. **View 3: Price Forecast (`#view-prediction`)**:
   - Crop selection (`wheat`, `rice`, `maize`, `potato`, `onion`), state filter, and forecast horizons (`7`, `15`, `30`, `60`, `90` days).
   - Renders Current Mandi Price, 30-Day Predicted Average, Expected Change %, Sell vs. Hold Decision Badge with net gain calculation, and **Chart.js Line Graph** displaying daily predictions, linear trend line, and 85% upper/lower confidence bounds.
4. **View 4: Combined Advisory (`#view-advisory`)**:
   - Single unified form outputting integrated farmer recommendations and financial market guidance.

---

## 2. Technical Stack & Dependencies

- **HTML5**: Semantic tags (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`).
- **CSS3**: CSS Custom Properties (Design Tokens), Flexbox, CSS Grid, Glassmorphism backdrop-filters, CSS animation keyframes.
- **JavaScript (ES6+)**: `fetch` API, `async`/`await`, DOM manipulation, dynamic event listeners.
- **Chart.js**: External CDN library (`https://cdn.jsdelivr.net/npm/chart.js`) for rendering price prediction curves and confidence bounds.

---
*AgroIntel v4.0 Technical Report — Frontend Architecture Complete*
