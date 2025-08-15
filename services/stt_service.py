import logging
import assemblyai as aai

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self, api_key: str):
        if not api_key or "your_assemblyai_api_key" in api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is not set correctly.")
        aai.settings.api_key = api_key
        self.transcriber = aai.Transcriber()
        logger.info("AssemblyAI initialized successfully.")

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        try:
            transcript = self.transcriber.transcribe(audio_bytes)
            if transcript.error:
                raise ValueError(transcript.error)
            text = transcript.text.strip()
            if not text:
                raise ValueError("No speech detected.")
            return text
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
