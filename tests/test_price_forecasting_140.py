import requests

BASE_URL = "http://localhost:8000"
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
            url = f"{BASE_URL}/api/predict?crop={crop}&state={state}&horizon_days=30"
            resp = requests.get(url, timeout=5)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("available") is True
            assert isinstance(data.get("predicted_price"), (int, float))
            assert data.get("recommendation") in ["SELL", "HOLD", "WAIT"]
            passed += 1
    assert passed == total
