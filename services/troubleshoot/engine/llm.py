"""LLM provider abstraction for vision and text calls."""

from __future__ import annotations

import base64
import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    async def vision_classify(self, image_path: str, prompt: str) -> dict:
        """Send image + prompt, return parsed JSON with 'category' key."""

    @abstractmethod
    async def text_complete(self, system: str, messages: list[dict]) -> str:
        """Text-only LLM call for escalate_llm nodes."""


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str | None = None,
        vision_model: str = "gpt-4o-mini",
        text_model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.vision_model = vision_model
        self.text_model = text_model

    def _get_client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.api_key)

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def vision_classify(self, image_path: str, prompt: str) -> dict:
        client = self._get_client()
        b64 = self._encode_image(image_path)
        ext = Path(image_path).suffix.lstrip(".").lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
            ext, "image/jpeg"
        )

        response = await client.chat.completions.create(
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

        # Try to parse JSON from the response
        try:
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"category": "unknown", "raw_response": raw}

    async def text_complete(self, system: str, messages: list[dict]) -> str:
        client = self._get_client()
        all_messages = [{"role": "system", "content": system}] + messages

        response = await client.chat.completions.create(
            model=self.text_model,
            messages=all_messages,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str | None = None,
        vision_model: str = "claude-haiku-4-5-20251001",
        text_model: str = "claude-haiku-4-5-20251001",
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.vision_model = vision_model
        self.text_model = text_model

    def _get_client(self):
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self.api_key)

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def vision_classify(self, image_path: str, prompt: str) -> dict:
        client = self._get_client()
        b64 = self._encode_image(image_path)
        ext = Path(image_path).suffix.lstrip(".").lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
            ext, "image/jpeg"
        )

        response = await client.messages.create(
            model=self.vision_model,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        logger.info("Vision raw response: %s", raw)

        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"category": "unknown", "raw_response": raw}

    async def text_complete(self, system: str, messages: list[dict]) -> str:
        client = self._get_client()

        response = await client.messages.create(
            model=self.text_model,
            max_tokens=1000,
            system=system,
            messages=messages,
        )
        return response.content[0].text.strip()


class GroqProvider(OpenAIProvider):
    """Groq Cloud — free vision via OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
        text_model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
    ):
        super().__init__(
            api_key=api_key or os.environ.get("GROQ_API_KEY", ""),
            vision_model=vision_model,
            text_model=text_model,
        )
        self.base_url = "https://api.groq.com/openai/v1"

    def _get_client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


def get_provider(provider_name: str | None = None) -> LLMProvider:
    """Factory function to get LLM provider from env or explicit name."""
    name = (provider_name or os.environ.get("LLM_PROVIDER", "openai")).lower()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "groq":
        return GroqProvider()
    return OpenAIProvider()
