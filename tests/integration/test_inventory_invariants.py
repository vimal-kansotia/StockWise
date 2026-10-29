"""Tests verifying inventory invariants, negative stock rejection, and over-receipt guards."""

import pytest
from inventory_forecasting.database.models import (
    Business,
    MovementType,
    OrderStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from inventory_forecasting.database.repository import InventoryRepository
from inventory_forecasting.database.session import SessionLocal
from inventory_forecasting.purchase_orders.service import PurchaseOrderService
from inventory_forecasting.stock_movements.service import StockMovementService


@pytest.fixture
def test_db():
    db = SessionLocal()
    yield db
    db.close()


def test_negative_stock_rejection(test_db):
    """Verify that an outbound stock movement cannot drive inventory below zero without audit flag."""
    biz_id = "test_invariant_biz"
    repo = InventoryRepository(test_db, business_id=biz_id)
    repo.ensure_business(name="Invariant Testing Corp")

    # Set up inventory snapshot with 10 units
    import pandas as pd
    from datetime import date
    df = pd.DataFrame([{
        "store_id": "STORE_INV_1",
        "item_id": "SKU_INV_1",
        "snapshot_date": date.today(),
        "stock_on_hand": 10,
        "incoming_stock": 0,
        "committed_stock": 0,
        "unit_cost": 5.0,
        "supplier_lead_time_days": 7,
    }])
    repo.persist_inventory_snapshots(df)

    movement_service = StockMovementService(test_db)

    # 1. Deduct 5 units -> Should succeed
    m1 = movement_service.record_movement(
        business_id=biz_id,
        store_id="STORE_INV_1",
        item_id="SKU_INV_1",
        movement_type=MovementType.SALE,
        quantity=-5,
        notes="Permitted reduction"
    )
    assert m1.quantity == -5

    # 2. Deduct 20 units (current stock is 5) -> Must raise ValueError
    with pytest.raises(ValueError, match="Insufficient stock on hand"):
        movement_service.record_movement(
            business_id=biz_id,
            store_id="STORE_INV_1",
            item_id="SKU_INV_1",
            movement_type=MovementType.SALE,
            quantity=-20,
            notes="Should fail due to insufficient stock"
        )


def test_over_receipt_rejection(test_db):
    """Verify that receiving more units than remaining ordered quantity raises ValueError."""
    biz_id = "test_overreceipt_biz"
    repo = InventoryRepository(test_db, business_id=biz_id)
    repo.ensure_business(name="Overreceipt Corp")

    sup = test_db.query(Supplier).filter_by(business_id=biz_id).first()
    if not sup:
        sup = Supplier(
            supplier_id="sup_test_01",
            business_id=biz_id,
            name="Test Supplier",
            default_lead_time_days=5
        )
        test_db.add(sup)
        test_db.commit()

    po_service = PurchaseOrderService(test_db)
    po = po_service.create_order(
        business_id=biz_id,
        supplier_id=sup.supplier_id,
        store_id="STORE_PO_1",
        items=[{"item_id": "ITEM_OVER_1", "ordered_qty": 50, "unit_cost": 10.0}],
        notes="Initial PO"
    )
    po_service.approve_order(po.order_id, biz_id, approved_by="manager_01")

    # 1. Attempt receipt with quantity <= 0 -> Must fail
    with pytest.raises(ValueError, match="Received quantity must be positive"):
        po_service.receive_order(
            po.order_id,
            biz_id,
            received_items=[{"item_id": "ITEM_OVER_1", "quantity": 0}],
            user_id="staff_01"
        )

    # 2. Attempt receiving 60 units (ordered 50) -> Must fail
    with pytest.raises(ValueError, match="Over-receipt rejected"):
        po_service.receive_order(
            po.order_id,
            biz_id,
            received_items=[{"item_id": "ITEM_OVER_1", "quantity": 60}],
            user_id="staff_01"
        )

    # 3. Valid partial receipt (30 units)
    p_partial = po_service.receive_order(
        po.order_id,
        biz_id,
        received_items=[{"item_id": "ITEM_OVER_1", "quantity": 30}],
        user_id="staff_01"
    )
    assert p_partial.status == OrderStatus.PARTIALLY_RECEIVED.value

    # 4. Attempt receiving 25 units (remaining balance is 20) -> Must fail
    with pytest.raises(ValueError, match="Over-receipt rejected"):
        po_service.receive_order(
            po.order_id,
            biz_id,
            received_items=[{"item_id": "ITEM_OVER_1", "quantity": 25}],
            user_id="staff_01"
        )
