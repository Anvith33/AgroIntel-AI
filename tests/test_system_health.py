import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert data.get("price_models") is True
    assert data.get("crop_model") is True

def test_frontend_mount():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "AgroIntel" in resp.text
