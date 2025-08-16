import logging
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Path, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.stt_service import STTService
from services.llm_service import LLMService
from services.tts_service import TTSService

# --- Load environment variables ---
load_dotenv()

# --- Settings ---
class Settings(BaseSettings):
    murf_api_key: str = Field(..., alias="MURF_API_KEY")
    assemblyai_api_key: str = Field(..., alias="ASSEMBLYAI_API_KEY")
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    murf_api_url: str = "https://api.murf.ai/v1/speech/generate"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Service Initialization ---
try:
    stt_service = STTService(settings.assemblyai_api_key)
except Exception as e:
    logger.error(e)
    stt_service = None

try:
    llm_service = LLMService(settings.gemini_api_key)
except Exception as e:
    logger.error(e)
    llm_service = None

try:
    tts_service = TTSService(settings.murf_api_key, settings.murf_api_url)
except Exception as e:
    logger.error(e)
    tts_service = None

# --- In-memory chat store ---
chat_histories: Dict[str, List[Dict[str, Any]]] = {}

# --- FastAPI App ---
app = FastAPI(
    title="AI Voice Agent Backend",
    description="Refactored backend for Day 14 + Day 15 WebSocket",
    version="3.1.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Pydantic Response Model ---
class ChatResponse(BaseModel):
    audio_url: str
    user_text: str
    ai_text: str

# --- Routes ---
@app.get("/")
async def serve_index():
    index_path = os.path.join("static", "index.html")
    if not os.path.exists(index_path):
        logger.error("index.html not found in static directory.")
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return FileResponse(index_path)

@app.post("/agent/chat/{session_id}", response_model=ChatResponse)
async def conversational_chat(
    session_id: str = Path(..., description="The unique conversation ID."),
    file: UploadFile = File(...),
    voice_id: str = Form("en-US-natalie")
):
    logger.info(f"Processing chat for session {session_id} with voice {voice_id}")

    if not stt_service or not llm_service or not tts_service:
        raise HTTPException(status_code=503, detail="One or more services are unavailable.")

    # Step 1: Speech-to-Text
    try:
        audio_bytes = await file.read()
        user_text = stt_service.transcribe_audio(audio_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Step 2: LLM Response
    try:
        history = chat_histories.get(session_id, [])
        history.append({"role": "user", "parts": [user_text]})
        ai_text = llm_service.generate_reply(history)
        history.append({"role": "model", "parts": [ai_text]})
        chat_histories[session_id] = history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Step 3: Text-to-Speech
    try:
        audio_url = await tts_service.synthesize(ai_text, voice_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(audio_url=audio_url, user_text=user_text, ai_text=ai_text)

# --- WebSocket Echo Endpoint (Day 15) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket: client connected")
    await websocket.send_text("👋 Connected to WebSocket echo server. Send me something!")
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"WebSocket received: {data}")
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket: client disconnected")
