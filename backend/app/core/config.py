import os

class Settings:
    PROJECT_NAME: str = "Crop Advisory and Price Prediction System"
    API_V1_STR: str = "/api/v1"
    
    # Official API keys from your data.gov.in and OpenWeatherMap accounts
    OPENWEATHER_API_KEY: str = "e58cde6cd745974ec10458fd1dfe4332"
    MARKET_DATA_API_KEY: str = "579b464db66ec23bdd00000100b983ce593940d87db6f88c1a387a12"
    
settings = Settings()
