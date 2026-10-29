import pytest
import numpy as np
import pandas as pd
from inventory_forecasting.inventory.calculations import (
    calculate_safety_stock,
    calculate_reorder_point,
    calculate_inventory_position,
    calculate_recommended_order_quantity,
    get_z_score,
)
from inventory_forecasting.inventory.alerts import classify_inventory_status, InventoryStatus


def test_z_score_lookup():
    assert round(get_z_score(0.95), 2) == 1.64
    assert round(get_z_score(0.99), 2) == 2.33


def test_safety_stock_deterministic_lead_time():
    # Demand std = 5, Lead time = 4 days, Service level = 95% (z = 1.645)
    # SS = 1.645 * 5 * sqrt(4) = 1.645 * 10 = 16.45
    ss = calculate_safety_stock(demand_std=5.0, lead_time_days=4, service_level=0.95)
    assert round(ss, 1) == 16.4


def test_reorder_point():
    # Lead time demand = 100, Safety stock = 20 -> ROP = 120
    rop = calculate_reorder_point(lead_time_demand=100.0, safety_stock=20.0)
    assert rop == 120.0


def test_inventory_position():
    # OnHand=50, InTransit=30, Committed=10 -> IP = 70
    ip = calculate_inventory_position(stock_on_hand=50, incoming_stock=30, committed_stock=10)
    assert ip == 70


def test_recommended_order_quantity_constraints():
    # IP=50, ROP=60 -> Reorder triggered
    # Target stock = 100. Raw difference = 50.
    # MOQ=20, multiple=15 -> 50 ceil with multiple 15 -> 60
    roq = calculate_recommended_order_quantity(
        inventory_position=50,
        reorder_point=60.0,
        target_stock_level=100.0,
        min_order_qty=20,
        order_multiple=15,
    )
    assert roq == 60

    # No order when IP > ROP
    roq_zero = calculate_recommended_order_quantity(
        inventory_position=70,
        reorder_point=60.0,
        target_stock_level=100.0,
    )
    assert roq_zero == 0


def test_classification_potential_stockout():
    status, alert, reason = classify_inventory_status(
        stock_on_hand=2,
        inventory_position=2,
        reorder_point=25.0,
        safety_stock=10.0,
        average_daily_demand=5.0,
        lead_time_days=5,
    )
    assert status == InventoryStatus.POTENTIAL_STOCKOUT
    assert alert is True


def test_classification_potential_overstock():
    status, alert, reason = classify_inventory_status(
        stock_on_hand=500,
        inventory_position=500,
        reorder_point=50.0,
        safety_stock=15.0,
        average_daily_demand=5.0,
        lead_time_days=5,
        overstock_threshold_days=45,
    )
    assert status == InventoryStatus.POTENTIAL_OVERSTOCK
    assert alert is True
