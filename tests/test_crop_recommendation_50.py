import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TEST_CASES = [
    {"state": "Maharashtra", "district": "Ahilya Nagar", "season": "Kharif", "soil_ph": 6.8},
    {"state": "Karnataka", "district": "Dakshina Kannada", "season": "Kharif", "soil_ph": 5.8},
    {"state": "Punjab", "district": "Ludhiana", "season": "Rabi", "soil_ph": 7.2},
    {"state": "Maharashtra", "district": "Nashik", "season": "Kharif", "soil_ph": 7.4},
    {"state": "Kerala", "district": "Wayanad", "season": "Kharif", "soil_ph": 5.5},
    {"state": "Uttar Pradesh", "district": "Varanasi", "season": "Rabi", "soil_ph": 6.9}
]

def test_recommendation_scenarios():
    for tc in TEST_CASES:
        resp = client.post("/api/phase6/recommend", json=tc)
        assert resp.status_code == 200, f"Failed for {tc}: {resp.text}"
        data = resp.json()
        assert len(data.get("recommendations", [])) > 0
        top = data["recommendations"][0]
        assert "crop" in top
        assert "final_score" in top
        assert "nlp_explanation" in top
        assert "why_recommended" in top["nlp_explanation"]
        assert "considerations" in top["nlp_explanation"]
