"""Evaluation metrics for time series and retail demand forecasting.

Provides implementations of:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- WAPE (Weighted Absolute Percentage Error) - highly recommended for retail over MAPE because of zero sales
- Forecast Bias (Normalized tracking signal)
"""

from typing import Dict
import numpy as np


def mean_absolute_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Computes MAE: mean(|y - y_hat|)."""
    return float(np.mean(np.abs(y_true - y_pred)))


def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Computes RMSE: sqrt(mean((y - y_hat)^2))."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def weighted_absolute_percentage_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Computes WAPE: sum(|y - y_hat|) / sum(y).
    
    Robust against zero demand days where traditional MAPE divides by zero.
    """
    total_actual = np.sum(np.abs(y_true))
    if total_actual == 0:
        return 0.0 if np.sum(np.abs(y_pred)) == 0 else 1.0
    return float(np.sum(np.abs(y_true - y_pred)) / total_actual)


def forecast_bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Computes Normalized Forecast Bias: sum(y_hat - y) / sum(y).
    
    Positive bias indicates over-forecasting, negative indicates under-forecasting.
    """
    total_actual = np.sum(y_true)
    if total_actual == 0:
        return 0.0
    return float(np.sum(y_pred - y_true) / total_actual)


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculates all standard demand forecasting metrics."""
    y_true = np.asarray(y_true, dtype=float)
    # Clip negative predictions to zero (sales cannot be negative)
    y_pred = np.maximum(0.0, np.asarray(y_pred, dtype=float))

    return {
        "mae": round(mean_absolute_error(y_true, y_pred), 4),
        "rmse": round(root_mean_squared_error(y_true, y_pred), 4),
        "wape": round(weighted_absolute_percentage_error(y_true, y_pred), 4),
        "bias": round(forecast_bias(y_true, y_pred), 4),
    }
