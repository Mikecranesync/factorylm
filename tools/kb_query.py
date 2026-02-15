#!/usr/bin/env python3
"""
FactoryLM KB Query Tool
========================
Load Telegram conversations into ChromaDB and query with natural language.

Usage:
    python tools/kb_query.py index                    # Index conversations into ChromaDB
    python tools/kb_query.py query "how did the old bot handle screenshots?"
    python tools/kb_query.py interactive              # Interactive Q&A mode
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ensure we can import chromadb
try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    print("Installing chromadb...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "chromadb", "-q"])
    import chromadb
    from chromadb.config import Settings


KB_DIR = Path(__file__).parent.parent / "kb"
CHROMA_DIR = KB_DIR / "chroma_db"
COLLECTION_NAME = "telegram_conversations"


def get_client():
    """Get ChromaDB client."""
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def index_conversations():
    """Index conversations into ChromaDB."""
    conversations_file = KB_DIR / "telegram" / "conversations.jsonl"

    if not conversations_file.exists():
        print(f"Error: {conversations_file} not found. Run telegram_ingest.py first.")
        sys.exit(1)

    print(f"Loading conversations from {conversations_file}")

    # Load conversations
    conversations = []
    with open(conversations_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                conversations.append(json.loads(line))

    print(f"  Loaded {len(conversations)} conversations")

    # Initialize ChromaDB
    client = get_client()

    # Delete existing collection if exists
    try:
        client.delete_collection(COLLECTION_NAME)
    except:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Telegram bot conversation history for training"}
    )

    # Index in batches
    batch_size = 100
    for i in range(0, len(conversations), batch_size):
        batch = conversations[i:i+batch_size]

        documents = []
        metadatas = []
        ids = []

        for j, conv in enumerate(batch):
            # Create searchable document combining user message and response
            doc = f"User: {conv['user_message']}\nBot: {conv['assistant_response']}"
            documents.append(doc)

            metadatas.append({
                "intent": conv.get("intent", "unknown"),
                "timestamp": conv.get("timestamp", ""),
                "user_message": conv["user_message"][:500],  # Truncate for metadata
                "assistant_response": conv["assistant_response"][:500],
            })

            ids.append(f"conv_{i+j}")

        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        print(f"  Indexed {min(i+batch_size, len(conversations))}/{len(conversations)}")

    print(f"\n✅ Indexed {len(conversations)} conversations into {CHROMA_DIR}")
    print(f"   Collection: {COLLECTION_NAME}")


def query_kb(query: str, n_results: int = 5):
    """Query the KB."""
    client = get_client()

    try:
        collection = client.get_collection(COLLECTION_NAME)
    except:
        print("Error: Collection not found. Run 'python tools/kb_query.py index' first.")
        sys.exit(1)

    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )

    return results


def print_results(results, query: str):
    """Pretty print query results."""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, (doc, meta, dist) in enumerate(zip(docs, metas, distances)):
        similarity = 1 - dist  # Convert distance to similarity
        intent = meta.get("intent", "unknown")
        timestamp = meta.get("timestamp", "")[:10]

        print(f"--- Result {i+1} (similarity: {similarity:.2f}, intent: {intent}) ---")
        print(f"Date: {timestamp}")
        print(doc[:500])
        print()


def interactive_mode():
    """Interactive Q&A mode."""
    print("\n" + "="*60)
    print("  FactoryLM KB Interactive Query")
    print("  Type 'quit' or 'exit' to stop")
    print("="*60 + "\n")

    client = get_client()

    try:
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()
        print(f"  Loaded {count} conversations from KB\n")
    except:
        print("Error: Collection not found. Run 'python tools/kb_query.py index' first.")
        sys.exit(1)

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue

        if query.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        results = query_kb(query, n_results=3)
        print_results(results, query)


def stats():
    """Show KB statistics."""
    client = get_client()

    try:
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()

        # Get intent distribution
        all_data = collection.get(include=["metadatas"])
        intents = {}
        for meta in all_data.get("metadatas", []):
            intent = meta.get("intent", "unknown")
            intents[intent] = intents.get(intent, 0) + 1

        print(f"\nKB Statistics")
        print(f"{'='*40}")
        print(f"Total conversations: {count}")
        print(f"\nIntent distribution:")
        for intent, cnt in sorted(intents.items(), key=lambda x: -x[1]):
            print(f"  {intent:<20} {cnt:>5}")

    except Exception as e:
        print(f"Error: {e}")
        print("Run 'python tools/kb_query.py index' first.")


def main():
    parser = argparse.ArgumentParser(description="Query FactoryLM KB")
    parser.add_argument("command", choices=["index", "query", "interactive", "stats"],
                        help="Command to run")
    parser.add_argument("query_text", nargs="?", default="",
                        help="Query text (for 'query' command)")
    parser.add_argument("-n", "--num-results", type=int, default=5,
                        help="Number of results to return")

    args = parser.parse_args()

    if args.command == "index":
        index_conversations()
    elif args.command == "query":
        if not args.query_text:
            print("Error: query command requires query text")
            sys.exit(1)
        results = query_kb(args.query_text, args.num_results)
        print_results(results, args.query_text)
    elif args.command == "interactive":
        interactive_mode()
    elif args.command == "stats":
        stats()


if __name__ == "__main__":
    main()
