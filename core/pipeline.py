"""FactoryLM Pipeline — unified process(input) → response for all channels.

Routes media to vision models, text to fast/reasoning models.
Reuses existing infrastructure:
  - cookoff/diagnosis_engine for vision (Cosmos R2 via vLLM)
  - services/llm-router SmartRouter for text routing
  - services/media/telegram_media_handler for file saves
  - services/matrix/app for PLC tag context
  - services/brain for Mem0 knowledge retrieval
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("factorylm.pipeline")

# Repo root (core/ is one level below monorepo root)
REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FactoryLMInput:
    """Inbound message from any channel."""
    text: Optional[str] = None
    media_path: Optional[str] = None
    media_type: Optional[str] = None  # "photo" | "video" | "document"
    caption: Optional[str] = None
    user_id: Optional[str] = None
    channel: str = "telegram"


@dataclass
class FactoryLMResponse:
    """Pipeline output sent back to the channel adapter."""
    text: str
    provider: Optional[str] = None
    task_type: Optional[str] = None
    elapsed_s: float = 0.0
    media_path: Optional[str] = None
    incident_id: Optional[int] = None
    trace_id: Optional[str] = None


# ---------------------------------------------------------------------------
# PLC context
# ---------------------------------------------------------------------------

MATRIX_URL = os.getenv("MATRIX_URL", os.getenv("MATRIX_API", "http://localhost:8000"))


async def get_plc_state() -> Optional[dict]:
    """Fetch latest PLC tag snapshot from Matrix API."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{MATRIX_URL}/api/tags/live")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("tags")
    except Exception as exc:
        logger.debug("PLC state unavailable: %s", exc)
    return None


# ---------------------------------------------------------------------------
# KB context (Mem0 / Open Brain)
# ---------------------------------------------------------------------------

_brain_memory = None


def _get_brain():
    """Lazy-init Mem0 memory (requires NEON_DATABASE_URL, GEMINI_API_KEY, GROQ_API_KEY)."""
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


async def _retrieve_kb_context(query: str) -> Optional[str]:
    """Search Mem0 knowledge base for relevant factory context."""
    brain = _get_brain()
    if brain is None:
        return None
    try:
        results = await asyncio.to_thread(
            brain.search, query, user_id="factorylm", limit=3
        )
        if not results:
            return None
        memories = results.get("results", results) if isinstance(results, dict) else results
        if not memories:
            return None
        texts = []
        for m in memories[:3]:
            text = m.get("memory", m.get("text", "")) if isinstance(m, dict) else str(m)
            if text:
                texts.append(text)
        return "\n".join(texts) if texts else None
    except Exception as exc:
        logger.debug("KB search failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# LLM Router (text-only path)
# ---------------------------------------------------------------------------

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_KEY = os.getenv("LITELLM_KEY", "sk-factorylm")


async def _route_text(
    text: str,
    task_type: str = "fast",
    system_prompt: Optional[str] = None,
    kb_context: Optional[str] = None,
    plc_context: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> dict:
    """Route a text query through LiteLLM proxy."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Enrich user message with context
    enriched = text
    if plc_context:
        enriched = f"Live PLC data:\n{plc_context}\n\nQuestion: {text}"
    if kb_context:
        enriched = f"Relevant knowledge:\n{kb_context}\n\n{enriched}"

    messages.append({"role": "user", "content": enriched})

    payload = {
        "model": "deepseek-main",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    headers = {
        "Authorization": f"Bearer {LITELLM_KEY}",
        "Content-Type": "application/json",
    }
    if trace_id:
        headers["x-trace-id"] = trace_id

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    model = data.get("model", "unknown")
    return {"content": content, "provider": model}


# ---------------------------------------------------------------------------
# Vision path (diagnosis engine)
# ---------------------------------------------------------------------------

async def _route_vision(
    media_path: str,
    caption: Optional[str] = None,
    plc_tags: Optional[dict] = None,
) -> dict:
    """Route media through the Cosmos R2 diagnosis engine."""
    # Import diagnosis engine (adds repo root to sys.path internally)
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from cookoff.diagnosis_engine import diagnose

    # diagnosis_engine.diagnose() is synchronous — run in executor
    result = await asyncio.to_thread(
        diagnose,
        media_path=media_path,
        plc_tags=plc_tags,
        question=caption,
    )
    return result


# ---------------------------------------------------------------------------
# Incident recording
# ---------------------------------------------------------------------------

async def _record_incident(
    plc_tags: Optional[dict],
    diagnosis_text: str,
    media_path: Optional[str] = None,
) -> Optional[int]:
    """Record an incident + cosmos insight in Matrix if fault detected."""
    if not plc_tags:
        return None
    has_fault = plc_tags.get("fault_alarm") or plc_tags.get("e_stop_active")
    if not has_fault:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Create incident via Matrix API
            tag_payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "node_id": "telegram_media",
                "motor_running": plc_tags.get("motor_running", False),
                "motor_speed": plc_tags.get("motor_speed", 0),
                "motor_current": plc_tags.get("motor_current", 0.0),
                "temperature": plc_tags.get("temperature", 0.0),
                "pressure": plc_tags.get("pressure", 0),
                "conveyor_running": plc_tags.get("conveyor_running", False),
                "conveyor_speed": plc_tags.get("conveyor_speed", 0),
                "sensor_1": plc_tags.get("sensor_1_active", False),
                "sensor_2": plc_tags.get("sensor_2_active", False),
                "fault_alarm": plc_tags.get("fault_alarm", False),
                "e_stop": plc_tags.get("e_stop_active", False),
                "error_code": plc_tags.get("error_code", 0),
                "error_message": "",
            }
            resp = await client.post(f"{MATRIX_URL}/api/tags", json=tag_payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("incident_id")
    except Exception as exc:
        logger.debug("Incident recording failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

FACTORY_SYSTEM_PROMPT = (
    "You are FactoryLM, an expert industrial maintenance AI. "
    "You help factory technicians diagnose equipment issues from PLC data "
    "and factory floor observations. Be concise, actionable, and practical. "
    "If something looks abnormal, explain the likely cause and recommended action."
)


async def _post_trace(trace: dict) -> None:
    """Fire-and-forget POST to Matrix API /api/traces."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(f"{MATRIX_URL}/api/traces", json=trace)
    except Exception as exc:
        logger.debug("Trace POST failed: %s", exc)


async def process(inp: FactoryLMInput) -> FactoryLMResponse:
    """Route an inbound message through the appropriate pipeline.

    Media (photo/video) → vision task type → vllm-cosmos or groq-kimi
    Text only           → fast task type   → groq-llama70b or deepseek
    """
    trace_id = uuid.uuid4().hex[:12]
    t_start = time.time()

    has_media = bool(inp.media_path and inp.media_type in ("photo", "video"))
    input_type = inp.media_type if has_media else "text"
    query = inp.caption or inp.text or ""

    # Summarize input for trace log
    if has_media:
        input_summary = f"{inp.media_type} {Path(inp.media_path).name}"
    else:
        input_summary = query[:100] if query else ""

    logger.info("[%s] Pipeline START channel=%s type=%s user=%s", trace_id, inp.channel, input_type, inp.user_id)

    # Gather PLC context (always, for both text and vision paths)
    plc_tags = await get_plc_state()
    plc_available = plc_tags is not None
    logger.info("[%s] PLC state: %s", trace_id, "available" if plc_available else "unavailable")

    # Trace record (filled in progressively)
    trace = {
        "trace_id": trace_id,
        "channel": inp.channel,
        "user_id": inp.user_id,
        "input_type": input_type,
        "input_summary": input_summary,
        "plc_state_available": plc_available,
    }

    if has_media:
        # --- VISION PATH ---
        logger.info("[%s] Routing to vision provider", trace_id)
        trace["task_type"] = "vision"

        result = await _route_vision(
            media_path=inp.media_path,
            caption=query or None,
            plc_tags=plc_tags,
        )
        elapsed = time.time() - t_start
        elapsed_ms = int(elapsed * 1000)

        if "error" in result:
            logger.info("[%s] Pipeline ERROR %dms: %s", trace_id, elapsed_ms, result["error"])
            trace.update(status="error", elapsed_ms=elapsed_ms, provider="vllm-cosmos",
                         error_message=str(result["error"])[:200])
            asyncio.create_task(_post_trace(trace))
            return FactoryLMResponse(
                text=f"Vision analysis failed: {result['error']}",
                task_type="vision",
                elapsed_s=round(elapsed, 1),
                media_path=inp.media_path,
                trace_id=trace_id,
            )

        diagnosis_text = result.get("diagnosis", result.get("raw_response", ""))

        # Record incident if fault detected
        incident_id = await _record_incident(plc_tags, diagnosis_text, inp.media_path)

        logger.info("[%s] LLM response: vllm-cosmos %dms", trace_id, elapsed_ms)
        logger.info("[%s] Pipeline DONE %dms", trace_id, elapsed_ms)
        trace.update(status="success", elapsed_ms=elapsed_ms, provider="vllm-cosmos",
                     model="nvidia/Cosmos-Reason2-8B", incident_id=incident_id,
                     response_summary=diagnosis_text[:200] if diagnosis_text else None)
        asyncio.create_task(_post_trace(trace))

        return FactoryLMResponse(
            text=diagnosis_text,
            provider="vllm-cosmos",
            task_type="vision",
            elapsed_s=round(elapsed, 1),
            media_path=inp.media_path,
            incident_id=incident_id,
            trace_id=trace_id,
        )

    else:
        # --- TEXT PATH ---
        if not query:
            return FactoryLMResponse(
                text="Send a photo, video, or question about your factory.",
                trace_id=trace_id,
            )

        # Get KB context
        kb_context = await _retrieve_kb_context(query)
        kb_available = kb_context is not None
        logger.info("[%s] KB context: %s", trace_id, "found" if kb_available else "none")
        trace["kb_context_available"] = kb_available

        # Format PLC context as text
        plc_text = None
        if plc_tags:
            from cookoff.diagnosis_engine import format_plc_registers
            plc_text = format_plc_registers(plc_tags)

        logger.info("[%s] Routing to fast provider", trace_id)
        trace["task_type"] = "fast"

        try:
            result = await _route_text(
                text=query,
                task_type="fast",
                system_prompt=FACTORY_SYSTEM_PROMPT,
                kb_context=kb_context,
                plc_context=plc_text,
                trace_id=trace_id,
            )
            elapsed = time.time() - t_start
            elapsed_ms = int(elapsed * 1000)
            provider = result.get("provider", "unknown")

            logger.info("[%s] LLM response: %s %dms", trace_id, provider, elapsed_ms)
            logger.info("[%s] Pipeline DONE %dms", trace_id, elapsed_ms)
            trace.update(status="success", elapsed_ms=elapsed_ms, provider=provider,
                         response_summary=result["content"][:200] if result.get("content") else None)
            asyncio.create_task(_post_trace(trace))

            return FactoryLMResponse(
                text=result["content"],
                provider=provider,
                task_type="fast",
                elapsed_s=round(elapsed, 1),
                trace_id=trace_id,
            )
        except Exception as exc:
            elapsed = time.time() - t_start
            elapsed_ms = int(elapsed * 1000)
            logger.error("[%s] Text routing failed: %s", trace_id, exc)
            trace.update(status="error", elapsed_ms=elapsed_ms, error_message=str(exc)[:200])
            asyncio.create_task(_post_trace(trace))
            return FactoryLMResponse(
                text=f"LLM unavailable: {exc}",
                task_type="fast",
                elapsed_s=round(elapsed, 1),
                trace_id=trace_id,
            )
