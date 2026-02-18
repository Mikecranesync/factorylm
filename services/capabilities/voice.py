"""
Voice Capability - Whisper + ElevenLabs
=======================================
Transcribe audio via Groq Whisper, TTS via ElevenLabs.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Sarah


class VoiceCapability:
    """Voice I/O via Groq Whisper and ElevenLabs."""

    def __init__(
        self,
        groq_api_key: str = None,
        elevenlabs_api_key: str = None,
        voice_id: str = None
    ):
        self.groq_api_key = groq_api_key or GROQ_API_KEY
        self.elevenlabs_api_key = elevenlabs_api_key or ELEVENLABS_API_KEY
        self.voice_id = voice_id or ELEVENLABS_VOICE_ID

    async def health(self) -> dict:
        """Check voice capability health."""
        return {
            "status": "ok" if self.groq_api_key else "degraded",
            "transcription": bool(self.groq_api_key),
            "tts": bool(self.elevenlabs_api_key),
        }

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.ogg",
        model: str = "whisper-large-v3"
    ) -> str:
        """
        Transcribe audio to text using Groq Whisper.

        Args:
            audio_bytes: Raw audio data
            filename: Original filename (for MIME type detection)
            model: Whisper model to use

        Returns:
            Transcribed text
        """
        if not self.groq_api_key:
            return "[Transcription unavailable - GROQ_API_KEY not set]"

        try:
            import httpx

            url = "https://api.groq.com/openai/v1/audio/transcriptions"

            files = {
                "file": (filename, audio_bytes, "audio/ogg"),
                "model": (None, model),
                "response_format": (None, "text"),
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    files=files,
                    headers={"Authorization": f"Bearer {self.groq_api_key}"}
                )

                if resp.status_code == 200:
                    return resp.text.strip()
                else:
                    logger.error(f"Transcription error: {resp.status_code} - {resp.text}")
                    return f"[Transcription error: {resp.status_code}]"

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return f"[Transcription error: {e}]"

    async def speak(
        self,
        text: str,
        voice_id: str = None,
        model_id: str = "eleven_turbo_v2_5",
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ) -> Optional[bytes]:
        """
        Convert text to speech using ElevenLabs.

        Args:
            text: Text to convert
            voice_id: ElevenLabs voice ID (default: Sarah)
            model_id: TTS model
            stability: Voice stability (0-1)
            similarity_boost: Voice similarity (0-1)

        Returns:
            Audio bytes (mp3) or None on error
        """
        if not self.elevenlabs_api_key:
            logger.warning("TTS unavailable - ELEVENLABS_API_KEY not set")
            return None

        try:
            import httpx

            voice = voice_id or self.voice_id
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"

            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost
                }
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "xi-api-key": self.elevenlabs_api_key,
                        "Content-Type": "application/json"
                    }
                )

                if resp.status_code == 200:
                    return resp.content
                else:
                    logger.error(f"TTS error: {resp.status_code}")
                    return None

        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return None

    async def list_voices(self) -> list:
        """List available ElevenLabs voices."""
        if not self.elevenlabs_api_key:
            return []

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": self.elevenlabs_api_key}
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        {"id": v["voice_id"], "name": v["name"]}
                        for v in data.get("voices", [])
                    ]
                return []

        except Exception as e:
            logger.error(f"List voices failed: {e}")
            return []
