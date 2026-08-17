"""
app.jobs — Daily Update, Ingestion, Retraining & Safe Model Promotion Package.
"""

from app.jobs.daily_pipeline import DailyPipelineRunner
from app.jobs.fetch_mandi import MandiIngestionJob
from app.jobs.fetch_news import NewsIngestionJob
from app.jobs.process_news import NewsProcessingJob
from app.jobs.update_weather import WeatherUpdateJob
from app.jobs.build_dataset import DatasetBuilderJob
from app.jobs.train_all import ModelTrainingJob
from app.jobs.validate_models import ModelValidationJob
from app.jobs.promote_models import ModelPromotionJob

__all__ = [
    "DailyPipelineRunner",
    "MandiIngestionJob",
    "NewsIngestionJob",
    "NewsProcessingJob",
    "WeatherUpdateJob",
    "DatasetBuilderJob",
    "ModelTrainingJob",
    "ModelValidationJob",
    "ModelPromotionJob",
]
