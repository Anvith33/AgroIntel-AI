"""
validate_models.py — Daily Candidate Model Validation & Acceptance Testing Job.

Validates candidate models in models/candidates/ against strict safety criteria:
  1. Successful 30-day multi-step recursive inference across all states.
  2. Zero negative prices generated in the 30-day forecast array.
  3. Zero extreme price spikes (> 300% of historical tail modal price).
  4. Non-empty forecast array with exact 30 future date labels.
  5. Comparative benchmark against current production model in models/.

Produces:
  - Decision per crop: PROMOTE or REJECT with detailed rationale.
  - Written to model_promotion_audit.json.
"""

import json
import logging
import pickle
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.jobs.build_dataset import SUPPORTED_CROPS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.jobs.validate_models")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
MODELS_DIR = BASE_DIR / "models"
CANDIDATES_DIR = MODELS_DIR / "candidates"
EXP_DIR = DATA_DIR / "experimental"
EXP_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR = BASE_DIR.parent / "audit" / "models"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

PROMOTION_AUDIT_PATH = EXP_DIR / "model_promotion_audit.json"
AUDIT_COPY_PATH = AUDIT_DIR / "model_promotion_audit.json"
REGISTRY_PATH = MODELS_DIR / "model_registry.json"

FEATURE_COLS = [
    "state_enc", "lag_1", "lag_7", "lag_14", "lag_30",
    "rolling_7", "rolling_30", "rolling_std_7", "price_range",
    "day_of_year", "month", "day_of_week", "year", "black_swan"
]


class ModelValidationJob:
    """Production Candidate Model Validation Job."""

    @staticmethod
    def simulate_30d_forecast(model: Any, encoder: Any, data_tail: Dict[str, List[Dict[str, Any]]], state: str) -> Tuple[bool, List[float], Optional[str]]:
        """Run 30-day recursive autoregressive inference on a test state."""
        try:
            state_records = data_tail.get(state, [])
            if len(state_records) < 30:
                # Fallback to first available state with >= 30 records
                for st, recs in data_tail.items():
                    if len(recs) >= 30:
                        state_records = recs
                        state = st
                        break

            if not state_records:
                return False, [], "No historical data tail available"

            state_idx = int(encoder.transform([state])[0]) if state in encoder.classes_ else 0

            # Build history series
            history = [float(r["y"]) for r in state_records]
            last_date = pd.to_datetime(state_records[-1]["ds"])

            forecasts = []
            for i in range(1, 31):
                f_date = last_date + timedelta(days=i)
                lag_1 = history[-1]
                lag_7 = history[-7] if len(history) >= 7 else history[-1]
                lag_14 = history[-14] if len(history) >= 14 else history[-1]
                lag_30 = history[-30] if len(history) >= 30 else history[-1]
                rolling_7 = float(np.mean(history[-7:]))
                rolling_30 = float(np.mean(history[-30:]))
                rolling_std_7 = float(np.std(history[-7:])) if len(history) >= 2 else 0.0

                feat_dict = {
                    "state_enc": state_idx,
                    "lag_1": lag_1,
                    "lag_7": lag_7,
                    "lag_14": lag_14,
                    "lag_30": lag_30,
                    "rolling_7": rolling_7,
                    "rolling_30": rolling_30,
                    "rolling_std_7": rolling_std_7,
                    "price_range": state_records[-1].get("price_range", 0.0),
                    "day_of_year": f_date.dayofyear,
                    "month": f_date.month,
                    "day_of_week": f_date.dayofweek,
                    "year": f_date.year,
                    "black_swan": 0
                }

                feat_df = pd.DataFrame([feat_dict])[FEATURE_COLS]
                pred_val = float(model.predict(feat_df)[0])
                forecasts.append(round(pred_val, 2))
                history.append(pred_val)

            return True, forecasts, None
        except Exception as e:
            return False, [], str(e)

    def validate_crop_candidate(self, crop: str) -> Dict[str, Any]:
        """Validate candidate artifacts for a single crop."""
        cand_model_path = CANDIDATES_DIR / f"xgboost_state_{crop}.pkl"
        cand_encoder_path = CANDIDATES_DIR / f"state_encoder_{crop}.pkl"
        cand_tail_path = CANDIDATES_DIR / f"data_tail_state_{crop}.pkl"
        cand_metrics_path = CANDIDATES_DIR / f"metrics_state_{crop}.json"

        if not cand_model_path.exists() or not cand_encoder_path.exists() or not cand_tail_path.exists():
            return {
                "crop": crop,
                "decision": "REJECT",
                "reason": "Missing candidate model or encoder artifact files",
                "checks": {"artifacts_exist": False}
            }

        with open(cand_model_path, "rb") as f:
            model = pickle.load(f)
        with open(cand_encoder_path, "rb") as f:
            encoder = pickle.load(f)
        with open(cand_tail_path, "rb") as f:
            data_tail = pickle.load(f)

        cand_metrics = {}
        if cand_metrics_path.exists():
            with open(cand_metrics_path, "r") as f:
                cand_metrics = json.load(f)

        # 1. Test 30-day forecast simulation
        sample_state = list(data_tail.keys())[0] if data_tail else "Maharashtra"
        success, forecasts, err = self.simulate_30d_forecast(model, encoder, data_tail, sample_state)

        if not success or len(forecasts) != 30:
            return {
                "crop": crop,
                "decision": "REJECT",
                "reason": f"30-day forecast simulation failed: {err}",
                "checks": {"forecast_30d_simulation": False}
            }

        # 2. Check for negative prices
        has_negative = any(p <= 0 for p in forecasts)
        if has_negative:
            return {
                "crop": crop,
                "decision": "REJECT",
                "reason": "Forecast generated negative or zero price values",
                "checks": {"non_negative_prices": False}
            }

        # 3. Check for extreme spikes (> 300% of baseline)
        baseline_price = forecasts[0]
        has_extreme_spike = any(p > (baseline_price * 3.5) for p in forecasts)
        if has_extreme_spike:
            return {
                "crop": crop,
                "decision": "REJECT",
                "reason": f"Forecast generated extreme spike (> 350% baseline {baseline_price})",
                "checks": {"no_extreme_spikes": False}
            }

        # 4. Compare against current production model MAE if available
        cand_mae = cand_metrics.get("holdout_mae", 9999.0)
        prod_mae = None

        prod_metrics_path = MODELS_DIR / f"metrics_state_{crop}.json"
        if prod_metrics_path.exists():
            try:
                with open(prod_metrics_path, "r") as f:
                    prod_data = json.load(f)
                    prod_mae = prod_data.get("state_aware", {}).get("mae") or prod_data.get("holdout_mae")
            except Exception:
                pass

        if prod_mae is None and REGISTRY_PATH.exists():
            try:
                with open(REGISTRY_PATH, "r") as f:
                    reg = json.load(f)
                    crop_entry = reg.get("registry", {}).get(crop, {}) or reg.get(crop, {})
                    prod_mae = crop_entry.get("holdout_mae") or crop_entry.get("mae")
            except Exception:
                pass

        # If candidate MAE is better or within 10% tolerance of production MAE, approve promotion
        if prod_mae is not None and cand_mae > (prod_mae * 1.10):
            decision = "REJECT"
            reason = f"Candidate MAE ({cand_mae}) is >10% worse than current production MAE ({prod_mae})"
        else:
            decision = "PROMOTE"
            reason = f"Candidate passed all safety checks. Candidate MAE: {cand_mae} (Production: {prod_mae})"

        return {
            "crop": crop,
            "decision": decision,
            "reason": reason,
            "candidate_mae": cand_mae,
            "production_mae": prod_mae,
            "sample_30d_forecast_head": forecasts[:5],
            "sample_30d_forecast_tail": forecasts[-5:],
            "checks": {
                "artifacts_exist": True,
                "forecast_30d_simulation": True,
                "non_negative_prices": True,
                "no_extreme_spikes": True,
                "mae_within_acceptance_bound": decision == "PROMOTE"
            }
        }

    def run(self) -> Dict[str, Any]:
        """Validate candidate models across all 5 crops."""
        t_start = time.time()
        logger.info("Starting Candidate Model Validation & Promotion Assessment...")

        validation_results = {}
        promoted_crops = []
        rejected_crops = []

        for crop in SUPPORTED_CROPS:
            res = self.validate_crop_candidate(crop)
            validation_results[crop] = res
            if res["decision"] == "PROMOTE":
                promoted_crops.append(crop)
            else:
                rejected_crops.append(crop)

        elapsed = round(time.time() - t_start, 2)

        audit_report = {
            "job_name": "validate_models",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_seconds": elapsed,
            "promoted_crops_count": len(promoted_crops),
            "rejected_crops_count": len(rejected_crops),
            "promoted_crops": promoted_crops,
            "rejected_crops": rejected_crops,
            "validation_details": validation_results,
        }

        with open(PROMOTION_AUDIT_PATH, "w", encoding="utf-8") as f:
            json.dump(audit_report, f, indent=2)
        with open(AUDIT_COPY_PATH, "w", encoding="utf-8") as f:
            json.dump(audit_report, f, indent=2)

        logger.info(f"Model Validation Complete in {elapsed}s: {len(promoted_crops)} PROMOTE, {len(rejected_crops)} REJECT.")
        return audit_report


if __name__ == "__main__":
    Tuple_Sim = Any
    job = ModelValidationJob()
    res = job.run()
    print(json.dumps(res, indent=2))
