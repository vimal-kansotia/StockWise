"""Recursive Multi-step Demand Predictor for 7 and 28-day Horizons."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from inventory_forecasting.config import settings
from inventory_forecasting.forecasting.model_registry import ModelRegistry


class DemandPredictor:
    def __init__(self, gold_file: Optional[Path] = None):
        self.gold_file = gold_file or (settings.gold_dir / "gold_demand_features.parquet")
        self.registry = ModelRegistry()

    def generate_forecasts(self, horizon_days: int = 7) -> List[Dict]:
        """Generates future product-store demand forecasts.
        
        Uses recursive forward stepping:
        - For each step t + k in the horizon, advances the date and calendar indicators
        - Computes dynamic lag and rolling predictions using previously predicted outputs
        - Avoids any peeking into real future demand data
        """
        model = self.registry.load_model("champion_model")
        metadata = self.registry.load_metadata("champion_model")
        features = metadata.get("features", [
            "sell_price", "has_event", "day_of_week", "day_of_month", "month",
            "is_weekend", "lag_1", "lag_7", "lag_14", "lag_28",
            "rolling_mean_7", "rolling_std_7", "rolling_mean_28", "rolling_std_28", "trend_ratio_7_28"
        ])

        df = pd.read_parquet(self.gold_file)
        df["date"] = pd.to_datetime(df["date"])

        forecast_results = []
        last_date = df["date"].max()

        # Iterate over each store-item time series
        for (store_id, item_id), group in df.groupby(["store_id", "item_id"]):
            group = group.sort_values("date")
            history = list(group["units_sold"].values)
            last_price = float(group["sell_price"].iloc[-1])

            # Forward recursive simulation
            for h in range(1, horizon_days + 1):
                f_date = last_date + timedelta(days=h)
                dow = f_date.dayofweek
                dom = f_date.day
                month = f_date.month
                is_wknd = int(dow in [5, 6])
                has_event = int(dom in [1, 15])

                # Construct dynamic features based on current extended history
                l1 = history[-1] if len(history) >= 1 else 0.0
                l7 = history[-7] if len(history) >= 7 else l1
                l14 = history[-14] if len(history) >= 14 else l7
                l28 = history[-28] if len(history) >= 28 else l14

                r7_mean = float(np.mean(history[-7:])) if len(history) >= 7 else float(np.mean(history))
                r7_std = float(np.std(history[-7:])) if len(history) >= 7 else 0.0
                r28_mean = float(np.mean(history[-28:])) if len(history) >= 28 else float(np.mean(history))
                r28_std = float(np.std(history[-28:])) if len(history) >= 28 else 0.0
                trend_ratio = (r7_mean + 1e-4) / (r28_mean + 1e-4)

                row_dict = {
                    "sell_price": last_price,
                    "has_event": has_event,
                    "day_of_week": dow,
                    "day_of_month": dom,
                    "month": month,
                    "is_weekend": is_wknd,
                    "lag_1": l1,
                    "lag_7": l7,
                    "lag_14": l14,
                    "lag_28": l28,
                    "rolling_mean_7": r7_mean,
                    "rolling_std_7": r7_std,
                    "rolling_mean_28": r28_mean,
                    "rolling_std_28": r28_std,
                    "trend_ratio_7_28": trend_ratio,
                }

                input_features = pd.DataFrame([[row_dict.get(c, 0.0) for c in features]], columns=features)
                pred_val = float(np.maximum(0.0, model.predict(input_features)[0]))

                # Append prediction to history for next recursive steps
                history.append(pred_val)

                forecast_results.append({
                    "store_id": store_id,
                    "item_id": item_id,
                    "forecast_date": f_date.strftime("%Y-%m-%d"),
                    "predicted_demand": round(pred_val, 2),
                })

        return forecast_results
