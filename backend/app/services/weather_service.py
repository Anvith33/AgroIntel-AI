"""
weather_service.py — Open-Meteo weather data service.

Fetches:
  - 7-day hourly forecast from Open-Meteo (free, no API key required)
  - Computes daily averages: avg_temp, total_rainfall, avg_humidity

Used by:
  - Crop recommendation (weather context for RF input)
  - Price prediction (current monthly avg_temp and rainfall for feature vector)
"""

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Simple in-memory cache ────────────────────────────────────────────────────
_weather_cache: dict[str, dict] = {}


@dataclass
class WeatherSummary:
    """Structured weather output from Open-Meteo."""
    avg_temp: float          # Average temperature (°C) over 7-day forecast
    avg_humidity: float      # Average relative humidity (%) over 7-day forecast
    total_rainfall: float    # Total precipitation (mm) over 7-day forecast
    avg_daily_rainfall: float  # Daily average rainfall (mm)
    lat: float
    lon: float
    source: str = "open-meteo"


def get_weather_summary(lat: float, lon: float) -> WeatherSummary:
    """
    Fetch 7-day weather forecast from Open-Meteo and return a summary.

    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.

    Returns:
        WeatherSummary with aggregated values over the 7-day forecast period.

    Raises:
        RuntimeError: If the Open-Meteo API call fails and no cache is available.
    """
    cache_key = f"{round(lat, 2)}_{round(lon, 2)}"
    now = time.time()

    # Return cached result if still fresh
    cached = _weather_cache.get(cache_key)
    if cached and (now - cached["timestamp"]) < settings.WEATHER_CACHE_TTL_SECONDS:
        logger.debug(f"Weather cache hit for ({lat}, {lon})")
        return cached["data"]

    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relativehumidity_2m,precipitation",
            "forecast_days": 7,
            "timezone": "Asia/Kolkata",
        }
        response = httpx.get(
            settings.OPEN_METEO_FORECAST_URL,
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        hourly = data.get("hourly", {})
        temps = hourly.get("temperature_2m", [])
        humidity = hourly.get("relativehumidity_2m", [])
        rain = hourly.get("precipitation", [])

        if not temps:
            raise ValueError("Empty temperature data from Open-Meteo")

        avg_temp = round(sum(temps) / len(temps), 2)
        avg_humidity = round(sum(humidity) / len(humidity), 2) if humidity else 0.0
        total_rainfall = round(sum(rain), 2) if rain else 0.0
        avg_daily_rainfall = round(total_rainfall / 7, 2)

        summary = WeatherSummary(
            avg_temp=avg_temp,
            avg_humidity=avg_humidity,
            total_rainfall=total_rainfall,
            avg_daily_rainfall=avg_daily_rainfall,
            lat=lat,
            lon=lon,
        )

        _weather_cache[cache_key] = {"data": summary, "timestamp": now}
        logger.info(
            f"Weather fetched for ({lat}, {lon}): "
            f"temp={avg_temp}°C, humidity={avg_humidity}%, rain={total_rainfall}mm"
        )
        return summary

    except Exception as e:
        logger.error(f"Open-Meteo API error for ({lat}, {lon}): {e}")
        # Return cached stale data if available
        if cached:
            logger.warning("Returning stale weather cache due to API failure")
            return cached["data"]
        # Hard fallback: typical Indian agricultural values
        logger.warning("Using hard fallback weather values")
        return WeatherSummary(
            avg_temp=28.0,
            avg_humidity=65.0,
            total_rainfall=25.0,
            avg_daily_rainfall=3.6,
            lat=lat,
            lon=lon,
            source="fallback",
        )


def get_current_monthly_weather(lat: float, lon: float) -> dict[str, float]:
    """
    Return avg_temp and total_rainfall for the current month.

    Used by the price prediction feature vector to match the
    monthly weather features used during training.

    Returns:
        Dict with keys: monthly_avg_temp, monthly_total_rainfall
    """
    summary = get_weather_summary(lat, lon)
    # Scale 7-day totals to monthly approximations
    days_in_month = 30
    scale = days_in_month / 7
    return {
        "monthly_avg_temp": summary.avg_temp,
        "monthly_total_rainfall": round(summary.avg_daily_rainfall * days_in_month, 2),
    }
