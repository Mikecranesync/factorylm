"""Mem0 configuration for Open Brain.

Wires up pgvector (Neon), Gemini embeddings, and Groq LLM (for fact extraction).
Gemini free-tier JSON mode has very low rate limits, so we use Groq for LLM calls.
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
                "embedding_model_dims": 768,  # Gemini gemini-embedding-001 (output_dimensionality=768)
            },
        },
        "embedder": {
            "provider": "gemini",
            "config": {
                "model": "models/gemini-embedding-001",
                "api_key": os.environ.get("GEMINI_API_KEY"),
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
