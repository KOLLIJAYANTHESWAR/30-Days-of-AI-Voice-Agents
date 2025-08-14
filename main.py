import logging
import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Path, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- SDK Imports ---
import assemblyai as aai
import google.generativeai as genai

# --- Load environment variables ---
load_dotenv()

# --- 1. Structured Configuration ---
class Settings(BaseSettings):
    murf_api_key: str = Field(..., alias="MURF_API_KEY")
    assemblyai_api_key: str = Field(..., alias="ASSEMBLYAI_API_KEY")
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    murf_api_url: str = "https://api.murf.ai/v1/speech/generate"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# --- 2. Logging & API Client Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize API clients
try:
    if not settings.assemblyai_api_key or "your_assemblyai_api_key" in settings.assemblyai_api_key:
        raise ValueError("ASSEMBLYAI_API_KEY is not set correctly.")
    aai.settings.api_key = settings.assemblyai_api_key
    transcriber = aai.Transcriber()
    logger.info("AssemblyAI initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize AssemblyAI: {e}")
    transcriber = None

try:
    if not settings.gemini_api_key or "your_new_gemini_api_key" in settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set correctly.")
    genai.configure(api_key=settings.gemini_api_key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("Google Gemini initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Google Gemini: {e}")
    gemini_model = None

# In-memory datastore for chat histories
chat_histories: Dict[str, List[Dict[str, Any]]] = {}

# --- 3. FastAPI Application ---
app = FastAPI(
    title="Revamped AI Voice Agent Backend",
    description="Backend for Day 12+ AI Voice Agent",
    version="2.3.0"
)

# Serve static files (including index.html)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- 4. Pydantic Models ---
class ChatResponse(BaseModel):
    audio_url: str
    user_text: str
    ai_text: str

# --- 5. Endpoints ---
@app.get("/")
async def serve_index():
    """Serve the frontend UI."""
    index_path = os.path.join("static", "index.html")
    if not os.path.exists(index_path):
        logger.error("index.html not found in static directory.")
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return FileResponse(index_path)

@app.post("/agent/chat/{session_id}", response_model=ChatResponse)
async def conversational_chat(
    session_id: str = Path(..., description="The unique ID for the conversation session."),
    file: UploadFile = File(...),
    voice_id: str = Form("en-US-natalie")
):
    logger.info(f"Processing chat for session {session_id} with voice {voice_id}")

    # Step 1: Transcription with AssemblyAI
    if not transcriber:
        raise HTTPException(status_code=503, detail="Transcription service is not available.")
    try:
        audio_bytes = await file.read()
        transcript = transcriber.transcribe(audio_bytes)
        if transcript.error:
            raise Exception(transcript.error)
        user_text = transcript.text.strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="No speech was detected in the audio.")
        logger.info(f"User ({session_id}): {user_text}")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error in transcription: {str(e)}")

    # Step 2: LLM Generation with Gemini
    if not gemini_model:
        raise HTTPException(status_code=503, detail="LLM service is not available.")
    try:
        history = chat_histories.get(session_id, [])
        history.append({"role": "user", "parts": [user_text]})
        
        llm_response = gemini_model.generate_content(history)
        llm_text = llm_response.text.strip() if llm_response.text else ""
        if not llm_text:
            raise Exception("LLM returned an empty response.")
        logger.info(f"AI ({session_id}): {llm_text}")
        
        history.append({"role": "model", "parts": [llm_text]})
        chat_histories[session_id] = history
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating LLM response: {str(e)}")

    # Step 3: Text-to-Speech with Murf
    if not settings.murf_api_key or "your_murf_api_key" in settings.murf_api_key:
        raise HTTPException(status_code=503, detail="TTS service is not configured.")
    try:
        murf_text = llm_text[:2999]
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "api-key": settings.murf_api_key
        }
        payload = {"text": murf_text, "voice_id": voice_id}
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            murf_response = await client.post(settings.murf_api_url, headers=headers, json=payload)
            murf_response.raise_for_status()
        data = murf_response.json()
        audio_url = data.get("audio_url") or data.get("audioFile")
        if not audio_url:
            raise Exception("TTS API did not return an audio URL.")
        
        return ChatResponse(audio_url=audio_url, user_text=user_text, ai_text=llm_text)
    except httpx.HTTPStatusError as e:
        logger.error(f"TTS API error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"TTS service error: {e.response.text}")
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error in TTS generation: {str(e)}")
