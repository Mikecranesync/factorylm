"""Qdrant vector store for FactoryLM knowledge base.

Two collections:
  - fault_history: Past fault diagnoses, work orders, resolution steps
  - manuals:       Equipment manuals, SOPs, maintenance procedures

Embedding: Sentence Transformers (all-MiniLM-L6-v2) — runs locally, no API key needed.
Qdrant: Runs on CHARLIE node (:6333) or localhost for dev.

Usage:
    store = QdrantKBStore()
    store.add("fault_history", "Motor overcurrent on conveyor 3...", {"equipment": "conveyor-3"})
    results = store.search("fault_history", "conveyor jam", limit=3)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("factorylm.brain.qdrant")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBEDDING_MODEL = os.getenv("QDRANT_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension

COLLECTIONS = ("fault_history", "manuals")


class QdrantKBStore:
    """Qdrant-backed knowledge base with local embeddings."""

    def __init__(self, url: str | None = None):
        self._url = url or QDRANT_URL
        self._client = None
        self._encoder = None

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=self._url)
            self._ensure_collections()
        return self._client

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(EMBEDDING_MODEL)
        return self._encoder

    def _ensure_collections(self):
        """Create collections if they don't exist."""
        from qdrant_client.models import Distance, VectorParams

        existing = {c.name for c in self._client.get_collections().collections}
        for name in COLLECTIONS:
            if name not in existing:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection: %s", name)

    def add(
        self,
        collection: str,
        text: str,
        metadata: dict | None = None,
        doc_id: str | None = None,
    ) -> str:
        """Add a document to a collection. Returns the point ID."""
        import uuid
        from qdrant_client.models import PointStruct

        point_id = doc_id or uuid.uuid4().hex
        vector = self.encoder.encode(text).tolist()
        payload = {"text": text, **(metadata or {})}

        self.client.upsert(
            collection_name=collection,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return point_id

    def search(
        self,
        collection: str,
        query: str,
        limit: int = 3,
        score_threshold: float = 0.3,
    ) -> list[dict]:
        """Search a collection. Returns list of {text, score, metadata}."""
        vector = self.encoder.encode(query).tolist()

        try:
            results = self.client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                score_threshold=score_threshold,
            ).points
        except Exception as exc:
            logger.warning("Qdrant search failed on %s: %s", collection, exc)
            return []

        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "metadata": {k: v for k, v in hit.payload.items() if k != "text"},
            }
            for hit in results
        ]

    def search_all(self, query: str, limit: int = 3) -> list[dict]:
        """Search across all collections, merged by score."""
        all_results = []
        for collection in COLLECTIONS:
            results = self.search(collection, query, limit=limit)
            for r in results:
                r["collection"] = collection
            all_results.extend(results)
        all_results.sort(key=lambda r: r["score"], reverse=True)
        return all_results[:limit]

    def count(self, collection: str) -> int:
        """Return document count for a collection."""
        try:
            info = self.client.get_collection(collection)
            return info.points_count
        except Exception:
            return 0

    def healthy(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False


# Module-level singleton (lazy)
_store: Optional[QdrantKBStore] = None


def get_store() -> QdrantKBStore:
    global _store
    if _store is None:
        _store = QdrantKBStore()
    return _store
