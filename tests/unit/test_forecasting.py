import pytest
import numpy as np
import pandas as pd
from inventory_forecasting.forecasting.evaluate import (
    mean_absolute_error,
    root_mean_squared_error,
    weighted_absolute_percentage_error,
    forecast_bias,
    calculate_metrics,
)
from inventory_forecasting.forecasting.baselines import SeasonalNaiveBaseline, MovingAverageBaseline


def test_forecast_metrics_exact():
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 30.0])

    # MAE = (2 + 2 + 0) / 3 = 1.3333
    assert round(mean_absolute_error(y_true, y_pred), 3) == 1.333
    # WAPE = 4 / 60 = 0.0667
    assert round(weighted_absolute_percentage_error(y_true, y_pred), 3) == 0.067
    # Bias = (60 - 60) / 60 = 0.0
    assert forecast_bias(y_true, y_pred) == 0.0


def test_wape_zero_actuals():
    y_true = np.array([0.0, 0.0])
    y_pred = np.array([0.0, 0.0])
    assert weighted_absolute_percentage_error(y_true, y_pred) == 0.0


def test_seasonal_naive_baseline():
    df = pd.DataFrame({
        "store_id": ["S1"] * 7,
        "item_id": ["I1"] * 7,
        "units_sold": [10, 12, 14, 16, 18, 20, 22],
    })
    model = SeasonalNaiveBaseline(season_length=7).fit(df)
    preds = model.predict(("S1", "I1"), horizon=7)
    assert len(preds) == 7
    assert np.array_equal(preds, [10, 12, 14, 16, 18, 20, 22])


def test_moving_average_baseline():
    df = pd.DataFrame({
        "store_id": ["S1"] * 5,
        "item_id": ["I1"] * 5,
        "units_sold": [10, 20, 30, 40, 50],
    })
    model = MovingAverageBaseline(window=3).fit(df)
    preds = model.predict(("S1", "I1"), horizon=4)
    # Recent 3 average = (30 + 40 + 50) / 3 = 40.0
    assert np.all(preds == 40.0)
