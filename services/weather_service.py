# services/weather_service.py

import os
import httpx
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from utils.config import settings
# Load env variables
load_dotenv()
OPENWEATHER_API_KEY = settings.OPENWEATHER_API_KEY
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not OPENWEATHER_API_KEY:
    raise ValueError("❌ Missing OPENWEATHER_API_KEY in .env")

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


async def get_detailed_weather(city: str) -> dict:
    """
    Fetch weather for yesterday (not available in free plan), today, and tomorrow.
    Uses /weather for current, /forecast for tomorrow.
    """
    try:
        city = city.strip().title()
        logger.info(f"🌍 Fetching detailed weather for city: {city}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            # --- Current weather (today) ---
            resp = await client.get(CURRENT_URL, params={
                "q": city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"
            })

            if resp.status_code != 200:
                logger.error(f"Weather API error {resp.status_code}: {resp.text}")
                return {
                    "today": {
                        "temp": "-",
                        "humidity": "-",
                        "wind": "-",
                        "condition": "City not found"
                    },
                    "yesterday": {
                        "temp": "-",
                        "humidity": "-",
                        "wind": "-",
                        "condition": "Not available on free plan"
                    },
                    "tomorrow": {
                        "temp": "-",
                        "humidity": "-",
                        "wind": "-",
                        "condition": "Not available"
                    }
                }

            data = resp.json()

            def extract_info(src: dict) -> dict:
                """Extracts key weather info safely"""
                return {
                    "temp": src.get("main", {}).get("temp", "-"),
                    "humidity": src.get("main", {}).get("humidity", "-"),
                    "wind": src.get("wind", {}).get("speed", "-"),
                    "condition": src.get("weather", [{}])[0].get("description", "-").capitalize()
                }

            result = {}

            # Today
            result["today"] = extract_info(data)

            # Yesterday (not available in free tier)
            result["yesterday"] = {
                "temp": "-",
                "humidity": "-",
                "wind": "-",
                "condition": "Not available on free plan"
            }

            # --- Tomorrow forecast ---
            forecast_resp = await client.get(FORECAST_URL, params={
                "q": city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"
            })

            if forecast_resp.status_code == 200:
                fdata = forecast_resp.json()
                tomorrow_date = (datetime.utcnow() + timedelta(days=1)).date()
                tomorrow_entry = None

                # Find forecast closest to 12:00 UTC tomorrow
                for entry in fdata.get("list", []):
                    dt = datetime.utcfromtimestamp(entry["dt"])
                    if dt.date() == tomorrow_date and dt.hour == 12:
                        tomorrow_entry = entry
                        break

                # Fallback → first available tomorrow entry
                if not tomorrow_entry:
                    for entry in fdata.get("list", []):
                        dt = datetime.utcfromtimestamp(entry["dt"])
                        if dt.date() == tomorrow_date:
                            tomorrow_entry = entry
                            break

                if tomorrow_entry:
                    result["tomorrow"] = extract_info(tomorrow_entry)
                else:
                    result["tomorrow"] = {
                        "temp": "-",
                        "humidity": "-",
                        "wind": "-",
                        "condition": "Not available"
                    }

            else:
                logger.error(f"Forecast API error {forecast_resp.status_code}: {forecast_resp.text}")
                result["tomorrow"] = {
                    "temp": "-",
                    "humidity": "-",
                    "wind": "-",
                    "condition": "Not available"
                }

            return result

    except Exception as e:
        logger.error(f"Weather service error: {e}")
        return {
            "today": {"temp": "-", "humidity": "-", "wind": "-", "condition": f"Error: {e}"},
            "yesterday": {"temp": "-", "humidity": "-", "wind": "-", "condition": "Not available"},
            "tomorrow": {"temp": "-", "humidity": "-", "wind": "-", "condition": "Not available"},
        }


async def get_weather(city: str, day: str = "today") -> str:
    """
    Returns a user-friendly weather string for today/tomorrow/yesterday.
    """
    detailed = await get_detailed_weather(city)
    info = detailed.get(day, detailed.get("today", {}))

    return (
        f"{day.title()} in {city}: {info['condition']}, "
        f"Temp: {info['temp']}°C, Humidity: {info['humidity']}%, "
        f"Wind: {info['wind']} km/h"
    )
