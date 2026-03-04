#!/usr/bin/env python3
"""Batch-ingest Telegram conversation history into Open Brain (Mem0).

Reads kb/telegram/conversations.jsonl and calls mem.add() directly.
Resume-aware: tracks progress in a state file so it can pick up where it left off.

Usage:
    python tools/brain_backfill.py --dry-run                    # preview, no API calls
    python tools/brain_backfill.py --limit 5                    # ingest 5 turns
    python tools/brain_backfill.py --limit 1400                 # day-1 batch (Gemini free tier)
    python tools/brain_backfill.py                              # resume from last checkpoint
    python tools/brain_backfill.py --no-resume                  # start from scratch
    python tools/brain_backfill.py --input path/to/other.jsonl  # custom input file

Rate limits:
    Gemini embedding free tier = 1,500 RPD.
    Default delay: 1s between calls → ~1,400/day safe.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows (Telegram messages contain emoji/unicode)
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Allow running from repo root: `python tools/brain_backfill.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.brain.config import get_memory

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "kb" / "telegram" / "conversations.jsonl"
STATE_FILE_NAME = ".brain_backfill_state"


def _state_path(input_path: Path) -> Path:
    return input_path.parent / STATE_FILE_NAME


def _read_state(input_path: Path) -> int:
    """Return the last successfully ingested line number (0-indexed)."""
    sf = _state_path(input_path)
    if sf.exists():
        try:
            data = json.loads(sf.read_text())
            return data.get("last_line", -1)
        except (json.JSONDecodeError, KeyError):
            return -1
    return -1


def _write_state(input_path: Path, last_line: int, total_ingested: int) -> None:
    sf = _state_path(input_path)
    sf.write_text(json.dumps({
        "last_line": last_line,
        "total_ingested": total_ingested,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2))


def _format_memory(turn: dict) -> str:
    """Format a conversation turn into a memory string."""
    ts = turn.get("timestamp", "unknown")
    user = turn.get("user_message", "")
    assistant = turn.get("assistant_response", "")
    return f"[{ts}] User: {user}\nAssistant: {assistant}"


def _build_metadata(turn: dict) -> dict:
    """Build metadata dict for mem.add()."""
    meta = {
        "source": "telegram_history",
        "intent": turn.get("intent"),
        "timestamp": turn.get("timestamp"),
    }
    # Pull user_name from nested metadata if present
    inner_meta = turn.get("metadata", {})
    if inner_meta.get("user_name"):
        meta["user_name"] = inner_meta["user_name"]
    return {k: v for k, v in meta.items() if v is not None}


def run_backfill(
    input_path: Path,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    resume: bool = True,
    delay: float = 1.0,
) -> None:
    # Load lines
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    print(f"Input: {input_path}")
    print(f"Total conversation turns: {total_lines}")

    # Resume logic
    start_line = 0
    if resume:
        last_done = _read_state(input_path)
        if last_done >= 0:
            start_line = last_done + 1
            print(f"Resuming from line {start_line} (already ingested {start_line})")

    if start_line >= total_lines:
        print("All lines already ingested. Nothing to do.")
        return

    # Calculate end
    remaining = total_lines - start_line
    count = min(limit, remaining) if limit else remaining
    end_line = start_line + count

    print(f"Will ingest lines {start_line}–{end_line - 1} ({count} turns)")

    if dry_run:
        print("\n[DRY RUN] No API calls will be made.")
        # Show a few samples
        for i in range(start_line, min(start_line + 3, end_line)):
            turn = json.loads(lines[i])
            print(f"\n  Line {i}: {_format_memory(turn)[:120]}...")
        if count > 3:
            print(f"\n  ... and {count - 3} more")
        return

    # Init Mem0
    print("\nInitializing Mem0...")
    mem = get_memory()
    print("Mem0 ready.\n")

    ingested = 0
    errors = 0

    for i in range(start_line, end_line):
        turn = json.loads(lines[i])
        content = _format_memory(turn)
        metadata = _build_metadata(turn)

        try:
            result = mem.add(content, user_id="mike", metadata=metadata)
            ingested += 1

            # Extract memory count from result
            memories = []
            if isinstance(result, dict):
                memories = result.get("results", [])
            extracted = len(memories)

            print(f"  [{i}/{end_line - 1}] OK — {extracted} memories extracted")

            # Checkpoint after every successful ingest
            _write_state(input_path, i, start_line + ingested)

        except Exception as e:
            errors += 1
            print(f"  [{i}/{end_line - 1}] ERROR: {e}")
            # Don't update state on error — will retry this line on resume

        # Rate limit
        if i < end_line - 1:
            time.sleep(delay)

    print(f"\nDone. Ingested: {ingested}, Errors: {errors}")
    print(f"State saved to: {_state_path(input_path)}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch-ingest Telegram conversations into Open Brain (Mem0)"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to conversations JSONL (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be ingested, no API calls",
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        help="Max number of turns to ingest (for rate-limit budgeting)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start from scratch, ignore previous state",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between API calls (default: 1.0)",
    )

    args = parser.parse_args()

    run_backfill(
        input_path=args.input,
        dry_run=args.dry_run,
        limit=args.limit,
        resume=not args.no_resume,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
