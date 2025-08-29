from pydantic_settings import BaseSettings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Centralized configuration for API keys and app settings.
    Reads from .env file by default, but allows runtime overrides.
    """

    # Speech-to-text
    ASSEMBLYAI_API_KEY: Optional[str] = None

    # LLM / AI
    GEMINI_API_KEY: Optional[str] = None

    # TTS
    MURF_API_KEY: Optional[str] = None

    # Weather
    OPENWEATHER_API_KEY: Optional[str] = None

    # WebSearch (Tavily)
    TAVILY_API_KEY: Optional[str] = None
    TAVILY_BASE_URL: Optional[str] = None

    # Optional default TTS voice
    DEFAULT_VOICE_ID: str = "en-US-ken"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instantiate global settings object
settings = Settings()


def override_api_keys(overrides: dict):
    """
    Allow runtime overrides for API keys (from frontend).
    Example: override_api_keys({"GEMINI_API_KEY": "user_provided_key"})
    """
    for key, value in overrides.items():
        if hasattr(settings, key) and value:
            setattr(settings, key, value)
            logger.info(f"🔑 Overrode {key} at runtime")
        else:
            logger.warning(f"⚠️ Tried to override unknown or empty key: {key}")
