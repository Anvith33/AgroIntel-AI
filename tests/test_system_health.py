import pytest, requests

BASE_URL = "http://localhost:8000"

def test_health():
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert data.get("price_models") is True
    assert data.get("crop_model") is True

def test_frontend_mount():
    resp = requests.get(f"{BASE_URL}/", timeout=5)
    assert resp.status_code == 200
    assert "AgroIntel" in resp.text
