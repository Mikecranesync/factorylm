"""
Digital Twin System Example Usage

Demonstrates how to use the twin registry and individual twins
for routing, health monitoring, and remote execution.
"""

import asyncio
import logging
from datetime import datetime

from registry import TwinRegistry
from plc_twin import PLCTwin
from travel_twin import TravelTwin
from vps_twin import VPSTwin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """Example: Basic twin registry usage"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Twin Registry Usage")
    print("="*60)

    # Create registry with default twins
    registry = TwinRegistry.create_default()

    # Get all twins
    all_twins = registry.get_all_twins()
    print(f"\n📋 Registered {len(all_twins)} twins:")
    for twin in all_twins:
        print(f"  - {twin.name} ({twin.id}): {len(twin.capabilities)} capabilities")

    # Resolve twins by different identifiers
    print("\n🔍 Resolving twins:")
    plc = registry.resolve_twin("plc")
    print(f"  resolve_twin('plc') → {plc.name if plc else 'Not found'}")

    factory = registry.resolve_twin("factory")
    print(f"  resolve_twin('factory') → {factory.name if factory else 'Not found'}")

    dev = registry.resolve_twin("dev")
    print(f"  resolve_twin('dev') → {dev.name if dev else 'Not found'}")


async def example_health_monitoring():
    """Example: Health monitoring and status"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Health Monitoring")
    print("="*60)

    registry = TwinRegistry.create_default()

    # Check health of all twins
    print("\n💓 Running health checks...")
    health_results = await registry.health_check_all()

    for twin_id, is_healthy in health_results.items():
        twin = registry.get_twin(twin_id)
        status_icon = "✅" if is_healthy else "❌"
        print(f"  {status_icon} {twin.name}: {twin.status.value}")

    # Get status summary
    summary = registry.get_status_summary()
    print(f"\n📊 Status Summary:")
    print(f"  Total: {summary['total_twins']}")
    print(f"  Online: {summary['online']}")
    print(f"  Offline: {summary['offline']}")
    print(f"  Degraded: {summary['degraded']}")


async def example_capability_routing():
    """Example: Capability-based routing"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Capability-Based Routing")
    print("="*60)

    registry = TwinRegistry.create_default()
    await registry.health_check_all()

    # Find twins with specific capabilities
    capabilities_to_test = [
        "read_plc_tags",
        "git_status",
        "send_telegram",
        "diagnose"
    ]

    for capability in capabilities_to_test:
        twins = registry.find_twins_with_capability(capability)
        print(f"\n🎯 Capability '{capability}':")
        if twins:
            for twin in twins:
                print(f"  - {twin.name} ({twin.status.value})")
        else:
            print(f"  No twins found")

    # Get best twin for a capability
    print("\n🏆 Best twin for 'diagnose':")
    best = registry.get_best_twin_for_capability("diagnose")
    if best:
        print(f"  Selected: {best.name}")


async def example_plc_operations():
    """Example: PLC twin operations"""
    print("\n" + "="*60)
    print("EXAMPLE 4: PLC Twin Operations")
    print("="*60)

    plc = PLCTwin()

    print(f"\n🏭 PLC Twin: {plc.name}")
    print(f"URL: {plc.url}")
    print(f"Capabilities: {len(plc.capabilities)}")

    # Example operations (will fail if PLC laptop is offline)
    print("\n📊 Example PLC operations:")
    print("  - Reading PLC tags...")
    # result = await plc.read_plc_tags(["Conveyor_Speed", "Motor_Running"])
    # print(f"    Result: {result}")

    print("  - Getting I/O status...")
    # result = await plc.get_io_status()
    # print(f"    Result: {result}")

    print("  - AI Diagnosis...")
    # diagnosis = await plc.diagnose("Is the conveyor running?")
    # print(f"    Diagnosis: {diagnosis}")

    print("\n⚠️ Actual execution commented out (requires live PLC connection)")


async def example_development_operations():
    """Example: Travel twin (development) operations"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Travel Twin (Development) Operations")
    print("="*60)

    travel = TravelTwin()

    print(f"\n💻 Travel Twin: {travel.name}")
    print(f"URL: {travel.url}")
    print(f"Capabilities: {len(travel.capabilities)}")

    print("\n🛠️ Example development operations:")
    print("  - Git status...")
    # result = await travel.git_status()
    # print(f"    Result: {result}")

    print("  - Running tests...")
    # result = await travel.run_tests(test_type="unit")
    # print(f"    Result: {result}")

    print("  - Code linting...")
    # result = await travel.lint_code()
    # print(f"    Result: {result}")

    print("\n⚠️ Actual execution commented out (requires live connection)")


async def example_orchestration():
    """Example: VPS twin orchestration"""
    print("\n" + "="*60)
    print("EXAMPLE 6: VPS Twin Orchestration")
    print("="*60)

    vps = VPSTwin()

    print(f"\n☁️ VPS Twin: {vps.name}")
    print(f"URL: {vps.url}")
    print(f"Capabilities: {len(vps.capabilities)}")

    print("\n📡 Example orchestration operations:")
    print("  - Sending Telegram message...")
    # result = await vps.send_telegram("123456789", "Test message from digital twin")
    # print(f"    Result: {result}")

    print("  - Triggering n8n workflow...")
    # result = await vps.trigger_workflow("factory-diagnosis", {"question": "What's the status?"})
    # print(f"    Result: {result}")

    print("  - Getting service status...")
    # result = await vps.get_service_status()
    # print(f"    Result: {result}")

    print("\n⚠️ Actual execution commented out (requires live VPS)")


async def example_multi_device_workflow():
    """Example: Multi-device workflow orchestration"""
    print("\n" + "="*60)
    print("EXAMPLE 7: Multi-Device Workflow")
    print("="*60)

    registry = TwinRegistry.create_default()
    await registry.health_check_all()

    print("\n🔄 Simulating factory diagnosis workflow:")
    print("  1. User sends Telegram message → VPS")
    print("  2. VPS routes to PLC laptop")
    print("  3. PLC reads tags and diagnoses issue")
    print("  4. PLC returns diagnosis to VPS")
    print("  5. VPS sends response to user via Telegram")

    # Get the required twins
    vps = registry.resolve_twin("vps")
    plc = registry.resolve_twin("plc")

    if vps and plc:
        print(f"\n✅ Required twins available:")
        print(f"  - {vps.name} ({vps.status.value})")
        print(f"  - {plc.name} ({plc.status.value})")

        if vps.is_online() and plc.is_online():
            print("\n🚀 All systems ready for workflow execution")
            # Actual workflow would execute here
        else:
            print("\n⚠️ One or more twins offline - workflow unavailable")
    else:
        print("\n❌ Required twins not found")


async def example_periodic_monitoring():
    """Example: Periodic health monitoring"""
    print("\n" + "="*60)
    print("EXAMPLE 8: Periodic Health Monitoring")
    print("="*60)

    registry = TwinRegistry.create_default()

    print("\n🏥 Starting periodic health monitoring...")
    print("  Interval: 10 seconds")
    print("  Duration: 30 seconds")

    # Start monitoring
    await registry.start_health_monitoring(interval=10)

    # Let it run for 30 seconds
    await asyncio.sleep(30)

    # Stop monitoring
    await registry.stop_health_monitoring()
    print("\n✅ Monitoring stopped")

    # Clean up
    await registry.shutdown()


async def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("DIGITAL TWIN SYSTEM - USAGE EXAMPLES")
    print("="*80)

    try:
        await example_basic_usage()
        await example_health_monitoring()
        await example_capability_routing()
        await example_plc_operations()
        await example_development_operations()
        await example_orchestration()
        await example_multi_device_workflow()

        # Skip periodic monitoring in batch mode
        # await example_periodic_monitoring()

    except Exception as e:
        logger.error(f"❌ Example error: {e}", exc_info=True)

    print("\n" + "="*80)
    print("Examples complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
