"""Quick test for Cosmos client."""
import os
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cosmos.client import CosmosClient

def test_stub_mode():
    """Test that stub mode works without API key."""
    print("Testing STUB mode (no API key)...")

    # Save and temporarily remove API key
    saved_key = os.environ.pop("NVIDIA_COSMOS_API_KEY", None)

    client = CosmosClient()
    assert not client.is_available(), "Client should not be 'available' without key"

    # Test incident analysis
    result = client.analyze_incident(
        incident_id="TEST-001",
        node_id="test-node",
        tags={
            "motor_running": True,
            "error_code": 3,  # Jam
            "motor_current": 8.5,
            "temperature": 45.2,
        },
    )

    print(f"  Summary: {result.summary}")
    print(f"  Root cause: {result.root_cause}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Suggested checks: {result.suggested_checks[:2]}...")
    print("  STUB mode: OK")

    # Restore API key if it existed
    if saved_key:
        os.environ["NVIDIA_COSMOS_API_KEY"] = saved_key

    return True


def test_api_mode():
    """Test real API mode (only if key is set)."""
    api_key = os.environ.get("NVIDIA_COSMOS_API_KEY")
    if not api_key:
        print("\nSkipping REAL API test (NVIDIA_COSMOS_API_KEY not set)")
        return True

    print("\nTesting REAL API mode...")
    client = CosmosClient()
    assert client.is_available(), "Client should be 'available' with key"

    result = client.analyze_incident(
        incident_id="TEST-002",
        node_id="test-node",
        tags={
            "motor_running": True,
            "error_code": 1,  # Overload
            "motor_current": 12.5,
            "temperature": 65.2,
        },
    )

    print(f"  Summary: {result.summary}")
    print(f"  Root cause: {result.root_cause}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Model: {result.cosmos_model}")
    print("  REAL API mode: OK")
    return True


if __name__ == "__main__":
    print("=== Cosmos Client Test ===\n")

    stub_ok = test_stub_mode()
    api_ok = test_api_mode()

    print("\n=== Results ===")
    print(f"Stub mode: {'PASS' if stub_ok else 'FAIL'}")
    print(f"API mode:  {'PASS' if api_ok else 'FAIL'}")

    if stub_ok and api_ok:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)
