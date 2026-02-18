"""
Photos Capability - Vision Analysis
===================================
Analyze images using OpenAI GPT-4V or Groq.
"""

import os
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


class PhotosCapability:
    """Vision analysis via OpenAI or Groq."""

    def __init__(
        self,
        openai_api_key: str = None,
        groq_api_key: str = None
    ):
        self.openai_api_key = openai_api_key or OPENAI_API_KEY
        self.groq_api_key = groq_api_key or GROQ_API_KEY

    async def health(self) -> dict:
        """Check vision capability health."""
        has_vision = bool(self.openai_api_key or self.groq_api_key)
        return {
            "status": "ok" if has_vision else "unavailable",
            "openai": bool(self.openai_api_key),
            "groq": bool(self.groq_api_key),
        }

    async def analyze(
        self,
        image_bytes: bytes,
        prompt: str = "Describe this image concisely.",
        max_tokens: int = 500
    ) -> str:
        """
        Analyze an image using vision AI.

        Args:
            image_bytes: Raw image data
            prompt: Analysis prompt
            max_tokens: Max response tokens

        Returns:
            Analysis text
        """
        # Try OpenAI first (better quality)
        if self.openai_api_key:
            result = await self._analyze_openai(image_bytes, prompt, max_tokens)
            if result and not result.startswith("["):
                return result

        # Fallback to Groq
        if self.groq_api_key:
            result = await self._analyze_groq(image_bytes, prompt, max_tokens)
            if result:
                return result

        return "[Vision analysis unavailable - no API keys configured]"

    async def _analyze_openai(
        self,
        image_bytes: bytes,
        prompt: str,
        max_tokens: int
    ) -> Optional[str]:
        """Analyze image with OpenAI GPT-4 Vision."""
        try:
            import httpx

            b64_image = base64.b64encode(image_bytes).decode("utf-8")

            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}",
                                    "detail": "auto"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens
            }

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.openai_api_key}"}
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenAI vision error: {resp.status_code} - {resp.text}")
                    return f"[Vision error: {resp.status_code}]"

        except Exception as e:
            logger.error(f"OpenAI vision failed: {e}")
            return None

    async def _analyze_groq(
        self,
        image_bytes: bytes,
        prompt: str,
        max_tokens: int
    ) -> Optional[str]:
        """Analyze image with Groq (if they support vision)."""
        # Note: Groq doesn't have vision yet, but leaving placeholder
        try:
            import httpx

            b64_image = base64.b64encode(image_bytes).decode("utf-8")

            payload = {
                "model": "llava-v1.5-7b-4096-preview",  # Groq vision model
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens
            }

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.groq_api_key}"}
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.debug(f"Groq vision not available: {resp.status_code}")
                    return None

        except Exception as e:
            logger.debug(f"Groq vision failed: {e}")
            return None

    async def identify_equipment(self, image_bytes: bytes) -> str:
        """Identify factory equipment in an image."""
        return await self.analyze(
            image_bytes,
            "Identify any factory equipment, machinery, or industrial components visible. "
            "Include model numbers if visible. Be concise."
        )

    async def read_display(self, image_bytes: bytes) -> str:
        """Read values from an equipment display or HMI."""
        return await self.analyze(
            image_bytes,
            "Read any text, numbers, or values visible on displays, screens, or labels. "
            "Format as a simple list. Be precise with numbers."
        )

    async def diagnose_visual(self, image_bytes: bytes, context: str = "") -> str:
        """Diagnose issues visible in an image."""
        prompt = (
            "Analyze this image for any visible issues, problems, or abnormalities. "
            "Look for: damage, wear, misalignment, leaks, improper connections, "
            "error indicators, warning lights."
        )
        if context:
            prompt += f"\n\nContext: {context}"

        return await self.analyze(image_bytes, prompt, max_tokens=800)
