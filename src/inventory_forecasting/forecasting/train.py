"""Time-series Model Training and Validation Pipeline.

Trains LightGBM Regressor and Baselines using chronological time-based splitting.
Compares models strictly out-of-sample and registers the champion model.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import lightgbm as lgb
import numpy as np
import pandas as pd
from inventory_forecasting.config import settings
from inventory_forecasting.forecasting.baselines import MovingAverageBaseline, SeasonalNaiveBaseline
from inventory_forecasting.forecasting.evaluate import calculate_metrics
from inventory_forecasting.forecasting.model_registry import ModelRegistry


class ForecastTrainer:
    def __init__(
        self,
        gold_file: Optional[Path] = None,
        val_days: int = 28,
        test_days: int = 28,
    ):
        self.gold_file = gold_file or (settings.gold_dir / "gold_demand_features.parquet")
        self.val_days = val_days
        self.test_days = test_days
        self.registry = ModelRegistry()

    def load_data(self) -> pd.DataFrame:
        if not self.gold_file.exists():
            raise FileNotFoundError(f"Gold feature dataset not found at {self.gold_file}")
        df = pd.read_parquet(self.gold_file)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values(["store_id", "item_id", "date"])

    def create_splits(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Performs strict temporal splitting: Train -> Validation -> Test."""
        max_date = df["date"].max()
        test_start = max_date - pd.Timedelta(days=self.test_days - 1)
        val_start = test_start - pd.Timedelta(days=self.val_days)

        train = df[df["date"] < val_start].copy()
        val = df[(df["date"] >= val_start) & (df["date"] < test_start)].copy()
        test = df[df["date"] >= test_start].copy()

        return train, val, test

    def train_and_evaluate(self) -> Dict[str, any]:
        """Trains Baselines and LightGBM, evaluates out-of-sample, and selects champion."""
        df = self.load_data()
        train_df, val_df, test_df = self.create_splits(df)

        feature_cols = [
            "sell_price",
            "has_event",
            "day_of_week",
            "day_of_month",
            "month",
            "is_weekend",
            "lag_1",
            "lag_7",
            "lag_14",
            "lag_28",
            "rolling_mean_7",
            "rolling_std_7",
            "rolling_mean_28",
            "rolling_std_28",
            "trend_ratio_7_28",
        ]
        feature_cols = [c for c in feature_cols if c in df.columns]

        # 1. Baseline Evaluation on Validation Split
        s_naive = SeasonalNaiveBaseline(season_length=7).fit(train_df)
        ma_baseline = MovingAverageBaseline(window=7).fit(train_df)

        val_records = []
        for (store, item), group in val_df.groupby(["store_id", "item_id"]):
            h = len(group)
            sn_preds = s_naive.predict((store, item), horizon=h)
            ma_preds = ma_baseline.predict((store, item), horizon=h)
            val_records.append({
                "actual": group["units_sold"].values,
                "s_naive": sn_preds,
                "ma": ma_preds,
            })

        actuals = np.concatenate([r["actual"] for r in val_records])
        sn_preds = np.concatenate([r["s_naive"] for r in val_records])
        ma_preds = np.concatenate([r["ma"] for r in val_records])

        sn_metrics = calculate_metrics(actuals, sn_preds)
        ma_metrics = calculate_metrics(actuals, ma_preds)

        # 2. Train LightGBM Regressor
        # Drop rows where lag features are null due to history warming
        train_clean = train_df.dropna(subset=feature_cols).copy()
        val_clean = val_df.dropna(subset=feature_cols).copy()
        test_clean = test_df.dropna(subset=feature_cols).copy()

        X_train = train_clean[feature_cols]
        y_train = train_clean["units_sold"]
        X_val = val_clean[feature_cols]
        y_val = val_clean["units_sold"]

        lgb_model = lgb.LGBMRegressor(
            n_estimators=150,
            learning_rate=0.05,
            num_leaves=31,
            random_state=settings.random_seed,
            min_child_samples=10,
            verbosity=-1,
        )
        lgb_model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=15, verbose=False)],
        )

        lgb_val_preds = np.maximum(0.0, lgb_model.predict(X_val))
        lgb_val_metrics = calculate_metrics(y_val.values, lgb_val_preds)

        # 3. Model Selection: compare on WAPE / RMSE
        evaluations = {
            "seasonal_naive": sn_metrics,
            "moving_average": ma_metrics,
            "lightgbm": lgb_val_metrics,
        }

        champion_name = "lightgbm"
        if lgb_val_metrics["wape"] > sn_metrics["wape"]:
            champion_name = "seasonal_naive"

        # 4. Final Evaluation on unseen Test split for the champion
        X_test = test_clean[feature_cols]
        y_test = test_clean["units_sold"]
        test_preds = np.maximum(0.0, lgb_model.predict(X_test))
        test_metrics = calculate_metrics(y_test.values, test_preds)

        # 5. Persist Champion Artifact
        metadata = {
            "champion_model": champion_name,
            "validation_metrics": evaluations,
            "test_metrics": test_metrics,
            "features": feature_cols,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_samples": len(train_clean),
            "val_samples": len(val_clean),
            "test_samples": len(test_clean),
        }
        self.registry.save_model("lightgbm", lgb_model, metadata, is_champion=(champion_name == "lightgbm"))

        return {
            "evaluations": evaluations,
            "test_metrics": test_metrics,
            "champion": champion_name,
            "features": feature_cols,
        }
