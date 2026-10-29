"""Inventory stock movement tracking, ledger transactions, and physical reconciliation."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from inventory_forecasting.database.models import (
    InventorySnapshot,
    MovementType,
    StockMovement,
)


class StockMovementService:
    def __init__(self, db: Session):
        self.db = db

    def record_movement(
        self,
        business_id: str,
        store_id: str,
        item_id: str,
        movement_type: MovementType,
        quantity: int,
        reference_id: Optional[str] = None,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> StockMovement:
        """Records an immutable stock movement and updates the inventory snapshot accordingly.
        
        Sign convention:
        - SALE, DAMAGE_SPOILAGE, SUPPLIER_RETURN: negative quantity.
        - CUSTOMER_RETURN, SUPPLIER_RECEIPT: positive quantity.
        - MANUAL_ADJUSTMENT, STOCK_RECONCILIATION: delta signed quantity.
        """
        try:
            # Create movement record
            movement = StockMovement(
                business_id=business_id,
                store_id=store_id,
                item_id=item_id,
                movement_type=movement_type.value,
                quantity=quantity,
                reference_id=reference_id,
                user_id=user_id,
                notes=notes,
                timestamp=datetime.now(timezone.utc),
            )
            self.db.add(movement)

            # Update latest snapshot with row-level lock where supported
            query = (
                self.db.query(InventorySnapshot)
                .filter_by(business_id=business_id, store_id=store_id, item_id=item_id)
                .order_by(InventorySnapshot.snapshot_date.desc())
            )
            # Use with_for_update on PostgreSQL; silently skipped on SQLite
            try:
                snapshot = query.with_for_update().first()
            except Exception:
                snapshot = query.first()

            if snapshot:
                new_stock = snapshot.stock_on_hand + quantity
                if new_stock < 0 and movement_type != MovementType.STOCK_RECONCILIATION:
                    raise ValueError(
                        f"Insufficient stock on hand ({snapshot.stock_on_hand}) for item '{item_id}' to reduce by {abs(quantity)}."
                    )
                snapshot.stock_on_hand = max(0, new_stock)
                # If supplier receipt, decrease incoming stock
                if movement_type == MovementType.SUPPLIER_RECEIPT and quantity > 0:
                    snapshot.incoming_stock = max(0, snapshot.incoming_stock - quantity)

            self.db.commit()
            self.db.refresh(movement)
            return movement
        except Exception:
            self.db.rollback()
            raise

    def reconcile_physical_stock(
        self,
        business_id: str,
        store_id: str,
        item_id: str,
        physical_count: int,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, any]:
        """Reconciles recorded system inventory with an actual physical stock audit count."""
        snapshot = (
            self.db.query(InventorySnapshot)
            .filter_by(business_id=business_id, store_id=store_id, item_id=item_id)
            .order_by(InventorySnapshot.snapshot_date.desc())
            .first()
        )
        previous_count = snapshot.stock_on_hand if snapshot else 0
        discrepancy = physical_count - previous_count

        movement = self.record_movement(
            business_id=business_id,
            store_id=store_id,
            item_id=item_id,
            movement_type=MovementType.STOCK_RECONCILIATION,
            quantity=discrepancy,
            user_id=user_id,
            notes=f"Physical reconciliation: previous={previous_count}, counted={physical_count}. {notes or ''}",
        )

        return {
            "store_id": store_id,
            "item_id": item_id,
            "previous_system_stock": previous_count,
            "physical_counted_stock": physical_count,
            "adjustment_quantity": discrepancy,
            "movement_id": movement.id,
        }

    def get_movements(
        self,
        business_id: str,
        store_id: Optional[str] = None,
        item_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[StockMovement]:
        query = self.db.query(StockMovement).filter_by(business_id=business_id)
        if store_id:
            query = query.filter_by(store_id=store_id)
        if item_id:
            query = query.filter_by(item_id=item_id)
        return query.order_by(StockMovement.timestamp.desc()).limit(limit).all()
