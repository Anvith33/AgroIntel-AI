"""
feature_engineering.py — Shared feature engineering utilities.
Used by both train.py and inference.py to ensure consistency.
"""

import numpy as np
import pandas as pd
from datetime import date

# ── Black Swan events registry (shared with train.py) ────────────────────────
BLACK_SWAN_EVENTS = [
    {"start": "2020-03-15", "end": "2020-06-30", "factor": 1.30, "label": "COVID-19 Lockdown Spike"},
    {"start": "2020-07-01", "end": "2020-12-31", "factor": 1.18, "label": "COVID-19 Recovery Inflation"},
    {"start": "2022-02-24", "end": "2022-06-30", "factor": 1.42, "label": "Russia-Ukraine War Shock"},
    {"start": "2022-07-01", "end": "2022-12-31", "factor": 1.25, "label": "War Supply Disruption"},
    {"start": "2023-01-01", "end": "2023-09-30", "factor": 1.15, "label": "Post-War Inflation"},
    {"start": "2019-06-01", "end": "2019-09-30", "factor": 1.12, "label": "2019 Drought"},
]

FEATURE_COLS = [
    "lag_1", "lag_7", "lag_14", "lag_30",
    "rolling_7", "rolling_30",
    "day_of_year", "month", "day_of_week", "year", "black_swan",
]


def is_black_swan_period(target_date: date) -> bool:
    """Check if a given date falls within any known black swan event."""
    ts = pd.Timestamp(target_date)
    for event in BLACK_SWAN_EVENTS:
        if pd.Timestamp(event["start"]) <= ts <= pd.Timestamp(event["end"]):
            return True
    return False


def get_active_black_swan(target_date: date) -> dict | None:
    """Return the active black swan event info for a date, or None."""
    ts = pd.Timestamp(target_date)
    for event in BLACK_SWAN_EVENTS:
        if pd.Timestamp(event["start"]) <= ts <= pd.Timestamp(event["end"]):
            return event
    return None


def build_inference_features(price_history: list[float], target_date: date) -> np.ndarray:
    """
    Given a list of recent prices (at least 30 values, most recent last)
    and a target prediction date, build the feature vector for XGBoost/MLP.

    Args:
        price_history: list of recent daily prices, oldest first
        target_date: the date we are predicting FOR

    Returns:
        numpy array of shape (1, len(FEATURE_COLS))
    """
    if len(price_history) < 30:
        raise ValueError("Need at least 30 days of price history for feature extraction.")

    prices = np.array(price_history)
    lag_1 = prices[-1]
    lag_7 = prices[-7]
    lag_14 = prices[-14]
    lag_30 = prices[-30]
    rolling_7 = float(np.mean(prices[-7:]))
    rolling_30 = float(np.mean(prices[-30:]))
    day_of_year = pd.Timestamp(target_date).dayofyear
    month = pd.Timestamp(target_date).month
    day_of_week = pd.Timestamp(target_date).dayofweek
    year = pd.Timestamp(target_date).year
    black_swan = 1 if is_black_swan_period(target_date) else 0

    features = np.array([[
        lag_1, lag_7, lag_14, lag_30,
        rolling_7, rolling_30,
        day_of_year, month, day_of_week, year, black_swan,
    ]])
    return features


def add_features_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all ML feature columns to a DataFrame that has 'ds' (datetime) and 'y' (price).
    Used during training.
    """
    df = df.copy().sort_values("ds").reset_index(drop=True)
    df["lag_1"] = df["y"].shift(1)
    df["lag_7"] = df["y"].shift(7)
    df["lag_14"] = df["y"].shift(14)
    df["lag_30"] = df["y"].shift(30)
    df["rolling_7"] = df["y"].shift(1).rolling(7).mean()
    df["rolling_30"] = df["y"].shift(1).rolling(30).mean()
    df["day_of_year"] = df["ds"].dt.dayofyear
    df["month"] = df["ds"].dt.month
    df["day_of_week"] = df["ds"].dt.dayofweek
    df["year"] = df["ds"].dt.year
    df["black_swan"] = 0
    for event in BLACK_SWAN_EVENTS:
        mask = (df["ds"] >= event["start"]) & (df["ds"] <= event["end"])
        df.loc[mask, "black_swan"] = 1
    df = df.dropna().reset_index(drop=True)
    return df
