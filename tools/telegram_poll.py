#!/usr/bin/env python3
"""Standalone Telegram Bot API poller → Open Brain ingest.

Captures messages when OpenClaw is NOT running. Uses getUpdates (long-polling)
and forwards each message to the brain ingest endpoint.

Safety: Checks if OpenClaw is alive (port 8340) before polling. If Jarvis is up,
the adapter hooks already handle brain capture — no double-polling.

Usage:
    python tools/telegram_poll.py --once              # one poll cycle, exit
    python tools/telegram_poll.py --once --test        # verify bot API connection
    python tools/telegram_poll.py --daemon             # continuous loop (30s interval)

Env vars:
    TELEGRAM_BOT_TOKEN   — required
    BRAIN_INGEST_URL     — brain endpoint (default: http://localhost:8500)
    BRAIN_ACCESS_KEY     — optional auth key for ingest endpoint
    OPENCLAW_URL         — OpenClaw health URL (default: http://localhost:8340)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

OFFSET_FILE = Path(__file__).resolve().parent.parent / "kb" / "telegram" / ".poll_offset"
DEFAULT_BRAIN_URL = "http://localhost:8500"
DEFAULT_OPENCLAW_URL = "http://localhost:8340"
POLL_INTERVAL = 30  # seconds between polls in daemon mode


def _read_offset() -> int | None:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except ValueError:
            return None
    return None


def _write_offset(offset: int) -> None:
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(offset))


def _openclaw_is_running(url: str) -> bool:
    """Check if OpenClaw/Jarvis is alive."""
    try:
        r = httpx.get(url, timeout=3)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectTimeout):
        return False


def _get_updates(token: str, offset: int | None, timeout: int = 10) -> list[dict]:
    """Call Telegram Bot API getUpdates."""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params: dict = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    r = httpx.get(url, params=params, timeout=timeout + 5)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data.get("result", [])


def _extract_content(update: dict) -> tuple[str, dict] | None:
    """Extract text content and metadata from an update. Returns (content, metadata) or None."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None

    text = msg.get("text", "")
    caption = msg.get("caption", "")
    content = text or caption
    if not content:
        return None

    user = msg.get("from", {})
    chat = msg.get("chat", {})

    metadata = {
        "source": "telegram_poll",
        "user_id": str(user.get("id", "")),
        "user_name": user.get("first_name", "") + " " + user.get("last_name", ""),
        "username": user.get("username", ""),
        "chat_id": str(chat.get("id", "")),
        "message_id": str(msg.get("message_id", "")),
        "date": msg.get("date"),
    }
    metadata = {k: v for k, v in metadata.items() if v}

    return content, metadata


def _send_to_brain(
    brain_url: str,
    content: str,
    metadata: dict,
    access_key: str | None = None,
) -> dict:
    """POST to brain ingest endpoint."""
    headers = {}
    if access_key:
        headers["X-Brain-Key"] = access_key

    payload = {
        "content": content,
        "source": "telegram_poll",
        "tags": ["telegram", "live"],
        "metadata": metadata,
    }

    r = httpx.post(f"{brain_url}/ingest", json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def poll_once(
    token: str,
    brain_url: str,
    access_key: str | None = None,
    test_mode: bool = False,
) -> int:
    """Run one poll cycle. Returns number of messages captured."""
    offset = _read_offset()
    updates = _get_updates(token, offset, timeout=1 if test_mode else 10)

    if test_mode:
        print(f"Bot API connection OK. Pending updates: {len(updates)}")
        if updates:
            for u in updates[:3]:
                msg = u.get("message", {})
                print(f"  - [{msg.get('date', '?')}] {msg.get('from', {}).get('first_name', '?')}: {msg.get('text', '(no text)')[:80]}")
        return len(updates)

    captured = 0
    for update in updates:
        update_id = update["update_id"]

        extracted = _extract_content(update)
        if extracted:
            content, metadata = extracted
            try:
                result = _send_to_brain(brain_url, content, metadata, access_key)
                captured += 1
                print(f"  Captured: {content[:80]}... → {result.get('status', '?')}")
            except Exception as e:
                print(f"  Error sending to brain: {e}")

        # Always advance offset even if we skip non-text updates
        _write_offset(update_id + 1)

    return captured


def run_daemon(
    token: str,
    brain_url: str,
    openclaw_url: str,
    access_key: str | None = None,
    interval: int = POLL_INTERVAL,
) -> None:
    """Continuous polling loop with OpenClaw guard."""
    print(f"Daemon mode. Polling every {interval}s. Ctrl+C to stop.")
    print(f"OpenClaw guard: {openclaw_url}")
    print(f"Brain endpoint: {brain_url}")

    while True:
        try:
            if _openclaw_is_running(openclaw_url):
                print(f"[{time.strftime('%H:%M:%S')}] OpenClaw is running — skipping poll (adapter hooks active)")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] OpenClaw down — polling Telegram...")
                captured = poll_once(token, brain_url, access_key)
                print(f"  Captured {captured} messages")
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"  Poll error: {e}")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Bot API poller → Open Brain (when OpenClaw is down)"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Single poll cycle, then exit")
    mode.add_argument("--daemon", action="store_true", help="Continuous polling loop")

    parser.add_argument("--test", action="store_true", help="Test bot API connection only (use with --once)")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL, help=f"Poll interval in seconds (default: {POLL_INTERVAL})")
    parser.add_argument("--skip-guard", action="store_true", help="Skip OpenClaw health check")

    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    brain_url = os.environ.get("BRAIN_INGEST_URL", DEFAULT_BRAIN_URL)
    openclaw_url = os.environ.get("OPENCLAW_URL", DEFAULT_OPENCLAW_URL)
    access_key = os.environ.get("BRAIN_ACCESS_KEY")

    if args.once:
        if not args.skip_guard and not args.test and _openclaw_is_running(openclaw_url):
            print("OpenClaw is running — adapter hooks handle brain capture. Skipping.")
            print("Use --skip-guard to force.")
            return
        captured = poll_once(token, brain_url, access_key, test_mode=args.test)
        if not args.test:
            print(f"Captured {captured} messages")
    else:
        run_daemon(token, brain_url, openclaw_url, access_key, interval=args.interval)


if __name__ == "__main__":
    main()
