"""M5 dataset validation module."""

from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd


class DataValidationError(Exception):
    """Raised when source or processed data fails validation constraints."""
    pass


def validate_m5_raw_files(data_dir: Path) -> Tuple[bool, List[str]]:
    """Checks for required M5 files and validates existence and basic size."""
    errors = []
    required_files = [
        "sales_train_validation.csv",
        "calendar.csv",
        "sell_prices.csv",
    ]
    for rf in required_files:
        fpath = data_dir / rf
        if not fpath.exists():
            errors.append(f"Missing required M5 file: {rf} at {data_dir}")
        elif fpath.stat().st_size == 0:
            errors.append(f"File {rf} is empty (0 bytes).")
            
    return (len(errors) == 0, errors)


def validate_sales_schema(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Validates M5 wide sales format columns and integrity."""
    errors = []
    required_meta = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    for col in required_meta:
        if col not in df.columns:
            errors.append(f"Missing required identifier column: {col}")

    # Check for d_* columns
    d_cols = [c for c in df.columns if c.startswith("d_")]
    if not d_cols:
        errors.append("No day sales columns ('d_1', 'd_2', ...) found in sales data.")

    # Check for duplicate series IDs
    if "id" in df.columns and df["id"].duplicated().any():
        n_dups = df["id"].duplicated().sum()
        errors.append(f"Found {n_dups} duplicate 'id' series rows in sales data.")

    return (len(errors) == 0, errors)


def validate_calendar_schema(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Validates calendar schema and continuity."""
    errors = []
    required = ["date", "wm_yr_wk", "weekday", "wday", "month", "year", "d"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing required calendar column: {col}")

    if "date" in df.columns:
        # Check date parsing
        try:
            parsed = pd.to_datetime(df["date"], errors="coerce")
            if parsed.isna().any():
                errors.append("Calendar contains invalid unparseable date values.")
        except Exception as e:
            errors.append(f"Calendar date parsing error: {str(e)}")

    return (len(errors) == 0, errors)


def validate_sell_prices_schema(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Validates sell prices table."""
    errors = []
    required = ["store_id", "item_id", "wm_yr_wk", "sell_price"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing required sell_prices column: {col}")

    if "sell_price" in df.columns:
        if (df["sell_price"] < 0).any():
            errors.append("Found negative sell prices.")
        if df["sell_price"].isna().any():
            errors.append("Found null sell prices.")

    return (len(errors) == 0, errors)
