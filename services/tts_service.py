import logging
import httpx
from utils.config import settings

logger = logging.getLogger(__name__)

# Ensure Murf API key is loaded
if not settings.MURF_API_KEY:
    raise ValueError("❌ MURF_API_KEY missing in environment variables.")


async def generate_speech(text: str, voice_id: str = None, max_chars: int = 2900) -> str:
    """
    Generate speech from text using Murf TTS API.

    Args:
        text (str): The text to convert to speech (max 3000 chars).
        voice_id (str, optional): Murf voice ID. Defaults to settings.DEFAULT_VOICE_ID.
        max_chars (int): Safety cutoff to prevent exceeding Murf's 3000-char limit.

    Returns:
        str: Base64-encoded audio string.
    """
    if not text:
        raise ValueError("❌ No text provided for TTS.")

    # Enforce length limit
    if len(text) > max_chars:
        logger.warning(f"⚠️ Text too long for Murf ({len(text)} chars). Truncating.")
        text = text[:max_chars].rstrip() + "..."

    # Fallback voice
    if not voice_id:
        voice_id = getattr(settings, "DEFAULT_VOICE_ID", None) or "en-US-ken"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.murf.ai/v1/speech/generate",
                headers={
                    "api-key": settings.MURF_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "voiceId": voice_id,
                    "format": "mp3",   # or "wav"
                    "base64": True
                }
            )

            if response.status_code != 200:
                logger.error(f"❌ Murf API failed: {response.text}")
                raise ValueError(f"Murf API failed: {response.text}")

            data = response.json()
            audio_b64 = data.get("audioFileBase64")

            if not audio_b64:
                logger.error(f"No base64 audio returned: {data}")
                raise ValueError("No base64 audio returned from Murf")

            logger.info("🎶 Murf TTS generated successfully")
            logger.debug(f"Base64 preview: {audio_b64[:200]}...")

            return audio_b64

    except Exception as e:
        logger.error(f"⚠️ Murf TTS generation failed: {e}")
        raise
