import asyncio
import assemblyai as aai
from assemblyai.streaming.v3 import (
    StreamingClient, StreamingClientOptions,
    StreamingParameters, StreamingSessionParameters,
    StreamingEvents, BeginEvent, TurnEvent,
    TerminationEvent, StreamingError
)
from fastapi import WebSocket
import websockets
import json
import requests, base64, time

from utils.config import settings
from services.llm_service import stream_response

# Set AssemblyAI API key from .env
aai.settings.api_key = settings.ASSEMBLYAI_API_KEY


class AssemblyAIStreamingTranscriber:
    def __init__(self, websocket: WebSocket, loop, sample_rate=16000):
        self.websocket = websocket
        self.loop = loop  # main FastAPI event loop

        self.client = StreamingClient(
            StreamingClientOptions(
                api_key=aai.settings.api_key,
                api_host="streaming.assemblyai.com"
            )
        )
        self.client.on(StreamingEvents.Begin, self.on_begin)
        self.client.on(StreamingEvents.Turn, self.on_turn)
        self.client.on(StreamingEvents.Termination, self.on_termination)
        self.client.on(StreamingEvents.Error, self.on_error)

        self.client.connect(
            StreamingParameters(sample_rate=sample_rate, format_turns=False)
        )

    def on_begin(self, client, event: BeginEvent):
        print(f"🎤 Session started: {event.id}")

    def on_turn(self, client, event: TurnEvent):
        # Print transcript to console (partial or final)
        print(f"{event.transcript} (end_of_turn={event.end_of_turn})")

        if event.end_of_turn:
            # Send final transcript to frontend
            try:
                asyncio.run_coroutine_threadsafe(
                    self.websocket.send_json({
                        "type": "transcript",
                        "text": event.transcript
                    }),
                    self.loop
                )
            except Exception as e:
                print("⚠️ Failed to send transcript:", e)

            # Day 19: Stream LLM response to CMD
            if event.transcript.strip():
                print("\n🎤 Final Transcript:", event.transcript)
                print("🤖 LLM Response (streaming):")

                accumulated = ""
                for token in stream_response(event.transcript):
                    print(token, end="", flush=True)  # token-by-token streaming
                    accumulated += token

                print("\n--- Final Response ---")
                print(accumulated)

                # Day 20: Send LLM response to Murf via WebSocket
                asyncio.run(self.send_to_murf(accumulated))

            # Keep turn formatting logic
            if not event.turn_is_formatted:
                client.set_params(StreamingSessionParameters(format_turns=True))

    def on_termination(self, client, event: TerminationEvent):
        print(f"🛑 Session terminated after {event.audio_duration_seconds} s")

    def on_error(self, client, error: StreamingError):
        print("❌ Error:", error)

    def stream_audio(self, audio_chunk: bytes):
        self.client.stream(audio_chunk)

    def close(self):
        self.client.disconnect(terminate=True)

    async def send_to_murf(self, text: str):
        """
        Send LLM response to Murf via REST API (not WS) and print base64 audio.
        """
        try:
            response = requests.post(
                "https://api.murf.ai/v1/speech/generate",
                headers={
                    "api-key": settings.MURF_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text,
                    "voiceId": "en-US-ken"  # Murf voice ID
                }
            )

            if response.status_code != 200:
                print("⚠️ Murf API error:", response.text)
                return

            data = response.json()
            audio_file_url = data.get("audioFile")
            if not audio_file_url:
                print("⚠️ No audio file returned from Murf")
                return

            # Poll until audio file is ready
            for _ in range(10):
                audio_response = requests.get(audio_file_url)
                if audio_response.status_code == 200:
                    audio_b64 = base64.b64encode(audio_response.content).decode("utf-8")
                    print("\n🔊 Murf base64 audio received:")
                    print(audio_b64[:100], "...")  # print first 100 chars only
                    return
                time.sleep(1)

            print("⚠️ Murf audio not ready after 10s")

        except Exception as e:
            print("⚠️ Murf REST error:", e)