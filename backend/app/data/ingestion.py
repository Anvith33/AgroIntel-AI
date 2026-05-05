import pandas as pd
import numpy as np
import requests
import logging
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

class DataIngestion:
    
    @staticmethod
    def fetch_live_weather(location: str = "Delhi") -> dict:
        """
        Fetches real-time weather from OpenWeather API.
        Falls back to simulation if no API key or API fails.
        """
        api_key = settings.OPENWEATHER_API_KEY
        if api_key and api_key != "mock_weather_key":
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "temperature": data["main"]["temp"],
                        "humidity": data["main"]["humidity"],
                        "rainfall": data.get("rain", {}).get("1h", 0) * 24 * 30, # Approx seasonal rainfall based on current
                    }
            except Exception as e:
                logger.warning(f"Live Weather API failed for {location}: {e}. Falling back to simulation.")
                
        # 2. Fallback Simulator
        return {
            "temperature": 28.5 + np.random.normal(0, 3),
            "humidity": 60.0 + np.random.normal(0, 10),
            "rainfall": 150.0 + np.random.normal(0, 50),
        }

    @staticmethod
    def fetch_live_market_data(crop_name: str, state: str = "All") -> dict:
        """
        Fetches current live mandi prices using data.gov.in.
        Falls back to simulation if no API key or API fails.
        """
        api_key = settings.MARKET_DATA_API_KEY
        if api_key and api_key != "mock_market_key":
            try:
                url = f"https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070?api-key={api_key}&format=json&filters[commodity]={crop_name.capitalize()}"
                if state.lower() != "all":
                    url += f"&filters[state]={state.capitalize()}"
                    
                response = requests.get(url, timeout=10) # 10s timeout for govt API
                if response.status_code == 200:
                    data = response.json()
                    if data.get("records"):
                        prices = [float(r["modal_price"]) for r in data["records"] if str(r.get("modal_price", "")).replace(".","",1).isdigit()]
                        if prices:
                            return {"current_price": sum(prices) / len(prices)}
            except Exception as e:
                logger.warning(f"Live Market API failed for {crop_name} in {state}: {e}. Falling back to simulation.")

        # 2. Fallback Simulator
        base = 2500 if crop_name.lower() == "wheat" else 3200
        state_multiplier = 1.0
        state_lower = state.lower()
        if state_lower in ["punjab", "haryana"]:
            state_multiplier = 0.95
        elif state_lower in ["maharashtra", "karnataka"]:
            state_multiplier = 1.10
            
        noise = np.random.normal(0, 50)
        return {
            "current_price": max(1000, base * state_multiplier + noise)
        }
