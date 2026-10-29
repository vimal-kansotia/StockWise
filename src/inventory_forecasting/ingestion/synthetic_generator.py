"""Synthetic Data Generator.

Generates realistic retail sales, calendar, and price datasets matching the M5 Walmart
schema with reproducible seasonality, trends, promotions, and lead times.
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from inventory_forecasting.config import settings


def generate_synthetic_m5_data(
    num_stores: int = 3,
    num_products: int = 15,
    start_date: str = "2023-01-01",
    end_date: str = "2024-03-31",
    seed: int = 42,
    output_dir: Optional[Path] = None,
) -> Dict[str, pd.DataFrame]:
    """Generates synthetic datasets adhering strictly to the M5 format.
    
    Produces:
    1. sales_train_validation: id, item_id, dept_id, cat_id, store_id, state_id, d_1, d_2, ...
    2. calendar: date, wm_yr_wk, weekday, wday, month, year, d, event_name_1, event_type_1, snap_CA, snap_TX, snap_WI
    3. sell_prices: store_id, item_id, wm_yr_wk, sell_price
    4. inventory_snapshots: store_id, item_id, date, stock_on_hand, incoming_stock, lead_time_days
    """
    np.random.seed(seed)
    out_path = output_dir or settings.synthetic_dir
    out_path.mkdir(parents=True, exist_ok=True)

    date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    n_days = len(date_range)
    day_cols = [f"d_{i+1}" for i in range(n_days)]

    # Categorical hierarchies
    states = ["CA", "TX", "WI"][:max(1, min(3, num_stores))]
    stores = [f"{states[i % len(states)]}_{i+1}" for i in range(num_stores)]
    categories = ["FOODS", "HOBBIES", "HOUSEHOLD"]
    departments = {
        "FOODS": ["FOODS_1", "FOODS_2", "FOODS_3"],
        "HOBBIES": ["HOBBIES_1", "HOBBIES_2"],
        "HOUSEHOLD": ["HOUSEHOLD_1", "HOUSEHOLD_2"],
    }

    products = []
    for i in range(num_products):
        cat = categories[i % len(categories)]
        dept = departments[cat][i % len(departments[cat])]
        item_id = f"{dept}_{i+1:03d}"
        products.append({"item_id": item_id, "dept_id": dept, "cat_id": cat})

    # 1. Calendar DataFrame
    calendar_rows = []
    for idx, dt in enumerate(date_range):
        d_name = f"d_{idx + 1}"
        wm_yr_wk = int(f"{dt.year % 100}{dt.isocalendar().week:02d}")
        
        # Add intermittent events / promotions
        event_name = ""
        event_type = ""
        if dt.day == 1:
            event_name = "NewMonthPromotion"
            event_type = "Promotional"
        elif dt.month == 11 and dt.day == 25:
            event_name = "BlackFriday"
            event_type = "National"
        elif dt.month == 12 and dt.day == 25:
            event_name = "Christmas"
            event_type = "Cultural"

        calendar_rows.append({
            "date": dt.strftime("%Y-%m-%d"),
            "wm_yr_wk": wm_yr_wk,
            "weekday": dt.strftime("%A"),
            "wday": dt.isoweekday(),
            "month": dt.month,
            "year": dt.year,
            "d": d_name,
            "event_name_1": event_name,
            "event_type_1": event_type,
            "snap_CA": int(dt.day in [1, 2, 3, 4, 5]),
            "snap_TX": int(dt.day in [6, 7, 8, 9, 10]),
            "snap_WI": int(dt.day in [1, 3, 5, 7, 9]),
        })
    calendar_df = pd.DataFrame(calendar_rows)

    # 2. Sales Train Validation DataFrame
    sales_rows = []
    t = np.arange(n_days)
    # Seasonality components: annual + weekly
    annual_cycle = np.sin(2 * np.pi * t / 365.25)
    weekly_cycle = np.sin(2 * np.pi * t / 7)

    for p in products:
        base_demand = np.random.uniform(5, 30)
        trend = np.linspace(0, np.random.uniform(-3, 8), n_days)
        
        for store in stores:
            state = store.split("_")[0]
            series_id = f"{p['item_id']}_{store}_validation"
            
            # Combine components with Poisson / Poisson-mixture noise
            lam = np.maximum(
                0.2,
                base_demand + (base_demand * 0.3 * weekly_cycle) + (base_demand * 0.2 * annual_cycle) + trend
            )
            # Weekend boost
            is_weekend = calendar_df["wday"].isin([6, 7]).values
            lam[is_weekend] *= 1.35

            # Event boost
            has_event = (calendar_df["event_name_1"] != "").values
            lam[has_event] *= 1.5

            sales = np.random.poisson(lam)
            # Add zero-demand sparsity (intermittent retail demand)
            zero_mask = np.random.rand(n_days) < np.random.uniform(0.05, 0.25)
            sales[zero_mask] = 0

            row = {
                "id": series_id,
                "item_id": p["item_id"],
                "dept_id": p["dept_id"],
                "cat_id": p["cat_id"],
                "store_id": store,
                "state_id": state,
            }
            for d_col, s_val in zip(day_cols, sales):
                row[d_col] = int(s_val)
            sales_rows.append(row)

    sales_df = pd.DataFrame(sales_rows)

    # 3. Sell Prices DataFrame
    price_rows = []
    unique_weeks = calendar_df[["wm_yr_wk"]].drop_duplicates()["wm_yr_wk"].tolist()
    for p in products:
        base_price = round(np.random.uniform(2.5, 45.0), 2)
        for store in stores:
            for wm_yr_wk in unique_weeks:
                # Occasional slight discount
                discount = 0.9 if np.random.rand() < 0.1 else 1.0
                price_rows.append({
                    "store_id": store,
                    "item_id": p["item_id"],
                    "wm_yr_wk": wm_yr_wk,
                    "sell_price": round(base_price * discount, 2),
                })
    sell_prices_df = pd.DataFrame(price_rows)

    # 4. Inventory Snapshots DataFrame (for inventory recommendations)
    inventory_rows = []
    latest_date = calendar_df["date"].max()
    for p in products:
        for store in stores:
            stock = int(np.random.randint(10, 150))
            incoming = int(np.random.choice([0, 0, 20, 50]))
            lead_time = int(np.random.choice([3, 5, 7, 10, 14]))
            unit_cost = round(sell_prices_df[sell_prices_df["item_id"] == p["item_id"]]["sell_price"].mean() * 0.6, 2)
            inventory_rows.append({
                "store_id": store,
                "item_id": p["item_id"],
                "snapshot_date": latest_date,
                "stock_on_hand": stock,
                "incoming_stock": incoming,
                "committed_stock": int(np.random.randint(0, 10)),
                "unit_cost": unit_cost,
                "supplier_lead_time_days": lead_time,
                "min_order_qty": 10,
                "order_multiple": 5,
            })
    inventory_df = pd.DataFrame(inventory_rows)

    # Save CSVs to synthetic directory
    calendar_df.to_csv(out_path / "calendar.csv", index=False)
    sales_df.to_csv(out_path / "sales_train_validation.csv", index=False)
    sell_prices_df.to_csv(out_path / "sell_prices.csv", index=False)
    inventory_df.to_csv(out_path / "inventory_snapshots.csv", index=False)

    return {
        "calendar": calendar_df,
        "sales": sales_df,
        "sell_prices": sell_prices_df,
        "inventory": inventory_df,
    }


if __name__ == "__main__":
    generate_synthetic_m5_data()
    print("Synthetic M5 data generated successfully.")
