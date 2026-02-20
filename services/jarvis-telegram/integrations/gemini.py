# Restored from: feature/rideview-continuous-improvement:projects/factorylm/puppeteer/bot.py
"""
Gemini Vision client for equipment photo analysis and voice processing.
"""

import json
import logging
from typing import Optional

import google.generativeai as genai

from ..prompts import DIAGNOSIS_PROMPT, WORK_ORDER_PROMPT

logger = logging.getLogger(__name__)

# Gemini 2.5 Flash — current multimodal model
MODEL_NAME = "gemini-2.5-flash"


class GeminiClient:
    """Wraps google-generativeai SDK for image/audio analysis."""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(MODEL_NAME)
        logger.info(f"Gemini client initialized with model {MODEL_NAME}")

    async def analyze_image(self, image_bytes: bytes, prompt: str = DIAGNOSIS_PROMPT) -> str:
        """Analyze an image with a text prompt."""
        try:
            response = self.model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_bytes},
            ])
            return response.text
        except Exception as e:
            logger.error(f"Gemini image analysis failed: {e}")
            return f"Analysis failed: {e}"

    async def analyze_voice(self, audio_bytes: bytes, prompt: str, mime_type: str = "audio/ogg") -> str:
        """Analyze a voice note with context prompt."""
        try:
            response = self.model.generate_content([
                prompt,
                {"mime_type": mime_type, "data": audio_bytes},
            ])
            return response.text
        except Exception as e:
            logger.error(f"Gemini voice analysis failed: {e}")
            return f"Voice processing failed: {e}"

    async def generate_work_order_json(self, diagnosis: str) -> Optional[dict]:
        """Generate a structured work order JSON from a diagnosis."""
        try:
            response = self.model.generate_content([
                WORK_ORDER_PROMPT,
                f"Diagnosis:\n{diagnosis}",
            ])
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception as e:
            logger.error(f"Work order generation failed: {e}")
            return None
