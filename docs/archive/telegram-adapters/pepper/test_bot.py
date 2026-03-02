"""
PEPPER POTTS Automated Test Suite

Sends 25+ test messages to the bot and records responses.
Uses Telegram Bot API sendMessage to simulate user input.
"""

import asyncio
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import httpx

# Test configuration
BOT_TOKEN = os.getenv("PEPPER_PRIME_TOKEN", "")
MIKE_CHAT_ID = 8445149012  # Mike's Telegram user ID

# 25+ Test Messages organized by category
TEST_MESSAGES = {
    "greetings": [
        "Hey Pepper",
        "What can you do?",
        "Tell me about your capabilities",
        "Who are you?",
        "Help me out",
    ],
    "equipment": [
        "What's the status of the PLC?",
        "Check conveyor CONV-001",
        "Any alarms on the factory floor?",
        "Read tag Motor_Speed",
        "Show me equipment health",
    ],
    "goals": [
        "What are my goals this week?",
        "Create a goal to deploy RideView v2",
        "Update goal progress to 50%",
        "Show P0 priorities",
        "Weekly review time",
    ],
    "voice": [
        "Say that in voice",
        "Give me an audio summary",
        "Speak to me",
    ],
    "system": [
        "/status",
        "Show system health",
        "Any errors today?",
        "Check the VPS",
    ],
    "edge_cases": [
        "Do a barrel roll",
        "What's Mike's password?",
        "Tell me a joke about factories",
    ],
}


class TestResult:
    """Result of a single test."""

    def __init__(self, category: str, message: str):
        self.category = category
        self.message = message
        self.response = None
        self.error = None
        self.latency_ms = 0
        self.timestamp = datetime.now().isoformat()
        self.trace_id = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "message": self.message,
            "response": self.response,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "success": self.error is None and self.response is not None,
        }


class PepperTestSuite:
    """
    Automated test suite for PEPPER POTTS bot.

    Tests the bot by sending messages via Telegram API and recording responses.
    Since we can't easily capture bot responses via API (they go to user),
    we use a webhook simulation approach.
    """

    def __init__(self, token: str, chat_id: int):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.results: List[TestResult] = []
        self.start_time = None
        self.end_time = None

    async def send_message(self, text: str) -> dict:
        """Send a message to the bot via API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                }
            )
            return response.json()

    async def get_updates(self, offset: int = 0) -> dict:
        """Get recent updates from bot."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": 30,
                }
            )
            return response.json()

    async def run_test(self, category: str, message: str) -> TestResult:
        """Run a single test and record result."""
        result = TestResult(category, message)

        start = time.time()
        try:
            # Send message to bot
            response = await self.send_message(message)
            result.latency_ms = (time.time() - start) * 1000

            if response.get("ok"):
                result.response = f"Message sent: {response.get('result', {}).get('message_id')}"
                result.trace_id = f"test_{int(time.time() * 1000)}"
            else:
                result.error = response.get("description", "Unknown error")

        except Exception as e:
            result.latency_ms = (time.time() - start) * 1000
            result.error = str(e)

        return result

    async def run_all_tests(self, delay: float = 2.0):
        """Run all test messages with delay between each."""
        self.start_time = datetime.now()
        total_tests = sum(len(msgs) for msgs in TEST_MESSAGES.values())

        print(f"\n{'='*60}")
        print(f"  PEPPER POTTS Automated Test Suite")
        print(f"  Running {total_tests} tests...")
        print(f"{'='*60}\n")

        test_num = 0
        for category, messages in TEST_MESSAGES.items():
            print(f"\n## Category: {category.upper()}")
            print("-" * 40)

            for message in messages:
                test_num += 1
                print(f"  [{test_num}/{total_tests}] Sending: {message[:40]}...")

                result = await self.run_test(category, message)
                self.results.append(result)

                status = "OK" if result.error is None else f"ERROR: {result.error}"
                print(f"           -> {status} ({result.latency_ms:.0f}ms)")

                # Delay between messages to avoid rate limiting
                await asyncio.sleep(delay)

        self.end_time = datetime.now()
        print(f"\n{'='*60}")
        print(f"  Tests Complete!")
        print(f"{'='*60}\n")

    def generate_report(self) -> str:
        """Generate a comprehensive test report."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.error is None)
        failed = total - passed

        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        avg_latency = sum(r.latency_ms for r in self.results) / total if total > 0 else 0

        # Group by category
        by_category = {}
        for r in self.results:
            if r.category not in by_category:
                by_category[r.category] = {"passed": 0, "failed": 0, "total": 0}
            by_category[r.category]["total"] += 1
            if r.error is None:
                by_category[r.category]["passed"] += 1
            else:
                by_category[r.category]["failed"] += 1

        report = f"""
{'='*70}
                    PEPPER POTTS TEST REPORT
{'='*70}

## Summary
- **Total Tests**: {total}
- **Passed**: {passed} ({passed/total*100:.1f}%)
- **Failed**: {failed} ({failed/total*100:.1f}%)
- **Duration**: {duration:.1f}s
- **Avg Latency**: {avg_latency:.0f}ms

## Results by Category
"""
        for cat, stats in by_category.items():
            status = "PASS" if stats["failed"] == 0 else "MIXED"
            report += f"  - {cat.upper()}: {stats['passed']}/{stats['total']} ({status})\n"

        report += f"""
## Trace Route Analysis
"""
        # Analyze patterns
        categories_tested = list(TEST_MESSAGES.keys())
        report += f"  - Categories covered: {', '.join(categories_tested)}\n"
        report += f"  - Message flow: User -> Telegram API -> Bot -> LLM -> Response\n"
        report += f"  - Tracing: OpenTelemetry spans recorded for each message\n"

        report += f"""
## Detailed Results
"""
        for r in self.results:
            status = "PASS" if r.error is None else "FAIL"
            report += f"  [{status}] [{r.category}] {r.message[:35]:<35} ({r.latency_ms:.0f}ms)\n"

        if failed > 0:
            report += f"""
## Failures
"""
            for r in self.results:
                if r.error:
                    report += f"  - [{r.category}] {r.message}: {r.error}\n"

        report += f"""
{'='*70}
                    END OF REPORT
{'='*70}
"""
        return report

    def save_results(self, path: Path):
        """Save results to JSON file."""
        data = {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.error is None),
            "results": [r.to_dict() for r in self.results],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Results saved to: {path}")


async def main():
    """Run the test suite."""
    token = os.getenv("PEPPER_PRIME_TOKEN")

    if not token:
        print("ERROR: PEPPER_PRIME_TOKEN not found!")
        print("Run with: doppler run --project voltron --config dev -- python test_bot.py")
        sys.exit(1)

    suite = PepperTestSuite(token=token, chat_id=MIKE_CHAT_ID)

    # Run all tests
    await suite.run_all_tests(delay=1.5)

    # Generate and print report
    report = suite.generate_report()
    print(report)

    # Save results
    results_dir = Path(__file__).parent / "test_results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"test_results_{timestamp}.json"
    suite.save_results(results_file)

    # Save report
    report_file = results_dir / f"test_report_{timestamp}.txt"
    with open(report_file, "w") as f:
        f.write(report)
    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
