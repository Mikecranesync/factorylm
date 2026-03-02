"""
Groq client for equipment photo analysis, voice transcription, and text generation.

Uses AsyncGroq for non-blocking calls:
- Vision: meta-llama/llama-4-scout-17b-16e-instruct (128K context, up to 5 images)
- Text: llama-3.3-70b-versatile
- Voice: whisper-large-v3-turbo (transcription) + text model for response
"""

import base64
import json
import io
import logging
from typing import Optional

from groq import AsyncGroq

from prompts import DIAGNOSIS_PROMPT, WORK_ORDER_PROMPT

logger = logging.getLogger(__name__)

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
TEXT_MODEL = "llama-3.3-70b-versatile"
WHISPER_MODEL = "whisper-large-v3-turbo"


class GroqClient:
    """Async Groq client for vision, text, and voice."""

    def __init__(self, api_key: str):
        self.client = AsyncGroq(api_key=api_key)
        logger.info(f"Groq client initialized — vision={VISION_MODEL}, text={TEXT_MODEL}")

    async def analyze_image(self, image_bytes: bytes, prompt: str = DIAGNOSIS_PROMPT) -> str:
        """Analyze an image with a text prompt using Llama 4 Scout vision."""
        try:
            b64 = base64.b64encode(image_bytes).decode()
            response = await self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }],
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq image analysis failed: {e}")
            return f"Analysis failed: {e}"

    async def analyze_voice(self, audio_bytes: bytes, prompt: str, mime_type: str = "audio/ogg") -> str:
        """Transcribe audio with Whisper, then generate a contextual response."""
        try:
            # Step 1: Transcribe with Whisper
            transcript = await self.client.audio.transcriptions.create(
                file=("voice.ogg", io.BytesIO(audio_bytes)),
                model=WHISPER_MODEL,
            )
            transcribed_text = transcript.text
            logger.info(f"Whisper transcription: {transcribed_text[:100]}")

            # Step 2: Send transcript + context to text model
            response = await self.client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": transcribed_text},
                ],
                max_tokens=512,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq voice analysis failed: {e}")
            return f"Voice processing failed: {e}"

    async def generate_text(self, context_parts: list[str]) -> str:
        """Generate a text response from context parts (system + user messages)."""
        try:
            # First part is system prompt, rest are user context
            system = context_parts[0] if context_parts else "You are a helpful industrial AI assistant."
            user_content = "\n\n".join(context_parts[1:]) if len(context_parts) > 1 else ""

            response = await self.client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=512,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq text generation failed: {e}")
            return f"Text generation failed: {e}"

    async def generate_work_order_json(self, diagnosis: str) -> Optional[dict]:
        """Generate a structured work order JSON from a diagnosis."""
        try:
            response = await self.client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": WORK_ORDER_PROMPT},
                    {"role": "user", "content": f"Diagnosis:\n{diagnosis}"},
                ],
                max_tokens=512,
            )
            text = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception as e:
            logger.error(f"Work order generation failed: {e}")
            return None
