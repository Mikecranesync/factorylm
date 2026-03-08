"""
Shared LLM client — all FactoryLM code calls LiteLLM Proxy through this.

Every LLM call is a standard OpenAI SDK call against localhost:4000.
Model routing, fallbacks, retries, and cost tracking are handled by the proxy.
"""

import logging
import os

import openai

logger = logging.getLogger(__name__)

LITELLM_URL = os.getenv("LITELLM_URL", "http://127.0.0.1:4000")
LITELLM_KEY = os.getenv("LITELLM_KEY", "sk-factorylm")

# Shared sync + async clients — import these from anywhere
llm_client = openai.OpenAI(api_key=LITELLM_KEY, base_url=LITELLM_URL)
llm_async_client = openai.AsyncOpenAI(api_key=LITELLM_KEY, base_url=LITELLM_URL)


def diagnose_fault(system_prompt: str, user_message: str, model: str = "groq-main") -> str:
    """Synchronous diagnosis call. Used by diagnosis service."""
    try:
        r = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return r.choices[0].message.content
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return None


async def async_diagnose(system_prompt: str, messages: list[dict], model: str = "groq-main") -> str:
    """Async diagnosis call. Used by Telegram bot and other async services."""
    try:
        r = await llm_async_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            max_tokens=400,
            temperature=0.3,
        )
        return r.choices[0].message.content
    except Exception as e:
        logger.error("Async LLM call failed: %s", e)
        return None


def classify_intent(text: str) -> str:
    """Classify user intent via local Gemma (free). Falls back to deepseek-main."""
    try:
        r = llm_client.chat.completions.create(
            model="local-gemma",
            messages=[{
                "role": "user",
                "content": f"Classify this maintenance message into one category: fault_report, status_check, work_order, general_question.\nMessage: {text}\nCategory:",
            }],
            max_tokens=20,
            temperature=0.0,
        )
        return r.choices[0].message.content.strip().lower()
    except Exception as e:
        logger.warning("Intent classification failed: %s", e)
        return "general_question"
