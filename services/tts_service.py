import logging
import httpx

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, api_key: str, api_url: str):
        if not api_key or "your_murf_api_key" in api_key:
            raise ValueError("MURF_API_KEY is not set correctly.")
        self.api_key = api_key
        self.api_url = api_url

    async def synthesize(self, text: str, voice_id: str) -> str:
        try:
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "api-key": self.api_key
            }
            payload = {"text": text[:2999], "voice_id": voice_id}

            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()

            data = response.json()
            audio_url = data.get("audio_url") or data.get("audioFile")
            if not audio_url:
                raise ValueError("TTS API did not return an audio URL.")
            return audio_url
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise
