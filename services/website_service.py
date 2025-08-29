# services/website_service.py

import re
from typing import Optional

# Common websites mapping (keys normalized automatically)
RAW_WEBSITE_MAP = {
    "github": "https://github.com",
    "youtube": "https://youtube.com",
    "yt": "https://youtube.com",
    "linkedin": "https://linkedin.com",
    "chatgpt": "https://chat.openai.com",
    "gemini": "https://gemini.google.com",
    "grok": "https://x.com/i/grok",  # Elon Musk's Grok AI
    "x": "https://x.com",  # Twitter/X
    "twitter": "https://x.com",
    "instagram": "https://instagram.com",
    "threads": "https://threads.net",
    "murf": "https://murf.ai",
    "assembly ai": "https://www.assemblyai.com",
    "oracle": "https://www.oracle.com",
    "udemy": "https://www.udemy.com",
    "aws": "https://aws.amazon.com",
    "amazon web services": "https://aws.amazon.com",
    "google cloud": "https://cloud.google.com",
    "gcp": "https://cloud.google.com",
    "azure": "https://azure.microsoft.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "stackoverflow": "https://stackoverflow.com",
    "google": "https://google.com",
}

def normalize_site_name(name: str) -> str:
    """Normalize site names (remove spaces, lowercase)."""
    return name.lower().strip().replace(" ", "")

# Normalize the WEBSITE_MAP keys upfront
WEBSITE_MAP = {normalize_site_name(k): v for k, v in RAW_WEBSITE_MAP.items()}

def detect_website_intent(text: str) -> Optional[dict]:
    """
    Detect if user wants to open a website.
    Returns { "type": "open_url", "url": ... } for frontend.
    """
    text = text.lower().strip()

    # Keywords that trigger site opening
    trigger_words = ["open", "go to", "visit", "launch"]

    if any(word in text for word in trigger_words):
        # Extract potential site name (last word after trigger)
        site_candidate = re.sub(r".*(open|go to|visit|launch)\s+", "", text).strip()
        site_candidate = site_candidate.replace("website", "").replace("please", "").strip()

        normalized = normalize_site_name(site_candidate)

        # Direct match in mapping
        url = WEBSITE_MAP.get(normalized)

        # Handle explicit domains (like youtube.com)
        if not url and "." in normalized:
            if not normalized.startswith("http"):
                url = f"https://{normalized}"
            else:
                url = normalized

        # Fallback: Google search
        if not url:
            url = f"https://www.google.com/search?q={site_candidate.replace(' ', '+')}"

        return {"type": "open_url", "url": url}

    return None
