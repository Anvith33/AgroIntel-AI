# AgroIntel v4.0 — Phase 6 Probability Normalization Fix Report

## Executive Summary

A mathematical probability normalization fix was implemented in `app/services/recommendation_engine.py`. Previously, Random Forest predicted probabilities across all 22 global crops, causing valid candidate crops to retain artificially diluted probabilities (e.g. `0.05` out of 22 classes) after non-candidate crops were filtered out.

The candidate probabilities are now strictly normalized over the valid candidate subset so that:
$$\sum_{i \in \text{Candidates}} P_{\text{normalized}}(i) = 1.0$$

---

## 1. Normalization Formula & Algorithm

Let $\{C_1, C_2, \dots, C_n\}$ be the set of $n$ valid candidate crops remaining after District Top 10 resolution, Season filtering, and Crop Alias mapping.

Let $P_{\text{raw}}(C_i)$ be the raw Random Forest output probability for candidate $C_i$.

1. Compute candidate sum:
   $$P_{\text{sum}} = \sum_{i=1}^{n} P_{\text{raw}}(C_i)$$

2. Compute normalized probability:
   $$P_{\text{normalized}}(C_i) = \frac{P_{\text{raw}}(C_i)}{P_{\text{sum}}}$$

3. Edge Case Handling:
   - **Single Candidate ($n=1$)**: $P_{\text{normalized}}(C_1) = 1.0$ (100% relative RF suitability within candidate set).
   - **Zero Candidate Sum ($P_{\text{sum}} = 0$)**: Uniform probability distribution $1 / n$ assigned across candidates.
   - **Zero Candidates ($n=0$)**: Graceful error raised ("No suitable crop found").

---

## 2. Updated Suitability Score Formula

$$\text{Suitability Score} = 40\% \times P_{\text{normalized}} + 20\% \times \text{Soil\_Match} + 20\% \times \text{Weather\_Match} + 10\% \times \text{District\_Match} + 10\% \times \text{Season\_Match}$$

$$\text{RF\_Points} = P_{\text{normalized}} \times 40.0$$

---

## 3. Verification Test Results

### Test 1: Single Candidate Normalization (`Pune, Maharashtra - Kharif`)
- **Candidate Crop**: `['onion']`
- **Raw RF Probability**: `0.0500`
- **Normalized RF Probability**: `1.0000` (100%)
- **Score Breakdown**:
  ```json
  "score_breakdown": {
    "random_forest": 40.0,
    "soil": 16.8,
    "weather": 13.8,
    "district": 10.0,
    "season": 10.0,
    "total": 90.6
  }
  ```

### Test 2: Multiple Candidate Normalization (`Ludhiana, Punjab - Rabi`)
- **Candidate Crops**: `['potato', 'onion', 'banana', 'apple', 'orange', 'pomegranate']`
- **Normalized Probabilities**:
  - `potato`: `0.4545` (45.45%)
  - `onion`: `0.4545` (45.45%)
  - `banana`: `0.0909` (9.09%)
  - `apple`: `0.0000` (0.00%)
  - `orange`: `0.0000` (0.00%)
  - `pomegranate`: `0.0000` (0.00%)
- **Sum of Normalized Probabilities**: **1.0000** (100.0%)

---

## 4. Response Schema Compliance

Every recommendation response returns both probability fields for transparent auditing:

```json
{
  "crop": "onion",
  "rank": 1,
  "raw_rf_probability": 0.05,
  "normalized_rf_probability": 1.0,
  "suitability_score": 90.6,
  "score_breakdown": {
    "random_forest": 40.0,
    "soil": 16.8,
    "weather": 13.8,
    "district": 10.0,
    "season": 10.0,
    "total": 90.6
  }
}
```

---
*AgroIntel v4.0 Technical Report — Phase 6 Probability Normalization Complete*
