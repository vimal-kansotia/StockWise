"""Local Pandas-based Medallion Processing Pipeline.

Executes Bronze -> Silver -> Gold data transformations:
- Bronze: unpivoting wide M5 sales (d_1, d_2, ...) into normalized tall time series.
- Silver: joining calendar and prices, handling legitimate zero-sales days, quality checks.
- Gold: lag and rolling feature engineering, temporal validation, ready for ML training.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
from inventory_forecasting.config import settings
from inventory_forecasting.processing.feature_engineering import generate_demand_features


class PandasPipeline:
    def __init__(
        self,
        bronze_dir: Optional[Path] = None,
        silver_dir: Optional[Path] = None,
        gold_dir: Optional[Path] = None,
    ):
        self.bronze_dir = bronze_dir or settings.bronze_dir
        self.silver_dir = silver_dir or settings.silver_dir
        self.gold_dir = gold_dir or settings.gold_dir

        self.silver_dir.mkdir(parents=True, exist_ok=True)
        self.gold_dir.mkdir(parents=True, exist_ok=True)

    def run_bronze_to_silver(self) -> Tuple[Path, Dict[str, any]]:
        """Cleans and joins Bronze sales, calendar, and prices into Silver layer."""
        sales_file = self.bronze_dir / "bronze_sales.parquet"
        cal_file = self.bronze_dir / "bronze_calendar.parquet"
        price_file = self.bronze_dir / "bronze_sell_prices.parquet"

        if not (sales_file.exists() and cal_file.exists() and price_file.exists()):
            raise FileNotFoundError(f"Missing required Bronze files in {self.bronze_dir}")

        sales_df = pd.read_parquet(sales_file)
        cal_df = pd.read_parquet(cal_file)
        price_df = pd.read_parquet(price_file)

        # 1. Identify metadata columns and day columns
        id_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
        meta_cols = [c for c in id_cols if c in sales_df.columns]
        day_cols = [c for c in sales_df.columns if c.startswith("d_")]

        # 2. Melt wide format to long format
        long_sales = pd.melt(
            sales_df,
            id_vars=meta_cols,
            value_vars=day_cols,
            var_name="d",
            value_name="units_sold"
        )
        long_sales["units_sold"] = pd.to_numeric(long_sales["units_sold"], errors="coerce").fillna(0).astype(int)

        # 3. Join with Calendar (date, wm_yr_wk, event indicators)
        cal_subset = cal_df[["d", "date", "wm_yr_wk", "wday", "month", "year", "event_name_1"]].copy()
        cal_subset["has_event"] = (cal_subset["event_name_1"].fillna("") != "").astype(int)

        merged = pd.merge(long_sales, cal_subset, on="d", how="inner")
        merged["date"] = pd.to_datetime(merged["date"])

        # 4. Join with Sell Prices (on store_id, item_id, wm_yr_wk)
        price_subset = price_df[["store_id", "item_id", "wm_yr_wk", "sell_price"]].drop_duplicates()
        merged = pd.merge(merged, price_subset, on=["store_id", "item_id", "wm_yr_wk"], how="left")

        # Fill missing prices with store-item mean or overall mean if store has no record
        if merged["sell_price"].isna().any():
            mean_item_price = merged.groupby("item_id")["sell_price"].transform("mean")
            merged["sell_price"] = merged["sell_price"].fillna(mean_item_price).fillna(5.0)

        # Quality metrics
        quality_metrics = {
            "total_records": len(merged),
            "unique_items": merged["item_id"].nunique(),
            "unique_stores": merged["store_id"].nunique(),
            "min_date": str(merged["date"].min().date()),
            "max_date": str(merged["date"].max().date()),
            "zero_sales_fraction": float((merged["units_sold"] == 0).mean()),
            "mean_units_sold": float(merged["units_sold"].mean()),
        }

        # Tag ingestion metadata
        merged["_silver_processed_at"] = datetime.now(timezone.utc).isoformat()

        silver_out = self.silver_dir / "silver_sales_daily.parquet"
        merged.to_parquet(silver_out, index=False)
        return silver_out, quality_metrics

    def run_silver_to_gold(self) -> Tuple[Path, Dict[str, any]]:
        """Generates ML features and persists Gold analytics table."""
        silver_file = self.silver_dir / "silver_sales_daily.parquet"
        if not silver_file.exists():
            raise FileNotFoundError(f"Silver table not found at {silver_file}")

        df = pd.read_parquet(silver_file)
        
        # Feature engineering
        gold_df = generate_demand_features(
            df=df,
            group_cols=["store_id", "item_id"],
            target_col="units_sold",
            date_col="date",
            lags=[1, 7, 14, 28],
            rolling_windows=[7, 28]
        )

        gold_df["_gold_processed_at"] = datetime.now(timezone.utc).isoformat()
        gold_out = self.gold_dir / "gold_demand_features.parquet"
        gold_df.to_parquet(gold_out, index=False)

        metrics = {
            "gold_records": len(gold_df),
            "num_features": len(gold_df.columns),
            "feature_columns": list(gold_df.columns),
        }
        return gold_out, metrics
