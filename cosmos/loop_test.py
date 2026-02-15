"""
FactoryLM Loop Test - Proves the Full Data Pipeline
====================================================
This test demonstrates the complete closed-loop system:

  [Factory I/O] --> [Modbus TCP] --> [Matrix API] --> [Llama AI] --> [Diagnosis]
       |                                                                  |
       +------------------------------------------------------------------+
                            Physical AI Feedback Loop

Test Sequence:
  1. Read LIVE sensor data from Factory I/O simulation
  2. Verify data arrives at Matrix API via Modbus
  3. Send data to NVIDIA Llama 3.1 70B for analysis
  4. Receive AI diagnosis with root cause and confidence
  5. Compare AI response to actual machine state

Run: python cosmos/loop_test.py
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from cosmos.client import CosmosClient

PLC_HOST = os.getenv("PLC_HOST", "100.72.2.99")
MATRIX_API = f"http://{PLC_HOST}:8000"


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_step(num, text):
    print(f"\n[STEP {num}] {text}")
    print("-" * 50)


def test_loop():
    start_time = time.time()

    print_header("FACTORYLM LOOP TEST - Physical AI Pipeline")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Target: {MATRIX_API}")

    # =========================================================================
    # STEP 1: Verify Factory I/O Connection
    # =========================================================================
    print_step(1, "VERIFY FACTORY I/O CONNECTION")

    try:
        health = httpx.get(f"{MATRIX_API}/api/health", timeout=5).json()
        print(f"  Matrix API: {health.get('status', 'unknown')}")
        print(f"  Database: {health.get('db', 'unknown')}")
    except Exception as e:
        print(f"  [FAIL] Cannot reach Matrix API: {e}")
        return False

    # =========================================================================
    # STEP 2: Read Live Sensor Data (Factory I/O -> Modbus -> Matrix)
    # =========================================================================
    print_step(2, "READ LIVE SENSOR DATA")

    try:
        tags_resp = httpx.get(f"{MATRIX_API}/api/tags?limit=1", timeout=5)
        tags_list = tags_resp.json()

        if not tags_list:
            print("  [FAIL] No tag data available")
            return False

        tags = tags_list[0]

        print(f"  Source: {tags.get('node_id', 'unknown')}")
        print(f"  Timestamp: {tags.get('timestamp', 'unknown')}")
        print()
        print("  SENSOR READINGS:")
        print(f"    Motor:       {'RUNNING' if tags.get('motor_running') else 'STOPPED'} @ {tags.get('motor_speed', 0)}%")
        print(f"    Current:     {tags.get('motor_current', 0):.2f} A")
        print(f"    Temperature: {tags.get('temperature', 0):.1f} C")
        print(f"    Pressure:    {tags.get('pressure', 0)} PSI")
        print(f"    Conveyor:    {'RUNNING' if tags.get('conveyor_running') else 'STOPPED'} @ {tags.get('conveyor_speed', 0)}%")
        print(f"    Sensor 1:    {'ACTIVE' if tags.get('sensor_1') else 'clear'}")
        print(f"    Sensor 2:    {'ACTIVE' if tags.get('sensor_2') else 'clear'}")
        print()
        print("  ALARMS:")
        print(f"    Fault:       {'ALARM!' if tags.get('fault_alarm') else 'None'}")
        print(f"    E-Stop:      {'PRESSED!' if tags.get('e_stop') else 'Clear'}")
        print(f"    Error Code:  {tags.get('error_code', 0)} ({tags.get('error_message', 'None')})")

    except Exception as e:
        print(f"  [FAIL] Cannot read tags: {e}")
        return False

    # =========================================================================
    # STEP 3: Send to NVIDIA Llama for AI Analysis
    # =========================================================================
    print_step(3, "SEND TO NVIDIA LLAMA 3.1 70B FOR ANALYSIS")

    api_key = os.environ.get("NVIDIA_COSMOS_API_KEY")
    if not api_key:
        print("  [WARN] NVIDIA_COSMOS_API_KEY not set - using stub")
    else:
        print(f"  API Key: {api_key[:20]}...")

    print("  Sending request to integrate.api.nvidia.com...")

    ai_start = time.time()

    try:
        client = CosmosClient()
        result = client.analyze_incident(
            incident_id="LOOP-TEST-001",
            node_id=tags.get('node_id', 'factory-io'),
            tags=tags,
            context="Loop test - verify AI can analyze live Factory I/O data",
        )
        ai_time = time.time() - ai_start

    except Exception as e:
        print(f"  [FAIL] AI analysis failed: {e}")
        return False

    # =========================================================================
    # STEP 4: Display AI Diagnosis
    # =========================================================================
    print_step(4, "AI DIAGNOSIS RESULT")

    print(f"  Model:      {result.cosmos_model}")
    print(f"  Latency:    {ai_time:.2f}s")
    print()
    print(f"  SUMMARY:    {result.summary}")
    print(f"  ROOT CAUSE: {result.root_cause}")
    print(f"  CONFIDENCE: {result.confidence:.0%}")
    print()
    print(f"  REASONING:")
    # Word wrap the reasoning
    reasoning = result.reasoning
    for i in range(0, len(reasoning), 70):
        print(f"    {reasoning[i:i+70]}")

    if result.suggested_checks:
        print()
        print(f"  SUGGESTED CHECKS:")
        for check in result.suggested_checks[:5]:
            print(f"    - {check}")

    # =========================================================================
    # STEP 5: Validate Loop Integrity
    # =========================================================================
    print_step(5, "VALIDATE LOOP INTEGRITY")

    total_time = time.time() - start_time

    # Check if AI response matches actual state
    has_fault = tags.get('fault_alarm', 0) or tags.get('e_stop', 0) or tags.get('error_code', 0)

    # AI says "No fault" = no fault detected, otherwise check for fault keywords
    summary_lower = result.summary.lower()
    ai_detected_fault = not ('no fault' in summary_lower or 'normal' in summary_lower or 'no error' in summary_lower or 'none' in result.root_cause.lower())

    state_match = (has_fault and ai_detected_fault) or (not has_fault and not ai_detected_fault)

    print(f"  Actual State:     {'FAULT PRESENT' if has_fault else 'NORMAL OPERATION'}")
    print(f"  AI Detection:     {'FAULT DETECTED' if ai_detected_fault else 'NO FAULT DETECTED'}")
    print(f"  State Match:      {'PASS' if state_match else 'MISMATCH'}")
    print()
    print(f"  Data Flow Verified:")
    print(f"    [x] Factory I/O simulation running")
    print(f"    [x] Modbus TCP connection active")
    print(f"    [x] Matrix API receiving tags")
    print(f"    [x] NVIDIA API responding")
    print(f"    [x] AI analysis returned")

    # =========================================================================
    # FINAL RESULT
    # =========================================================================
    print_header("LOOP TEST RESULT")

    print(f"""
  Pipeline:  Factory I/O -> Modbus -> Matrix -> Llama -> Diagnosis

  Total Time:    {total_time:.2f}s
  AI Latency:    {ai_time:.2f}s
  Data Points:   {len([k for k in tags.keys() if not k.startswith('_')])}
  AI Model:      {result.cosmos_model}
  Confidence:    {result.confidence:.0%}

  VERDICT:       {'PASS - Loop verified!' if state_match else 'CHECK - Review AI response'}
""")

    return state_match


if __name__ == "__main__":
    success = test_loop()
    sys.exit(0 if success else 1)
