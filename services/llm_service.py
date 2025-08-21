# services/llm_service.py

import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import WebSocket

# Load .env
load_dotenv()

logger = logging.getLogger(__name__)

# Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY missing. Add it to your .env file.")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Model
model = genai.GenerativeModel("gemini-1.5-flash")


def get_response_from_gemini(conversation_history: list) -> str:
    """
    Get a one-shot response from Gemini.
    Used in chat_system.py
    """
    try:
        messages = [
            {"role": "user" if msg["role"] == "user" else "model", "parts": [msg["text"]]}
            for msg in conversation_history
        ]
        response = model.generate_content(messages)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return "⚠️ Sorry, I couldn't process that."


def stream_response(prompt: str):
    """
    Stream Gemini responses to the console (sync generator).
    Used in transcriber.py (Day 19 - CMD only).
    """
    try:
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        logger.error(f"Gemini streaming error: {e}")
        yield "⚠️ Sorry, I couldn't process that."


async def stream_response_from_gemini(prompt: str, websocket: WebSocket):
    """
    Stream Gemini responses in real-time to WebSocket (Day 20).
    """
    try:
        response = model.generate_content(prompt, stream=True)

        accumulated = ""
        for chunk in response:
            if chunk.text:
                accumulated += chunk.text
                await websocket.send_json({
                    "type": "llm_chunk",
                    "text": chunk.text
                })

        await websocket.send_json({
            "type": "llm_response",
            "text": accumulated
        })

    except Exception as e:
        logger.error(f"Gemini streaming error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "⚠️ Gemini could not process your request."
        })
