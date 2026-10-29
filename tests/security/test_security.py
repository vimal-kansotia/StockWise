import pytest
from fastapi.testclient import TestClient
from inventory_forecasting.api.main import app
from inventory_forecasting.database.session import init_db

init_db()
client = TestClient(app)


def test_cross_tenant_data_isolation():
    # 1. Register Business A (Retailer Alpha)
    res_a = client.post("/auth/register", json={
        "email": "owner@alpha-retail.com",
        "password": "Password123!",
        "full_name": "Alice Alpha",
        "business_id": "biz_alpha",
        "business_name": "Alpha Supermarket",
        "role": "OWNER"
    })
    assert res_a.status_code == 200
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Register Business B (Retailer Beta)
    res_b = client.post("/auth/register", json={
        "email": "owner@beta-store.com",
        "password": "Password123!",
        "full_name": "Bob Beta",
        "business_id": "biz_beta",
        "business_name": "Beta Electronics",
        "role": "OWNER"
    })
    assert res_b.status_code == 200
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Business A creates product ITEM_ALPHA_001
    prod_res = client.post(
        "/products",
        json={"item_id": "ITEM_ALPHA_001", "dept_id": "GROCERY", "cat_id": "DAIRY", "name": "Alpha Milk"},
        headers=headers_a,
    )
    assert prod_res.status_code == 200
    assert prod_res.json()["business_id"] == "biz_alpha"

    # 4. Business B lists products: ITEM_ALPHA_001 MUST NOT BE VISIBLE
    list_b = client.get("/products", headers=headers_b)
    assert list_b.status_code == 200
    b_items = [p["item_id"] for p in list_b.json()]
    assert "ITEM_ALPHA_001" not in b_items

    # 5. Business B direct GET /products/ITEM_ALPHA_001 must return 404 NOT FOUND
    direct_get = client.get("/products/ITEM_ALPHA_001", headers=headers_b)
    assert direct_get.status_code == 404


def test_unauthenticated_request_rejected():
    res = client.get("/products")
    assert res.status_code == 401


def test_role_permission_enforcement():
    # Register analyst with read-only rights
    res = client.post("/auth/register", json={
        "email": "analyst@gamma.com",
        "password": "Password123!",
        "full_name": "Charlie Gamma",
        "business_id": "biz_gamma",
        "business_name": "Gamma Retail",
        "role": "ANALYST"
    })
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to create product as ANALYST -> 403 FORBIDDEN
    res_create = client.post(
        "/products",
        json={"item_id": "ITEM_GAMMA_001", "dept_id": "HARDWARE", "cat_id": "TOOLS"},
        headers=headers,
    )
    assert res_create.status_code == 403


def test_security_headers_present():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
