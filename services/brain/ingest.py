"""FastAPI ingest webhook for Open Brain.

POST /ingest  — capture a thought/event into Mem0
GET  /health   — basic health check
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services.brain.config import get_memory

logger = logging.getLogger(__name__)

app = FastAPI(title="Open Brain Ingest", version="0.1.0")

_memory = None


def _get_memory():
    global _memory
    if _memory is None:
        _memory = get_memory()
    return _memory


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_ACCESS_KEY = os.environ.get("BRAIN_ACCESS_KEY")


def _check_auth(key: str | None) -> None:
    if _ACCESS_KEY and key != _ACCESS_KEY:
        raise HTTPException(status_code=401, detail="Invalid access key")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    content: str
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "service": "open-brain-ingest"}


@app.post("/ingest")
def ingest(
    body: IngestRequest,
    x_brain_key: str | None = Header(None),
):
    _check_auth(x_brain_key)

    meta = {
        "source": body.source,
        "tags": body.tags,
        **body.metadata,
    }

    mem = _get_memory()
    result = mem.add(body.content, user_id="mike", metadata=meta)

    memories = result.get("results", []) if isinstance(result, dict) else []

    return {
        "status": "captured",
        "id": memories[0].get("id") if memories else None,
        "memories_extracted": memories,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8500)
