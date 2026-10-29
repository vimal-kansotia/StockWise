import pytest
from fastapi.testclient import TestClient
from inventory_forecasting.api.main import app
from inventory_forecasting.config import settings

from inventory_forecasting.database.session import init_db

init_db()
client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "version" in data


def test_products_endpoint():
    headers = {"X-API-Key": settings.api_key}
    response = client.get("/products?limit=10", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_secured_endpoint_unauthorized():
    response = client.post("/pipeline/ingest", json={"use_synthetic": True})
    # Missing auth header
    assert response.status_code in [401, 403]


def test_secured_endpoint_authorized():
    # Pass valid API key header
    headers = {"X-API-Key": settings.api_key}
    # Test invalid product 404
    resp = client.get("/products/NON_EXISTENT_ITEM_12345", headers=headers)
    assert resp.status_code == 404
