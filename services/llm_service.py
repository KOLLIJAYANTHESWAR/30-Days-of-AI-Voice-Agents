# services/llm_service.py

import os
import logging
from typing import Iterable
import re
from dotenv import load_dotenv
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

import google.generativeai as genai
from services.weather_service import get_detailed_weather  # Updated weather API
from personas import friend, funny, teacher

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Gemini API key ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY missing. Add it to your .env file.")

genai.configure(api_key=GEMINI_API_KEY)

# Gemini model
model = genai.GenerativeModel("gemini-1.5-flash")

# --- Persona prompts ---
personas_map = {
    "friend": friend.friend_prompt,
    "funny": funny.funny_prompt,
    "teacher": teacher.teacher_prompt,
}

# ---------- Helpers ----------
def get_last_user_message(conversation_history: list[dict]) -> str:
    if not conversation_history:
        return ""
    return conversation_history[-1].get("text", "") or ""

def looks_like_weather(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ("weather", "temperature", "forecast", "climate", "cold", "fever", "sick", "flu"))

# ---------- Main APIs ----------
async def get_response_with_persona(conversation_history: list[dict], persona: str = "friend") -> str:
    """
    Async to allow awaiting weather without blocking the event loop.
    """
    try:
        user_message = get_last_user_message(conversation_history)

        # 🌦 Weather / cold-flu detection
        if looks_like_weather(user_message):
            # Extract city
            city_match = re.search(r'weather in (\w+)', user_message.lower())
            city = city_match.group(1) if city_match else None

            if not city:
                return "Could you tell me your city so I can check the weather?"

            detailed_weather = await get_detailed_weather(city)
            response_text = f"Weather for {city}:\n"
            for day, info in detailed_weather.items():
                response_text += (
                    f"{day.title()}: Temp {info['temp']}°C, Humidity {info['humidity']}%, "
                    f"Wind {info['wind']} km/h, Condition: {info['condition']}\n"
                )

            # Health advice for mild cold/flu
            if any(k in user_message.lower() for k in ["cold", "fever", "sick", "flu"]):
                response_text += (
                    "It seems like a mild cold or flu due to weather conditions. "
                    "Drink warm water, rest well, and you'll be fine! 😊\n"
                )

            # Daily suggestions
            today = detailed_weather.get("today")
            if today:
                cond = today['condition'].lower()
                if "rain" in cond:
                    response_text += "Tip: It may rain today, carry an umbrella. ☔\n"
                elif "sun" in cond or "clear" in cond:
                    response_text += "Tip: It’s sunny today, wear sunscreen and stay hydrated. 🌞\n"

            return response_text

        # Normal persona prompt for LLM
        prompt_func = personas_map.get(persona, friend.friend_prompt)
        prompt = prompt_func(user_message)

        # Build history for Gemini
        messages = [
            {"role": ("user" if msg.get("role") == "user" else "model"), "parts": [msg.get("text", "")]}
            for msg in conversation_history[:-1]
        ]
        messages.append({"role": "user", "parts": [prompt]})

        # Call Gemini
        response = model.generate_content(messages)
        return (getattr(response, "text", None) or str(response)).strip()

    except Exception as e:
        if persona not in personas_map:
            logger.warning(f"Unknown persona: {persona}, defaulting to friend.")
        logger.error(f"get_response_with_persona error: {e}")
        return "⚠️ Sorry, I couldn't process that."


def stream_response(conversation_history: list[dict], persona: str = "friend") -> Iterable[str]:
    """
    Streaming generator for non-weather chats.
    """
    try:
        user_message = get_last_user_message(conversation_history)

        prompt_func = personas_map.get(persona, friend.friend_prompt)
        prompt = prompt_func(user_message)

        messages = [
            {"role": ("user" if msg.get("role") == "user" else "model"), "parts": [msg.get("text", "")]}
            for msg in conversation_history[:-1]
        ]
        messages.append({"role": "user", "parts": [prompt]})

        response_stream = model.generate_content(messages, stream=True)
        for chunk in response_stream:
            text_chunk = getattr(chunk, "text", None) or str(chunk)
            if text_chunk:
                yield text_chunk

    except Exception as e:
        logger.error(f"Gemini streaming persona error: {e}")
        yield "⚠️ Sorry, I couldn't process that."


async def stream_response_from_gemini(conversation_history: list, websocket: WebSocket, persona: str = "friend"):
    """
    Stream Gemini responses in real-time to WebSocket safely.
    """
    try:
        await websocket.accept()
        user_message = get_last_user_message(conversation_history)

        # Weather short-circuit
        if looks_like_weather(user_message):
            city_match = re.search(r'weather in (\w+)', user_message.lower())
            city = city_match.group(1) if city_match else None

            if not city:
                await websocket.send_json({"type": "llm_response", "text": "Could you tell me your city to check the weather?"})
                return

            detailed_weather = await get_detailed_weather(city)
            response_text = f"Weather for {city}:\n"
            for day, info in detailed_weather.items():
                response_text += (
                    f"{day.title()}: Temp {info['temp']}°C, Humidity {info['humidity']}%, "
                    f"Wind {info['wind']} km/h, Condition: {info['condition']}\n"
                )

            # Health advice for cold/flu
            if any(k in user_message.lower() for k in ["cold", "fever", "sick", "flu"]):
                response_text += (
                    "It seems like a mild cold or flu due to weather conditions. "
                    "Drink warm water, rest well, and you'll be fine! 😊\n"
                )

            # Daily suggestions
            today = detailed_weather.get("today")
            if today:
                cond = today['condition'].lower()
                if "rain" in cond:
                    response_text += "Tip: It may rain today, carry an umbrella. ☔\n"
                elif "sun" in cond or "clear" in cond:
                    response_text += "Tip: It’s sunny today, wear sunscreen and stay hydrated. 🌞\n"

            await websocket.send_json({"type": "llm_response", "text": response_text})
            return

        # Normal Gemini streaming
        prompt_func = personas_map.get(persona, friend.friend_prompt)
        prompt = prompt_func(user_message)

        messages = [
            {"role": ("user" if msg.get("role") == "user" else "model"), "parts": [msg.get("text", "")]}
            for msg in conversation_history[:-1]
        ]
        messages.append({"role": "user", "parts": [prompt]})

        accumulated = ""
        response_stream = model.generate_content(messages, stream=True)

        for chunk in response_stream:
            text_chunk = getattr(chunk, "text", None) or str(chunk)
            if not text_chunk:
                continue

            accumulated += text_chunk
            try:
                await websocket.send_json({"type": "llm_chunk", "text": text_chunk})
            except WebSocketDisconnect:
                logger.warning("Client disconnected during streaming.")
                break
            except Exception as send_err:
                logger.error(f"WebSocket send error: {send_err}")
                break

        # Final response
        try:
            await websocket.send_json({"type": "llm_response", "text": accumulated})
        except WebSocketDisconnect:
            logger.warning("Client disconnected before final send.")
        except Exception as send_err:
            logger.error(f"WebSocket send error: {send_err}")

    except Exception as e:
        logger.error(f"Gemini streaming persona error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "⚠️ Gemini could not process your request."})
        except Exception:
            pass

# Backward compatibility alias
get_response_from_gemini = get_response_with_persona
