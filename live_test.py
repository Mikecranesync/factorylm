"""
Live test: Read Factory I/O tags and analyze with Cosmos/Llama.
Bypasses Matrix API for quick testing.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from cosmos.client import CosmosClient

PLC_API = os.getenv("PLC_HOST", "100.72.2.99")


def fetch_plc_tags():
    """Fetch live tags from PLC API."""
    try:
        resp = httpx.get(f"http://{PLC_API}:8000/api/plc/io", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching PLC tags: {e}")
        return None


def main():
    print("=" * 60)
    print("LIVE TEST: Factory I/O -> Cosmos/Llama Analysis")
    print("=" * 60)

    # Check API key
    api_key = os.environ.get("NVIDIA_COSMOS_API_KEY")
    if not api_key:
        print("\n[!]  NVIDIA_COSMOS_API_KEY not set - will use stub responses")
    else:
        print(f"\n[OK] API key found: {api_key[:20]}...")

    # Fetch live tags
    print(f"\n[>] Fetching tags from PLC API at {PLC_API}:8000...")
    tags = fetch_plc_tags()

    if not tags:
        print("[X] Could not fetch tags. Is Factory I/O running?")
        return

    print("\n[DATA] Live Tag Data:")
    print("-" * 40)

    # Handle nested structure from PLC API
    if "coils" in tags:
        print("Coils:")
        for k, v in tags.get("coils", {}).items():
            print(f"  {k}: {v}")
        print("Registers:")
        for k, v in tags.get("registers", {}).items():
            print(f"  {k}: {v}")

        # Flatten for analysis
        flat_tags = {
            "motor_running": tags["coils"].get("motor_running", False),
            "fault_alarm": tags["coils"].get("fault_alarm", False),
            "conveyor_running": tags["coils"].get("conveyor_running", False),
            "motor_speed": tags["registers"].get("motor_speed", 0),
            "motor_current": tags["registers"].get("motor_current", 0),
            "temperature": tags["registers"].get("temperature", 0),
            "error_code": tags["registers"].get("error_code", 0),
        }
    else:
        # Already flat
        flat_tags = tags
        for k, v in tags.items():
            print(f"  {k}: {v}")

    # Analyze with Cosmos/Llama
    print("\n[AI] Sending to Cosmos/Llama for analysis...")
    print("-" * 40)

    client = CosmosClient()
    result = client.analyze_incident(
        incident_id="LIVE-TEST-001",
        node_id=f"factoryio-{PLC_API}",
        tags=flat_tags,
        context="Live test from Factory I/O simulation",
    )

    print(f"\n[RESULT] Analysis Result:")
    print(f"  Model: {result.cosmos_model}")
    print(f"  Summary: {result.summary}")
    print(f"  Root Cause: {result.root_cause}")
    print(f"  Confidence: {result.confidence:.0%}")
    print(f"\n  Reasoning: {result.reasoning[:300]}...")
    print(f"\n  Suggested Checks:")
    for check in result.suggested_checks[:4]:
        print(f"    - {check}")

    print("\n" + "=" * 60)
    print("[OK] Live test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
