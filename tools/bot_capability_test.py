#!/usr/bin/env python3
"""
Bot Capability Test Suite
=========================
Standardized testing across all 4 bots with Sentry observability.

Usage:
    # Watch mode - monitor all bot traces in real-time
    doppler run --project voltron --config dev -- python tools/bot_capability_test.py watch

    # Test mode - send test commands to a specific bot
    doppler run --project voltron --config dev -- python tools/bot_capability_test.py test pepper

    # Full test - test all bots sequentially
    doppler run --project voltron --config dev -- python tools/bot_capability_test.py test all
"""

import os
import sys
import json
import time
import asyncio
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Bot configurations
BOTS = {
    "pepper": {
        "name": "PEPPER",
        "handle": "@Spicyclawd_bot",
        "token_env": "PEPPER_BOT_TOKEN",
        "service": "pepper",
    },
    "friday": {
        "name": "FRIDAY",
        "handle": "@FRIDAY_MCU_bot",
        "token_env": "FRIDAY_BOT_TOKEN",
        "service": "friday",
    },
    "gus": {
        "name": "Gus",
        "handle": "@FactoryLM_bot",
        "token_env": "TELEGRAM_BOT_TOKEN",
        "service": "factorylm",
    },
    "remoteme": {
        "name": "RemoteMe",
        "handle": "@JarvisMIO_bot",
        "token_env": "REMOTEME_BOT_TOKEN",
        "service": "remoteme",
    },
}

# Test cases for each capability
TEST_CASES = [
    {
        "id": "nodes_screenshot",
        "capability": "nodes",
        "name": "Screenshot",
        "command": "ss on travel",
        "expect": "image or screenshot confirmation",
    },
    {
        "id": "nodes_shell",
        "capability": "nodes",
        "name": "Shell Command",
        "command": "run hostname on travel",
        "expect": "hostname output",
    },
    {
        "id": "memory_query",
        "capability": "memory",
        "name": "Memory Query",
        "command": "what did we discuss about screenshots before?",
        "expect": "RAG results from conversation history",
    },
    {
        "id": "factory_diagnosis",
        "capability": "factory",
        "name": "Factory Diagnosis",
        "command": "why would a conveyor stop suddenly?",
        "expect": "AI diagnosis with troubleshooting steps",
    },
    {
        "id": "github_gist",
        "capability": "github",
        "name": "GitHub Gist",
        "command": "create a gist with test content",
        "expect": "gist URL",
    },
    {
        "id": "status_check",
        "capability": "telemetry",
        "name": "Status Check",
        "command": "status",
        "expect": "system health report",
    },
]

# Mike's chat ID for sending test messages
MIKE_CHAT_ID = 8445149012


class BotTester:
    """Test harness for bot capabilities."""

    def __init__(self):
        self.results: Dict[str, Dict[str, dict]] = {}
        self.http = httpx.AsyncClient(timeout=30)

    async def close(self):
        await self.http.aclose()

    async def send_message(self, bot_key: str, text: str) -> dict:
        """Send a message to a bot via Telegram API."""
        bot = BOTS[bot_key]
        token = os.getenv(bot["token_env"])

        if not token:
            return {"success": False, "error": f"Missing {bot['token_env']}"}

        url = f"https://api.telegram.org/bot{token}/sendMessage"

        try:
            resp = await self.http.post(url, json={
                "chat_id": MIKE_CHAT_ID,
                "text": text,
            })

            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run_test(self, bot_key: str, test: dict) -> dict:
        """Run a single test case."""
        bot = BOTS[bot_key]

        print(f"\n  [{test['id']}] {test['name']}")
        print(f"    Command: {test['command']}")

        start = time.time()
        result = await self.send_message(bot_key, test["command"])
        elapsed = (time.time() - start) * 1000

        if result["success"]:
            print(f"    Status: SENT ({elapsed:.0f}ms)")
            print(f"    Expect: {test['expect']}")
        else:
            print(f"    Status: FAILED - {result['error']}")

        return {
            "test_id": test["id"],
            "capability": test["capability"],
            "success": result["success"],
            "elapsed_ms": elapsed,
            "error": result.get("error"),
        }

    async def test_bot(self, bot_key: str) -> List[dict]:
        """Run all tests on a single bot."""
        bot = BOTS[bot_key]
        print(f"\n{'='*60}")
        print(f"TESTING: {bot['name']} ({bot['handle']})")
        print(f"{'='*60}")

        results = []
        for test in TEST_CASES:
            result = await self.run_test(bot_key, test)
            results.append(result)
            await asyncio.sleep(1)  # Rate limiting

        return results

    async def test_all(self):
        """Test all bots."""
        print("\n" + "="*60)
        print("UNIFIED CAPABILITIES TEST SUITE")
        print(f"Started: {datetime.now().isoformat()}")
        print("="*60)

        all_results = {}

        for bot_key in BOTS:
            results = await self.test_bot(bot_key)
            all_results[bot_key] = results

        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)

        for bot_key, results in all_results.items():
            bot = BOTS[bot_key]
            sent = sum(1 for r in results if r["success"])
            print(f"  {bot['name']}: {sent}/{len(results)} messages sent")

        print("\nNote: Check Sentry/Telegram for actual responses")
        print("Watch mode: python tools/bot_capability_test.py watch")

        return all_results


class SentryWatcher:
    """Watch Sentry events in real-time."""

    def __init__(self):
        self.sentry_token = os.getenv("SENTRY_AUTH_TOKEN")
        self.sentry_org = os.getenv("SENTRY_ORG", "factorylm")
        self.http = httpx.AsyncClient(timeout=30)

    async def close(self):
        await self.http.aclose()

    async def get_recent_events(self, project: str, limit: int = 10) -> List[dict]:
        """Get recent events from Sentry."""
        if not self.sentry_token:
            return []

        url = f"https://sentry.io/api/0/projects/{self.sentry_org}/{project}/events/"

        try:
            resp = await self.http.get(
                url,
                headers={"Authorization": f"Bearer {self.sentry_token}"},
                params={"limit": limit}
            )

            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Sentry API error: {e}")
            return []


class TraceWatcher:
    """Watch local trace files in real-time."""

    def __init__(self):
        self.traces_dirs = [
            Path("traces"),
            Path("services/telegram/pepper/traces"),
            Path("services/telegram/jarvis_mio/remoteme/traces"),
        ]
        self.last_positions: Dict[str, int] = {}

    def get_new_traces(self) -> List[dict]:
        """Get new traces since last check."""
        new_traces = []
        today = datetime.now().strftime("%Y-%m-%d")

        for traces_dir in self.traces_dirs:
            if not traces_dir.exists():
                continue

            trace_file = traces_dir / f"{today}.jsonl"
            if not trace_file.exists():
                continue

            file_key = str(trace_file)
            last_pos = self.last_positions.get(file_key, 0)

            try:
                with open(trace_file, "r") as f:
                    f.seek(last_pos)
                    for line in f:
                        if line.strip():
                            try:
                                trace = json.loads(line)
                                trace["_source"] = traces_dir.name
                                new_traces.append(trace)
                            except json.JSONDecodeError:
                                pass
                    self.last_positions[file_key] = f.tell()
            except Exception as e:
                logger.debug(f"Error reading {trace_file}: {e}")

        return new_traces

    def format_trace(self, trace: dict) -> str:
        """Format a trace for display."""
        source = trace.get("_source", "unknown")
        name = trace.get("name", trace.get("type", "event"))
        status = trace.get("status", "")
        duration = trace.get("duration_ms", 0)

        attrs = trace.get("attributes", {})
        intent = attrs.get("parsed.intent", attrs.get("intent", ""))
        node = attrs.get("node.name", attrs.get("node", ""))

        parts = [f"[{source}]", name]
        if intent:
            parts.append(f"intent={intent}")
        if node:
            parts.append(f"node={node}")
        if duration:
            parts.append(f"{duration:.0f}ms")
        if status:
            parts.append(f"[{status}]")

        return " | ".join(parts)


async def watch_mode():
    """Real-time trace watching."""
    print("\n" + "="*60)
    print("TRACE WATCHER - Real-time Bot Monitoring")
    print("="*60)
    print("\nWatching for bot activity...")
    print("Send messages to any bot to see traces here.")
    print("Press Ctrl+C to stop.\n")

    watcher = TraceWatcher()

    # Initial read to skip existing
    watcher.get_new_traces()

    try:
        while True:
            traces = watcher.get_new_traces()

            for trace in traces:
                timestamp = trace.get("timestamp", datetime.now().isoformat())
                if isinstance(timestamp, str):
                    timestamp = timestamp[11:19]  # Extract time portion

                formatted = watcher.format_trace(trace)
                print(f"{timestamp} {formatted}")

            await asyncio.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\nStopped watching.")


async def main():
    parser = argparse.ArgumentParser(description="Bot Capability Test Suite")
    parser.add_argument("command", choices=["test", "watch"], help="Command to run")
    parser.add_argument("target", nargs="?", default="all",
                       help="Bot to test (pepper, friday, gus, remoteme, all)")

    args = parser.parse_args()

    if args.command == "watch":
        await watch_mode()

    elif args.command == "test":
        tester = BotTester()

        try:
            if args.target == "all":
                await tester.test_all()
            elif args.target in BOTS:
                await tester.test_bot(args.target)
            else:
                print(f"Unknown bot: {args.target}")
                print(f"Available: {', '.join(BOTS.keys())}, all")
                sys.exit(1)
        finally:
            await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
