"""Baseline forecasting models.

Implements standard benchmark models:
1. SeasonalNaiveBaseline: Repeats sales from the same day of the week in prior cycle (e.g. 7 days ago).
2. MovingAverageBaseline: Simple moving average over recent past window.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class SeasonalNaiveBaseline:
    """Predicts future value using the value from exactly one seasonal cycle ago."""

    def __init__(self, season_length: int = 7):
        self.season_length = season_length
        self.history_: Dict[tuple, List[float]] = {}

    def fit(self, df: pd.DataFrame, group_cols: List[str] = ["store_id", "item_id"], target_col: str = "units_sold"):
        """Fits baseline by storing the most recent season history per series."""
        self.history_ = {}
        for keys, group in df.groupby(group_cols):
            recent_vals = group[target_col].tail(self.season_length).tolist()
            # If group has fewer than season_length items, pad with mean
            if len(recent_vals) < self.season_length:
                mean_val = np.mean(recent_vals) if recent_vals else 0.0
                recent_vals = [mean_val] * (self.season_length - len(recent_vals)) + recent_vals
            self.history_[keys] = recent_vals
        return self

    def predict(self, series_keys: tuple, horizon: int) -> np.ndarray:
        """Projects seasonal pattern cyclically over the horizon."""
        hist = self.history_.get(series_keys, [0.0] * self.season_length)
        preds = []
        for step in range(horizon):
            idx = step % self.season_length
            preds.append(hist[idx])
        return np.maximum(0.0, np.array(preds))


class MovingAverageBaseline:
    """Predicts future demand using the mean of the most recent window."""

    def __init__(self, window: int = 7):
        self.window = window
        self.averages_: Dict[tuple, float] = {}

    def fit(self, df: pd.DataFrame, group_cols: List[str] = ["store_id", "item_id"], target_col: str = "units_sold"):
        self.averages_ = {}
        for keys, group in df.groupby(group_cols):
            recent = group[target_col].tail(self.window)
            self.averages_[keys] = float(recent.mean()) if len(recent) > 0 else 0.0
        return self

    def predict(self, series_keys: tuple, horizon: int) -> np.ndarray:
        val = self.averages_.get(series_keys, 0.0)
        return np.full(shape=(horizon,), fill_value=max(0.0, val))
