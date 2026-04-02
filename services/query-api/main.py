#!/usr/bin/env python3
"""
FactoryLM Query API — V1
POST /api/query: accepts a question + optional machine name, returns a unified
response assembled from Qdrant KB, Nautobot device records, and the LLM router.

Run with: uvicorn main:app --host 0.0.0.0 --port 8300
"""
import logging
import os
import time
from datetime import datetime
from typing import List, Optional

import requests
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("factorylm.query-api")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:8000")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "factorylm_brain")

NAUTOBOT_URL = os.getenv("NAUTOBOT_URL", "http://localhost:8443")
NAUTOBOT_TOKEN = os.getenv("NAUTOBOT_TOKEN", "7ed85bda94d2c7b5396bd83b319cd7235fe57e0f")

LLM_ROUTER_URL = os.getenv("LLM_ROUTER_URL", "http://localhost:8100")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

KB_RESULT_LIMIT = int(os.getenv("KB_RESULT_LIMIT", "5"))

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str
    machine: Optional[str] = None


class KBSource(BaseModel):
    text: str
    source: Optional[str] = None
    score: Optional[float] = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    machine: Optional[str] = None
    machine_context: Optional[dict] = None
    sources: List[KBSource] = []
    timestamp: str
    latency_ms: int


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FactoryLM Query API",
    description="Unified knowledge query layer: Qdrant KB + Nautobot + LLM",
    version="1.0.0",
)

QUERY_SYSTEM_PROMPT = (
    "You are an expert industrial maintenance AI assistant for FactoryLM. "
    "You help factory technicians by answering questions about equipment, "
    "fault codes, Modbus registers, and maintenance procedures. "
    "When relevant knowledge is available, cite the source. "
    "Keep responses under 300 words. Be direct and actionable. "
    "If a Modbus register or fault code is mentioned, explain exactly what it means "
    "and what the technician should check or do."
)


# ---------------------------------------------------------------------------
# Qdrant KB search
# ---------------------------------------------------------------------------

def _search_qdrant_scroll(question: str) -> List[KBSource]:
    """
    Retrieve KB chunks from Qdrant using scroll (no embedding required).
    Filters results in Python by keyword relevance.
    Returns up to KB_RESULT_LIMIT results.
    """
    try:
        # Scroll up to 100 points from the collection
        r = requests.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
            json={
                "limit": 100,
                "with_payload": True,
                "with_vector": False,
            },
            timeout=5,
        )
        if r.status_code != 200:
            logger.warning("Qdrant scroll returned %d: %s", r.status_code, r.text[:200])
            return []

        points = r.json().get("result", {}).get("points", [])
        if not points:
            logger.debug("Qdrant collection %s is empty", QDRANT_COLLECTION)
            return []

        # Score points by keyword overlap with question
        q_words = set(question.lower().split())
        scored = []
        for pt in points:
            payload = pt.get("payload", {})
            text = payload.get("memory", payload.get("text", payload.get("content", "")))
            if not text:
                continue
            t_words = set(text.lower().split())
            overlap = len(q_words & t_words)
            scored.append((overlap, text, payload))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for overlap, text, payload in scored[:KB_RESULT_LIMIT]:
            if overlap == 0 and len(scored) > KB_RESULT_LIMIT:
                # Skip zero-overlap results unless collection is tiny
                break
            source = payload.get("file", payload.get("source", payload.get("data_source", "brain")))
            results.append(KBSource(text=text[:400], source=str(source) if source else None, score=float(overlap)))

        logger.info("Qdrant scroll: %d points, %d results for '%s'", len(points), len(results), question[:60])
        return results

    except requests.ConnectionError:
        logger.warning("Qdrant unreachable at %s", QDRANT_URL)
        return []
    except Exception as exc:
        logger.warning("Qdrant search failed (non-fatal): %s", exc)
        return []


# ---------------------------------------------------------------------------
# Nautobot device lookup
# ---------------------------------------------------------------------------

def _fetch_nautobot_device(machine: str) -> Optional[dict]:
    """
    Look up a device record in Nautobot by name.
    Returns a simplified dict with name, status, role, comments, or None.
    """
    try:
        r = requests.get(
            f"{NAUTOBOT_URL}/api/dcim/devices/",
            params={"name": machine, "limit": 1},
            headers={
                "Authorization": f"Token {NAUTOBOT_TOKEN}",
                "Accept": "application/json",
            },
            timeout=5,
        )
        if r.status_code != 200:
            logger.warning("Nautobot returned %d for machine=%s", r.status_code, machine)
            return None

        results = r.json().get("results", [])
        if not results:
            logger.info("Nautobot: no device found for '%s'", machine)
            return None

        dev = results[0]
        return {
            "name": dev.get("name"),
            "status": dev.get("status", {}).get("label") if isinstance(dev.get("status"), dict) else dev.get("status"),
            "role": dev.get("role", {}).get("display") if isinstance(dev.get("role"), dict) else dev.get("role"),
            "comments": dev.get("comments", ""),
            "last_updated": dev.get("last_updated"),
        }

    except requests.ConnectionError:
        logger.warning("Nautobot unreachable at %s", NAUTOBOT_URL)
        return None
    except Exception as exc:
        logger.warning("Nautobot lookup failed (non-fatal): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def _build_prompt(
    question: str,
    kb_sources: List[KBSource],
    machine_context: Optional[dict],
) -> str:
    parts = []

    if machine_context:
        parts.append(
            f"Device Record (Nautobot):\n"
            f"  Name: {machine_context.get('name')}\n"
            f"  Status: {machine_context.get('status')}\n"
            f"  Role: {machine_context.get('role')}\n"
            f"  Notes: {(machine_context.get('comments') or '')[:400]}"
        )

    if kb_sources:
        kb_block = ["Relevant knowledge from KB:"]
        for s in kb_sources:
            src_label = f" [source: {s.source}]" if s.source else ""
            kb_block.append(f"- {s.text}{src_label}")
        parts.append("\n".join(kb_block))

    parts.append(f"Technician Question: {question}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def _ask_llm_via_router(prompt: str) -> Optional[str]:
    """Try the LLM router (budget tracking + multi-provider)."""
    try:
        r = requests.post(
            f"{LLM_ROUTER_URL}/v1/chat/completions",
            json={
                "model": "auto",
                "task_type": "fast",
                "messages": [
                    {"role": "system", "content": QUERY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 600,
                "temperature": 0.3,
            },
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            logger.info("LLM router responded (provider=%s)", data.get("x_provider", "?"))
            return data["choices"][0]["message"]["content"]
        logger.warning("LLM router returned %d — falling back", r.status_code)
        return None
    except Exception as exc:
        logger.warning("LLM router unreachable (%s) — falling back", exc)
        return None


def _ask_llm_direct_groq(prompt: str) -> Optional[str]:
    """Direct Groq API fallback."""
    if not GROQ_API_KEY:
        return None
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": QUERY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 600,
                "temperature": 0.3,
            },
            timeout=30,
        )
        if r.status_code == 200:
            logger.info("LLM response via direct Groq")
            return r.json()["choices"][0]["message"]["content"]
        logger.error("Groq API error: %d - %s", r.status_code, r.text[:200])
        return None
    except Exception as exc:
        logger.error("Groq call failed: %s", exc)
        return None


def _ask_llm(prompt: str) -> str:
    """Try router → Groq → fallback message."""
    result = _ask_llm_via_router(prompt) or _ask_llm_direct_groq(prompt)
    if result:
        return result
    # Last resort: return assembled context so the caller gets something useful
    return f"[LLM unavailable — assembled context below]\n\n{prompt}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root() -> dict:
    return {
        "service": "FactoryLM Query API",
        "version": "1.0.0",
        "endpoints": {
            "/health": "GET — service health",
            "/api/query": "POST — unified KB + device + LLM query",
        },
    }


@app.get("/health")
async def health() -> dict:
    """Health check — verifies Qdrant connectivity."""
    qdrant_ok = False
    try:
        r = requests.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}", timeout=3)
        qdrant_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "healthy",
        "service": "factorylm-query-api",
        "qdrant_url": QDRANT_URL,
        "qdrant_collection": QDRANT_COLLECTION,
        "qdrant_reachable": qdrant_ok,
        "nautobot_url": NAUTOBOT_URL,
        "llm_router_url": LLM_ROUTER_URL,
        "llm_configured": bool(GROQ_API_KEY),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Unified technician query endpoint.

    1. Searches Qdrant KB for relevant chunks (top-5)
    2. Fetches Nautobot device record if machine is provided
    3. Assembles context and calls the LLM router
    4. Returns answer with cited sources
    """
    t0 = time.monotonic()
    logger.info("QUERY: question=%r machine=%r", request.question[:100], request.machine)

    # 1. KB search
    kb_sources = _search_qdrant_scroll(request.question)

    # 2. Nautobot device lookup
    machine_context: Optional[dict] = None
    if request.machine:
        machine_context = _fetch_nautobot_device(request.machine)

    # 3. Assemble context + LLM
    prompt = _build_prompt(request.question, kb_sources, machine_context)
    answer = _ask_llm(prompt)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "QUERY complete: %dms, kb_sources=%d, machine=%s",
        elapsed_ms, len(kb_sources), request.machine or "none",
    )

    return QueryResponse(
        question=request.question,
        answer=answer,
        machine=request.machine,
        machine_context=machine_context,
        sources=kb_sources,
        timestamp=datetime.utcnow().isoformat(),
        latency_ms=elapsed_ms,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8300)
