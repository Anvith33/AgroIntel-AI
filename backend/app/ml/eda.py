"""
eda.py — Exploratory Data Analysis (EDA) for AgroIntel Price Data.

Performs data validation and generates visualization artifacts:
  1. Price distribution boxplots & histograms per crop
  2. 6-year daily trend time series (2019–2024)
  3. Monthly seasonality curves per crop
  4. Feature correlation matrix heatmap (11 engineered features)
  5. Missing value & outlier audit report

Outputs saved to:
  app/data/eda_plots/
"""

import json
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

from app.core.config import settings
from app.core.constants import PRICE_FEATURE_COLS, PRICE_PREDICTION_CROPS
from app.ml.feature_engineering import add_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

PLOT_DIR = settings.DATA_DIR / "eda_plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)


def run_eda() -> dict:
    """Run full EDA pipeline and save plots & summary stats."""
    raw_path = settings.DATA_DIR / "real_historical_prices.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing price dataset: {raw_path}")

    df_raw = pd.read_csv(raw_path, parse_dates=["ds"])
    logger.info(f"Loaded raw price dataset: {len(df_raw)} rows, crops={df_raw['crop'].unique().tolist()}")

    summary = {
        "dataset_rows": len(df_raw),
        "crops": {},
        "missing_values": df_raw.isnull().sum().to_dict(),
        "outlier_summary": {},
    }

    # Set aesthetic style
    sns.set_theme(style="whitegrid", palette="muted")
    plt.rcParams.update({"font.size": 10, "figure.autolayout": True})

    # ── 1. Price Distribution Plot ───────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Boxplot
    sns.boxplot(data=df_raw, x="crop", y="y", ax=axes[0], palette="Set2")
    axes[0].set_title("Crop Price Distribution (Boxplot)")
    axes[0].set_ylabel("Price (₹/quintal)")
    axes[0].set_xlabel("Crop")

    # KDE Distribution
    for crop in PRICE_PREDICTION_CROPS:
        crop_data = df_raw[df_raw["crop"] == crop]["y"]
        sns.kdeplot(crop_data, ax=axes[1], label=crop.capitalize(), fill=True, alpha=0.2)
    axes[1].set_title("Price Density Distribution (KDE)")
    axes[1].set_xlabel("Price (₹/quintal)")
    axes[1].set_ylabel("Density")
    axes[1].legend()

    dist_path = PLOT_DIR / "price_distribution.png"
    fig.savefig(dist_path, dpi=200)
    plt.close(fig)
    logger.info(f"Saved {dist_path}")

    # ── 2. Time Series Trend Plot ────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 6))
    for crop in PRICE_PREDICTION_CROPS:
        sub = df_raw[df_raw["crop"] == crop].sort_values("ds")
        ax.plot(sub["ds"], sub["y"], label=crop.capitalize(), linewidth=1.2)
    
    ax.set_title("Historical Market Prices (2019–2024 Daily Modal Prices)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (₹/quintal)")
    ax.legend(loc="upper left")
    
    trend_path = PLOT_DIR / "price_trends.png"
    fig.savefig(trend_path, dpi=200)
    plt.close(fig)
    logger.info(f"Saved {trend_path}")

    # ── 3. Monthly Seasonality Plot ──────────────────────────────────────────
    df_raw["month"] = df_raw["ds"].dt.month
    seasonality_df = df_raw.groupby(["crop", "month"])["y"].mean().reset_index()

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.lineplot(data=seasonality_df, x="month", y="y", hue="crop", marker="o", linewidth=2, ax=ax)
    ax.set_title("Average Price Seasonality by Month (1–12)")
    ax.set_xlabel("Month (1 = Jan, 12 = Dec)")
    ax.set_ylabel("Average Price (₹/quintal)")
    ax.set_xticks(range(1, 13))
    ax.legend(title="Crop")

    season_path = PLOT_DIR / "price_seasonality.png"
    fig.savefig(season_path, dpi=200)
    plt.close(fig)
    logger.info(f"Saved {season_path}")

    # ── 4. Feature Correlation Matrix Heatmap ────────────────────────────────
    # Combine features across crops for overall feature correlation
    feat_dfs = []
    for crop in PRICE_PREDICTION_CROPS:
        sub = df_raw[df_raw["crop"] == crop].copy()
        feat_sub = add_features(sub)
        feat_dfs.append(feat_sub)
    
    all_feat_df = pd.concat(feat_dfs, ignore_index=True)
    corr = all_feat_df[PRICE_FEATURE_COLS + ["y"]].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title("Engineered Features Correlation Matrix (including Target y)")

    corr_path = PLOT_DIR / "feature_correlation.png"
    fig.savefig(corr_path, dpi=200)
    plt.close(fig)
    logger.info(f"Saved {corr_path}")

    # ── 5. Statistical & Outlier Report per Crop ────────────────────────────
    for crop in PRICE_PREDICTION_CROPS:
        sub = df_raw[df_raw["crop"] == crop]["y"]
        q1 = sub.quantile(0.25)
        q3 = sub.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = sub[(sub < lower_bound) | (sub > upper_bound)]

        summary["crops"][crop] = {
            "count": int(len(sub)),
            "mean": round(float(sub.mean()), 2),
            "std": round(float(sub.std()), 2),
            "min": round(float(sub.min()), 2),
            "q25": round(float(q1), 2),
            "median": round(float(sub.median()), 2),
            "q75": round(float(q3), 2),
            "max": round(float(sub.max()), 2),
            "outliers_count": int(len(outliers)),
            "outliers_pct": round(len(outliers) / len(sub) * 100, 2),
        }

    # Save summary report JSON
    summary_path = PLOT_DIR / "eda_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"EDA Summary saved to {summary_path}")

    return summary


if __name__ == "__main__":
    run_eda()
