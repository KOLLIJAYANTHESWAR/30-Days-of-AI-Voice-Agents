# routes/transcriber.py

import asyncio
import base64
import re
import logging
from fastapi import WebSocket, WebSocketDisconnect
import httpx
import assemblyai as aai
from assemblyai.streaming.v3 import (
    StreamingClient, StreamingClientOptions,
    StreamingParameters, StreamingSessionParameters,
    StreamingEvents, BeginEvent, TurnEvent,
    TerminationEvent, StreamingError
)
from services.llm_service import stream_response
from services.weather_service import get_weather
from services.website_service import detect_website_intent
from utils.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Set AssemblyAI API key
aai.settings.api_key = settings.ASSEMBLYAI_API_KEY


# Set AssemblyAI API key dynamically inside class, not at import
class AssemblyAIStreamingTranscriber:
    def __init__(self, websocket: WebSocket, loop, sample_rate: int = 16000):
        self.websocket = websocket
        self.loop = loop
        self.conversation_history = []

        aai.settings.api_key = settings.ASSEMBLYAI_API_KEY

        self.client = StreamingClient(
            StreamingClientOptions(
                api_key=aai.settings.api_key,
                url=f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={sample_rate}"
            )
        )



        # Attach event handlers
        self.client.on(StreamingEvents.Begin, self.on_begin)
        self.client.on(StreamingEvents.Turn, self.on_turn)
        self.client.on(StreamingEvents.Termination, self.on_termination)
        self.client.on(StreamingEvents.Error, self.on_error)

        # Connect to AssemblyAI streaming
        self.client.connect(
            StreamingParameters(sample_rate=sample_rate, format_turns=False)
        )


    def on_begin(self, client, event: BeginEvent):
        logger.info(f"🎤 Session started: {event.id}")

    def on_turn(self, client, event: TurnEvent):
        transcript = event.transcript.strip()
        logger.info(f"{transcript} (end_of_turn={event.end_of_turn})")

        if event.end_of_turn and transcript:
            self.conversation_history.append({"role": "user", "text": transcript})
            asyncio.run_coroutine_threadsafe(
                self.safe_send({"type": "transcript", "text": transcript}),
                self.loop
            )
            asyncio.run_coroutine_threadsafe(
                self.safe_send({"type": "transcription", "text": transcript}),
                self.loop
            )
            asyncio.run_coroutine_threadsafe(
                self.handle_response(transcript), self.loop
            )

            # Re-enable formatted turns if disabled
            try:
                if not event.turn_is_formatted:
                    client.set_params(StreamingSessionParameters(format_turns=True))
            except Exception as e:
                logger.warning(f"Could not set format_turns: {e}")

    async def handle_response(self, transcript: str):
        """
        Handle website intents, weather checks, LLM streaming, and TTS.
        """
        accumulated = ""

        # 🌐 Web search intent
        search_match = re.search(r"(search for|look up|find|search)\s+(.*)", transcript, re.IGNORECASE)
        if search_match:
            query = search_match.group(2).strip()
            if query.lower().startswith("on "):
                query = query[3:].strip()
            try:
                from services.websearch_service import search_web
                accumulated = await search_web(query)
                await self.safe_send({"type": "llm_response", "text": accumulated})
                await self.send_to_murf(accumulated)
                return
            except Exception as e:
                accumulated = f"⚠️ WebSearch error: {e}"
                await self.safe_send({"type": "error", "message": str(e)})
                return

        # 🖥 Website intent check
        site_intent = detect_website_intent(transcript)
        if site_intent:
            await self.safe_send(site_intent)  # sends { "type": "open_url", "url": ... }
            accumulated = f"Opening {site_intent['url']}..."
            await self.safe_send({"type": "llm_response", "text": accumulated})
            await self.send_to_murf(accumulated)
            return

        # 🌦 Weather check
        weather_match = re.search(r"weather in ([a-zA-Z\s]+)", transcript, re.IGNORECASE)
        if weather_match:
            city = weather_match.group(1).strip()
            try:
                accumulated = await get_weather(city)
            except Exception as e:
                accumulated = f"⚠️ Weather error: {e}"
        else:
            # Normal LLM streaming response
            try:
                async for chunk in self.stream_llm_response(transcript):
                    accumulated += chunk
                    await self.safe_send({"type": "llm_chunk", "text": chunk})
            except Exception as e:
                accumulated = f"⚠️ LLM error: {e}"
                await self.safe_send({"type": "error", "message": str(e)})

        # Save assistant reply
        self.conversation_history.append({"role": "assistant", "text": accumulated})

        # Send final response
        await self.safe_send({"type": "llm_response", "text": accumulated})

        # TTS via Murf
        await self.send_to_murf(accumulated)

######################################################################################################################
    async def stream_llm_response(self, user_input: str):
        """
        Async wrapper for streaming chunks from LLM.
        """
        self.conversation_history.append({"role": "user", "text": user_input})
        for chunk in stream_response(self.conversation_history):
            yield chunk

    def on_termination(self, client, event: TerminationEvent):
        logger.info(f"🛑 Session terminated after {event.audio_duration_seconds} s")

    def on_error(self, client, error: StreamingError):
        logger.error(f"❌ AssemblyAI Error: {error}")

    def stream_audio(self, audio_chunk: bytes):
        self.client.stream(audio_chunk)

    def close(self):
        self.client.disconnect(terminate=True)

    async def safe_send(self, message: dict):
        """Send JSON to WebSocket safely, ignoring closed connections."""
        try:
            await self.websocket.send_json(message)
        except (WebSocketDisconnect, RuntimeError):
            logger.warning("⚠️ WebSocket disconnected, cannot send message")
        except Exception as e:
            logger.error(f"⚠️ WebSocket send error: {e}")

    async def send_to_murf(self, text: str):
        """Generate Murf TTS audio and send base64 to client."""
        try:
            voice_id = getattr(settings, "DEFAULT_VOICE_ID", None) or "en-US-ken"
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
                        "format": "mp3",
                        "base64": True
                    }
                )

                if response.status_code != 200:
                    await self.safe_send({"type": "error", "message": f"Murf API error: {response.text}"})
                    return

                data = response.json()
                audio_b64 = data.get("audioFileBase64")
                audio_url = data.get("audioFile")

                # Fallback: fetch audio from URL if base64 missing
                if not audio_b64 and audio_url:
                    fetch = await client.get(audio_url)
                    if fetch.status_code == 200:
                        audio_b64 = base64.b64encode(fetch.content).decode("utf-8")
                    else:
                        await self.safe_send({"type": "error", "message": f"Failed to fetch Murf audio: {fetch.status_code}"})
                        return

                if audio_b64:
                    await self.safe_send({"type": "murf_audio", "audio": audio_b64})
                    logger.info("🔊 Murf audio sent to client")
                else:
                    await self.safe_send({"type": "error", "message": "No audio returned from Murf"})

        except Exception as e:
            logger.error(f"⚠️ Murf REST error: {e}")
            await self.safe_send({"type": "error", "message": "Murf audio streaming failed"})
