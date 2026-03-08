"""Scene Observer — Cosmos R2 vision + Mem0 KB read/write.

Wraps vision model calls for scene description and change detection.
Integrates with Mem0/Neon pgvector for cross-scene knowledge transfer.

Reuses encode_media() and vLLM POST pattern from cookoff/diagnosis_engine.py.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx
import yaml

logger = logging.getLogger("factorylm.learner.observer")

REPO_ROOT = Path(__file__).parent.parent.parent

# Model endpoints
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_KEY = os.getenv("LITELLM_KEY", "sk-factorylm")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000/v1/chat/completions")

# Prompt templates
PROMPTS_PATH = Path(__file__).parent / "prompts" / "learner_prompts.yaml"

# Vision model preference order
VISION_MODELS = ["vllm-cosmos", "sonnet-vision"]
TEXT_MODELS = ["deepseek-main", "local-gemma"]


# ---------------------------------------------------------------------------
# Media encoding (reuses pattern from cookoff/diagnosis_engine.py)
# ---------------------------------------------------------------------------

def encode_media(path: str) -> tuple[str, str]:
    """Encode image or video as base64 with MIME type."""
    ext = Path(path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".mp4": "video/mp4",
    }
    mime = mime_map.get(ext, "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return b64, mime


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

_prompts_cache: Optional[dict] = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is not None:
        return _prompts_cache
    if PROMPTS_PATH.exists():
        with open(PROMPTS_PATH) as f:
            _prompts_cache = yaml.safe_load(f)
    else:
        _prompts_cache = {}
    return _prompts_cache


def get_prompt(name: str, **kwargs) -> str:
    """Get a prompt template by name and format with kwargs."""
    prompts = _load_prompts()
    template = prompts.get(name, {}).get("template", "")
    if not template:
        logger.warning("Prompt '%s' not found in templates", name)
        return kwargs.get("fallback", "Describe what you see.")
    try:
        return template.format(**kwargs)
    except KeyError as exc:
        logger.warning("Missing prompt variable %s in '%s'", exc, name)
        return template


# ---------------------------------------------------------------------------
# Vision calls
# ---------------------------------------------------------------------------

async def _call_vllm(image_path: str, prompt: str,
                     system_prompt: str = "") -> dict:
    """Call vLLM directly (Cosmos R2)."""
    b64, mime = encode_media(image_path)

    if mime.startswith("video"):
        media_content = {"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}}
    else:
        media_content = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}

    payload = {
        "model": "nvidia/Cosmos-Reason2-8B",
        "messages": [
            {"role": "system", "content": system_prompt or "You are a factory floor vision assistant."},
            {"role": "user", "content": [media_content, {"type": "text", "text": prompt}]},
        ],
        "max_tokens": 2048,
        "temperature": 0.6,
        "top_p": 0.95,
    }

    t_start = time.time()
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            VLLM_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
    elapsed = time.time() - t_start

    if resp.status_code != 200:
        return {"error": f"vLLM HTTP {resp.status_code}: {resp.text[:300]}", "elapsed_s": elapsed}

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # Parse <think> blocks
    reasoning = ""
    answer = content
    if "<think>" in content and "</think>" in content:
        think_start = content.index("<think>") + len("<think>")
        think_end = content.index("</think>")
        reasoning = content[think_start:think_end].strip()
        answer = content[think_end + len("</think>"):].strip()

    return {
        "content": answer,
        "reasoning": reasoning,
        "raw": content,
        "provider": "vllm-cosmos",
        "elapsed_s": round(elapsed, 1),
    }


async def _call_litellm_vision(image_path: str, prompt: str,
                                system_prompt: str = "",
                                model: str = "sonnet-vision") -> dict:
    """Call LiteLLM proxy for vision (Claude Sonnet, etc.)."""
    b64, mime = encode_media(image_path)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "You are a factory floor vision assistant."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ]},
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
    }

    t_start = time.time()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {LITELLM_KEY}",
                "Content-Type": "application/json",
            },
        )
    elapsed = time.time() - t_start

    if resp.status_code != 200:
        return {"error": f"LiteLLM HTTP {resp.status_code}: {resp.text[:300]}", "elapsed_s": elapsed}

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return {
        "content": content,
        "reasoning": "",
        "raw": content,
        "provider": data.get("model", model),
        "elapsed_s": round(elapsed, 1),
    }


async def _call_litellm_text(prompt: str, system_prompt: str = "",
                              model: str = "deepseek-main") -> dict:
    """Call LiteLLM proxy for text-only reasoning."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "You are a factory automation expert."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.3,
    }

    t_start = time.time()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {LITELLM_KEY}",
                "Content-Type": "application/json",
            },
        )
    elapsed = time.time() - t_start

    if resp.status_code != 200:
        return {"error": f"LiteLLM HTTP {resp.status_code}: {resp.text[:300]}", "elapsed_s": elapsed}

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return {
        "content": content,
        "provider": data.get("model", model),
        "elapsed_s": round(elapsed, 1),
    }


async def ask_vision(image_path: str, prompt: str,
                     system_prompt: str = "") -> dict:
    """Ask a vision model about an image, with fallback chain.

    Tries: vLLM Cosmos R2 → LiteLLM sonnet-vision
    """
    # Try vLLM first
    result = await _call_vllm(image_path, prompt, system_prompt)
    if "error" not in result:
        return result
    logger.warning("vLLM failed: %s — trying LiteLLM vision", result.get("error", ""))

    # Fallback to LiteLLM vision
    result = await _call_litellm_vision(image_path, prompt, system_prompt)
    if "error" not in result:
        return result
    logger.error("All vision providers failed: %s", result.get("error", ""))
    return result


async def ask_text(prompt: str, system_prompt: str = "") -> dict:
    """Ask a text model, with fallback chain.

    Tries: deepseek-main → local-gemma
    """
    for model in TEXT_MODELS:
        result = await _call_litellm_text(prompt, system_prompt, model)
        if "error" not in result:
            return result
        logger.warning("Model %s failed: %s", model, result.get("error", ""))

    return {"error": "All text providers failed", "content": ""}


# ---------------------------------------------------------------------------
# High-level observer methods (used by experiment_engine)
# ---------------------------------------------------------------------------

async def describe_scene(image_path: str) -> dict:
    """Describe a Factory I/O scene from a screenshot."""
    prompt = get_prompt("describe_scene",
                        fallback="What factory equipment do you see? What is moving and what is stopped?")
    return await ask_vision(image_path, prompt)


async def describe_change(image_before: str, image_after: str,
                           coil_name: str, coil_desc: str) -> dict:
    """Describe what changed after toggling a coil.

    Uses the AFTER image with context about what was done.
    """
    prompt = get_prompt(
        "describe_change",
        coil_name=coil_name,
        coil_desc=coil_desc,
        fallback=f"I toggled coil '{coil_name}' (documented as '{coil_desc}'). What changed in the scene?",
    )
    return await ask_vision(image_after, prompt)


async def verify_behavior(image_path: str, coil_name: str,
                           official_desc: str, observed_delta: str) -> dict:
    """Verify if observed behavior matches official documentation."""
    prompt = get_prompt(
        "verify_behavior",
        coil_name=coil_name,
        official_desc=official_desc,
        observed_delta=observed_delta,
        fallback=(
            f"The PLC program says coil '{coil_name}' is '{official_desc}'. "
            f"I observed: {observed_delta}. "
            f"Does the observed behavior match the documentation? "
            f"Reply MATCH or MISMATCH with a brief explanation."
        ),
    )
    return await ask_vision(image_path, prompt)


async def extract_learning(image_path: str, coil_name: str,
                            tag_delta: dict) -> dict:
    """Extract a one-sentence learning from an experiment."""
    delta_text = ", ".join(f"{k}: {v['old']}→{v['new']}" for k, v in tag_delta.items())
    prompt = get_prompt(
        "extract_learning",
        coil_name=coil_name,
        tag_delta=delta_text,
        fallback=f"In one sentence, what does coil '{coil_name}' control? Tag changes: {delta_text}",
    )
    return await ask_vision(image_path, prompt)


async def plan_next_experiment(context: str) -> dict:
    """Ask a reasoning model what to test next."""
    prompt = get_prompt(
        "plan_experiment",
        context=context,
        fallback=f"Given what we know so far:\n{context}\n\nWhat should we test next and why?",
    )
    return await ask_text(prompt)


async def consolidate_scene(context: str) -> dict:
    """Summarize everything learned about a scene."""
    prompt = get_prompt(
        "consolidate",
        context=context,
        fallback=f"Summarize how this factory scene works based on our experiments:\n{context}",
    )
    return await ask_text(prompt)


# ---------------------------------------------------------------------------
# KB integration (Mem0 / Neon pgvector)
# ---------------------------------------------------------------------------

_brain_memory = None


def _get_brain():
    """Lazy-init Mem0 memory."""
    global _brain_memory
    if _brain_memory is not None:
        return _brain_memory
    try:
        from services.brain.config import get_memory
        _brain_memory = get_memory()
        return _brain_memory
    except Exception as exc:
        logger.debug("Brain/Mem0 unavailable: %s", exc)
        return None


async def search_kb(query: str, limit: int = 3) -> list[str]:
    """Search Mem0 KB for relevant prior knowledge."""
    brain = _get_brain()
    if brain is None:
        return []
    try:
        results = await asyncio.to_thread(
            brain.search, query, user_id="factorylm-learner", limit=limit,
        )
        if not results:
            return []
        memories = results.get("results", results) if isinstance(results, dict) else results
        texts = []
        for m in memories[:limit]:
            text = m.get("memory", m.get("text", "")) if isinstance(m, dict) else str(m)
            if text:
                texts.append(text)
        return texts
    except Exception as exc:
        logger.debug("KB search failed: %s", exc)
        return []


async def capture_learning(scene_name: str, tag_name: str, learning: str,
                            confidence: float, experiment_id: int) -> bool:
    """Write a confirmed learning to KB via Mem0."""
    brain = _get_brain()
    if brain is None:
        return False
    try:
        content = f"Scene '{scene_name}': {tag_name} — {learning}"
        await asyncio.to_thread(
            brain.add,
            messages=[{"role": "user", "content": content}],
            user_id="factorylm-learner",
            metadata={
                "source": "scene_learner",
                "scene": scene_name,
                "tag": tag_name,
                "experiment_id": str(experiment_id),
                "confidence": str(confidence),
            },
        )
        logger.info("KB captured: %s → %s", tag_name, learning[:80])
        return True
    except Exception as exc:
        logger.error("KB capture failed: %s", exc)
        return False
