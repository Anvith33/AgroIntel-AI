"""
state_specific_price_validation.py — State-Specific Price Forecasting Audit & Validation

Validates price predictions across 28 Indian States x 5 Major Crops.
Saves validation matrix to state_specific_price_validation.json and state_specific_forecast_validation.json.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, date

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
EXP_DIR = BASE_DIR / "app" / "data" / "experimental"
EXP_DIR.mkdir(parents=True, exist_ok=True)

CROPS = ["rice", "wheat", "maize", "onion", "potato"]

# 28 Official States of India
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal"
]


def run_state_validation():
    from app.ml.inference import predict_price

    logger.info("=== Starting 28-State x 5-Crop State-Specific Price Validation ===")
    results = []
    summary_by_crop = {c: {"total_states": len(INDIAN_STATES), "state_aware": 0, "crop_only_fallback": 0, "diff_predictions": set()} for c in CROPS}

    for crop in CROPS:
        logger.info(f"\nTesting Crop: {crop.upper()}")
        for state in INDIAN_STATES:
            try:
                res = predict_price(crop=crop, state=state, horizon_days=30)
                cur_p = res.get("current_price")
                pred_p = res.get("predicted_price")
                dec = res.get("recommendation", "WAIT")
                model_level = res.get("model_level", "STATE_AWARE")
                status = res.get("forecast_status", "SUCCESS")
                obs_date = res.get("observation_date", date.today().isoformat())
                src = res.get("price_data_source", "agmarknet")
                
                pct_chg = round(((pred_p - cur_p) / cur_p) * 100, 2) if cur_p and cur_p > 0 else 0.0

                item = {
                    "crop": crop.capitalize(),
                    "state": state,
                    "current_price": cur_p,
                    "predicted_price": pred_p,
                    "percentage_change": pct_chg,
                    "decision": dec,
                    "observation_date": obs_date,
                    "data_source": src,
                    "model_level": model_level,
                    "forecast_status": status
                }
                results.append(item)

                if pred_p:
                    summary_by_crop[crop]["diff_predictions"].add(round(pred_p, 1))

                if "STATE" in model_level.upper():
                    summary_by_crop[crop]["state_aware"] += 1
                else:
                    summary_by_crop[crop]["crop_only_fallback"] += 1

                logger.info(f"  [{crop.upper()}] {state:20s} -> Current: ₹{cur_p} | Pred: ₹{pred_p} ({pct_chg:+.1f}%) | Level: {model_level} | Dec: {dec}")

            except Exception as e:
                logger.error(f"Error testing {crop} + {state}: {e}")
                results.append({
                    "crop": crop.capitalize(),
                    "state": state,
                    "current_price": None,
                    "predicted_price": None,
                    "percentage_change": 0.0,
                    "decision": "WAIT",
                    "observation_date": None,
                    "data_source": "error",
                    "model_level": "ERROR",
                    "forecast_status": str(e)
                })

    # Prepare summary report
    formatted_summary = {}
    for c, s in summary_by_crop.items():
        formatted_summary[c] = {
            "total_states": s["total_states"],
            "state_aware_forecasts": s["state_aware"],
            "fallback_forecasts": s["crop_only_fallback"],
            "unique_predicted_prices_count": len(s["diff_predictions"])
        }

    output = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "states_tested_count": len(INDIAN_STATES),
        "crops_tested_count": len(CROPS),
        "crop_summary": formatted_summary,
        "results": results
    }

    # Save to both requested file paths
    file1 = EXP_DIR / "state_specific_price_validation.json"
    file2 = EXP_DIR / "state_specific_forecast_validation.json"

    with open(file1, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    with open(file2, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    logger.info(f"\nSaved validation to {file1} and {file2}")
    return output


if __name__ == "__main__":
    run_state_validation()
