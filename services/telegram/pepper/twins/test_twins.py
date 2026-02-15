"""
Quick validation test for Digital Twin system

Run this to verify the twin system is working correctly.
"""

import asyncio
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add pepper directory to path for imports
pepper_dir = Path(__file__).parent.parent
sys.path.insert(0, str(pepper_dir))

from twins.twin import DigitalTwin, TwinStatus
from twins.registry import TwinRegistry
from twins.plc_twin import PLCTwin
from twins.travel_twin import TravelTwin
from twins.vps_twin import VPSTwin


def test_twin_creation():
    """Test: Create individual twins"""
    print("\n🧪 Test 1: Twin Creation")

    plc = PLCTwin()
    assert plc.id == "plc"
    assert plc.name == "PLC Laptop"
    assert "read_plc_tags" in plc.capabilities
    print("  ✅ PLC Twin created")

    travel = TravelTwin()
    assert travel.id == "travel"
    assert "git_status" in travel.capabilities
    print("  ✅ Travel Twin created")

    vps = VPSTwin()
    assert vps.id == "vps"
    assert "send_telegram" in vps.capabilities
    print("  ✅ VPS Twin created")


def test_registry_creation():
    """Test: Create registry and register twins"""
    print("\n🧪 Test 2: Registry Creation")

    registry = TwinRegistry()
    assert len(registry.get_all_twins()) == 0
    print("  ✅ Empty registry created")

    plc = PLCTwin()
    registry.register(plc)
    assert len(registry.get_all_twins()) == 1
    print("  ✅ Twin registered")

    registry.unregister("plc")
    assert len(registry.get_all_twins()) == 0
    print("  ✅ Twin unregistered")


def test_default_registry():
    """Test: Create default registry"""
    print("\n🧪 Test 3: Default Registry")

    registry = TwinRegistry.create_default()
    twins = registry.get_all_twins()

    assert len(twins) == 3
    print(f"  ✅ Created 3 default twins")

    assert registry.get_twin("plc") is not None
    assert registry.get_twin("travel") is not None
    assert registry.get_twin("vps") is not None
    print("  ✅ All twins accessible by ID")


def test_twin_resolution():
    """Test: Resolve twins by various identifiers"""
    print("\n🧪 Test 4: Twin Resolution")

    registry = TwinRegistry.create_default()

    # Test ID resolution
    plc = registry.resolve_twin("plc")
    assert plc is not None
    print("  ✅ Resolve by ID: 'plc'")

    # Test alias resolution
    factory = registry.resolve_twin("factory")
    assert factory is not None
    assert factory.id == "plc"
    print("  ✅ Resolve by alias: 'factory' → 'plc'")

    # Test name resolution
    plc_by_name = registry.resolve_twin("PLC Laptop")
    assert plc_by_name is not None
    assert plc_by_name.id == "plc"
    print("  ✅ Resolve by name: 'PLC Laptop' → 'plc'")


def test_capability_search():
    """Test: Find twins by capability"""
    print("\n🧪 Test 5: Capability Search")

    registry = TwinRegistry.create_default()

    # Search for PLC-specific capability
    twins = registry.find_twins_with_capability("read_plc_tags", online_only=False)
    assert len(twins) == 1
    assert twins[0].id == "plc"
    print("  ✅ Found twin with 'read_plc_tags'")

    # Search for git capability
    twins = registry.find_twins_with_capability("git_status", online_only=False)
    assert len(twins) == 1
    assert twins[0].id == "travel"
    print("  ✅ Found twin with 'git_status'")

    # Search for Telegram capability
    twins = registry.find_twins_with_capability("send_telegram", online_only=False)
    assert len(twins) == 1
    assert twins[0].id == "vps"
    print("  ✅ Found twin with 'send_telegram'")


def test_status_summary():
    """Test: Get registry status summary"""
    print("\n🧪 Test 6: Status Summary")

    registry = TwinRegistry.create_default()
    summary = registry.get_status_summary()

    assert summary["total_twins"] == 3
    print(f"  ✅ Total twins: {summary['total_twins']}")

    # All should be UNKNOWN initially
    assert summary["online"] == 0
    print(f"  ✅ Online twins: {summary['online']}")

    assert len(summary["twins"]) == 3
    print(f"  ✅ Twin details: {len(summary['twins'])} entries")


async def test_health_check():
    """Test: Health check functionality"""
    print("\n🧪 Test 7: Health Check (will fail if devices offline)")

    registry = TwinRegistry.create_default()

    # This will attempt to contact real devices
    print("  ⏳ Checking health of all twins...")
    results = await registry.health_check_all()

    assert len(results) == 3
    print(f"  ✅ Health check completed for {len(results)} twins")

    for twin_id, is_healthy in results.items():
        twin = registry.get_twin(twin_id)
        status_icon = "✅" if is_healthy else "❌"
        print(f"    {status_icon} {twin.name}: {twin.status.value}")

    # Clean up
    await registry.shutdown()


def test_has_capability():
    """Test: Check twin capabilities"""
    print("\n🧪 Test 8: Capability Checking")

    plc = PLCTwin()

    assert plc.has_capability("read_plc_tags") == True
    print("  ✅ PLC has 'read_plc_tags'")

    assert plc.has_capability("git_status") == False
    print("  ✅ PLC does not have 'git_status'")

    travel = TravelTwin()
    assert travel.has_capability("git_status") == True
    assert travel.has_capability("read_plc_tags") == False
    print("  ✅ Travel has correct capabilities")


def test_twin_metadata():
    """Test: Twin metadata"""
    print("\n🧪 Test 9: Twin Metadata")

    plc = PLCTwin()
    assert "plc_model" in plc.metadata
    assert plc.metadata["plc_model"] == "Micro 820"
    print("  ✅ PLC metadata correct")

    travel = TravelTwin()
    assert "role" in travel.metadata
    assert travel.metadata["role"] == "development"
    print("  ✅ Travel metadata correct")


def run_sync_tests():
    """Run synchronous tests"""
    print("\n" + "="*60)
    print("DIGITAL TWIN SYSTEM - VALIDATION TESTS")
    print("="*60)

    try:
        test_twin_creation()
        test_registry_creation()
        test_default_registry()
        test_twin_resolution()
        test_capability_search()
        test_status_summary()
        test_has_capability()
        test_twin_metadata()

        print("\n✅ All synchronous tests passed!")
        return True

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_async_tests():
    """Run asynchronous tests"""
    print("\n" + "="*60)
    print("ASYNC TESTS (requires live devices)")
    print("="*60)

    try:
        await test_health_check()
        print("\n✅ All async tests completed!")
        return True

    except Exception as e:
        print(f"\n❌ Async test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    # Run sync tests
    sync_ok = run_sync_tests()

    # Run async tests
    print("\nℹ️ Running async tests (may fail if devices offline)...")
    async_ok = asyncio.run(run_async_tests())

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Synchronous tests: {'✅ PASS' if sync_ok else '❌ FAIL'}")
    print(f"Asynchronous tests: {'✅ PASS' if async_ok else '❌ FAIL (expected if devices offline)'}")
    print("="*60 + "\n")

    return sync_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
