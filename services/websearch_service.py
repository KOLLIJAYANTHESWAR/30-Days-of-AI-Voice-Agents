# services/websearch_service.py

import logging
import asyncio
from tavily import TavilyClient
from utils.config import settings

logger = logging.getLogger(__name__)

if not settings.TAVILY_API_KEY:
    raise ValueError("❌ TAVILY_API_KEY is missing. Please provide it in .env or UI config.")

client = TavilyClient(api_key=settings.TAVILY_API_KEY)

async def search_web(query: str, max_results: int = 3, max_chars: int = 2500) -> str:
    """
    Query Tavily WebSearch API and return a concise summary.
    Limits result size so total response stays < max_chars (safe for TTS).
    """
    try:
        # Run sync Tavily search in thread for async safety
        data = await asyncio.to_thread(client.search, query=query)

        results = data.get("results", [])
        if not results:
            return "No relevant information found on the web."

        # Limit results
        results = results[:max_results]

        # Build concise summary
        summary_parts = []
        for r in results:
            title = r.get("title", "No title").strip()
            snippet = r.get("content", "No snippet").strip()

            # Trim snippet to ~200 chars max
            if len(snippet) > 200:
                snippet = snippet[:200].rstrip() + "..."

            url = r.get("url", "")
            summary_parts.append(f"- {title}: {snippet} ({url})")

        summary = "\n".join(summary_parts)

        # Enforce global character limit (Murf safe)
        if len(summary) > max_chars:
            summary = summary[:max_chars].rstrip() + "..."

        return summary

    except Exception as e:
        logger.error(f"WebSearch error: {e}")
        return f"[WebSearch error: {e}]"
