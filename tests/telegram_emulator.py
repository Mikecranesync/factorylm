"""
Telegram Bot Emulator for FactoryLM
====================================
Simulates Telegram conversations for testing maintenance flows without
a real Telegram account.

Features:
- Mock Telegram Update/Message objects
- Simulates user sending messages to bot
- Routes to diagnosis service and captures responses
- Scripted conversation playback for CI

Usage:
    # Interactive mode
    python tests/telegram_emulator.py

    # Run scripted test
    python tests/telegram_emulator.py --script tests/conversations/maintenance_flow.json

    # CI mode (exit code reflects pass/fail)
    python tests/telegram_emulator.py --ci
"""

import os
import sys
import json
import time
import asyncio
import httpx
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Mock Telegram Objects
# ============================================================================

@dataclass
class MockUser:
    id: int = 12345
    first_name: str = "TestTech"
    last_name: str = "User"
    username: str = "test_technician"
    is_bot: bool = False


@dataclass
class MockChat:
    id: int = 12345
    type: str = "private"
    first_name: str = "TestTech"
    username: str = "test_technician"


@dataclass
class MockMessage:
    message_id: int
    date: datetime
    chat: MockChat
    from_user: MockUser
    text: str
    reply_to_message: Optional['MockMessage'] = None

    @classmethod
    def create(cls, text: str, message_id: int = None):
        return cls(
            message_id=message_id or int(time.time() * 1000),
            date=datetime.now(),
            chat=MockChat(),
            from_user=MockUser(),
            text=text
        )


@dataclass
class MockUpdate:
    update_id: int
    message: MockMessage

    @classmethod
    def create(cls, text: str):
        return cls(
            update_id=int(time.time() * 1000),
            message=MockMessage.create(text)
        )


# ============================================================================
# Bot Response Handler
# ============================================================================

@dataclass
class BotResponse:
    text: str
    latency_ms: int
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


class TelegramEmulator:
    """
    Emulates Telegram bot interactions for testing.

    Connects to:
    - Diagnosis service (http://localhost:8200 or Matrix API)
    - Demo UI (http://localhost:8080)
    """

    def __init__(
        self,
        diagnosis_url: str = None,
        demo_ui_url: str = None,
        matrix_url: str = None,
        verbose: bool = True
    ):
        self.diagnosis_url = diagnosis_url or os.getenv("DIAGNOSIS_URL", "http://localhost:8200")
        self.demo_ui_url = demo_ui_url or os.getenv("DEMO_UI_URL", "http://localhost:8080")
        self.matrix_url = matrix_url or os.getenv("MATRIX_URL", "http://100.72.2.99:8000")
        self.verbose = verbose
        self.conversation_history: List[Dict] = []
        self.client = httpx.Client(timeout=30)

    def log(self, msg: str):
        if self.verbose:
            print(msg)

    def send_message(self, text: str) -> BotResponse:
        """
        Simulate sending a message to the bot and getting a response.

        Routes based on message content:
        - "show me io" / "show io" -> Matrix API tags
        - "why stopped" / "why is" / "diagnose" -> Diagnosis service
        - Other -> Echo or help
        """
        start_time = time.time()
        update = MockUpdate.create(text)

        self.log(f"\n[USER] {text}")

        # Store in history
        self.conversation_history.append({
            "role": "user",
            "text": text,
            "timestamp": datetime.now().isoformat()
        })

        try:
            response_text = self._route_message(text.lower(), text)
            latency_ms = int((time.time() - start_time) * 1000)

            response = BotResponse(
                text=response_text,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            response = BotResponse(
                text=f"Error: {str(e)}",
                latency_ms=latency_ms,
                error=str(e)
            )

        # Store response
        self.conversation_history.append({
            "role": "bot",
            "text": response.text,
            "latency_ms": response.latency_ms,
            "timestamp": datetime.now().isoformat()
        })

        self.log(f"[BOT] ({response.latency_ms}ms) {response.text[:500]}...")

        return response

    def _route_message(self, text_lower: str, original_text: str) -> str:
        """Route message to appropriate handler."""

        # Command: /start
        if text_lower.startswith("/start"):
            return self._handle_start()

        # Command: /help
        if text_lower.startswith("/help"):
            return self._handle_help()

        # Command: /status
        if text_lower.startswith("/status"):
            return self._handle_status()

        # Show IO request
        if any(kw in text_lower for kw in ["show io", "show me io", "live io", "plc io", "tag"]):
            return self._handle_show_io()

        # Why stopped / diagnosis request
        if any(kw in text_lower for kw in ["why", "stopped", "diagnose", "fault", "problem", "wrong", "issue"]):
            return self._handle_diagnosis(original_text)

        # Default: help
        return self._handle_unknown(original_text)

    def _handle_start(self) -> str:
        return """Welcome to FactoryLM!

I can help you monitor and diagnose your equipment.

Commands:
  /status - Check system status
  /help - Show available commands

Try asking:
  "Show me IO for the conveyor"
  "Why is the motor stopped?"
  "What faults are active?"
"""

    def _handle_help(self) -> str:
        return """FactoryLM Commands:

Monitoring:
  "show me IO" - Display live PLC tags
  "show status" - Equipment status summary

Diagnosis:
  "why is this stopped?" - AI fault analysis
  "what's wrong?" - Check for active faults
  "diagnose [issue]" - Ask about specific problem

System:
  /status - Check service connectivity
  /help - This message
"""

    def _handle_status(self) -> str:
        """Check connectivity to all services."""
        status_lines = ["System Status:"]

        # Check Matrix API
        try:
            resp = self.client.get(f"{self.matrix_url}/api/health", timeout=5)
            if resp.status_code == 200:
                status_lines.append(f"  [OK] Matrix API: {self.matrix_url}")
            else:
                status_lines.append(f"  [!] Matrix API: HTTP {resp.status_code}")
        except Exception as e:
            status_lines.append(f"  [X] Matrix API: {str(e)[:50]}")

        # Check Demo UI
        try:
            resp = self.client.get(f"{self.demo_ui_url}/health", timeout=5)
            if resp.status_code == 200:
                status_lines.append(f"  [OK] Demo UI: {self.demo_ui_url}")
            else:
                status_lines.append(f"  [!] Demo UI: HTTP {resp.status_code}")
        except Exception as e:
            status_lines.append(f"  [X] Demo UI: {str(e)[:50]}")

        return "\n".join(status_lines)

    def _handle_show_io(self) -> str:
        """Fetch and format live IO from Matrix API."""
        try:
            resp = self.client.get(f"{self.matrix_url}/api/tags?limit=1", timeout=10)
            resp.raise_for_status()
            tags_list = resp.json()

            if not tags_list:
                return "No tag data available. Is Factory I/O running?"

            tags = tags_list[0]

            # Format as readable output
            lines = [
                "Live I/O Status:",
                f"  Node: {tags.get('node_id', 'unknown')}",
                f"  Time: {tags.get('timestamp', 'unknown')[:19]}",
                "",
                "Motors:",
                f"  Motor:     {'RUNNING' if tags.get('motor_running') else 'STOPPED'} @ {tags.get('motor_speed', 0)}%",
                f"  Current:   {tags.get('motor_current', 0):.2f} A",
                f"  Conveyor:  {'RUNNING' if tags.get('conveyor_running') else 'STOPPED'} @ {tags.get('conveyor_speed', 0)}%",
                "",
                "Sensors:",
                f"  Temp:      {tags.get('temperature', 0):.1f} C",
                f"  Pressure:  {tags.get('pressure', 0)} PSI",
                f"  Sensor 1:  {'ACTIVE' if tags.get('sensor_1') else 'clear'}",
                f"  Sensor 2:  {'ACTIVE' if tags.get('sensor_2') else 'clear'}",
                "",
                "Alarms:",
                f"  Fault:     {'ACTIVE!' if tags.get('fault_alarm') else 'None'}",
                f"  E-Stop:    {'PRESSED!' if tags.get('e_stop') else 'Clear'}",
                f"  Error:     {tags.get('error_code', 0)} - {tags.get('error_message', 'None')}"
            ]

            return "\n".join(lines)

        except Exception as e:
            return f"Failed to fetch IO: {str(e)}"

    def _handle_diagnosis(self, question: str) -> str:
        """Send diagnosis request to Demo UI or Diagnosis service."""
        try:
            # Try Demo UI first (has full diagnosis pipeline)
            resp = self.client.post(
                f"{self.demo_ui_url}/api/diagnose",
                json={"question": question},
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                lines = [
                    f"AI Diagnosis ({data.get('latency_ms', 0)}ms):",
                    f"Model: {data.get('model', 'unknown')}",
                    "",
                    data.get('answer', 'No answer available')
                ]

                faults = data.get('faults_detected', [])
                if faults:
                    lines.append("")
                    lines.append(f"Active Faults: {', '.join(faults)}")

                return "\n".join(lines)

            # Fallback to diagnosis service
            resp = self.client.post(
                f"{self.diagnosis_url}/diagnose",
                json={"question": question},
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                return data.get('diagnosis', 'No diagnosis available')

            return f"Diagnosis service error: HTTP {resp.status_code}"

        except Exception as e:
            return f"Diagnosis failed: {str(e)}"

    def _handle_unknown(self, text: str) -> str:
        return f"""I didn't understand: "{text}"

Try:
  "show me IO" - View live PLC tags
  "why is this stopped?" - AI diagnosis
  /help - All commands
"""

    def run_script(self, script_path: str) -> Dict[str, Any]:
        """
        Run a scripted conversation from JSON file.

        Script format:
        {
            "name": "Test Name",
            "steps": [
                {"user": "message", "expect_contains": ["keyword1", "keyword2"]},
                ...
            ]
        }
        """
        with open(script_path) as f:
            script = json.load(f)

        results = {
            "name": script.get("name", "Unknown"),
            "passed": 0,
            "failed": 0,
            "steps": []
        }

        self.log(f"\n{'='*60}")
        self.log(f"Running: {results['name']}")
        self.log('='*60)

        for i, step in enumerate(script.get("steps", [])):
            user_msg = step.get("user", "")
            expect_contains = step.get("expect_contains", [])
            expect_not_contains = step.get("expect_not_contains", [])

            response = self.send_message(user_msg)

            # Check expectations
            passed = True
            failures = []

            for keyword in expect_contains:
                if keyword.lower() not in response.text.lower():
                    passed = False
                    failures.append(f"Missing: '{keyword}'")

            for keyword in expect_not_contains:
                if keyword.lower() in response.text.lower():
                    passed = False
                    failures.append(f"Unexpected: '{keyword}'")

            step_result = {
                "step": i + 1,
                "user": user_msg,
                "response": response.text[:200],
                "latency_ms": response.latency_ms,
                "passed": passed,
                "failures": failures
            }

            results["steps"].append(step_result)

            if passed:
                results["passed"] += 1
                self.log(f"  [PASS] Step {i+1}")
            else:
                results["failed"] += 1
                self.log(f"  [FAIL] Step {i+1}: {failures}")

        self.log(f"\nResults: {results['passed']} passed, {results['failed']} failed")

        return results

    def interactive(self):
        """Run interactive chat session."""
        print("\n" + "="*60)
        print("FactoryLM Telegram Emulator")
        print("="*60)
        print("Type messages as if you were chatting with the bot.")
        print("Commands: /start, /help, /status, /quit")
        print("="*60 + "\n")

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["/quit", "/exit", "quit", "exit"]:
                    print("Goodbye!")
                    break

                self.send_message(user_input)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                break


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Telegram Bot Emulator for FactoryLM")
    parser.add_argument("--script", help="Path to conversation script JSON")
    parser.add_argument("--ci", action="store_true", help="CI mode (exit code reflects pass/fail)")
    parser.add_argument("--matrix-url", default=os.getenv("MATRIX_URL", "http://100.72.2.99:8000"))
    parser.add_argument("--demo-url", default=os.getenv("DEMO_UI_URL", "http://localhost:8080"))
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    emulator = TelegramEmulator(
        matrix_url=args.matrix_url,
        demo_ui_url=args.demo_url,
        verbose=not args.quiet
    )

    if args.script:
        results = emulator.run_script(args.script)
        if args.ci:
            sys.exit(0 if results["failed"] == 0 else 1)
    else:
        emulator.interactive()


if __name__ == "__main__":
    main()
