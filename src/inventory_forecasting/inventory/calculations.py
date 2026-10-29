"""Inventory optimization calculations.

Formulas implemented:
1. Demand During Lead Time (DDLT): Sum of forecast demand over lead time horizon.
2. Safety Stock (SS):
   - Formula: z * sqrt(L * sigma_d^2 + d_bar^2 * sigma_L^2)
   - When lead time is deterministic (sigma_L = 0): z * sigma_d * sqrt(L)
   - Where z is inverse CDF of standard normal for target service level (e.g. 1.645 for 95%).
3. Reorder Point (ROP): DDLT + Safety Stock.
4. Inventory Position (IP): On Hand + On Order (Incoming) - Backorders (Committed).
5. Recommended Order Quantity (ROQ):
   - If IP <= ROP: Target Stock Level - IP, rounded up to order multiples and MOQ.
"""

import math
from typing import Optional


# Z-scores for standard service level targets
Z_SCORE_MAP = {
    0.80: 0.8416,
    0.85: 1.0364,
    0.90: 1.2816,
    0.95: 1.6449,
    0.98: 2.0537,
    0.99: 2.3263,
}


def get_z_score(service_level: float = 0.95) -> float:
    """Gets standard normal distribution z-factor for given service level."""
    if service_level in Z_SCORE_MAP:
        return Z_SCORE_MAP[service_level]
    # Simple clamped polynomial approximation for other values between 0.50 and 0.999
    p = min(0.999, max(0.50, service_level))
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308
    return t - ((c0 + c1 * t + c2 * (t**2)) / (1.0 + d1 * t + d2 * (t**2) + d3 * (t**3)))


def calculate_safety_stock(
    demand_std: float,
    lead_time_days: int,
    service_level: float = 0.95,
    lead_time_std: float = 0.0,
    average_daily_demand: float = 0.0,
) -> float:
    """Calculates statistical safety stock accounting for demand and lead time variability.
    
    Formula: z * sqrt(L * sigma_d^2 + d_bar^2 * sigma_L^2)
    """
    z = get_z_score(service_level)
    variance_term = (lead_time_days * (demand_std ** 2)) + ((average_daily_demand ** 2) * (lead_time_std ** 2))
    ss = z * math.sqrt(max(0.0, variance_term))
    return max(0.0, ss)


def calculate_reorder_point(lead_time_demand: float, safety_stock: float) -> float:
    """Calculates Reorder Point (ROP = Lead Time Demand + Safety Stock)."""
    return max(0.0, lead_time_demand + safety_stock)


def calculate_inventory_position(
    stock_on_hand: int,
    incoming_stock: int = 0,
    committed_stock: int = 0,
) -> int:
    """Calculates effective inventory position: OnHand + InTransit - Committed."""
    return stock_on_hand + incoming_stock - committed_stock


def calculate_recommended_order_quantity(
    inventory_position: int,
    reorder_point: float,
    target_stock_level: float,
    min_order_qty: int = 10,
    order_multiple: int = 5,
) -> int:
    """Determines recommended replenishment order size when inventory position <= ROP.
    
    Applies constraints:
    - Minimum Order Quantity (MOQ)
    - Order Pack Multiple (e.g. increments of 5 or 10 units)
    """
    if inventory_position > reorder_point:
        return 0

    raw_order = target_stock_level - inventory_position
    if raw_order <= 0:
        return 0

    order_qty = max(min_order_qty, int(math.ceil(raw_order)))
    
    # Enforce order multiple (pack size)
    if order_multiple > 1:
        remainder = order_qty % order_multiple
        if remainder != 0:
            order_qty += (order_multiple - remainder)

    return order_qty
