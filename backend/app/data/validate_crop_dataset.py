"""
validate_crop_dataset.py — One-time crop recommendation dataset validator.

Validates crop_recommendation.csv (Kaggle dataset):
  - Missing values
  - Duplicate rows
  - Data type correctness
  - Label normalization

Also generates the CROP_NAME_MAP report:
  - Maps district/mandi crop names → RF dataset labels
  - Reports mapped vs unmapped crops

Usage:
    python -m app.data.validate_crop_dataset

Output:
    Prints a validation report to stdout.
    Does NOT modify the dataset.
"""

import json
import logging
from pathlib import Path

import pandas as pd

from app.core.constants import MANDI_TO_RF_LABEL
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

CROP_CSV_PATH    = settings.DATA_DIR / "crop_recommendation.csv"
REGION_MAP_PATH  = settings.DATA_DIR / "region_crop_mapping.json"

EXPECTED_COLUMNS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall", "label"]
EXPECTED_LABELS  = {
    "rice", "maize", "chickpea", "kidneybeans", "pigeonpeas",
    "mothbeans", "mungbean", "blackgram", "lentil", "pomegranate",
    "banana", "mango", "grapes", "watermelon", "muskmelon",
    "apple", "orange", "papaya", "coconut", "cotton", "jute", "coffee",
}


def validate_crop_csv() -> dict:
    """Validate the crop recommendation CSV and return a report dict."""
    report = {}

    if not CROP_CSV_PATH.exists():
        report["error"] = f"File not found: {CROP_CSV_PATH}"
        return report

    df = pd.read_csv(CROP_CSV_PATH)
    report["total_rows"] = len(df)
    report["columns"]    = list(df.columns)

    # ── 1. Column check ───────────────────────────────────────────────────
    missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
    extra_cols   = set(df.columns) - set(EXPECTED_COLUMNS)
    report["missing_columns"] = sorted(missing_cols)
    report["extra_columns"]   = sorted(extra_cols)

    # ── 2. Missing values ─────────────────────────────────────────────────
    mv = df.isnull().sum()
    report["missing_values"] = {col: int(cnt) for col, cnt in mv.items() if cnt > 0}

    # ── 3. Duplicates ─────────────────────────────────────────────────────
    dups = df.duplicated().sum()
    report["duplicate_rows"] = int(dups)

    # ── 4. Label validation ───────────────────────────────────────────────
    # Normalize labels to lowercase
    df["label"] = df["label"].str.lower().str.strip()
    actual_labels = set(df["label"].unique())
    unexpected_labels = actual_labels - EXPECTED_LABELS
    missing_labels    = EXPECTED_LABELS - actual_labels
    report["unique_labels"]       = sorted(actual_labels)
    report["unexpected_labels"]   = sorted(unexpected_labels)
    report["missing_labels"]      = sorted(missing_labels)
    report["label_counts"]        = df["label"].value_counts().to_dict()

    # ── 5. Numeric range checks ───────────────────────────────────────────
    range_issues = {}
    checks = {
        "N":           (0, 200),
        "P":           (0, 200),
        "K":           (0, 200),
        "temperature": (0, 50),
        "humidity":    (0, 100),
        "ph":          (0, 14),
        "rainfall":    (0, 3000),
    }
    for col, (lo, hi) in checks.items():
        if col in df.columns:
            out_of_range = ((df[col] < lo) | (df[col] > hi)).sum()
            if out_of_range > 0:
                range_issues[col] = int(out_of_range)
    report["range_issues"] = range_issues

    return report


def generate_crop_name_map_report() -> dict:
    """
    Cross-reference MANDI_TO_RF_LABEL against all district crops in
    region_crop_mapping.json and report mapped vs unmapped crops.

    Returns:
        dict with keys: mapped, unmapped, coverage_pct
    """
    if not REGION_MAP_PATH.exists():
        return {"error": "region_crop_mapping.json not found"}

    with open(REGION_MAP_PATH) as f:
        region_data = json.load(f)

    # Collect all unique district-level crop names
    all_district_crops: set[str] = set()
    for dist_info in region_data.get("districts", {}).values():
        for crop in dist_info.get("top_crops", []):
            all_district_crops.add(crop)

    map_lower = {k.lower(): v for k, v in MANDI_TO_RF_LABEL.items()}

    mapped:   dict[str, str] = {}
    unmapped: list[str]      = []

    for crop in sorted(all_district_crops):
        rf_label = map_lower.get(crop.lower())
        if rf_label:
            mapped[crop] = rf_label
        else:
            unmapped.append(crop)

    total        = len(all_district_crops)
    mapped_count = len(mapped)
    coverage_pct = round(mapped_count / total * 100, 1) if total > 0 else 0.0

    return {
        "total_district_crops": total,
        "mapped_count":         mapped_count,
        "unmapped_count":       len(unmapped),
        "coverage_pct":         coverage_pct,
        "mapped":               mapped,
        "unmapped":             sorted(unmapped),
    }


def print_report(csv_report: dict, map_report: dict) -> None:
    """Print both reports in human-readable format."""
    SEP = "=" * 60

    print(f"\n{SEP}")
    print("CROP RECOMMENDATION CSV VALIDATION REPORT")
    print(SEP)

    if "error" in csv_report:
        print(f"  ❌ ERROR: {csv_report['error']}")
    else:
        status = "✅ CLEAN" if (
            not csv_report.get("missing_values")
            and csv_report.get("duplicate_rows", 0) == 0
            and not csv_report.get("range_issues")
            and not csv_report.get("missing_columns")
            and not csv_report.get("unexpected_labels")
        ) else "⚠ ISSUES FOUND"
        print(f"  Status        : {status}")
        print(f"  Total rows    : {csv_report.get('total_rows', '?')}")
        print(f"  Columns       : {csv_report.get('columns', [])}")
        print(f"  Unique labels : {len(csv_report.get('unique_labels', []))}")
        print(f"  Duplicate rows: {csv_report.get('duplicate_rows', 0)}")
        mv = csv_report.get("missing_values", {})
        print(f"  Missing values: {mv if mv else 'None'}")
        ri = csv_report.get("range_issues", {})
        print(f"  Range issues  : {ri if ri else 'None'}")
        ul = csv_report.get("unexpected_labels", [])
        print(f"  Unknown labels: {ul if ul else 'None'}")

    print(f"\n{SEP}")
    print("CROP NAME MAP REPORT (District → RF Label)")
    print(SEP)

    if "error" in map_report:
        print(f"  ❌ ERROR: {map_report['error']}")
    else:
        print(f"  Total district crops : {map_report['total_district_crops']}")
        print(f"  Mapped to RF label   : {map_report['mapped_count']}")
        print(f"  Unmapped             : {map_report['unmapped_count']}")
        print(f"  Coverage             : {map_report['coverage_pct']}%")
        print()
        print("  MAPPED CROPS (sample — first 20):")
        for i, (mandi, rf) in enumerate(list(map_report.get("mapped", {}).items())[:20]):
            print(f"    '{mandi}' → '{rf}'")
        print()
        print(f"  UNMAPPED CROPS ({map_report['unmapped_count']} total):")
        print("  NOTE: Unmapped crops remain valid district candidates.")
        print("        They are kept as alternatives but skipped during RF scoring.")
        for crop in map_report.get("unmapped", [])[:30]:
            print(f"    - {crop}")
        if map_report["unmapped_count"] > 30:
            print(f"    ... and {map_report['unmapped_count'] - 30} more")


if __name__ == "__main__":
    csv_report = validate_crop_csv()
    map_report = generate_crop_name_map_report()
    print_report(csv_report, map_report)
