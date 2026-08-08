"""
price_trainer.py — Multi-Crop, Multi-Model Price Training Pipeline for AgroIntel.

Trains models per crop:
  1. ARIMA(1,1,1) — Statistical baseline
  2. Prophet (yearly_seasonality=True) — Seasonality baseline
  3. LSTM (TensorFlow/Keras) — Deep Learning (skipped safely if TF binary segfaults or fails)
  4. XGBoost (Grid Search over max_depth, learning_rate, n_estimators) — Preferred Production Model

Validation Strategy:
  - Chronological 60-day validation set (last 60 days per crop)
  - Evaluated using MAE and RMSE (no MAPE)
  - Production model selection:
      best_baseline = min(ARIMA, Prophet, LSTM) by MAE
      if XGBoost.MAE < best_baseline.MAE -> production_model = XGBoost
      else -> production_model = best_baseline

Artifacts saved:
  - models/arima_{crop}.pkl
  - models/prophet_{crop}.pkl
  - models/lstm_{crop}.keras (if TensorFlow available)
  - models/xgboost_{crop}.pkl
  - models/metrics_{crop}.json
  - models/data_tail_{crop}.pkl
  - models/model_registry.json (updated)
"""

import json
import logging
import pickle
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.constants import PRICE_FEATURE_COLS, PRICE_PREDICTION_CROPS
from app.ml.feature_engineering import add_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = settings.MODELS_DIR
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ── Metrics Helper Functions ──────────────────────────────────────────────────

def compute_metrics(actual: np.ndarray, pred: np.ndarray) -> Dict[str, float]:
    """Compute MAE and RMSE for prediction array against actual array."""
    actual = np.array(actual, dtype=float)
    pred = np.array(pred, dtype=float)
    mae = float(np.mean(np.abs(actual - pred)))
    rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
    return {"mae": round(mae, 2), "rmse": round(rmse, 2)}


# ── Model Trainer: ARIMA ──────────────────────────────────────────────────────

def train_arima(train_df: pd.DataFrame, val_df: pd.DataFrame, crop: str) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Train ARIMA(1,1,1) model on training series and evaluate on validation set."""
    start_time = time.time()
    try:
        from statsmodels.tsa.arima.model import ARIMA

        logger.info(f"[{crop.upper()}] Training ARIMA(1,1,1)...")
        series = train_df["y"].values
        model = ARIMA(series, order=(1, 1, 1))
        fitted = model.fit()

        val_len = len(val_df)
        preds = fitted.forecast(steps=val_len)

        metrics = compute_metrics(val_df["y"].values, preds)
        elapsed = round(time.time() - start_time, 2)
        metrics["training_time_sec"] = elapsed
        logger.info(f"[{crop.upper()}] ARIMA trained in {elapsed}s — MAE: {metrics['mae']}, RMSE: {metrics['rmse']}")

        save_path = MODELS_DIR / f"arima_{crop}.pkl"
        with open(save_path, "wb") as f:
            pickle.dump(fitted, f)

        return fitted, metrics

    except Exception as e:
        logger.error(f"[{crop.upper()}] ARIMA training failed: {e}")
        return None, {"mae": 999999.0, "rmse": 999999.0, "error": str(e), "training_time_sec": 0.0}


# ── Model Trainer: Prophet ────────────────────────────────────────────────────

def train_prophet(train_df: pd.DataFrame, val_df: pd.DataFrame, crop: str) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Train Prophet model with yearly seasonality and evaluate on validation set."""
    start_time = time.time()
    try:
        from prophet import Prophet

        logger.info(f"[{crop.upper()}] Training Prophet...")
        p_train = train_df[["ds", "y"]].copy()

        model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
        logging.getLogger("prophet").setLevel(logging.ERROR)
        model.fit(p_train)

        future = val_df[["ds"]].copy()
        forecast = model.predict(future)
        preds = forecast["yhat"].values

        metrics = compute_metrics(val_df["y"].values, preds)
        elapsed = round(time.time() - start_time, 2)
        metrics["training_time_sec"] = elapsed
        logger.info(f"[{crop.upper()}] Prophet trained in {elapsed}s — MAE: {metrics['mae']}, RMSE: {metrics['rmse']}")

        save_path = MODELS_DIR / f"prophet_{crop}.pkl"
        with open(save_path, "wb") as f:
            pickle.dump(model, f)

        return model, metrics

    except Exception as e:
        logger.error(f"[{crop.upper()}] Prophet training failed: {e}")
        return None, {"mae": 999999.0, "rmse": 999999.0, "error": str(e), "training_time_sec": 0.0}


# ── Model Trainer: LSTM (TensorFlow/Keras) ────────────────────────────────────

def _check_tf_availability() -> bool:
    """Check if TensorFlow can be imported safely without process segfault."""
    try:
        cmd = [sys.executable, "-c", "import tensorflow as tf"]
        res = subprocess.run(cmd, capture_output=True, timeout=10)
        return res.returncode == 0
    except Exception:
        return False


def train_lstm(train_df: pd.DataFrame, val_df: pd.DataFrame, crop: str) -> Tuple[Optional[Any], Dict[str, Any]]:
    """
    Train LSTM model with Keras if TensorFlow is safely available.
    Architecture: Input -> LSTM(64) -> Dropout(0.2) -> LSTM(32) -> Dense(16) -> Dense(1)

    Skipped safely if TensorFlow is missing or causes binary segfault.
    """
    start_time = time.time()
    if not _check_tf_availability():
        logger.warning(f"[{crop.upper()}] TensorFlow unavailable or binary incompatible with Python runtime. Skipping LSTM cleanly.")
        return None, {
            "mae": 999999.0,
            "rmse": 999999.0,
            "skipped": True,
            "reason": "TensorFlow binary incompatible with Python runtime",
            "training_time_sec": 0.0,
        }

    try:
        from sklearn.preprocessing import StandardScaler
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout

        logger.info(f"[{crop.upper()}] Training LSTM (Keras)...")

        scaler = StandardScaler()
        X_train_raw = train_df[PRICE_FEATURE_COLS].values
        X_train_scaled = scaler.fit_transform(X_train_raw)
        y_train = train_df["y"].values

        seq_len = 30
        if len(X_train_scaled) <= seq_len:
            raise ValueError(f"Training set length ({len(X_train_scaled)}) smaller than seq_len={seq_len}")

        X_seq, y_seq = [], []
        for i in range(seq_len, len(X_train_scaled)):
            X_seq.append(X_train_scaled[i - seq_len : i])
            y_seq.append(y_train[i])

        X_seq, y_seq = np.array(X_seq), np.array(y_seq)

        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(seq_len, X_train_scaled.shape[1])),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dense(16, activation="relu"),
            Dense(1),
        ])

        model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        model.fit(X_seq, y_seq, epochs=15, batch_size=32, verbose=0)

        full_X = pd.concat([train_df.tail(seq_len), val_df], ignore_index=True)[PRICE_FEATURE_COLS].values
        full_X_scaled = scaler.transform(full_X)

        val_preds = []
        for i in range(len(val_df)):
            seq = full_X_scaled[i : i + seq_len].reshape(1, seq_len, X_train_scaled.shape[1])
            pred_val = float(model.predict(seq, verbose=0)[0, 0])
            val_preds.append(pred_val)

        metrics = compute_metrics(val_df["y"].values, val_preds)
        elapsed = round(time.time() - start_time, 2)
        metrics["training_time_sec"] = elapsed
        logger.info(f"[{crop.upper()}] LSTM trained in {elapsed}s — MAE: {metrics['mae']}, RMSE: {metrics['rmse']}")

        save_path = MODELS_DIR / f"lstm_{crop}.keras"
        model.save(save_path)

        scaler_path = MODELS_DIR / f"lstm_scaler_{crop}.pkl"
        with open(scaler_path, "wb") as f:
            pickle.dump(scaler, f)

        return model, metrics

    except Exception as e:
        logger.warning(f"[{crop.upper()}] LSTM failed: {e}")
        return None, {"mae": 999999.0, "rmse": 999999.0, "skipped": True, "error": str(e), "training_time_sec": 0.0}


# ── Model Trainer: XGBoost (Grid Search) ──────────────────────────────────────

def train_xgboost(train_df: pd.DataFrame, val_df: pd.DataFrame, crop: str) -> Tuple[Optional[Any], Dict[str, Any]]:
    """
    Train XGBoost Regressor with small grid search:
      max_depth: [3, 5, 7]
      learning_rate: [0.03, 0.05, 0.1]
      n_estimators: [100, 150, 200]
    """
    start_time = time.time()
    try:
        import xgboost as xgb

        logger.info(f"[{crop.upper()}] Training XGBoost with Grid Search...")
        X_train = train_df[PRICE_FEATURE_COLS].values
        y_train = train_df["y"].values

        X_val = val_df[PRICE_FEATURE_COLS].values
        y_val = val_df["y"].values

        param_grid = [
            {"max_depth": md, "learning_rate": lr, "n_estimators": ne}
            for md in [3, 5, 7]
            for lr in [0.03, 0.05, 0.1]
            for ne in [100, 150, 200]
        ]

        best_mae = float("inf")
        best_params = None
        best_model = None

        for params in param_grid:
            model = xgb.XGBRegressor(
                max_depth=params["max_depth"],
                learning_rate=params["learning_rate"],
                n_estimators=params["n_estimators"],
                random_state=42,
                n_jobs=1,
            )
            model.fit(X_train, y_train)
            preds = model.predict(X_val)
            mae = float(np.mean(np.abs(y_val - preds)))

            if mae < best_mae:
                best_mae = mae
                best_params = params
                best_model = model

        # Final evaluation of best model
        val_preds = best_model.predict(X_val)
        metrics = compute_metrics(y_val, val_preds)
        metrics["best_params"] = best_params
        elapsed = round(time.time() - start_time, 2)
        metrics["training_time_sec"] = elapsed

        logger.info(
            f"[{crop.upper()}] XGBoost Grid Search completed in {elapsed}s — Best params: {best_params}, "
            f"MAE: {metrics['mae']}, RMSE: {metrics['rmse']}"
        )

        save_path = MODELS_DIR / f"xgboost_{crop}.pkl"
        with open(save_path, "wb") as f:
            pickle.dump(best_model, f)

        return best_model, metrics

    except Exception as e:
        logger.error(f"[{crop.upper()}] XGBoost training failed: {e}")
        return None, {"mae": 999999.0, "rmse": 999999.0, "error": str(e), "training_time_sec": 0.0}


# ── Full Crop Pipeline ────────────────────────────────────────────────────────

def train_crop_models(crop: str, df_crop: pd.DataFrame) -> Dict[str, Any]:
    """Train and evaluate all 4 models for a single crop and select production model."""
    logger.info(f"\n==================================================")
    logger.info(f"    TRAINING PIPELINE FOR CROP: {crop.upper()}")
    logger.info(f"==================================================")

    # 1. Feature Engineering
    df_feat = add_features(df_crop)
    logger.info(f"[{crop.upper()}] Total feature-engineered samples: {len(df_feat)}")

    # 2. Chronological Train / Validation Split (Last 60 days = Validation)
    val_size = 60
    train_df = df_feat.iloc[:-val_size].copy()
    val_df = df_feat.iloc[-val_size:].copy()

    logger.info(
        f"[{crop.upper()}] Train set: {len(train_df)} rows ({train_df['ds'].min().date()} → {train_df['ds'].max().date()})"
    )
    logger.info(
        f"[{crop.upper()}] Val set:   {len(val_df)} rows ({val_df['ds'].min().date()} → {val_df['ds'].max().date()})"
    )

    # Save historical data tail (last 60 days of features) for inference
    tail_path = MODELS_DIR / f"data_tail_{crop}.pkl"
    with open(tail_path, "wb") as f:
        pickle.dump(df_feat.tail(60), f)

    # 3. Train all models
    models_metrics = {}

    arima_model, arima_metrics = train_arima(train_df, val_df, crop)
    models_metrics["arima"] = arima_metrics

    prophet_model, prophet_metrics = train_prophet(train_df, val_df, crop)
    models_metrics["prophet"] = prophet_metrics

    lstm_model, lstm_metrics = train_lstm(train_df, val_df, crop)
    models_metrics["lstm"] = lstm_metrics

    xgb_model, xgb_metrics = train_xgboost(train_df, val_df, crop)
    models_metrics["xgboost"] = xgb_metrics

    # 4. Model Selection Strategy
    # Best baseline = min(ARIMA, Prophet, LSTM) by MAE
    baselines = {k: models_metrics[k] for k in ["arima", "prophet", "lstm"]}
    valid_baselines = {k: v for k, v in baselines.items() if v.get("mae", 999999.0) < 999999.0}

    if valid_baselines:
        best_baseline_name = min(valid_baselines, key=lambda k: valid_baselines[k]["mae"])
        best_baseline_mae = valid_baselines[best_baseline_name]["mae"]
    else:
        best_baseline_name = "arima"
        best_baseline_mae = 999999.0

    xgb_mae = models_metrics["xgboost"].get("mae", 999999.0)

    if xgb_mae < best_baseline_mae:
        production_model_name = "xgboost"
    else:
        production_model_name = best_baseline_name

    logger.info(
        f"[{crop.upper()}] SELECTION RESULT: Best Baseline = {best_baseline_name.upper()} (MAE={best_baseline_mae}), "
        f"XGBoost (MAE={xgb_mae}) -> PRODUCTION MODEL = {production_model_name.upper()}"
    )

    # 5. Save per-crop metrics JSON
    metrics_summary = {
        "crop": crop,
        "best_baseline": best_baseline_name,
        "production_model": production_model_name,
        "models": models_metrics,
        "training_rows": len(train_df),
        "validation_rows": len(val_df),
        "dataset_range": f"{df_feat['ds'].min().date()} to {df_feat['ds'].max().date()}",
    }

    metrics_file = MODELS_DIR / f"metrics_{crop}.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics_summary, f, indent=2)

    return metrics_summary


# ── Global Training Pipeline ──────────────────────────────────────────────────

def run_training_pipeline() -> Dict[str, Any]:
    """Train models for all configured crops and update global model registry."""
    raw_path = settings.DATA_DIR / "real_historical_prices.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Dataset not found: {raw_path}")

    df_raw = pd.read_csv(raw_path, parse_dates=["ds"])
    logger.info(f"Loaded dataset for training: {len(df_raw)} total rows across crops.")

    global_results = {}
    timestamp = datetime.now().isoformat()

    for crop in PRICE_PREDICTION_CROPS:
        df_crop = df_raw[df_raw["crop"] == crop].copy()
        if len(df_crop) == 0:
            logger.error(f"No price data found for crop '{crop}'")
            continue

        crop_metrics = train_crop_models(crop, df_crop)
        global_results[crop] = crop_metrics

    # Update global model_registry.json
    registry_path = MODELS_DIR / "model_registry.json"
    registry_data = {
        "system_version": "4.0.0",
        "last_updated": timestamp,
        "registry": {},
    }

    for crop, res in global_results.items():
        prod_m = res["production_model"]
        prod_metrics = res["models"].get(prod_m, {})
        registry_data["registry"][crop] = {
            "production_model": prod_m,
            "best_baseline": res["best_baseline"],
            "training_date": timestamp,
            "feature_version": "4.0.0",
            "dataset_version": "2019-2024-v1",
            "weather_version": "open-meteo-nagpur-monthly-v1",
            "training_rows": res["training_rows"],
            "validation_rows": res["validation_rows"],
            "mae": prod_metrics.get("mae"),
            "rmse": prod_metrics.get("rmse"),
            "all_models_mae": {k: v.get("mae") for k, v in res["models"].items()},
        }

    with open(registry_path, "w") as f:
        json.dump(registry_data, f, indent=2)

    logger.info(f"\n==================================================")
    logger.info(f"   GLOBAL TRAINING PIPELINE COMPLETED SUCCESSFULLY")
    logger.info(f"   Registry updated at: {registry_path}")
    logger.info(f"==================================================")

    return global_results


def train_all_crops():
    """Alias function for running global price model training pipeline."""
    return run_training_pipeline()


def train_price_models_for_crop(crop: str):
    """Synchronously retrain price prediction models for a single crop."""
    crop_lower = crop.lower().strip()
    df_raw = load_dataset()
    df_crop = preprocess_crop_dataset(df_raw, crop_lower)
    return train_crop_models(crop_lower, df_crop)


if __name__ == "__main__":
    run_training_pipeline()

