import requests

BASE_URL = "http://localhost:8000"

TEST_CASES = [
    {"state": "Karnataka", "district": "Dakshina Kannada", "season": "Kharif", "soil_ph": 5.8},
    {"state": "Punjab", "district": "Ludhiana", "season": "Rabi", "soil_ph": 7.2},
    {"state": "Maharashtra", "district": "Nashik", "season": "Kharif", "soil_ph": 7.4},
    {"state": "Kerala", "district": "Wayanad", "season": "Kharif", "soil_ph": 5.5},
    {"state": "Uttar Pradesh", "district": "Varanasi", "season": "Rabi", "soil_ph": 6.9}
]

def test_recommendation_scenarios():
    for tc in TEST_CASES:
        resp = requests.post(f"{BASE_URL}/api/phase6/recommend", json=tc, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data.get("recommendations", [])) > 0
        top = data["recommendations"][0]
        assert "crop" in top
        assert "final_score" in top
