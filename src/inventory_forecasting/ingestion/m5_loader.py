"""M5 Dataset Loader and Ingestion to Bronze Lake layer.

Handles reading original or synthetic M5 retail datasets, verifying schemas,
recording ingestion metadata, and persisting unmutated records into Bronze Parquet.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
from inventory_forecasting.config import settings
from inventory_forecasting.ingestion.validation import (
    DataValidationError,
    validate_calendar_schema,
    validate_m5_raw_files,
    validate_sales_schema,
    validate_sell_prices_schema,
)


class M5Loader:
    def __init__(self, source_dir: Optional[Path] = None, bronze_dir: Optional[Path] = None):
        self.source_dir = source_dir or settings.raw_dir
        self.bronze_dir = bronze_dir or settings.bronze_dir
        self.bronze_dir.mkdir(parents=True, exist_ok=True)

    def load_and_ingest_bronze(self, is_synthetic: bool = False) -> Dict[str, Path]:
        """Ingests raw CSV files into Bronze Parquet layer with metadata.
        
        Args:
            is_synthetic: Flag indicating whether source is synthetic or real Kaggle M5.
            
        Returns:
            Dict mapping dataset name to stored Parquet filepath.
        """
        valid, errors = validate_m5_raw_files(self.source_dir)
        if not valid:
            raise DataValidationError(
                f"Source directory '{self.source_dir}' failed validation:\n" + "\n".join(errors)
            )

        ingestion_ts = datetime.now(timezone.utc).isoformat()
        bronze_outputs = {}

        # 1. Sales
        sales_path = self.source_dir / "sales_train_validation.csv"
        sales_df = pd.read_csv(sales_path)
        s_valid, s_errs = validate_sales_schema(sales_df)
        if not s_valid:
            raise DataValidationError(f"Sales schema error:\n" + "\n".join(s_errs))
        
        sales_df["_ingested_at"] = ingestion_ts
        sales_df["_is_synthetic"] = is_synthetic
        sales_out = self.bronze_dir / "bronze_sales.parquet"
        sales_df.to_parquet(sales_out, index=False)
        bronze_outputs["sales"] = sales_out

        # 2. Calendar
        cal_path = self.source_dir / "calendar.csv"
        cal_df = pd.read_csv(cal_path)
        c_valid, c_errs = validate_calendar_schema(cal_df)
        if not c_valid:
            raise DataValidationError(f"Calendar schema error:\n" + "\n".join(c_errs))
            
        cal_df["_ingested_at"] = ingestion_ts
        cal_df["_is_synthetic"] = is_synthetic
        cal_out = self.bronze_dir / "bronze_calendar.parquet"
        cal_df.to_parquet(cal_out, index=False)
        bronze_outputs["calendar"] = cal_out

        # 3. Prices
        price_path = self.source_dir / "sell_prices.csv"
        price_df = pd.read_csv(price_path)
        p_valid, p_errs = validate_sell_prices_schema(price_df)
        if not p_valid:
            raise DataValidationError(f"Sell prices schema error:\n" + "\n".join(p_errs))
            
        price_df["_ingested_at"] = ingestion_ts
        price_df["_is_synthetic"] = is_synthetic
        price_out = self.bronze_dir / "bronze_sell_prices.parquet"
        price_df.to_parquet(price_out, index=False)
        bronze_outputs["sell_prices"] = price_out

        # 4. Optional Inventory Snapshots (if present)
        inv_path = self.source_dir / "inventory_snapshots.csv"
        if inv_path.exists():
            inv_df = pd.read_csv(inv_path)
            inv_df["_ingested_at"] = ingestion_ts
            inv_df["_is_synthetic"] = is_synthetic
            inv_out = self.bronze_dir / "bronze_inventory.parquet"
            inv_df.to_parquet(inv_out, index=False)
            bronze_outputs["inventory"] = inv_out

        return bronze_outputs
