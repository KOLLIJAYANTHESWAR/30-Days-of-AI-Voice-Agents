from fastapi import APIRouter, HTTPException, File, UploadFile
from services.stt_service import transcribe_audio
from services.tts_service import generate_speech
from services.llm_service import get_response_with_persona
from services.weather_service import get_weather
import re
import logging
from typing import Dict, List
chat_store: Dict[str, List[Dict[str, str]]] = {}

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# In-memory chat store (replace with DB/Redis for production)
chat_store: dict[str, list[dict[str, str]]] = {}

@router.post("/agent/chat/{session_id}")
async def chat_with_history(
    session_id: str,
    file: UploadFile = File(...),
    persona: str = "friend"
):
    """
    Audio → STT → Persona-aware LLM → Weather analysis → TTS → Return text + audio + history
    """
    allowed_types = {"audio/mp3", "audio/mpeg", "audio/webm", "audio/wav", "audio/ogg"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")

    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # 1️⃣ Transcribe audio
        transcription: str = transcribe_audio(audio_bytes).strip()
        if not transcription:
            raise HTTPException(status_code=400, detail="Failed to transcribe audio")

        logger.info(f"🔥 Transcription: {transcription}")
        user_message = {"role": "user", "text": transcription}

        # 2️⃣ Manage conversation history
        history = chat_store.setdefault(session_id, [])
        history.append(user_message)

        # 3️⃣ Weather intent detection
        text_lower = transcription.lower().strip()
        weather_keywords = ["weather", "temperature", "climate", "forecast", "cold", "hot", "rain", "sunny"]
        if any(k in text_lower for k in weather_keywords):
            logger.info("🌦 Weather-related intent detected")
            city_match = re.search(r'weather in ([a-zA-Z\s]+)', text_lower)
            day_match = re.search(r'(today|tomorrow|yesterday)', text_lower)

            city = city_match.group(1).strip() if city_match else None
            day = day_match.group(1) if day_match else "today"

            if not city:
                ai_reply = "Please provide your city name so I can check the weather."
            else:
                try:
                    # Fetch detailed weather info
                    ai_reply = await get_weather(city, day)
                    # Optionally, append advice like cold remedies or weather-based tips
                    if "cold" in text_lower or "flu" in text_lower:
                        ai_reply += " 💡 Stay warm, drink fluids, and rest well. You'll be fine!"
                    elif "rain" in ai_reply.lower():
                        ai_reply += " ☔ Consider carrying an umbrella or raincoat today."
                    elif "sun" in ai_reply.lower() or "clear" in ai_reply.lower():
                        ai_reply += " 🌞 Remember to wear sunscreen and stay hydrated."
                except Exception as w_err:
                    ai_reply = f"⚠️ Weather service error: {w_err}"
                    logger.error(f"Weather API error: {w_err}")
        else:
            logger.info("🧠 Fallback to persona-aware AI")
            try:
                ai_reply: str = (await get_response_with_persona(history, persona=persona)).strip()
            except Exception as llm_err:
                ai_reply = f"[LLM error: {llm_err}]"
                logger.error(f"LLM error: {llm_err}")

        logger.info(f"🤖 AI Reply: {ai_reply}")

        # 4️⃣ Append AI response to history
        history.append({"role": "assistant", "text": ai_reply})

        # 5️⃣ Convert AI reply to speech
        try:
            audio_b64: str = generate_speech(ai_reply)
        except Exception as tts_err:
            audio_b64 = ""
            logger.warning(f"⚠️ TTS generation failed: {tts_err}")

        # 6️⃣ Return response
        return {
            "text": ai_reply,
            "audio_base64": audio_b64,
            "history": history
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")
