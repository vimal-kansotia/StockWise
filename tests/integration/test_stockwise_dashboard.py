"""Integration tests verifying frontend static asset serving, monitoring, and suppliers endpoints."""

import pytest
from fastapi.testclient import TestClient
from inventory_forecasting.api.main import app

client = TestClient(app)


def test_static_index_html_serving():
    """Verify that root URL serves StockWise Intelligence index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "StockWise Intelligence" in response.text
    assert "Executive Dashboard" in response.text


def test_monitoring_spark_endpoint():
    """Verify Spark monitoring endpoint returns real connectivity status."""
    response = client.get("/monitoring/spark", headers={"X-API-Key": "dev-secret-api-key-2026"})
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "status" in data


def test_monitoring_airflow_endpoint():
    """Verify Airflow monitoring endpoint returns real health structure."""
    response = client.get("/monitoring/airflow", headers={"X-API-Key": "dev-secret-api-key-2026"})
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "status" in data


def test_monitoring_data_quality_endpoint():
    """Verify data quality endpoint returns real Medallion lake layer details."""
    response = client.get("/monitoring/data-quality", headers={"X-API-Key": "dev-secret-api-key-2026"})
    assert response.status_code == 200
    data = response.json()
    assert "medallion_layers" in data
    assert "database_integrity" in data
    assert "schema_checks" in data


def test_suppliers_and_stores_endpoints():
    """Verify suppliers and stores endpoints return valid lists."""
    sup_res = client.get("/suppliers", headers={"X-API-Key": "dev-secret-api-key-2026"})
    assert sup_res.status_code == 200
    assert isinstance(sup_res.json(), list)

    store_res = client.get("/stores", headers={"X-API-Key": "dev-secret-api-key-2026"})
    assert store_res.status_code == 200
    assert isinstance(store_res.json(), list)
