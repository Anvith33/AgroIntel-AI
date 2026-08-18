import requests
import json
import sys
from app.core.config import settings

def test_weather():
    api_key = settings.OPENWEATHER_API_KEY
    print("Testing OpenWeatherMap API...")
    url = f"http://api.openweathermap.org/data/2.5/weather?q=Delhi&appid={api_key}&units=metric"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if resp.status_code == 200:
            print(f"✅ Success! Temperature in Delhi: {data['main']['temp']}°C, Humidity: {data['main']['humidity']}%")
        else:
            print(f"❌ Failed: HTTP {resp.status_code} - {json.dumps(data)}")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

def test_mandi():
    api_key = settings.MARKET_DATA_API_KEY
    print("\nTesting Data.gov.in Mandi Price API...")
    url = f"https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070?api-key={api_key}&format=json&filters[commodity]=Wheat"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("records"):
                record = data["records"][0]
                print(f"✅ Success! Live Wheat price in {record.get('state', 'Unknown')}: ₹{record.get('modal_price', 'Unknown')} per quintal")
            else:
                print("⚠️ API returned success but no data for Wheat today.")
        else:
            print(f"❌ Failed: HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    test_weather()
    test_mandi()
