import requests
import os
import logging

logger = logging.getLogger(__name__)
MURF_API_KEY = os.getenv("MURF_API_KEY") 

def generate_speech(text: str, voice_id: str = "en-US-ken") -> str:
    response = requests.post(
        "https://api.murf.ai/v1/speech/generate",
        headers={
            "api-key": MURF_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "voiceId": voice_id,
            "format": "mp3",      # you can also use wav
            "base64": True        # ✅ ensures response has base64 audio
        }
    )

    if response.status_code != 200:
        logger.error(f"Murf API failed: {response.text}")
        raise ValueError(f"Murf API failed: {response.text}")

    data = response.json()
    audio_b64 = data.get("audioFileBase64")   # ✅ base64 audio
    if not audio_b64:
        logger.error(f"No base64 audio returned: {data}")
        raise ValueError("No base64 audio returned from Murf")

    # Print so you can screenshot for LinkedIn
    print("🎶 Murf returned audio (base64):")
    print(audio_b64[:200] + "...")  # print first 200 chars for preview

    return audio_b64
