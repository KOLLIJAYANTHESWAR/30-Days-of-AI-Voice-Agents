from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ASSEMBLYAI_API_KEY: str
    GEMINI_API_KEY: str
    MURF_API_KEY: str  # Added for Day 20 streaming to Murf

    class Config:
        env_file = ".env"
        extra = "ignore"  # ✅ ignore any extra env vars

# Load settings
settings = Settings()