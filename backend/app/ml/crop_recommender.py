"""
crop_recommender.py — Validated Random Forest Crop Recommender for AgroIntel v4.0.

Performs strict 80/20 Train/Test Split and 5-Fold Cross-Validation on unseen test data.
Saves comprehensive metrics (accuracy, precision, recall, f1, confusion matrix, cv_scores)
to models/crop_recommender_metrics.json.
"""

import json
import logging
import pickle
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder

from app.core.config import settings

logger = logging.getLogger(__name__)

MODELS_DIR = settings.MODELS_DIR
MODELS_DIR.mkdir(parents=True, exist_ok=True)

RF_MODEL_PATH = MODELS_DIR / "crop_recommender_rf.pkl"
ENCODER_PATH = MODELS_DIR / "crop_recommender_encoder.pkl"
METRICS_PATH = MODELS_DIR / "crop_recommender_metrics.json"

FEATURE_NAMES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def train_and_validate_crop_recommender() -> Dict[str, Any]:
    """
    Train Random Forest model and strictly evaluate ONLY on unseen validation/test data (80/20 split)
    and 5-Fold Stratified Cross Validation.
    """
    csv_path = settings.DATA_DIR / "crop_recommendation.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Crop dataset missing: {csv_path}")

    df = pd.read_csv(csv_path)
    logger.info(f"Loaded crop dataset: {len(df)} rows, 7 features, {df['label'].nunique()} classes.")

    X = df[FEATURE_NAMES]
    y_raw = df["label"].str.lower().str.strip()

    encoder = LabelEncoder()
    y = encoder.fit_transform(y_raw)

    # 1. Strict 80/20 Train/Test Split (stratified)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # 2. Train Random Forest on 80% Training Split
    rf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    rf.fit(X_train, y_train)

    # 3. Evaluate ONLY on 20% Unseen Test Set
    y_pred = rf.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted")
    cm = confusion_matrix(y_test, y_pred).tolist()
    clf_report = classification_report(y_test, y_pred, target_names=encoder.classes_, output_dict=True)

    # 4. 5-Fold Stratified Cross-Validation over full dataset
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(rf, X, y, cv=skf, scoring="accuracy")

    # Save trained model pipeline fit on all data for production deployment
    rf_prod = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)
    rf_prod.fit(X, y)

    with open(RF_MODEL_PATH, "wb") as f:
        pickle.dump(rf_prod, f)
    with open(ENCODER_PATH, "wb") as f:
        pickle.dump(encoder, f)

    metrics = {
        "model": "RandomForestClassifier",
        "n_estimators": 100,
        "classes_count": len(encoder.classes_),
        "classes": encoder.classes_.tolist(),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "unseen_test_accuracy": round(float(test_acc), 4),
        "weighted_precision": round(float(prec), 4),
        "weighted_recall": round(float(rec), 4),
        "weighted_f1_score": round(float(f1), 4),
        "cv_5fold_scores": [round(float(s), 4) for s in cv_scores],
        "cv_5fold_mean": round(float(np.mean(cv_scores)), 4),
        "cv_5fold_std": round(float(np.std(cv_scores)), 4),
        "confusion_matrix": cm,
        "classification_report": clf_report,
        "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(
        f"Model Validation Complete: Unseen Test Accuracy = {test_acc*100:.2f}%, "
        f"5-Fold CV Mean = {np.mean(cv_scores)*100:.2f}%"
    )

    return metrics


def predict_crop_probabilities(
    n: float,
    p: float,
    k: float,
    temperature: float,
    humidity: float,
    ph: float,
    rainfall: float,
) -> Dict[str, float]:
    """
    Predict Random Forest class probabilities for all 22 crop target labels.
    """
    if not RF_MODEL_PATH.exists() or not ENCODER_PATH.exists():
        logger.info("Model missing. Running training & validation now...")
        train_and_validate_crop_recommender()

    with open(RF_MODEL_PATH, "rb") as f:
        rf: RandomForestClassifier = pickle.load(f)
    with open(ENCODER_PATH, "rb") as f:
        encoder: LabelEncoder = pickle.load(f)

    input_df = pd.DataFrame([[n, p, k, temperature, humidity, ph, rainfall]], columns=FEATURE_NAMES)
    probas = rf.predict_proba(input_df)[0]

    prob_dict = {
        cls_name: round(float(prob), 4)
        for cls_name, prob in zip(encoder.classes_, probas)
    }

    return prob_dict


if __name__ == "__main__":
    metrics = train_and_validate_crop_recommender()
    print("Random Forest Unseen Data Validation Summary:")
    print(f"  Unseen Test Accuracy: {metrics['unseen_test_accuracy']*100:.2f}%")
    print(f"  5-Fold CV Mean Accuracy: {metrics['cv_5fold_mean']*100:.2f}% (+/- {metrics['cv_5fold_std']*100:.2f}%)")
    print(f"  Weighted Precision: {metrics['weighted_precision']:.4f}")
    print(f"  Weighted Recall: {metrics['weighted_recall']:.4f}")
    print(f"  Weighted F1 Score: {metrics['weighted_f1_score']:.4f}")
