import pytest
import pandas as pd
import numpy as np
from inventory_forecasting.processing.feature_engineering import generate_demand_features


def test_feature_engineering_no_leakage():
    # Construct 10-day time series
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "store_id": ["S1"] * 10,
        "item_id": ["I1"] * 10,
        "date": dates,
        "units_sold": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    })

    feat_df = generate_demand_features(
        df,
        group_cols=["store_id", "item_id"],
        target_col="units_sold",
        date_col="date",
        lags=[1, 7],
        rolling_windows=[7],
    )

    # First row lag_1 must be NaN (no prior observation)
    assert pd.isna(feat_df.iloc[0]["lag_1"])

    # Second row lag_1 must equal first row target (10)
    assert feat_df.iloc[1]["lag_1"] == 10

    # Ensure rolling_mean_7 at row t does NOT include row t value
    # At row index 1 (date 2023-01-02), shifted series has only [10]
    assert feat_df.iloc[1]["rolling_mean_7"] == 10.0
