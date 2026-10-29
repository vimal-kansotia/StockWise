"""Inventory Recommendation Engine.

Combines forward forecasts, inventory snapshots, and supplier constraints
to generate actionable stock replenishment recommendations.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from inventory_forecasting.config import settings
from inventory_forecasting.inventory.alerts import InventoryStatus, classify_inventory_status
from inventory_forecasting.inventory.calculations import (
    calculate_inventory_position,
    calculate_recommended_order_quantity,
    calculate_reorder_point,
    calculate_safety_stock,
)


class InventoryEngine:
    def __init__(
        self,
        service_level: float = 0.95,
        overstock_threshold_days: int = 45,
    ):
        self.service_level = service_level
        self.overstock_threshold_days = overstock_threshold_days

    def generate_recommendations(
        self,
        inventory_df: pd.DataFrame,
        forecasts_df: pd.DataFrame,
        historical_sales_df: Optional[pd.DataFrame] = None,
    ) -> List[Dict]:
        """Generates replenishment recommendations across all items and stores.
        
        Args:
            inventory_df: Snapshots (store_id, item_id, stock_on_hand, incoming_stock, lead_time_days, MOQ...)
            forecasts_df: Forecast records (store_id, item_id, forecast_date, predicted_demand)
            historical_sales_df: Optional sales history for historical demand standard deviation
        """
        recommendations = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for _, inv in inventory_df.iterrows():
            store_id = inv["store_id"]
            item_id = inv["item_id"]
            stock_on_hand = int(inv.get("stock_on_hand", 0))
            incoming_stock = int(inv.get("incoming_stock", 0))
            committed_stock = int(inv.get("committed_stock", 0))
            lead_time_days = int(inv.get("supplier_lead_time_days", settings.default_lead_time_days))
            min_order_qty = int(inv.get("min_order_qty", 10))
            order_multiple = int(inv.get("order_multiple", 5))

            # Filter forecasts for this store-item
            sub_fc = forecasts_df[
                (forecasts_df["store_id"] == store_id) & (forecasts_df["item_id"] == item_id)
            ].sort_values("forecast_date")

            # 1. Demand During Lead Time (sum of first L days of forecast)
            lt_forecasts = sub_fc.head(lead_time_days)
            if len(lt_forecasts) > 0:
                lead_time_demand = float(lt_forecasts["predicted_demand"].sum())
                avg_daily_demand = float(lt_forecasts["predicted_demand"].mean())
            else:
                lead_time_demand = 0.0
                avg_daily_demand = 0.0

            # 2. Demand variability (sigma_d)
            if historical_sales_df is not None and not historical_sales_df.empty:
                hist_sub = historical_sales_df[
                    (historical_sales_df["store_id"] == store_id) & (historical_sales_df["item_id"] == item_id)
                ]
                demand_std = float(hist_sub["units_sold"].std()) if len(hist_sub) > 1 else avg_daily_demand * 0.3
            else:
                # Approximation: standard retail coefficient of variation ~ 0.3 - 0.4
                demand_std = avg_daily_demand * 0.35

            if np.isnan(demand_std) or demand_std <= 0:
                demand_std = max(1.0, avg_daily_demand * 0.3)

            # 3. Calculate Safety Stock & Reorder Point
            safety_stock = calculate_safety_stock(
                demand_std=demand_std,
                lead_time_days=lead_time_days,
                service_level=self.service_level,
                average_daily_demand=avg_daily_demand,
            )
            reorder_point = calculate_reorder_point(lead_time_demand, safety_stock)

            # 4. Inventory Position
            inventory_position = calculate_inventory_position(
                stock_on_hand=stock_on_hand,
                incoming_stock=incoming_stock,
                committed_stock=committed_stock,
            )

            # 5. Target stock level: covers lead time demand + review cycle (7 days) + safety stock
            target_stock = lead_time_demand + (avg_daily_demand * 7) + safety_stock
            recommended_order_qty = calculate_recommended_order_quantity(
                inventory_position=inventory_position,
                reorder_point=reorder_point,
                target_stock_level=target_stock,
                min_order_qty=min_order_qty,
                order_multiple=order_multiple,
            )

            # 6. Classification & Alert
            status, alert, reason = classify_inventory_status(
                stock_on_hand=stock_on_hand,
                inventory_position=inventory_position,
                reorder_point=reorder_point,
                safety_stock=safety_stock,
                average_daily_demand=avg_daily_demand,
                lead_time_days=lead_time_days,
                overstock_threshold_days=self.overstock_threshold_days,
            )

            recommendations.append({
                "store_id": store_id,
                "item_id": item_id,
                "recommendation_date": today_str,
                "current_stock": stock_on_hand,
                "incoming_stock": incoming_stock,
                "committed_stock": committed_stock,
                "inventory_position": inventory_position,
                "lead_time_demand": round(lead_time_demand, 2),
                "safety_stock": round(safety_stock, 2),
                "reorder_point": round(reorder_point, 2),
                "recommended_order_qty": recommended_order_qty,
                "classification": status.value,
                "alert_triggered": alert,
                "policy_notes": reason,
            })

        return recommendations
