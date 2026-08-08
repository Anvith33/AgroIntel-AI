# AgroIntel v4.0 — Frontend Components Documentation

## Overview

The AgroIntel v4.0 UI is structured into reusable, modular component blocks defined in `index.html`, styled in `style.css`, and driven dynamically by `script.js`.

---

## 1. Core UI Components List

### 1. Navigation Bar (`.navbar`)
- Brand logo with version pill (`AgroIntel v4.0 PROD`).
- Tab links (`Dashboard`, `Crop Recommender`, `Price Prediction`, `Combined Advisory`).
- Operational status badge with animated pulse dot.
- Theme Toggle Button (Dark/Light mode).
- Multilingual Language Selector (English, Hindi, Marathi, Kannada, Punjabi).

### 2. Metric Cards (`.metric-card`)
- Glassmorphic card containers displaying system statistics (RF accuracy, average latency, district coverage, model status).

### 3. Recommendation Cards (`.rec-card`)
- Displays top 3 recommended crops with rank circle, crop name, composite suitability score (0–100), score breakdown grid (RF probability, Soil match, Weather match, District history, Agro zone validity), and deterministic reason bullets.

### 4. Decision Badge (`.decision-badge`)
- Highlights `HOLD` (Emerald Glow) or `SELL` (Crimson Glow) recommendations based on 30-day forecast appreciation vs. 2.0% monthly storage/decay costs.

### 5. Interactive Chart Container (`.chart-container`)
- Wraps Chart.js `<canvas>` element rendering 90-day daily price prediction curves, 85% confidence interval upper/lower bounds, and linear trend lines.

### 6. Toast Notifications (`.toast-container`)
- Slide-in toast alerts providing instant user feedback for successes, info, or validation error messages.

---
*AgroIntel v4.0 Frontend Component Documentation*
