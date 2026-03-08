"""
FactoryLM Telegram Bot — End-to-end simulation test (V003).

Proves the full chain works without a real Telegram token:
  Bot handler → LLM client → LiteLLM proxy → groq-main → response
  + work order create/close lifecycle
  + conversation history management

Run: PYTHONPATH=. python3.12 tests/test_telegram_bot_e2e.py
Requires: LiteLLM proxy on :4000
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.src.factorylm.llm.client import async_diagnose, classify_intent
from services.telegram_bot.prompts import build_system_prompt
from services.telegram_bot.work_orders import WorkOrderStore


async def sim_conversation():
    """Simulate a full technician conversation without Telegram."""
    print("=" * 60)
    print("FactoryLM V003 Simulation — Telegram Bot E2E")
    print("=" * 60)

    work_orders = WorkOrderStore()
    conversation = []
    user_id = "sim_tech_001"
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name} — {detail}")

    # --- Test 1: Intent classification (local-gemma) ---
    print("\n[1] Intent Classification (local-gemma)")
    t0 = time.time()
    intent = classify_intent("Motor current spiked to 5.8A, error code 1")
    t1 = time.time()
    print(f"  Intent: {intent} ({t1 - t0:.1f}s)")
    check("Intent returned", intent is not None)
    check("Reasonable intent", "fault" in intent or "report" in intent or "general" in intent, f"got: {intent}")

    # --- Test 2: System prompt builds cleanly ---
    print("\n[2] System Prompt Construction")
    prompt = build_system_prompt(
        plc_state="  Motor_Run: ON\n  Motor_Speed: 75%\n  Temperature: 52.3 C",
        active_faults="  E001: E-Stop active — conveyor halted",
        recent_incidents="  2026-03-08 12:00: E-Stop triggered on line 2",
        open_work_order=None,
    )
    check("Prompt built", len(prompt) > 100, f"len={len(prompt)}")
    check("Contains FactoryLM identity", "FactoryLM" in prompt or "maintenance" in prompt.lower())

    # --- Test 3: LLM diagnosis (groq-main via LiteLLM) ---
    print("\n[3] LLM Diagnosis — Fault Report")
    user_msg = "Motor current spiked to 5.8A on conveyor line 2, error code 1. What should I do?"
    conversation.append({"role": "user", "content": user_msg})

    t0 = time.time()
    response = await async_diagnose(prompt, conversation)
    t1 = time.time()
    print(f"  Response: {response[:150]}..." if len(response or "") > 150 else f"  Response: {response}")
    print(f"  Latency: {t1 - t0:.1f}s")

    check("Got response", response is not None and len(response) > 50, "empty or too short")
    check("Response is actionable", any(w in (response or "").lower() for w in ["check", "inspect", "stop", "overload", "motor", "current"]))
    check("Under 5s latency", t1 - t0 < 5, f"{t1 - t0:.1f}s")

    conversation.append({"role": "assistant", "content": response or ""})

    # --- Test 4: Work order lifecycle ---
    print("\n[4] Work Order Lifecycle")
    wo = work_orders.create(user_id, "E001", "Motor overload on line 2")
    check("WO created", wo is not None)
    check("WO has ID", wo.wo_id.startswith("WO-"))
    check("WO is open", wo.status == "open")

    open_wo = work_orders.get_open(user_id)
    check("Can retrieve open WO", open_wo is not None and open_wo.wo_id == wo.wo_id)

    closed = work_orders.close(wo.wo_id, "Replaced motor bearings, current normalized to 3.2A")
    check("WO closed", closed is not None and closed.status == "closed")
    check("Root cause recorded", closed is not None and "bearings" in (closed.root_cause or ""))

    # --- Test 5: Follow-up conversation (context maintained) ---
    print("\n[5] Follow-up Conversation")
    follow_up = "What's the normal current range for this motor?"
    conversation.append({"role": "user", "content": follow_up})

    t0 = time.time()
    response2 = await async_diagnose(prompt, conversation)
    t1 = time.time()
    print(f"  Response: {response2[:150]}..." if len(response2 or "") > 150 else f"  Response: {response2}")
    print(f"  Latency: {t1 - t0:.1f}s")

    check("Follow-up response", response2 is not None and len(response2) > 20)
    check("Mentions current range", any(w in (response2 or "").lower() for w in ["amp", "current", "0-5", "4", "5"]))

    # --- Test 6: General question (with factory context) ---
    print("\n[6] General Question")
    t0 = time.time()
    factory_prompt = (
        "You are FactoryLM, an industrial automation assistant. "
        "Error codes: 0=None, 1=Motor overload, 2=Temp high, 3=Conveyor jam, "
        "4=Sensor failure, 5=Comm loss. Be concise."
    )
    response3 = await async_diagnose(
        factory_prompt,
        [{"role": "user", "content": "What does error code 3 mean?"}],
    )
    t1 = time.time()
    print(f"  Response: {response3[:150]}..." if len(response3 or "") > 150 else f"  Response: {response3}")
    check("General answer", response3 is not None)
    check("Mentions conveyor or jam", any(w in (response3 or "").lower() for w in ["conveyor", "jam", "belt", "stuck"]))

    # --- Summary ---
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"V003 SIMULATION: {passed}/{total} checks passed")
    if failed == 0:
        print("STATUS: ALL CLEAR — Bot ready for Telegram token")
    else:
        print(f"STATUS: {failed} FAILURES — fix before deploying")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(sim_conversation())
    sys.exit(0 if success else 1)
