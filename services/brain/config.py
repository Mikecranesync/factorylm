"""Mem0 configuration for Open Brain.

Wires up pgvector (Neon), Ollama embeddings, and Groq LLM (for fact extraction).
Gemini free-tier JSON mode has very low rate limits, so we use Groq for LLM calls.

Embeddings: Ollama nomic-embed-text (768d) running locally on CHARLIE.
Switched from Gemini gemini-embedding-001 on 2026-05-23 because the Gemini key
kept expiring. Both produce 768d vectors so the pgvector schema is unchanged,
but the vector spaces are different — the 5,493 memories embedded before this
switch will return lower-relevance results on cross-space queries until they
are re-embedded with `tools/brain_backfill.py`.

Aligns with MIRA's knowledge_entries KB (also nomic-embed-text) for future
vector-space unification.
"""

from __future__ import annotations

import os

from mem0 import Memory


def get_memory() -> Memory:
    """Return a configured Mem0 Memory instance."""
    config = {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "connection_string": os.environ["NEON_DATABASE_URL"],
                "collection_name": "brain_memories",
                "embedding_model_dims": 768,  # nomic-embed-text (also 768d, matches prior Gemini schema)
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            },
        },
        "llm": {
            "provider": "groq",
            "config": {
                "model": "llama-3.3-70b-versatile",
                "api_key": os.environ.get("GROQ_API_KEY"),
            },
        },
    }
    return Memory.from_config(config)
