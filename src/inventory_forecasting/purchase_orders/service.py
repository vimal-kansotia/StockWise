"""Purchase order drafting, approval workflows, and receipt ledger posting."""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from inventory_forecasting.database.models import (
    MovementType,
    OrderStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from inventory_forecasting.stock_movements.service import StockMovementService


class PurchaseOrderService:
    def __init__(self, db: Session):
        self.db = db
        self.movement_service = StockMovementService(db)

    def create_order(
        self,
        business_id: str,
        supplier_id: str,
        store_id: str,
        items: List[Dict[str, any]],
        created_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PurchaseOrder:
        """Creates a new purchase order draft from recommendations or manual planning."""
        order_id = f"po-{uuid.uuid4().hex[:8]}"
        total_cost = 0.0

        po = PurchaseOrder(
            order_id=order_id,
            business_id=business_id,
            supplier_id=supplier_id,
            store_id=store_id,
            status=OrderStatus.DRAFT.value,
            created_by=created_by,
            notes=notes,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(po)

        for it in items:
            cost = float(it.get("unit_cost", 10.0))
            qty = int(it["ordered_qty"])
            total_cost += cost * qty
            po_item = PurchaseOrderItem(
                order_id=order_id,
                item_id=it["item_id"],
                recommended_qty=int(it.get("recommended_qty", qty)),
                ordered_qty=qty,
                received_qty=0,
                unit_cost=cost,
            )
            self.db.add(po_item)

        po.total_cost = round(total_cost, 2)
        self.db.commit()
        self.db.refresh(po)
        return po

    def approve_order(self, order_id: str, business_id: str, approved_by: str) -> PurchaseOrder:
        """Approves a draft purchase order and transitions status to APPROVED."""
        po = self.db.query(PurchaseOrder).filter_by(order_id=order_id, business_id=business_id).first()
        if not po:
            raise ValueError(f"Purchase order '{order_id}' not found.")
        if po.status not in [OrderStatus.DRAFT.value, OrderStatus.PENDING_APPROVAL.value]:
            raise ValueError(f"Cannot approve purchase order in '{po.status}' state.")

        po.status = OrderStatus.APPROVED.value
        po.approved_by = approved_by
        self.db.commit()
        self.db.refresh(po)
        return po

    def receive_order(
        self,
        order_id: str,
        business_id: str,
        received_items: List[Dict[str, int]],
        user_id: Optional[str] = None,
    ) -> PurchaseOrder:
        """Records physical goods receipt, prevents duplicate postings, and records stock movements."""
        po = self.db.query(PurchaseOrder).filter_by(order_id=order_id, business_id=business_id).first()
        if not po:
            raise ValueError(f"Purchase order '{order_id}' not found.")
        if po.status not in [OrderStatus.APPROVED.value, OrderStatus.ORDERED.value, OrderStatus.PARTIALLY_RECEIVED.value]:
            raise ValueError(f"Cannot receive items for order in '{po.status}' state.")

        try:
            item_map = {item.item_id: item for item in po.items}
            all_completed = True

            for rec in received_items:
                item_id = rec["item_id"]
                qty = int(rec["quantity"])
                if qty <= 0:
                    raise ValueError(f"Received quantity must be positive, got {qty} for item '{item_id}'.")

                if item_id in item_map:
                    p_item = item_map[item_id]
                    if p_item.received_qty + qty > p_item.ordered_qty:
                        raise ValueError(
                            f"Over-receipt rejected: Attempted to receive {qty} for item '{item_id}', "
                            f"but remaining order balance is {p_item.ordered_qty - p_item.received_qty}."
                        )
                    p_item.received_qty += qty
                    if p_item.received_qty < p_item.ordered_qty:
                        all_completed = False

                    # Post stock movement transaction
                    self.movement_service.record_movement(
                        business_id=business_id,
                        store_id=po.store_id,
                        item_id=item_id,
                        movement_type=MovementType.SUPPLIER_RECEIPT,
                        quantity=qty,
                        reference_id=order_id,
                        user_id=user_id,
                        notes=f"Receipt for PO {order_id}",
                    )

            po.status = OrderStatus.RECEIVED.value if all_completed else OrderStatus.PARTIALLY_RECEIVED.value
            self.db.commit()
            self.db.refresh(po)
            return po
        except Exception:
            self.db.rollback()
            raise

    def get_orders(self, business_id: str, status: Optional[str] = None) -> List[PurchaseOrder]:
        query = self.db.query(PurchaseOrder).filter_by(business_id=business_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(PurchaseOrder.created_at.desc()).all()
