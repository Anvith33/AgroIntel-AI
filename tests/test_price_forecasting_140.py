import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

CROPS = ["rice", "wheat", "maize", "onion", "potato"]
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal"
]

def test_140_state_crop_forecasts():
    passed = 0
    total = len(CROPS) * len(STATES)
    for crop in CROPS:
        for state in STATES:
            url = f"/api/predict?crop={crop}&state={state}&horizon_days=30"
            resp = client.get(url)
            assert resp.status_code == 200, f"Failed for {crop} in {state}: {resp.text}"
            data = resp.json()
            assert data.get("available") is True
            assert isinstance(data.get("predicted_price"), (int, float))
            assert data.get("recommendation") in ["SELL", "HOLD", "WAIT"]
            passed += 1
    assert passed == total
