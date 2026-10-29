"""Inventory Classification and Alerting Rules."""

from enum import Enum
from typing import Dict, Tuple


class InventoryStatus(str, Enum):
    POTENTIAL_STOCKOUT = "POTENTIAL_STOCKOUT"
    REORDER_REQUIRED = "REORDER_REQUIRED"
    HEALTHY = "HEALTHY"
    POTENTIAL_OVERSTOCK = "POTENTIAL_OVERSTOCK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def classify_inventory_status(
    stock_on_hand: int,
    inventory_position: int,
    reorder_point: float,
    safety_stock: float,
    average_daily_demand: float,
    lead_time_days: int,
    overstock_threshold_days: int = 45,
) -> Tuple[InventoryStatus, bool, str]:
    """Classifies inventory health and determines whether an operational alert is triggered.
    
    Returns:
        (InventoryStatus, alert_triggered: bool, reason: str)
    """
    if average_daily_demand <= 0:
        return InventoryStatus.INSUFFICIENT_DATA, False, "Zero or insufficient historical demand."

    # Days of supply on hand
    days_of_supply = stock_on_hand / max(1e-4, average_daily_demand)

    # 1. Potential Stockout: stock on hand is below safety stock or days of supply < 2
    if stock_on_hand <= safety_stock or days_of_supply < 2:
        return (
            InventoryStatus.POTENTIAL_STOCKOUT,
            True,
            f"Critically low stock ({stock_on_hand} units, {days_of_supply:.1f} days of supply) below safety stock ({safety_stock:.1f}).",
        )

    # 2. Reorder Required: inventory position has breached reorder point
    if inventory_position <= reorder_point:
        return (
            InventoryStatus.REORDER_REQUIRED,
            True,
            f"Inventory position ({inventory_position}) is below reorder point ({reorder_point:.1f}). Replenishment required.",
        )

    # 3. Potential Overstock: stock on hand exceeds configured threshold days of supply
    if days_of_supply > overstock_threshold_days:
        return (
            InventoryStatus.POTENTIAL_OVERSTOCK,
            True,
            f"Excess inventory ({stock_on_hand} units, {days_of_supply:.1f} days of supply) exceeds {overstock_threshold_days} days threshold.",
        )

    # 4. Healthy Inventory
    return (
        InventoryStatus.HEALTHY,
        False,
        f"Inventory position is healthy ({stock_on_hand} units, {days_of_supply:.1f} days of supply).",
    )
