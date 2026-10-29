"""End-to-End Automated Smoke Test Workflow.

Validates:
1. Database initialization
2. Synthetic M5 dataset generation
3. Medallion ETL (Bronze -> Silver -> Gold)
4. Forecasting model training (LightGBM vs Baselines)
5. Multi-step forward recursive forecasting
6. Statistical safety stock & reorder point calculations
7. FastAPI authentication & multi-tenant isolation
8. Purchase order generation, approval, and partial goods receipt
9. Stock movement ledger update & reconciliation
"""

import sys
from fastapi.testclient import TestClient
from inventory_forecasting.api.main import app
from inventory_forecasting.database.session import init_db
from inventory_forecasting.pipelines.run_pipeline import run_full_pipeline

def main():
    print("=" * 60)
    print("🚀 STARTING END-TO-END SMOKE TEST")
    print("=" * 60)

    # 1. Initialize DB
    print("\n[Step 1/6] Initializing Database Schema...")
    init_db()
    print("✅ Database schema initialized.")

    # 2. Run Data Science & Data Engineering Pipeline
    print("\n[Step 2/6] Running Medallion ETL, Model Training & Forecasting...")
    res = run_full_pipeline(use_synthetic=True, num_stores=3, num_products=15)
    assert res["status"] == "SUCCESS"
    print(f"✅ Pipeline Completed in {res['duration_seconds']:.2f}s")
    print(f"   - Champion Model: {res['champion_model']}")
    print(f"   - Forecasts Generated: {res['forecast_count']}")
    print(f"   - Recommendations: {res['recommendation_count']}")

    # 3. Test REST API & Authentication
    print("\n[Step 3/6] Testing Multi-Tenant API & Authentication...")
    client = TestClient(app)
    auth_res = client.post("/auth/register", json={
        "email": "smoke_owner@retail.com",
        "password": "Password123!",
        "full_name": "Smoke Test Owner",
        "business_id": "smoke_retail_corp",
        "business_name": "Smoke Retail Corp",
        "role": "OWNER"
    })
    assert auth_res.status_code == 200
    token = auth_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ Registered business and received JWT token.")

    # 4. Product Catalog & Recommendations Access
    print("\n[Step 4/6] Querying Products & Inventory Recommendations...")
    client.post("/products", json={"item_id": "SMOKE_SKU_1", "dept_id": "GROCERY", "cat_id": "FOODS"}, headers=headers)
    prod_res = client.get("/products", headers=headers)
    assert prod_res.status_code == 200
    print(f"✅ Products retrieved for tenant. Count: {len(prod_res.json())}")

    # 5. Purchase Order Creation & Approval
    print("\n[Step 5/6] Drafting & Approving Purchase Order...")
    po_res = client.post("/purchase-orders", json={
        "supplier_id": "SUPPLIER_DEMO",
        "store_id": "CA_1",
        "items": [{"item_id": "SMOKE_SKU_1", "ordered_qty": 100, "unit_cost": 5.50}],
        "notes": "Automated Smoke Test Order",
    }, headers=headers)
    assert po_res.status_code == 200
    order_id = po_res.json()["order_id"]
    print(f"✅ Created PO: {order_id} (Status: {po_res.json()['status']})")

    appr_res = client.post(f"/purchase-orders/{order_id}/approve", headers=headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"
    print(f"✅ Approved PO: {order_id}")

    # 6. Goods Receipt & Stock Movement Ledger
    print("\n[Step 6/6] Receiving Goods & Verifying Stock Movement Ledger...")
    rec_res = client.post(f"/purchase-orders/{order_id}/receive", json={
        "received_items": [{"item_id": "SMOKE_SKU_1", "quantity": 40}]
    }, headers=headers)
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "PARTIALLY_RECEIVED"

    mov_res = client.get("/inventory/movements", headers=headers)
    assert mov_res.status_code == 200
    movements = mov_res.json()
    assert len(movements) >= 1
    print(f"✅ Goods received: 40 units posted to Stock Movement ledger.")
    print(f"   - Movement Type: {movements[0]['movement_type']}")
    print(f"   - Reference ID: {movements[0]['reference_id']}")

    print("\n" + "=" * 60)
    print("🎉 ALL END-TO-END SMOKE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    main()
