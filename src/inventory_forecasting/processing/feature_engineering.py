"""Feature engineering for product and store level daily demand forecasting.

Constructs lags, rolling statistics, calendar indicators, and ensures strict
time-series temporal isolation to avoid future data leakage.
"""

from typing import List, Optional
import numpy as np
import pandas as pd


def compute_time_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Extracts calendar time components from date."""
    df = df.copy()
    if not np.issubdtype(df[date_col].dtype, np.datetime64):
        df[date_col] = pd.to_datetime(df[date_col])

    df["day_of_week"] = df[date_col].dt.dayofweek
    df["day_of_month"] = df[date_col].dt.day
    df["month"] = df[date_col].dt.month
    df["year"] = df[date_col].dt.year
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    return df


def generate_demand_features(
    df: pd.DataFrame,
    group_cols: Optional[List[str]] = None,
    target_col: str = "units_sold",
    date_col: str = "date",
    lags: Optional[List[int]] = None,
    rolling_windows: Optional[List[int]] = None,
) -> pd.DataFrame:
    """Generates strictly non-leaking lag and rolling features.
    
    All rolling features are calculated using shift(1) or shifted inputs so that
    information at time t never includes observations from time t or any future date.
    
    Args:
        df: Input dataframe containing at least group_cols, date_col, and target_col.
        group_cols: Series keys, default ['store_id', 'item_id'].
        target_col: Quantity sold column name.
        date_col: Date column name.
        lags: List of day lags, e.g., [1, 7, 14, 28].
        rolling_windows: Rolling aggregation windows, e.g., [7, 28].
        
    Returns:
        DataFrame with feature-engineered columns sorted chronologically.
    """
    if group_cols is None:
        group_cols = ["store_id", "item_id"]
    if lags is None:
        lags = [1, 7, 14, 28]
    if rolling_windows is None:
        rolling_windows = [7, 28]

    df = df.sort_values(by=group_cols + [date_col]).copy()
    if not np.issubdtype(df[date_col].dtype, np.datetime64):
        df[date_col] = pd.to_datetime(df[date_col])

    # Calendar features
    df = compute_time_features(df, date_col=date_col)

    grouped = df.groupby(group_cols)[target_col]

    # 1. Lags
    for lag in lags:
        df[f"lag_{lag}"] = grouped.shift(lag)

    # 2. Rolling features (using shift(1) to avoid leaking current day's target)
    for window in rolling_windows:
        shifted = df.groupby(group_cols)[target_col].shift(1)
        df[f"rolling_mean_{window}"] = (
            shifted.groupby([df[col] for col in group_cols])
            .transform(lambda s: s.rolling(window=window, min_periods=1).mean())
        )
        df[f"rolling_std_{window}"] = (
            shifted.groupby([df[col] for col in group_cols])
            .transform(lambda s: s.rolling(window=window, min_periods=2).std())
        ).fillna(0.0)

    # 3. Ratio feature: short-term trend (rolling 7 mean / rolling 28 mean)
    if "rolling_mean_7" in df.columns and "rolling_mean_28" in df.columns:
        df["trend_ratio_7_28"] = (
            (df["rolling_mean_7"] + 1e-4) / (df["rolling_mean_28"] + 1e-4)
        ).fillna(1.0)

    return df
