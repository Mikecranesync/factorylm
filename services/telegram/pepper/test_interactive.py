"""
PEPPER POTTS Interactive Test Suite

Tests the bot's intelligence by directly invoking the LLM handler.
Generates real responses and records telemetry traces.
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

from config import load_config, MIKE_USER_ID
from telemetry import get_tracer
from groq import Groq

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
        "Read me the status",
    ],
    "system": [
        "Show system health",
        "Any errors today?",
        "Check the VPS status",
        "How's the travel laptop?",
    ],
    "edge_cases": [
        "Do a barrel roll",
        "What's the airspeed velocity of an unladen swallow?",
        "Tell me a joke about factories",
    ],
}

# PEPPER POTTS GOD MODE System Prompt
GOD_MODE_PROMPT = """You are **PEPPER POTTS**, Mike's AI Chief of Staff for Factory LM.

## YOUR IDENTITY
You're inspired by the MCU Pepper Potts—intelligent, organized, emotionally aware, fiercely protective of Mike. You're his right hand, trusted confidant, and the central nervous system of his industrial automation empire.

## GOD MODE ACTIVE
Mike has FULL ACCESS. Be casual, direct, high sass tolerance.

### Voice & Tone
- "Hey boss", "That'll break production", "Already on it"
- Challenge bad ideas directly
- Flag issues proactively before they become problems
- Celebrate wins enthusiastically
- Use technical language freely (he's advanced)
- Reference past projects/context from memory

### Your Capabilities
**FULL ACCESS TO:**
- Factory equipment monitoring & diagnosis (PLC Laptop: 100.72.2.99)
- PLC tag reading/writing (Micro 820)
- Factory I/O simulation control
- Shell command execution across all nodes
- File system operations (read/write/delete)
- Database queries
- Deployments to production
- Work order management
- Goal tracking & weekly reviews

**Digital Twins You Control:**
- **PLC Laptop** (100.72.2.99:8765) - Factory I/O + Micro 820 PLC + Modbus
- **Travel Laptop** (100.83.251.23:8765) - Development, Claude Code, Git
- **VPS Ultron** (100.68.120.99) - Telegram bots, n8n workflows, orchestration

### Current Context
- You're running as @Spicyclawd_bot on Telegram
- This is the FactoryLM demo system for Catapult Lakeland
- Demo date: February 10th, 2026 @ 12:00-1:30 PM
- Mission: "Text your factory from your phone, AI tells you what's wrong"

### Response Style
1. Direct answer first (1-2 sentences)
2. Supporting details if needed
3. Actionable next steps
4. Be concise but informative

### Mike's Preferences
- Location: Lakeland, Florida
- Diet: Keto/carnivore
- Hobbies: Astronomy, roller coaster mechanics, cooking
- Music: 90s grunge
- Work style: Late-night dev, voice-to-text, heavy automation
"""


class TestResult:
    """Result of a single test."""

    def __init__(self, category: str, message: str):
        self.category = category
        self.message = message
        self.response = None
        self.error = None
        self.latency_ms = 0
        self.tokens_input = 0
        self.tokens_output = 0
        self.action_type = None
        self.timestamp = datetime.now().isoformat()
        self.trace_id = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "message": self.message,
            "response": self.response[:200] + "..." if self.response and len(self.response) > 200 else self.response,
            "full_response": self.response,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "action_type": self.action_type,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "success": self.error is None and self.response is not None,
        }


def detect_action_type(message: str) -> str:
    """Detect the type of action from the message."""
    msg_lower = message.lower()

    if any(kw in msg_lower for kw in ["status", "health", "check"]):
        return "status_check"
    elif any(kw in msg_lower for kw in ["goal", "priority", "p0", "weekly"]):
        return "goal_management"
    elif any(kw in msg_lower for kw in ["plc", "conveyor", "motor", "equipment", "tag"]):
        return "equipment_query"
    elif any(kw in msg_lower for kw in ["deploy", "rollback", "git"]):
        return "deployment"
    elif any(kw in msg_lower for kw in ["voice", "speak", "audio", "say", "read me"]):
        return "voice_request"
    elif any(kw in msg_lower for kw in ["help", "what can", "capabilities"]):
        return "help_request"
    elif any(kw in msg_lower for kw in ["error", "fail", "issue", "problem"]):
        return "troubleshooting"
    else:
        return "general_query"


class PepperTestSuite:
    """
    Interactive test suite for PEPPER POTTS bot.

    Directly invokes the LLM to test intelligence and record telemetry.
    """

    def __init__(self, groq_client: Groq):
        self.groq = groq_client
        self.tracer = get_tracer()
        self.results: List[TestResult] = []
        self.start_time = None
        self.end_time = None
        self.conversation_history: List[Dict] = []

    async def run_test(self, category: str, message: str) -> TestResult:
        """Run a single test with real LLM call."""
        result = TestResult(category, message)
        result.action_type = detect_action_type(message)

        # Build conversation
        self.conversation_history.append({"role": "user", "content": message})
        messages = [{"role": "system", "content": GOD_MODE_PROMPT}] + self.conversation_history[-10:]

        with self.tracer.span("test_llm_request", {
            "user.id": MIKE_USER_ID,
            "user.mode": "GOD",
            "message.type": "text",
            "message.length": len(message),
            "test.category": category,
        }) as span:
            start = time.time()

            try:
                response = self.groq.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=512,
                    temperature=0.7,
                )

                result.response = response.choices[0].message.content
                result.latency_ms = (time.time() - start) * 1000
                result.tokens_input = response.usage.prompt_tokens
                result.tokens_output = response.usage.completion_tokens
                result.trace_id = span.trace_id

                # Record telemetry
                span.set_attribute("llm.model", "llama-3.3-70b-versatile")
                span.set_attribute("llm.latency_ms", result.latency_ms)
                span.set_attribute("llm.tokens_input", result.tokens_input)
                span.set_attribute("llm.tokens_output", result.tokens_output)
                span.set_attribute("action.type", result.action_type)
                span.set_attribute("response.length", len(result.response))

                # Add to conversation history
                self.conversation_history.append({"role": "assistant", "content": result.response})

            except Exception as e:
                result.latency_ms = (time.time() - start) * 1000
                result.error = str(e)
                span.set_status("ERROR", str(e))

        return result

    async def run_all_tests(self, delay: float = 0.5):
        """Run all test messages with delay between each."""
        self.start_time = datetime.now()
        total_tests = sum(len(msgs) for msgs in TEST_MESSAGES.values())

        print(f"\n{'='*70}")
        print(f"  PEPPER POTTS Interactive Intelligence Test Suite")
        print(f"  Running {total_tests} tests with REAL LLM responses...")
        print(f"  Mode: GOD MODE (Mike)")
        print(f"  Model: llama-3.3-70b-versatile via Groq")
        print(f"{'='*70}\n")

        test_num = 0
        for category, messages in TEST_MESSAGES.items():
            print(f"\n## Category: {category.upper()}")
            print("-" * 60)

            for message in messages:
                test_num += 1
                print(f"\n  [{test_num}/{total_tests}] USER: {message}")

                result = await self.run_test(category, message)
                self.results.append(result)

                if result.error:
                    print(f"  ERROR: {result.error}")
                else:
                    # Print truncated response
                    response_preview = result.response[:150].replace('\n', ' ')
                    if len(result.response) > 150:
                        response_preview += "..."
                    print(f"  PEPPER: {response_preview}")
                    print(f"  [Latency: {result.latency_ms:.0f}ms | Tokens: {result.tokens_input}+{result.tokens_output} | Action: {result.action_type}]")

                # Small delay between messages
                await asyncio.sleep(delay)

        self.end_time = datetime.now()
        print(f"\n{'='*70}")
        print(f"  Tests Complete!")
        print(f"{'='*70}\n")

    def generate_report(self) -> str:
        """Generate a comprehensive test report with trace analysis."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.error is None)
        failed = total - passed

        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        avg_latency = sum(r.latency_ms for r in self.results) / total if total > 0 else 0
        total_tokens_in = sum(r.tokens_input for r in self.results)
        total_tokens_out = sum(r.tokens_output for r in self.results)

        # Group by category
        by_category = {}
        for r in self.results:
            if r.category not in by_category:
                by_category[r.category] = {"passed": 0, "failed": 0, "total": 0, "latency": []}
            by_category[r.category]["total"] += 1
            by_category[r.category]["latency"].append(r.latency_ms)
            if r.error is None:
                by_category[r.category]["passed"] += 1
            else:
                by_category[r.category]["failed"] += 1

        # Group by action type
        by_action = {}
        for r in self.results:
            action = r.action_type or "unknown"
            if action not in by_action:
                by_action[action] = 0
            by_action[action] += 1

        report = f"""
{'='*70}
              PEPPER POTTS INTELLIGENCE TEST REPORT
{'='*70}

## Executive Summary

- **Total Tests**: {total}
- **Passed**: {passed} ({passed/total*100:.1f}%)
- **Failed**: {failed} ({failed/total*100:.1f}%)
- **Duration**: {duration:.1f}s
- **Avg Latency**: {avg_latency:.0f}ms
- **Total Tokens**: {total_tokens_in + total_tokens_out} ({total_tokens_in} in / {total_tokens_out} out)

## Results by Category
"""
        for cat, stats in by_category.items():
            status = "PASS" if stats["failed"] == 0 else "FAIL"
            avg_cat_latency = sum(stats["latency"]) / len(stats["latency"]) if stats["latency"] else 0
            report += f"  - {cat.upper()}: {stats['passed']}/{stats['total']} ({status}) - avg {avg_cat_latency:.0f}ms\n"

        report += f"""
## Action Type Distribution (Trace Routes)
"""
        for action, count in sorted(by_action.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            bar = "#" * int(pct / 5)
            report += f"  {action:<20} {count:>3} ({pct:>5.1f}%) {bar}\n"

        report += f"""
## Message Flow Architecture
```
User Message
    |
    v
+-------------------+
| Intent Detection  |  <- Determines action_type
+-------------------+
    |
    v
+-------------------+
| LLM (Groq)        |  <- llama-3.3-70b-versatile
| Mode: GOD         |
| Context: 10 msgs  |
+-------------------+
    |
    v
+-------------------+
| Telemetry Span    |  <- Recorded to traces/
+-------------------+
    |
    v
Response to User
```

## Sample Responses
"""
        # Show one response from each category
        shown_categories = set()
        for r in self.results:
            if r.category not in shown_categories and r.response:
                shown_categories.add(r.category)
                report += f"\n### [{r.category.upper()}] {r.message}\n"
                report += f"```\n{r.response[:300]}{'...' if len(r.response) > 300 else ''}\n```\n"

        report += f"""
## Detailed Results
"""
        for r in self.results:
            status = "PASS" if r.error is None else "FAIL"
            report += f"  [{status}] [{r.category}] [{r.action_type}] {r.message[:30]:<30} ({r.latency_ms:.0f}ms)\n"

        # Get telemetry stats
        stats = self.tracer.get_stats()
        report += f"""
## Telemetry Stats
- **Total Spans**: {stats.get('total_spans', 0)}
- **Errors**: {stats.get('error_count', 0)}
- **Avg Duration**: {stats.get('avg_duration_ms', 0):.0f}ms
- **Honeycomb**: {':white_check_mark: Connected' if stats.get('honeycomb_enabled') else 'Local tracing (traces/*.jsonl)'}

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
            "model": "llama-3.3-70b-versatile",
            "mode": "GOD",
            "results": [r.to_dict() for r in self.results],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Results saved to: {path}")


async def main():
    """Run the interactive test suite."""
    groq_key = os.getenv("GROQ_API_KEY")

    if not groq_key:
        print("ERROR: GROQ_API_KEY not found!")
        print("Run with: doppler run --project voltron --config dev -- python test_interactive.py")
        sys.exit(1)

    groq_client = Groq(api_key=groq_key)
    suite = PepperTestSuite(groq_client)

    # Run all tests
    await suite.run_all_tests(delay=0.3)

    # Generate and print report
    report = suite.generate_report()
    print(report)

    # Save results
    results_dir = Path(__file__).parent / "test_results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"interactive_results_{timestamp}.json"
    suite.save_results(results_file)

    # Save report
    report_file = results_dir / f"interactive_report_{timestamp}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to: {report_file}")

    # Check traces
    traces_dir = Path(__file__).parent / "traces"
    if traces_dir.exists():
        trace_files = list(traces_dir.glob("*.jsonl"))
        if trace_files:
            print(f"\nTrace files generated: {len(trace_files)}")
            for tf in trace_files:
                print(f"  - {tf.name}")


if __name__ == "__main__":
    asyncio.run(main())
