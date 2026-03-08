"""LLM provider — all calls route through LiteLLM Proxy at :4000."""

from __future__ import annotations

import base64
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from core.src.factorylm.llm.client import llm_async_client

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    async def vision_classify(self, image_path: str, prompt: str) -> dict:
        """Send image + prompt, return parsed JSON with 'category' key."""

    @abstractmethod
    async def text_complete(self, system: str, messages: list[dict]) -> str:
        """Text-only LLM call for escalate_llm nodes."""


class LiteLLMProvider(LLMProvider):
    """Routes all calls through LiteLLM Proxy. Vision uses sonnet, text uses deepseek."""

    def __init__(self, text_model: str = "deepseek-main", vision_model: str = "sonnet-vision"):
        self.text_model = text_model
        self.vision_model = vision_model

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def vision_classify(self, image_path: str, prompt: str) -> dict:
        b64 = self._encode_image(image_path)
        ext = Path(image_path).suffix.lstrip(".").lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
            ext, "image/jpeg"
        )

        response = await llm_async_client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )

        raw = response.choices[0].message.content.strip()
        logger.info("Vision raw response: %s", raw)

        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"category": "unknown", "raw_response": raw}

    async def text_complete(self, system: str, messages: list[dict]) -> str:
        all_messages = [{"role": "system", "content": system}] + messages

        response = await llm_async_client.chat.completions.create(
            model=self.text_model,
            messages=all_messages,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()


def get_provider(provider_name: str | None = None) -> LLMProvider:
    """Return LiteLLM provider. The provider_name arg is kept for backward compat but ignored."""
    return LiteLLMProvider()
