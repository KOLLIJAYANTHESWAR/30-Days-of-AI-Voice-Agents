import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        if not api_key or "your_new_gemini_api_key" in api_key:
            raise ValueError("GEMINI_API_KEY is not set correctly.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        logger.info("Google Gemini initialized successfully.")

    def generate_reply(self, history: list) -> str:
        try:
            llm_response = self.model.generate_content(history)
            text = llm_response.text.strip() if llm_response.text else ""
            if not text:
                raise ValueError("LLM returned an empty response.")
            return text
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
