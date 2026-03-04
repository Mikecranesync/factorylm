"""MCP server for Open Brain — semantic memory retrieval and capture.

Exposes tools for searching, capturing, and inspecting the brain memory layer.
Uses Mem0 + Neon pgvector under the hood.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Ensure monorepo root is on path for imports
_monorepo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _monorepo not in sys.path:
    sys.path.insert(0, _monorepo)

app = FastMCP("factorylm-brain")

_memory = None


def _get_memory():
    global _memory
    if _memory is None:
        from services.brain.config import get_memory
        _memory = get_memory()
    return _memory


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@app.tool()
def brain_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Semantic search across all captured memories.

    Returns the most relevant memories for the given query.
    """
    mem = _get_memory()
    results = mem.search(query, user_id="mike", limit=limit)

    memories = results.get("results", []) if isinstance(results, dict) else results
    return [
        {
            "id": m.get("id"),
            "memory": m.get("memory"),
            "score": m.get("score"),
            "metadata": m.get("metadata", {}),
        }
        for m in memories
    ]


@app.tool()
def brain_capture(
    content: str,
    source: str = "mcp",
    tags: list[str] = [],
    metadata: dict = {},
) -> dict[str, Any]:
    """Capture a thought, fact, or event into the brain.

    Use this to save anything worth remembering — decisions, discoveries,
    patterns, or context that might be useful later.
    """
    meta = {"source": source, "tags": tags, **metadata}
    mem = _get_memory()
    result = mem.add(content, user_id="mike", metadata=meta)

    memories = result.get("results", []) if isinstance(result, dict) else []
    return {
        "status": "captured",
        "memories_extracted": memories,
    }


@app.tool()
def brain_research(question: str, search_focus: str = "internet") -> dict[str, Any]:
    """Query Perplexity for research and auto-capture results into the brain.

    Use for questions requiring current information, technical research,
    or anything beyond the brain's existing knowledge.
    """
    import httpx

    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        return {"error": "PERPLEXITY_API_KEY not set"}

    resp = httpx.post(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "sonar",
            "messages": [{"role": "user", "content": question}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    answer = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])

    # Auto-capture into brain
    mem = _get_memory()
    mem.add(
        f"Research: {question}\n\nAnswer: {answer}\n\nSources: {citations}",
        user_id="mike",
        metadata={"source": "perplexity", "question": question, "citations": citations},
    )

    return {"answer": answer, "citations": citations, "captured": True}


@app.tool()
def brain_ingest_file(file_path: str, source: str = "repo", tags: list[str] = []) -> dict[str, Any]:
    """Ingest a file's contents into the brain.

    Use for .md knowledge files, code summaries, architecture docs, etc.
    Large files are chunked by paragraphs (split on double newlines).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    mem = _get_memory()
    # Chunk large files by paragraphs
    chunks = [c.strip() for c in content.split("\n\n") if c.strip() and len(c.strip()) > 50]

    if not chunks:
        chunks = [content[:5000]]

    results = []
    for chunk in chunks:
        result = mem.add(
            chunk,
            user_id="mike",
            metadata={"source": source, "file": file_path, "tags": tags},
        )
        results.append(result)

    return {"status": "ingested", "file": file_path, "chunks": len(chunks)}


@app.tool()
def brain_stats() -> dict[str, Any]:
    """Get memory statistics — count, recent activity, source breakdown."""
    import psycopg2

    neon_url = os.environ.get("NEON_DATABASE_URL")
    if not neon_url:
        return {"error": "NEON_DATABASE_URL not set"}

    try:
        conn = psycopg2.connect(neon_url)
        cur = conn.cursor()

        # Total count — Mem0 pgvector uses (id, vector, payload) schema
        cur.execute("SELECT COUNT(*) FROM brain_memories")
        total = cur.fetchone()[0]

        # Source breakdown from payload JSONB
        cur.execute("""
            SELECT payload->>'source' as source, COUNT(*) as count
            FROM brain_memories
            WHERE payload->>'source' IS NOT NULL
            GROUP BY payload->>'source'
            ORDER BY count DESC
            LIMIT 10
        """)
        sources = {row[0]: row[1] for row in cur.fetchall()}

        # Recent activity — no created_at column, use id ordering
        cur.execute("""
            SELECT id, payload
            FROM brain_memories
            ORDER BY id DESC
            LIMIT 5
        """)
        recent = [
            {"id": str(row[0]), "payload": row[1]}
            for row in cur.fetchall()
        ]

        cur.close()
        conn.close()

        return {
            "total_memories": total,
            "sources": sources,
            "recent": recent,
        }
    except Exception as e:
        logger.error("brain_stats query failed: %s", e)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
