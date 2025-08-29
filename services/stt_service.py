# services/stt_service.py

import os
import io
import logging
import assemblyai as aai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Set AssemblyAI API key
AAPI_KEY = os.getenv("ASSEMBLYAI_API_KEY")
if not AAPI_KEY:
    raise ValueError("❌ ASSEMBLYAI_API_KEY missing in environment variables.")
aai.settings.api_key = AAPI_KEY


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribes audio bytes (mp3, wav, ogg, webm) using AssemblyAI.

    Args:
        audio_bytes (bytes): Raw audio bytes uploaded by user.

    Returns:
        str: The transcribed text.

    Raises:
        ValueError: If AssemblyAI returns an error.
        Exception: For other transcription failures.
    """
    try:
        # Initialize AssemblyAI client
        client = aai.Client(api_key=AAPI_KEY)

        # Upload audio bytes to AssemblyAI
        audio_file = io.BytesIO(audio_bytes)
        audio_url = client.upload(audio_file)
        if not audio_url:
            raise ValueError("Failed to upload audio to AssemblyAI.")

        # Request transcription
        transcript = client.transcribe(audio_url)

        # Check for errors
        if transcript.status == "error":
            logger.error(f"AssemblyAI error: {transcript.error}")
            raise ValueError(f"AssemblyAI error: {transcript.error}")

        return transcript.text or ""

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise
