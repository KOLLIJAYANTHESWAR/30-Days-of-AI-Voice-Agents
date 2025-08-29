# main.py

import json
import asyncio
import logging
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from utils.config import settings, override_api_keys
from utils.logging import setup_logger
from routes.transcriber import AssemblyAIStreamingTranscriber
from services.llm_service import get_response_with_persona
from services.tts_service import generate_speech
from services.weather_service import get_detailed_weather
from services.websearch_service import search_web
from services.website_service import detect_website_intent

# -------------------- Setup --------------------
setup_logger()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory="templates")

# -------------------- Static endpoints --------------------
@app.get("/")
def get_homepage():
    return FileResponse(BASE_DIR / "index.html", media_type="text/html")

@app.get("/style.css")
def get_style():
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")

@app.get("/script.js")
def get_script():
    return FileResponse(BASE_DIR / "script.js", media_type="application/javascript")


# -------------------- Runtime API-key overrides --------------------
ALLOWED_OVERRIDE_KEYS = {
    "ASSEMBLYAI_API_KEY",
    "GEMINI_API_KEY",
    "MURF_API_KEY",
    "OPENWEATHER_API_KEY",
    "TAVILY_API_KEY",
    "TAVILY_BASE_URL",
    "DEFAULT_VOICE_ID",
}

def _mask(val: Optional[str]) -> str:
    if not val:
        return "EMPTY"
    if len(val) <= 6:
        return "*" * len(val)
    return f"{val[:3]}***{val[-3:]}"

@app.get("/api/keys")
def get_keys_status():
    """Return which keys are set (masked)."""
    status = {k: _mask(getattr(settings, k, None)) for k in ALLOWED_OVERRIDE_KEYS}
    return JSONResponse({"keys": status})

@app.post("/api/keys")
async def post_keys_overrides(request: Request):
    """
    Accept runtime overrides from the frontend settings modal.
    """
    try:
        payload: Dict[str, Any] = await request.json()
        safe_payload = {k: v for k, v in payload.items() if k in ALLOWED_OVERRIDE_KEYS and v}
        if not safe_payload:
            raise HTTPException(status_code=400, detail="No valid keys provided to override")

        override_api_keys(safe_payload)
        logger.info(f"Runtime overrides applied via HTTP: {list(safe_payload.keys())}")
        return {"ok": True, "overridden": list(safe_payload.keys())}
    except Exception as e:
        logger.exception("Failed to apply key overrides")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------- Per-connection chat history --------------------
SESSION_HISTORY: Dict[str, List[Dict[str, str]]] = {}

def get_session_id(ws: WebSocket) -> str:
    return getattr(ws, "_session_id", None)


# -------------------- WebSocket --------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept connection and create session
    await websocket.accept()
    loop = asyncio.get_running_loop()

    session_id = str(uuid.uuid4())
    setattr(websocket, "_session_id", session_id)
    SESSION_HISTORY[session_id] = []
    await websocket.send_json({"type": "session", "id": session_id})

    logger.info(f"🎤 Client connected (session={session_id})")

    # Initialize transcriber (uses settings.ASSEMBLYAI_API_KEY internally)
    transcriber = AssemblyAIStreamingTranscriber(websocket, loop, sample_rate=16000)

    current_persona = "friend"
    awaiting_city = False

    try:
        # SAFELY receive messages until client disconnects.
        # We'll use a manual receive loop but explicitly handle RuntimeError that
        # Starlette raises when a disconnect message was already processed.
        while True:
            try:
                msg = await websocket.receive()
            except WebSocketDisconnect:
                logger.info(f"⚠️ Client disconnected (session={session_id})")
                break
            except RuntimeError as re:
                # Starlette may raise RuntimeError("Cannot call 'receive' once a disconnect message has been received.")
                if "disconnect" in str(re).lower():
                    logger.info(f"⚠️ Receive called after disconnect (session={session_id}), exiting loop")
                    break
                # Unexpected runtime error — log and break to avoid crash loop
                logger.exception(f"Unexpected RuntimeError on receive (session={session_id}): {re}")
                break
            except Exception as e:
                logger.exception(f"Unexpected exception on websocket.receive (session={session_id}): {e}")
                break

            # Parse message (text or bytes)
            msg_type = None
            data: Dict[str, Any] = {}

            if "text" in msg and msg["text"] is not None:
                # text frame
                raw = msg["text"]
                try:
                    parsed = json.loads(raw)
                    msg_type = parsed.get("type", "text")
                    data = parsed
                except json.JSONDecodeError:
                    msg_type = "text"
                    data = {"text": raw}
            elif "bytes" in msg and msg["bytes"] is not None:
                # binary frame (audio chunk)
                msg_type = "audio"
                data = {"audio": msg["bytes"]}
            else:
                # other control frames (e.g., ping/pong) — ignore
                continue

            # Handle different message types
            if msg_type == "persona_change":
                current_persona = data.get("persona", "friend")
                await websocket.send_json({"type": "info", "message": f"Persona set to {current_persona}"})
                logger.info(f"Persona changed to {current_persona} (session={session_id})")
                continue

            if msg_type == "override_keys":
                # Accept override keys from websocket (script.js sends this)
                keys = data.get("keys", {}) if isinstance(data, dict) else {}
                safe_payload = {k: v for k, v in keys.items() if k in ALLOWED_OVERRIDE_KEYS and v}
                if safe_payload:
                    override_api_keys(safe_payload)
                    logger.info(f"Runtime overrides applied via WS: {list(safe_payload.keys())} (session={session_id})")
                    await websocket.send_json({"type": "info", "message": f"Overrode {len(safe_payload)} key(s)."})
                else:
                    await websocket.send_json({"type": "error", "message": "No valid keys provided to override."})
                continue

            if msg_type == "audio" and data.get("audio"):
                # stream raw audio bytes to AssemblyAI transcriber
                try:
                    transcriber.stream_audio(data["audio"])
                except Exception as e:
                    logger.exception(f"Error forwarding audio to transcriber (session={session_id}): {e}")
                    # inform client but keep session alive
                    await websocket.send_json({"type": "error", "message": "Failed to forward audio to transcriber."})
                continue

            # Text-based flow (user typed text or transcription passed as text)
            text_input: Optional[str] = data.get("text")
            if not text_input:
                continue

            text_input = text_input.strip()
            await websocket.send_json({"type": "transcription", "text": text_input})
            SESSION_HISTORY[session_id].append({"role": "user", "text": text_input})

            # Website intent
            # Website intent
            open_intent = detect_website_intent(text_input)
            if open_intent:
                url = open_intent["url"]
                msg_txt = f"Opening {url} for you."
                await websocket.send_json({"type": "llm_chunk", "text": msg_txt})
                await websocket.send_json({"type": "open_url", "url": url})
                SESSION_HISTORY[session_id].append({"role": "assistant", "text": msg_txt})
                logger.info(f"🌐 Website intent → {url} (session={session_id})")
                continue


            # Weather intent
            text_lower = text_input.lower()
            weather_keywords = ["weather", "temperature", "forecast", "climate", "cold", "fever", "sick"]
            if any(k in text_lower for k in weather_keywords):
                if awaiting_city:
                    city = text_input
                    try:
                        detailed = await get_detailed_weather(city)
                        response_text = f"Here’s the weather for {city}:\n"
                        for day, info in detailed.items():
                            response_text += (
                                f"{day.title()}: Temp {info['temp']}°C, "
                                f"Humidity {info['humidity']}%, "
                                f"Wind {info['wind']} km/h, "
                                f"Condition: {info['condition']}\n"
                            )
                        today = detailed.get("today")
                        if today:
                            cond = (today.get("condition") or "").lower()
                            if "rain" in cond:
                                response_text += "Tip: It may rain today, carry an umbrella. ☔\n"
                            elif "sun" in cond or "clear" in cond:
                                response_text += "Tip: It’s sunny today, wear sunscreen and stay hydrated. 🌞\n"
                        await websocket.send_json({"type": "llm_chunk", "text": response_text})
                        SESSION_HISTORY[session_id].append({"role": "assistant", "text": response_text})
                    except Exception as e:
                        err = f"⚠️ Weather error: {e}"
                        await websocket.send_json({"type": "error", "message": err})
                        SESSION_HISTORY[session_id].append({"role": "assistant", "text": err})
                    finally:
                        awaiting_city = False
                    continue
                else:
                    prompt = "Could you tell me your city name so I can check the weather?"
                    await websocket.send_json({"type": "llm_chunk", "text": prompt})
                    SESSION_HISTORY[session_id].append({"role": "assistant", "text": prompt})
                    awaiting_city = True
                    continue

            # WebSearch intent
            search_keywords = ["search", "who is", "what is", "find", "look up"]
            if any(k in text_lower for k in search_keywords):
                try:
                    summary = await search_web(text_input)
                except Exception as e:
                    summary = f"[WebSearch error: {e}]"
                    logger.error(summary)
                await websocket.send_json({"type": "llm_chunk", "text": summary})
                SESSION_HISTORY[session_id].append({"role": "assistant", "text": summary})
                continue

            # Normal LLM conversation (persona-aware)
            try:
                assistant_text = await get_response_with_persona(SESSION_HISTORY[session_id], persona=current_persona)
            except Exception as e:
                assistant_text = f"⚠️ LLM error: {e}"
                logger.exception("LLM error")

            await websocket.send_json({"type": "llm_chunk", "text": assistant_text})
            SESSION_HISTORY[session_id].append({"role": "assistant", "text": assistant_text})

            # TTS — run in thread so we don't block the loop
            try:
                audio_base64 = await asyncio.to_thread(generate_speech, assistant_text)
                await websocket.send_json({"type": "audio", "data": audio_base64})
            except Exception as tts_err:
                err = f"TTS error: {tts_err}"
                await websocket.send_json({"type": "error", "message": err})
                logger.warning(err)

    except Exception as e:
        # Catch-all (shouldn't be hit often thanks to inner handling)
        logger.exception(f"WebSocket error (session={session_id}): {e}")
    finally:
        # Always try to gracefully close and cleanup
        try:
            transcriber.close()
        except Exception:
            pass
        SESSION_HISTORY.pop(session_id, None)
        logger.info(f"🛑 WebSocket session ended (session={session_id})")
