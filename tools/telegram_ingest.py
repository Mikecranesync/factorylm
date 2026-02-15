#!/usr/bin/env python3
"""
Telegram Chat Ingester for FactoryLM KB
========================================
Parses Telegram Desktop JSON exports into training data format.

Usage:
    python tools/telegram_ingest.py <export_dir> [--output kb/telegram]
    python tools/telegram_ingest.py C:/Users/hharp/Downloads/Telegram\ Desktop/ChatExport_2026-02-15

Input: Telegram Desktop export folder containing result.json
Output:
    - kb/telegram/conversations.jsonl (training pairs)
    - kb/telegram/commands.jsonl (command->response pairs)
    - kb/telegram/summary.json (stats)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Message:
    id: int
    date: str
    from_name: str
    from_id: str | None
    text: str
    reply_to_id: int | None = None
    is_bot: bool = False


@dataclass
class ConversationTurn:
    """Single user->assistant exchange."""
    user_message: str
    assistant_response: str
    timestamp: str
    user_id: str | None = None
    intent: str | None = None  # screenshot, shell, interpret, etc.
    metadata: dict = field(default_factory=dict)


@dataclass
class IngestStats:
    total_messages: int = 0
    user_messages: int = 0
    bot_messages: int = 0
    conversation_turns: int = 0
    unique_users: int = 0
    date_range: str = ""
    intents: dict = field(default_factory=dict)


def parse_html_export(export_path: Path) -> list[Message]:
    """Parse Telegram Desktop HTML export."""
    import html.parser

    messages: list[Message] = []
    html_files = sorted(export_path.glob("messages*.html"))

    if not html_files:
        raise FileNotFoundError(f"No messages*.html found in {export_path}")

    print(f"  Found {len(html_files)} HTML files")

    for html_file in html_files:
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Simple regex parsing for Telegram HTML export
        # Pattern: <div class="message ... id="message####">...<div class="from_name">NAME</div>...<div class="text">TEXT</div>
        import re

        # Find all message blocks
        msg_pattern = re.compile(
            r'<div class="message[^"]*"[^>]*id="message(\d+)"[^>]*>.*?'
            r'<div class="from_name">\s*([^<]+?)\s*</div>.*?'
            r'<div class="text"[^>]*>\s*(.*?)\s*</div>',
            re.DOTALL
        )

        # Also get date from title attribute
        date_pattern = re.compile(r'title="([^"]+)"')

        for match in msg_pattern.finditer(content):
            msg_id = int(match.group(1))
            from_name = match.group(2).strip()
            text_html = match.group(3).strip()

            # Clean HTML from text
            text = re.sub(r'<[^>]+>', '', text_html)
            text = text.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            text = text.strip()

            if not text:
                continue

            # Extract date from nearby context
            msg_block = match.group(0)
            date_match = date_pattern.search(msg_block)
            date_str = date_match.group(1) if date_match else ""

            # Detect bot vs user
            is_bot = "bot" in from_name.lower() or from_name in ["JarvisVPS", "Jarvis", "JarvisMIO_bot"]

            messages.append(Message(
                id=msg_id,
                date=date_str,
                from_name=from_name,
                from_id=None,
                text=text,
                is_bot=is_bot,
            ))

    return messages


def parse_telegram_export(export_path: Path) -> list[Message]:
    """Parse Telegram Desktop export (JSON or HTML)."""

    # Check for HTML export first (more common)
    html_files = list(export_path.glob("messages*.html"))
    if html_files:
        return parse_html_export(export_path)

    # Fall back to JSON
    result_file = export_path / "result.json"
    if not result_file.exists():
        # Maybe they passed the file directly
        if export_path.suffix == ".json":
            result_file = export_path
        else:
            raise FileNotFoundError(f"No result.json or messages*.html found in {export_path}")

    with open(result_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages: list[Message] = []
    chat_name = data.get("name", "Unknown")

    for msg in data.get("messages", []):
        if msg.get("type") != "message":
            continue

        # Extract text (can be string or list of text entities)
        text_content = msg.get("text", "")
        if isinstance(text_content, list):
            # Handle rich text with entities
            text_parts = []
            for part in text_content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict):
                    text_parts.append(part.get("text", ""))
            text_content = "".join(text_parts)

        if not text_content.strip():
            continue

        from_name = msg.get("from", "Unknown")
        from_id = msg.get("from_id", None)

        # Detect if this is from the bot
        is_bot = False
        if from_name and ("bot" in from_name.lower() or from_name == chat_name):
            is_bot = True
        if from_id and str(from_id).startswith("user"):
            is_bot = False
        if from_id and str(from_id).startswith("channel"):
            is_bot = True

        messages.append(Message(
            id=msg.get("id", 0),
            date=msg.get("date", ""),
            from_name=from_name,
            from_id=str(from_id) if from_id else None,
            text=text_content.strip(),
            reply_to_id=msg.get("reply_to_message_id"),
            is_bot=is_bot,
        ))

    return messages


def detect_intent(text: str) -> str | None:
    """Detect command intent from message text."""
    text_lower = text.lower().strip()

    # Screenshot
    if text_lower in ["ss", "screenshot", "screen", "snap"] or text_lower.startswith("ss "):
        return "screenshot"

    # Shell commands
    if text_lower.startswith(("run ", "shell ", "cmd ", "$")):
        return "shell"

    # Status/health
    if any(w in text_lower for w in ["status", "health", "/start", "/help"]):
        return "status"

    # Questions about factory/PLC
    if any(w in text_lower for w in ["why", "what", "how", "fault", "error", "stopped", "diagnose"]):
        return "diagnosis"

    # File operations
    if any(w in text_lower for w in ["read file", "show file", "cat ", "open "]):
        return "files"

    return "conversation"


def extract_conversations(messages: list[Message]) -> list[ConversationTurn]:
    """Extract user->bot conversation turns."""
    turns: list[ConversationTurn] = []

    # Sort by date
    messages = sorted(messages, key=lambda m: m.date)

    # Group into user->bot pairs
    i = 0
    while i < len(messages):
        msg = messages[i]

        # Find user message
        if not msg.is_bot and msg.text:
            user_msg = msg

            # Look for bot response (next message from bot)
            bot_response = None
            for j in range(i + 1, min(i + 5, len(messages))):  # Look ahead up to 5 messages
                if messages[j].is_bot:
                    bot_response = messages[j]
                    break

            if bot_response:
                intent = detect_intent(user_msg.text)
                turns.append(ConversationTurn(
                    user_message=user_msg.text,
                    assistant_response=bot_response.text,
                    timestamp=user_msg.date,
                    user_id=user_msg.from_id,
                    intent=intent,
                    metadata={
                        "user_name": user_msg.from_name,
                        "msg_id": user_msg.id,
                        "response_id": bot_response.id,
                    }
                ))

        i += 1

    return turns


def generate_training_data(turns: list[ConversationTurn]) -> list[dict]:
    """Convert to OpenAI/Anthropic fine-tuning format."""
    training_data = []

    for turn in turns:
        # Standard chat format
        training_data.append({
            "messages": [
                {"role": "user", "content": turn.user_message},
                {"role": "assistant", "content": turn.assistant_response}
            ],
            "metadata": {
                "timestamp": turn.timestamp,
                "intent": turn.intent,
                "source": "telegram",
            }
        })

    return training_data


def compute_stats(messages: list[Message], turns: list[ConversationTurn]) -> IngestStats:
    """Compute ingestion statistics."""
    stats = IngestStats()
    stats.total_messages = len(messages)
    stats.user_messages = sum(1 for m in messages if not m.is_bot)
    stats.bot_messages = sum(1 for m in messages if m.is_bot)
    stats.conversation_turns = len(turns)
    stats.unique_users = len(set(m.from_id for m in messages if not m.is_bot and m.from_id))

    # Date range
    dates = [m.date for m in messages if m.date]
    if dates:
        stats.date_range = f"{min(dates)[:10]} to {max(dates)[:10]}"

    # Intent distribution
    for turn in turns:
        intent = turn.intent or "unknown"
        stats.intents[intent] = stats.intents.get(intent, 0) + 1

    return stats


def ingest(export_path: Path, output_dir: Path) -> IngestStats:
    """Main ingestion pipeline."""
    print(f"Parsing Telegram export: {export_path}")

    # Parse
    messages = parse_telegram_export(export_path)
    print(f"  Found {len(messages)} messages")

    # Extract conversations
    turns = extract_conversations(messages)
    print(f"  Extracted {len(turns)} conversation turns")

    # Generate training data
    training_data = generate_training_data(turns)

    # Compute stats
    stats = compute_stats(messages, turns)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write conversations JSONL
    conversations_file = output_dir / "conversations.jsonl"
    with open(conversations_file, "w", encoding="utf-8") as f:
        for turn in turns:
            f.write(json.dumps(asdict(turn), ensure_ascii=False) + "\n")
    print(f"  Wrote {conversations_file}")

    # Write training data JSONL (OpenAI format)
    training_file = output_dir / "training_data.jsonl"
    with open(training_file, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  Wrote {training_file}")

    # Write command-specific data
    commands_file = output_dir / "commands.jsonl"
    command_turns = [t for t in turns if t.intent in ("screenshot", "shell", "files")]
    with open(commands_file, "w", encoding="utf-8") as f:
        for turn in command_turns:
            f.write(json.dumps({
                "input": turn.user_message,
                "intent": turn.intent,
                "response": turn.assistant_response,
            }, ensure_ascii=False) + "\n")
    print(f"  Wrote {commands_file} ({len(command_turns)} commands)")

    # Write summary
    summary_file = output_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(asdict(stats), f, indent=2)
    print(f"  Wrote {summary_file}")

    # Print stats
    print(f"\n  Summary:")
    print(f"    Total messages:     {stats.total_messages}")
    print(f"    User messages:      {stats.user_messages}")
    print(f"    Bot messages:       {stats.bot_messages}")
    print(f"    Conversation turns: {stats.conversation_turns}")
    print(f"    Unique users:       {stats.unique_users}")
    print(f"    Date range:         {stats.date_range}")
    print(f"    Intents:            {stats.intents}")

    return stats


def ingest_to_sqlite(turns: list[ConversationTurn], db_path: str) -> int:
    """Write conversation turns to RemoteMe SQLite database."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure commands table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT NOT NULL,
            assistant_response TEXT NOT NULL,
            intent TEXT,
            timestamp TEXT,
            user_id TEXT,
            source TEXT DEFAULT 'telegram_import',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert turns
    inserted = 0
    for turn in turns:
        cursor.execute("""
            INSERT INTO training_data (user_message, assistant_response, intent, timestamp, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (turn.user_message, turn.assistant_response, turn.intent, turn.timestamp, turn.user_id))
        inserted += 1

    conn.commit()
    conn.close()
    return inserted


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Telegram chat export into FactoryLM KB"
    )
    parser.add_argument("export_path", help="Path to Telegram export folder or result.json")
    parser.add_argument("--output", "-o", default="kb/telegram", help="Output directory for JSONL files")
    parser.add_argument("--db", help="SQLite database path (e.g., remoteme.db)")
    parser.add_argument("--remote", action="store_true", help="Copy to VPS /opt/remoteme/remoteme.db")

    args = parser.parse_args()

    export_path = Path(args.export_path)
    output_dir = Path(args.output)

    if not export_path.exists():
        print(f"Error: {export_path} not found")
        sys.exit(1)

    stats = ingest(export_path, output_dir)

    # Also write to SQLite if requested
    if args.db:
        print(f"\n  Writing to SQLite: {args.db}")
        messages = parse_telegram_export(export_path)
        turns = extract_conversations(messages)
        count = ingest_to_sqlite(turns, args.db)
        print(f"  Inserted {count} conversation turns into training_data table")

    if args.remote:
        # SCP the JSONL to VPS
        import subprocess
        print(f"\n  Syncing to VPS...")
        subprocess.run([
            "scp", "-r", str(output_dir),
            "root@100.68.120.99:/opt/remoteme/kb/"
        ])
        print(f"  Synced to /opt/remoteme/kb/telegram/")

    print(f"\n  Done! Training data ready in {output_dir}/")


if __name__ == "__main__":
    main()
