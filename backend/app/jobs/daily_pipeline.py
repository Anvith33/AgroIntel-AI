"""
daily_pipeline.py — Master Orchestrator for AgroIntel Daily Update Pipeline.

Executes all pipeline stages in sequence:
  1. Mandi Ingestion (data.gov.in AGMARKNET normalization & deduplication)
  2. RSS News Ingestion (37 multi-tier sources)
  3. News Processing & Cross-Verification (21-event classification)
  4. Weather Ingestion (Open-Meteo 28-state signals)
  5. Dataset Build & Anti-Leakage Audit
  6. Multi-Crop Candidate Retraining (Rice, Wheat, Maize, Onion, Potato)
  7. Candidate Validation (30-day forecast simulation, spike rejection)
  8. Safe Model Promotion & Versioned Archival

Error Resilience:
  - Failure in one subsystem (e.g. RSS feed offline) does NOT halt remaining pipelines.
  - Generates comprehensive master audit artifact: daily_pipeline_audit.json.
"""

import json
import logging
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.jobs.fetch_mandi import MandiIngestionJob
from app.jobs.fetch_news import NewsIngestionJob
from app.jobs.process_news import NewsProcessingJob
from app.jobs.update_weather import WeatherUpdateJob
from app.jobs.build_dataset import DatasetBuilderJob
from app.jobs.train_all import ModelTrainingJob
from app.jobs.validate_models import ModelValidationJob
from app.jobs.promote_models import ModelPromotionJob

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app.jobs.daily_pipeline")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
EXP_DIR = DATA_DIR / "experimental"
EXP_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR = BASE_DIR.parent / "audit" / "system"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

MASTER_AUDIT_PATH = EXP_DIR / "daily_pipeline_audit.json"
AUDIT_COPY_PATH = AUDIT_DIR / "daily_pipeline_audit.json"


class DailyPipelineRunner:
    """Master Daily Automated Pipeline Runner."""

    @classmethod
    def run_daily_pipeline(cls) -> Dict[str, Any]:
        t_global_start = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        logger.info("===================================================================")
        logger.info(f" STARTING AGROINTEL DAILY UPDATE PIPELINE — RUN: {now_iso}")
        logger.info("===================================================================")

        stages_status = {}
        errors = []

        # ── Stage 1: Mandi Data Ingestion ─────────────────────────────────────
        try:
            logger.info("\n>>> [STAGE 1/8] Mandi Price Ingestion...")
            mandi_job = MandiIngestionJob()
            mandi_res = mandi_job.run()
            stages_status["fetch_mandi"] = {"status": "SUCCESS", "records_added": mandi_res.get("new_records_added", 0)}
        except Exception as e:
            err = f"Mandi Ingestion Stage Failed: {e}"
            logger.error(err)
            errors.append(err)
            stages_status["fetch_mandi"] = {"status": "FAILED", "error": str(e)}

        # ── Stage 2: News RSS Ingestion ───────────────────────────────────────
        try:
            logger.info("\n>>> [STAGE 2/8] Multi-Tier News RSS Ingestion...")
            news_job = NewsIngestionJob()
            news_res = news_job.run()
            stages_status["fetch_news"] = {
                "status": "SUCCESS",
                "sources_active": news_res.get("sources_active", 0),
                "articles_ingested": news_res.get("new_articles_ingested", 0),
            }
        except Exception as e:
            err = f"News Ingestion Stage Failed: {e}"
            logger.warning(err)
            errors.append(err)
            stages_status["fetch_news"] = {"status": "FAILED", "error": str(e)}

        # ── Stage 3: News Processing & Cross-Verification ─────────────────────
        try:
            logger.info("\n>>> [STAGE 3/8] News Event Classification & Verification...")
            proc_job = NewsProcessingJob()
            proc_res = proc_job.run()
            stages_status["process_news"] = {
                "status": "SUCCESS",
                "verified_clusters": proc_res.get("verified_clusters_count", 0),
            }
        except Exception as e:
            err = f"News Processing Stage Failed: {e}"
            logger.warning(err)
            errors.append(err)
            stages_status["process_news"] = {"status": "FAILED", "error": str(e)}

        # ── Stage 4: Weather Ingestion ─────────────────────────────────────────
        try:
            logger.info("\n>>> [STAGE 4/8] 28-State Weather Ingestion...")
            weather_job = WeatherUpdateJob()
            weather_res = weather_job.run()
            stages_status["update_weather"] = {
                "status": "SUCCESS",
                "states_success": weather_res.get("states_success", 0),
            }
        except Exception as e:
            err = f"Weather Ingestion Stage Failed: {e}"
            logger.warning(err)
            errors.append(err)
            stages_status["update_weather"] = {"status": "FAILED", "error": str(e)}

        # ── Stage 5: Dataset Build & Anti-Leakage Audit ───────────────────────
        try:
            logger.info("\n>>> [STAGE 5/8] Dataset Verification & Anti-Leakage Checks...")
            ds_job = DatasetBuilderJob()
            ds_res = ds_job.run()
            stages_status["build_dataset"] = {
                "status": ds_res.get("data_quality_status", "PASS"),
                "total_records": ds_res.get("total_records", 0),
            }
        except Exception as e:
            err = f"Dataset Builder Stage Failed: {e}"
            logger.error(err)
            errors.append(err)
            stages_status["build_dataset"] = {"status": "FAILED", "error": str(e)}

        # ── Stage 6: Multi-Crop Model Retraining ───────────────────────────────
        try:
            logger.info("\n>>> [STAGE 6/8] Retraining 5 Crop Price Forecasting Models...")
            train_job = ModelTrainingJob()
            train_res = train_job.run()
            stages_status["train_all"] = {
                "status": "SUCCESS",
                "crops_trained": train_res.get("crops_trained_count", 0),
                "crops": train_res.get("crops_successful", []),
            }
        except Exception as e:
            err = f"Model Retraining Stage Failed: {e}"
            logger.error(err)
            errors.append(err)
            stages_status["train_all"] = {"status": "FAILED", "error": str(e)}

        # ── Stage 7: Candidate Model Validation ────────────────────────────────
        try:
            logger.info("\n>>> [STAGE 7/8] Candidate Validation & Safety Checks...")
            val_job = ModelValidationJob()
            val_res = val_job.run()
            stages_status["validate_models"] = {
                "status": "SUCCESS",
                "promoted_count": val_res.get("promoted_count", len(val_res.get("promoted_crops", []))),
                "rejected_count": val_res.get("rejected_count", len(val_res.get("rejected_crops", []))),
                "promoted_crops": val_res.get("promoted_crops", []),
            }
        except Exception as e:
            err = f"Candidate Validation Stage Failed: {e}"
            logger.error(err)
            errors.append(err)
            stages_status["validate_models"] = {"status": "FAILED", "error": str(e)}

        # ── Stage 8: Safe Model Promotion ─────────────────────────────────────
        try:
            logger.info("\n>>> [STAGE 8/8] Promoting Approved Candidate Models...")
            prom_job = ModelPromotionJob()
            prom_res = prom_job.run()
            stages_status["promote_models"] = {
                "status": "SUCCESS",
                "promoted_models": prom_res.get("models_promoted", []),
                "version_tag": prom_res.get("archive_version_tag"),
            }
        except Exception as e:
            err = f"Model Promotion Stage Failed: {e}"
            logger.error(err)
            errors.append(err)
            stages_status["promote_models"] = {"status": "FAILED", "error": str(e)}

        total_elapsed = round(time.time() - t_global_start, 2)
        overall_status = "SUCCESS" if not errors else ("PARTIAL_SUCCESS" if len(errors) < 4 else "FAILED")

        master_summary = {
            "pipeline_name": "AgroIntel Daily Update Pipeline",
            "run_timestamp": now_iso,
            "overall_status": overall_status,
            "total_duration_seconds": total_elapsed,
            "stages": stages_status,
            "errors_count": len(errors),
            "errors": errors,
        }

        with open(MASTER_AUDIT_PATH, "w", encoding="utf-8") as f:
            json.dump(master_summary, f, indent=2)
        with open(AUDIT_COPY_PATH, "w", encoding="utf-8") as f:
            json.dump(master_summary, f, indent=2)

        logger.info("===================================================================")
        logger.info(f" AGROINTEL DAILY UPDATE COMPLETE in {total_elapsed}s — STATUS: {overall_status}")
        logger.info("===================================================================")
        return master_summary


if __name__ == "__main__":
    runner = DailyPipelineRunner()
    res = runner.run_daily_pipeline()
    print(json.dumps(res, indent=2))
