import pytest
from fastapi.testclient import TestClient
from inventory_forecasting.api.main import app
from inventory_forecasting.database.session import init_db

init_db()
client = TestClient(app)


def test_purchase_order_lifecycle_and_goods_receipt():
    # 1. Register business
    res = client.post("/auth/register", json={
        "email": "manager@store-po.com",
        "password": "Password123!",
        "full_name": "Mary Manager",
        "business_id": "biz_po_test",
        "business_name": "PO Test Retail",
        "role": "OWNER"
    })
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create supplier & product
    client.post(
        "/products",
        json={"item_id": "PO_ITEM_100", "dept_id": "FOODS", "cat_id": "SNACKS"},
        headers=headers,
    )

    # 3. Create Draft PO
    po_res = client.post(
        "/purchase-orders",
        json={
            "supplier_id": "SUPPLIER_GLOBAL",
            "store_id": "STORE_MAIN",
            "items": [{"item_id": "PO_ITEM_100", "ordered_qty": 50, "unit_cost": 12.0}],
            "notes": "Weekly replenishment",
        },
        headers=headers,
    )
    assert po_res.status_code == 200
    order_id = po_res.json()["order_id"]
    assert po_res.json()["status"] == "DRAFT"
    assert po_res.json()["total_cost"] == 600.0

    # 4. Approve PO
    app_res = client.post(f"/purchase-orders/{order_id}/approve", headers=headers)
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"

    # 5. Receive Partial Goods (20 units)
    rec_res = client.post(
        f"/purchase-orders/{order_id}/receive",
        json={"received_items": [{"item_id": "PO_ITEM_100", "quantity": 20}]},
        headers=headers,
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "PARTIALLY_RECEIVED"

    # 6. Verify Stock Movement Ledger entry was created
    mov_res = client.get("/inventory/movements", headers=headers)
    assert mov_res.status_code == 200
    movements = mov_res.json()
    assert len(movements) >= 1
    assert movements[0]["movement_type"] == "SUPPLIER_RECEIPT"
    assert movements[0]["quantity"] == 20
    assert movements[0]["reference_id"] == order_id


def test_physical_stock_reconciliation():
    # Register store staff
    res = client.post("/auth/register", json={
        "email": "audit@reconcile.com",
        "password": "Password123!",
        "full_name": "Auditor Dave",
        "business_id": "biz_reconcile",
        "business_name": "Reconcile Corp",
        "role": "OWNER"
    })
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Reconcile physical count to 150 units
    recon_res = client.post(
        "/inventory/reconcile",
        json={"store_id": "STORE_1", "item_id": "AUDIT_SKU_1", "physical_count": 150},
        headers=headers,
    )
    assert recon_res.status_code == 200
    data = recon_res.json()
    assert data["physical_counted_stock"] == 150
    assert data["adjustment_quantity"] == 150
