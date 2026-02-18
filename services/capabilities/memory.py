"""
Memory Capability - RAG with ChromaDB
=====================================
Query conversation history and add new memories.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ChromaDB paths
KB_DIR = Path(__file__).parent.parent.parent / "kb"
CHROMA_DIR = KB_DIR / "chroma_db"
COLLECTION_NAME = "telegram_conversations"


class MemoryCapability:
    """RAG-based memory using ChromaDB."""

    def __init__(self):
        self._client = None
        self._collection = None

    def _get_client(self):
        """Lazy-load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            except ImportError:
                logger.warning("ChromaDB not installed, memory disabled")
                return None
        return self._client

    def _get_collection(self):
        """Get or create the conversations collection."""
        if self._collection is None:
            client = self._get_client()
            if client:
                try:
                    self._collection = client.get_collection(COLLECTION_NAME)
                except:
                    self._collection = client.create_collection(
                        name=COLLECTION_NAME,
                        metadata={"description": "Bot conversation history"}
                    )
        return self._collection

    async def health(self) -> dict:
        """Check memory system health."""
        collection = self._get_collection()
        if collection:
            count = collection.count()
            return {"status": "ok", "conversations": count}
        return {"status": "unavailable", "reason": "ChromaDB not loaded"}

    async def query(
        self,
        query: str,
        n_results: int = 5,
        intent_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query memory for relevant conversations.

        Args:
            query: Natural language query
            n_results: Number of results to return
            intent_filter: Optional filter by intent (screenshot, shell, diagnosis, etc.)

        Returns:
            List of conversation matches with metadata
        """
        collection = self._get_collection()
        if not collection:
            return []

        try:
            where = {"intent": intent_filter} if intent_filter else None

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where
            )

            # Format results
            matches = []
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for doc, meta, dist in zip(docs, metas, distances):
                matches.append({
                    "content": doc,
                    "user_message": meta.get("user_message", ""),
                    "assistant_response": meta.get("assistant_response", ""),
                    "intent": meta.get("intent", "unknown"),
                    "timestamp": meta.get("timestamp", ""),
                    "similarity": 1 - dist,
                })

            return matches

        except Exception as e:
            logger.error(f"Memory query failed: {e}")
            return []

    async def add(
        self,
        user_message: str,
        assistant_response: str,
        intent: str = "conversation",
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add a conversation to memory.

        Args:
            user_message: What the user said
            assistant_response: What the bot responded
            intent: Classified intent
            metadata: Additional metadata

        Returns:
            True if successful
        """
        collection = self._get_collection()
        if not collection:
            return False

        try:
            import datetime
            doc_id = f"conv_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            document = f"User: {user_message}\nBot: {assistant_response}"

            meta = {
                "user_message": user_message[:500],
                "assistant_response": assistant_response[:500],
                "intent": intent,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            if metadata:
                meta.update(metadata)

            collection.add(
                documents=[document],
                metadatas=[meta],
                ids=[doc_id]
            )

            return True

        except Exception as e:
            logger.error(f"Memory add failed: {e}")
            return False

    async def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get most recent conversations."""
        collection = self._get_collection()
        if not collection:
            return []

        try:
            # Get all and sort by timestamp (ChromaDB doesn't have native sorting)
            results = collection.get(
                limit=n * 2,  # Get extra to filter
                include=["documents", "metadatas"]
            )

            items = []
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])

            for doc, meta in zip(docs, metas):
                items.append({
                    "content": doc,
                    "timestamp": meta.get("timestamp", ""),
                    "intent": meta.get("intent", ""),
                })

            # Sort by timestamp descending
            items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return items[:n]

        except Exception as e:
            logger.error(f"Memory get_recent failed: {e}")
            return []

    async def search_by_intent(self, intent: str, n: int = 20) -> List[Dict]:
        """Get all conversations of a specific intent."""
        collection = self._get_collection()
        if not collection:
            return []

        try:
            results = collection.get(
                where={"intent": intent},
                limit=n,
                include=["documents", "metadatas"]
            )

            items = []
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])

            for doc, meta in zip(docs, metas):
                items.append({
                    "content": doc,
                    "user_message": meta.get("user_message", ""),
                    "assistant_response": meta.get("assistant_response", ""),
                    "timestamp": meta.get("timestamp", ""),
                })

            return items

        except Exception as e:
            logger.error(f"Memory search_by_intent failed: {e}")
            return []

    async def count(self) -> int:
        """Get total number of memories."""
        collection = self._get_collection()
        if collection:
            return collection.count()
        return 0
