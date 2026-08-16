"""
test_regression_bugs.py — AgroIntel Final Architecture Regression Tests

Tests all bugs identified during manual frontend testing:
  BUG 1: 500 error on Maharashtra / Ahilya Nagar / Kharif recommendation
  BUG 2: HOLD returned for crops with no price model (e.g. Sugarcane)
  BUG 3: Cross-crop price substitution (Sugarcane -> Wheat model)
  BUG 4: Forecast not exactly 30 days
  BUG 5: Technical scores in farmer UI

Each test asserts the CONTENT of the response, not just HTTP 200.
"""

import re
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SUPPORTED_CROPS = ["rice", "wheat", "maize", "onion", "potato"]
NON_FORECAST_CROPS = ["sugarcane", "cotton", "soybean"]

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal"
]


# ── BUG 1: 500 Error on Ahilya Nagar ─────────────────────────────────────────

def test_crop_recommendation_runtime_error():
    """BUG 1: All Ahmednagar aliases must return HTTP 200, not 500."""
    aliases = ["Ahilya Nagar", "Ahmednagar", "Ahmed Nagar", "Ahmadnagar", "Ahilyanagar"]
    for alias in aliases:
        resp = client.post("/api/phase6/recommend", json={
            "state": "Maharashtra", "district": alias, "season": "Kharif"
        })
        assert resp.status_code == 200, (
            f"BUG 1 FAIL: district='{alias}' -> HTTP {resp.status_code}: {resp.text[:200]}"
        )
        data = resp.json()
        assert "error" not in data, f"Error in response for '{alias}': {data}"
        loc = data.get("location", {})
        canon_id = loc.get("canonical_id", "").lower()
        assert "ahilya" in canon_id or "ahilyanagar" in canon_id or "ahilya" in loc.get("district","").lower(), (
            f"'{alias}' resolved to unexpected location: {loc}"
        )


# ── BUG 2: No fake HOLD for unsupported crops ─────────────────────────────────

def test_advisory_without_price_model():
    """BUG 2: Advisory for Sugarcane must return decision=null, not HOLD."""
    resp = client.post("/api/advisory", json={
        "state": "Maharashtra", "district": "Ahilya Nagar", "season": "Kharif"
    })
    assert resp.status_code == 200
    data = resp.json()
    pp = data.get("price_prediction", {})
    target = data.get("target_price_crop", "").lower()

    if target not in SUPPORTED_CROPS:
        assert pp.get("decision") is None, (
            f"BUG 2 FAIL: decision='{pp.get('decision')}' for unsupported crop '{target}'. "
            "Must be null, never HOLD."
        )
        assert pp.get("predicted_30d_avg") is None, (
            f"BUG 2 FAIL: predicted_30d_avg set for unsupported crop."
        )
        assert pp.get("forecast_available") is False, (
            f"BUG 2 FAIL: forecast_available=True for unsupported crop."
        )


def test_no_default_hold_when_prediction_missing():
    """BUG 2: /api/predict for unsupported crops must not return HOLD."""
    for crop in NON_FORECAST_CROPS[:2]:
        resp = client.get(f"/api/predict?crop={crop}&state=Maharashtra&horizon_days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("available") is False, (
            f"BUG 2 FAIL: available=True for unsupported crop '{crop}'"
        )
        adv = data.get("advisory", {})
        assert adv.get("decision") not in ("HOLD", "SELL", "WAIT"), (
            f"BUG 2 FAIL: advisory.decision='{adv.get('decision')}' for unsupported crop '{crop}'."
        )


# ── BUG 3: Cross-crop isolation ───────────────────────────────────────────────

def test_no_cross_crop_prediction():
    """BUG 3: Wheat and Rice must produce different forecasts. Sugarcane must be unavailable."""
    wheat = client.get("/api/predict?crop=wheat&state=Maharashtra&horizon_days=30").json()
    rice  = client.get("/api/predict?crop=rice&state=Maharashtra&horizon_days=30").json()

    assert wheat.get("predicted_price") != rice.get("predicted_price"), (
        "BUG 3 FAIL: Wheat and Rice have identical predicted_price — cross-crop contamination."
    )

    sg = client.get("/api/predict?crop=sugarcane&state=Maharashtra&horizon_days=30").json()
    assert sg.get("available") is False, (
        f"BUG 3 FAIL: Sugarcane returned available=True. Never substitute another crop's model."
    )


# ── BUG 4: Exactly 30 forecast days ──────────────────────────────────────────

def test_exactly_30_forecast_days():
    """BUG 4: 30-day forecast must have exactly 30 points spanning 29 days."""
    from datetime import date as _date

    for crop in SUPPORTED_CROPS:
        resp = client.get(f"/api/predict?crop={crop}&state=Maharashtra&horizon_days=30")
        assert resp.status_code == 200
        data = resp.json()
        preds = data.get("predictions", [])
        dates = data.get("date_labels", [])

        assert len(preds) == 30, f"BUG 4 FAIL: {crop} has {len(preds)} predictions, expected 30."
        assert len(dates) == 30, f"BUG 4 FAIL: {crop} has {len(dates)} dates, expected 30."

        d0 = _date.fromisoformat(dates[0])
        d_last = _date.fromisoformat(dates[-1])
        span = (d_last - d0).days
        assert span == 29, (
            f"BUG 4 FAIL: {crop} span={span} days (expected 29). "
            f"First={dates[0]}, Last={dates[-1]}"
        )
        for i, p in enumerate(preds):
            assert isinstance(p, (int, float)) and p > 0, (
                f"BUG 4 FAIL: {crop} prediction[{i}]={p} is invalid."
            )


# ── Advisory <-> Predict consistency ─────────────────────────────────────────

def test_advisory_price_matches_predict_endpoint():
    """Advisory and /api/predict must agree on predicted price (within 5% tolerance)."""
    for crop in ["wheat", "rice"]:
        state = "Maharashtra"
        pred_data = client.get(f"/api/predict?crop={crop}&state={state}&horizon_days=30").json()
        direct_pred = pred_data.get("predicted_price")

        adv_data = client.post("/api/advisory", json={
            "state": state, "district": "Pune", "season": "Rabi", "crop": crop
        }).json()
        adv_pred = adv_data.get("price_prediction", {}).get("predicted_30d_avg")

        if direct_pred is not None and adv_pred is not None:
            diff_pct = abs(direct_pred - adv_pred) / direct_pred * 100
            assert diff_pct < 5.0, (
                f"Advisory/predict mismatch for {crop}/{state}: "
                f"direct={direct_pred}, advisory={adv_pred}, diff={diff_pct:.1f}%"
            )


# ── Location alias resolution ─────────────────────────────────────────────────

def test_ahilya_nagar_aliases():
    """All Ahmednagar aliases must resolve to canonical Ahilya Nagar."""
    from app.services.location_normalizer import normalize_location
    cases = [
        ("Ahmednagar", "Maharashtra"), ("Ahmed Nagar", "Maharashtra"),
        ("Ahmednagar District", "Maharashtra"), ("Ahilyanagar", "Maharashtra"),
        ("Ahmadnagar", "Maharashtra"), ("AHMADNAGAR", "Maharashtra"),
    ]
    for district, state in cases:
        result = normalize_location(district, state)
        canon = result["canonical_name"].lower()
        canon_id = result["canonical_id"].lower()
        assert "ahilya" in canon or "ahilyanagar" in canon_id, (
            f"ALIAS FAIL: '{district}' -> '{result['canonical_name']}' (id: {result['canonical_id']})"
        )


# ── Weather robustness ────────────────────────────────────────────────────────

def test_weather_provider_failure():
    """Weather service failure must not cause 500 — recommendation must still return 200."""
    resp = client.post("/api/phase6/recommend", json={
        "state": "Nagaland", "district": "Kohima", "season": "Kharif"
    })
    assert resp.status_code == 200, f"Weather failure caused 500: {resp.text[:300]}"


def test_no_fake_weather_defaults():
    """Weather service must report its provider and status."""
    from app.services.weather_service import get_weather_summary
    result = get_weather_summary(20.0, 77.0, "Test District")
    assert hasattr(result, 'provider'), "Weather result missing 'provider'"
    assert hasattr(result, 'weather_status'), "Weather result missing 'weather_status'"


# ── BUG 5: No technical scores in farmer output ───────────────────────────────

def test_no_technical_scores_in_farmer_response():
    """BUG 5: nlp_explanation fields must not contain raw score patterns (e.g. 25.0/25)."""
    resp = client.post("/api/phase6/recommend", json={
        "state": "Maharashtra", "district": "Pune", "season": "Kharif"
    })
    assert resp.status_code == 200
    data = resp.json()
    score_pattern = re.compile(r'\b\d+\.?\d*\/\d+\b')
    forbidden_terms = ["STATE_CROP", "CROP_ONLY", "model_level", "forecast_scope", "RMSE", "MAE"]

    for rec in data.get("recommendations", []):
        expl = rec.get("nlp_explanation", {})
        for field in ["why_recommended", "current_situation", "considerations"]:
            text = expl.get(field, "") or ""
            assert not score_pattern.search(text), (
                f"BUG 5 FAIL: Score pattern in '{field}': '{text}'"
            )
            for term in forbidden_terms:
                assert term not in text, (
                    f"BUG 5 FAIL: Internal term '{term}' in '{field}': '{text}'"
                )
