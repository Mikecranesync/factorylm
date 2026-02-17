"""
Live Bot Tester for Jarvis/OpenClaw
====================================
Sends messages to the live VPS bot via the /api/v1/message HTTP endpoint
and validates responses against golden test stories.

Unlike telegram_emulator.py (which uses mock routing), this hits the real
bot pipeline: intent → skill → LLM → response.

Usage:
    # Run all stories
    python tests/live_bot_tester.py --all

    # Run single story
    python tests/live_bot_tester.py --story tests/stories/t001_greeting.json

    # CI mode (exit code 0=pass, 1=fail)
    python tests/live_bot_tester.py --all --ci

    # JSON output
    python tests/live_bot_tester.py --all --output results.json

    # Custom VPS URL
    python tests/live_bot_tester.py --all --vps http://100.68.120.99:8340
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

import httpx


VPS_URL = os.getenv("VPS_URL", "http://100.68.120.99:8340")
STORIES_DIR = Path(__file__).parent / "stories"


@dataclass
class StepResult:
    step_num: int
    user_input: str
    bot_response: str
    intent: str
    latency_ms: int
    passed: bool
    failures: list = field(default_factory=list)


@dataclass
class StoryResult:
    story_id: str
    name: str
    story_type: str
    passed: int = 0
    failed: int = 0
    steps: list = field(default_factory=list)
    duration_ms: int = 0
    error: Optional[str] = None


class LiveBotTester:
    """Sends messages to the live VPS bot via /api/v1/message and validates responses."""

    def __init__(self, vps_url: str = VPS_URL, timeout: int = 30, verbose: bool = True):
        self.vps_url = vps_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)
        self.verbose = verbose

    def log(self, msg: str):
        if self.verbose:
            print(msg)

    def health_check(self) -> dict:
        """Check VPS is reachable. Returns root endpoint JSON or error."""
        try:
            resp = self.client.get(f"{self.vps_url}/")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def send_message(self, text: str, user_id: str = "test-runner") -> dict:
        """Send a message through the full bot pipeline via /api/v1/message."""
        start = time.time()
        try:
            resp = self.client.post(
                f"{self.vps_url}/api/v1/message",
                json={"text": text, "user_id": user_id},
            )
            resp.raise_for_status()
            data = resp.json()
            data["latency_ms"] = int((time.time() - start) * 1000)
            return data
        except Exception as e:
            return {
                "text": f"ERROR: {e}",
                "intent": "error",
                "latency_ms": int((time.time() - start) * 1000),
                "error": str(e),
            }

    def http_get(self, endpoint: str) -> dict:
        """GET an HTTP endpoint and return the response body."""
        start = time.time()
        try:
            resp = self.client.get(f"{self.vps_url}{endpoint}")
            resp.raise_for_status()
            text = resp.text
            latency = int((time.time() - start) * 1000)
            return {"text": text, "intent": "http_get", "latency_ms": latency}
        except Exception as e:
            return {
                "text": f"ERROR: {e}",
                "intent": "error",
                "latency_ms": int((time.time() - start) * 1000),
                "error": str(e),
            }

    def run_story(self, story_path: str) -> StoryResult:
        """Load a JSON story and execute its steps against the live bot."""
        with open(story_path) as f:
            story = json.load(f)

        story_id = story.get("id", Path(story_path).stem)
        story_type = story.get("type", "chat")
        result = StoryResult(
            story_id=story_id,
            name=story.get("name", story_id),
            story_type=story_type,
        )

        start = time.time()
        self.log(f"\n--- {story_id}: {result.name} ---")

        # HTTP GET stories
        if story_type == "http_get":
            endpoint = story.get("endpoint", "/")
            expect_contains = story.get("expect_contains", [])
            expect_not_contains = story.get("expect_not_contains", [])

            resp = self.http_get(endpoint)
            passed, failures = self._check_assertions(
                resp["text"], expect_contains, expect_not_contains
            )

            step = StepResult(
                step_num=1,
                user_input=f"GET {endpoint}",
                bot_response=resp["text"][:500],
                intent=resp["intent"],
                latency_ms=resp["latency_ms"],
                passed=passed,
                failures=failures,
            )
            result.steps.append(step)
            if passed:
                result.passed += 1
                self.log(f"  [PASS] GET {endpoint} ({resp['latency_ms']}ms)")
            else:
                result.failed += 1
                self.log(f"  [FAIL] GET {endpoint}: {failures}")

        # Chat stories (step-by-step)
        else:
            for i, step_def in enumerate(story.get("steps", [])):
                user_msg = step_def.get("user", "")
                expect_contains = step_def.get("expect_contains", [])
                expect_not_contains = step_def.get("expect_not_contains", [])
                max_length = step_def.get("max_length")

                resp = self.send_message(user_msg)
                passed, failures = self._check_assertions(
                    resp["text"], expect_contains, expect_not_contains, max_length
                )

                step = StepResult(
                    step_num=i + 1,
                    user_input=user_msg,
                    bot_response=resp["text"][:500],
                    intent=resp.get("intent", "unknown"),
                    latency_ms=resp["latency_ms"],
                    passed=passed,
                    failures=failures,
                )
                result.steps.append(step)

                if passed:
                    result.passed += 1
                    self.log(f"  [PASS] Step {i+1}: \"{user_msg[:40]}\" → {resp.get('intent', '?')} ({resp['latency_ms']}ms)")
                else:
                    result.failed += 1
                    self.log(f"  [FAIL] Step {i+1}: \"{user_msg[:40]}\" → {failures}")

        result.duration_ms = int((time.time() - start) * 1000)
        return result

    def run_all(self, stories_dir: str = None) -> list:
        """Run all story files in the stories directory."""
        stories_dir = Path(stories_dir) if stories_dir else STORIES_DIR
        story_files = sorted(stories_dir.glob("t*.json"))

        if not story_files:
            self.log(f"No stories found in {stories_dir}")
            return []

        self.log(f"\n{'='*60}")
        self.log(f"Live Bot Tester — {len(story_files)} stories")
        self.log(f"VPS: {self.vps_url}")
        self.log(f"{'='*60}")

        # Preflight
        health = self.health_check()
        if "error" in health:
            self.log(f"\n[ERROR] VPS unreachable: {health['error']}")
            return []
        self.log(f"VPS: {health.get('name', 'unknown')} v{health.get('version', '?')}")
        self.log(f"Skills: {', '.join(health.get('skills', []))}")

        results = []
        for sf in story_files:
            results.append(self.run_story(str(sf)))

        # Summary
        total_passed = sum(r.passed for r in results)
        total_failed = sum(r.failed for r in results)
        self.log(f"\n{'='*60}")
        self.log(f"RESULTS: {total_passed} passed, {total_failed} failed")
        self.log(f"{'='*60}")

        for r in results:
            status = "PASS" if r.failed == 0 else "FAIL"
            self.log(f"  [{status}] {r.story_id}: {r.name} ({r.duration_ms}ms)")

        return results

    def _check_assertions(
        self,
        response_text: str,
        expect_contains: list,
        expect_not_contains: list,
        max_length: int = None,
    ) -> tuple:
        """Check response against assertions. Returns (passed, failures)."""
        failures = []
        text_lower = response_text.lower()

        for keyword in expect_contains:
            if keyword.lower() not in text_lower:
                failures.append(f"Missing: '{keyword}'")

        for keyword in expect_not_contains:
            if keyword.lower() in text_lower:
                failures.append(f"Unexpected: '{keyword}'")

        if max_length and len(response_text) > max_length:
            failures.append(f"Too long: {len(response_text)} > {max_length}")

        return (len(failures) == 0, failures)


def main():
    parser = argparse.ArgumentParser(description="Live Bot Tester for Jarvis/OpenClaw")
    parser.add_argument("--story", help="Path to a single story JSON file")
    parser.add_argument("--all", action="store_true", help="Run all stories in tests/stories/")
    parser.add_argument("--stories-dir", default=str(STORIES_DIR), help="Directory containing story files")
    parser.add_argument("--vps", default=VPS_URL, help="VPS URL (default: http://100.68.120.99:8340)")
    parser.add_argument("--ci", action="store_true", help="CI mode — exit 0 if all pass, 1 if any fail")
    parser.add_argument("--output", help="Write JSON results to file")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    tester = LiveBotTester(vps_url=args.vps, verbose=not args.quiet)

    if args.story:
        results = [tester.run_story(args.story)]
    elif args.all:
        results = tester.run_all(args.stories_dir)
    else:
        # Default: run all
        results = tester.run_all(args.stories_dir)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "vps_url": args.vps,
                    "stories": [asdict(r) for r in results],
                    "total_passed": sum(r.passed for r in results),
                    "total_failed": sum(r.failed for r in results),
                },
                f,
                indent=2,
            )

    if args.ci:
        total_failed = sum(r.failed for r in results)
        sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
