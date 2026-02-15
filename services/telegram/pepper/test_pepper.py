"""
Test script for PEPPER bot system

Quick validation of core functionality without running the full bot.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.telegram.pepper.modes import (
    UserMode,
    get_user_mode,
    get_mode_config,
    is_command_allowed,
    GOD_MODE_USERS
)
from services.telegram.pepper.config import load_config, validate_config


def test_user_modes():
    """Test user mode detection"""
    print("Testing User Modes")
    print("=" * 50)

    # Test God Mode
    mike_id = 8445149012
    mode = get_user_mode(mike_id)
    config = get_mode_config(mike_id)

    print(f"\nMike's User ID: {mike_id}")
    print(f"Mode: {mode.value}")
    print(f"Greeting: {config.greeting}")
    print(f"Max Requests/Hour: {config.max_requests_per_hour}")
    print(f"PLC Access: {config.allow_direct_plc_access}")
    print(f"System Commands: {config.allow_system_commands}")

    assert mode == UserMode.GOD, "Mike should have God Mode"
    assert config.allow_direct_plc_access, "God Mode should have PLC access"

    # Test Demo Mode
    demo_user_id = 123456789
    demo_mode = get_user_mode(demo_user_id)
    demo_config = get_mode_config(demo_user_id)

    print(f"\nDemo User ID: {demo_user_id}")
    print(f"Mode: {demo_mode.value}")
    print(f"Greeting: {demo_config.greeting}")
    print(f"Max Requests/Hour: {demo_config.max_requests_per_hour}")
    print(f"PLC Access: {demo_config.allow_direct_plc_access}")
    print(f"System Commands: {demo_config.allow_system_commands}")

    assert demo_mode == UserMode.DEMO, "Unknown users should have Demo Mode"
    assert not demo_config.allow_direct_plc_access, "Demo Mode should not have PLC access"

    print("\n✅ User mode tests passed!")


def test_command_permissions():
    """Test command permission checking"""
    print("\n\nTesting Command Permissions")
    print("=" * 50)

    mike_id = 8445149012
    demo_id = 123456789

    # God Mode tests
    print("\nGod Mode Commands:")
    for cmd in ["/start", "/help", "/status", "/plc", "/logs", "/debug"]:
        allowed = is_command_allowed(mike_id, cmd)
        print(f"  {cmd}: {'✅ Allowed' if allowed else '❌ Denied'}")
        assert allowed, f"God Mode should allow {cmd}"

    # Demo Mode tests
    print("\nDemo Mode Commands:")
    for cmd in ["/start", "/help", "/status", "/diagnose", "/equipment"]:
        allowed = is_command_allowed(demo_id, cmd)
        print(f"  {cmd}: {'✅ Allowed' if allowed else '❌ Denied'}")
        assert allowed, f"Demo Mode should allow {cmd}"

    # Demo Mode forbidden commands
    for cmd in ["/plc", "/logs", "/debug"]:
        allowed = is_command_allowed(demo_id, cmd)
        print(f"  {cmd}: {'✅ Allowed' if allowed else '❌ Denied'}")
        assert not allowed, f"Demo Mode should deny {cmd}"

    print("\n✅ Command permission tests passed!")


def test_config_loading():
    """Test configuration loading"""
    print("\n\nTesting Configuration Loading")
    print("=" * 50)

    try:
        config = load_config()

        print(f"\nVersion: {config.version}")
        print(f"Bots: {', '.join(config.bots.keys())}")
        print(f"God Users: {config.god_users}")
        print(f"Nodes: {', '.join(config.nodes.keys())}")

        # Validate configuration
        validate_config(config)

        # Check nodes
        print("\nNode Configuration:")
        for node_name, node in config.nodes.items():
            print(f"  {node_name}:")
            print(f"    URL: {node.url}")
            print(f"    Enabled: {node.enabled}")
            print(f"    Timeout: {node.timeout}s")

        print("\n✅ Configuration tests passed!")

    except FileNotFoundError:
        print("\n⚠️  config.yaml not found - this is expected if not deployed yet")
    except Exception as e:
        print(f"\n❌ Configuration test failed: {e}")
        raise


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PEPPER Bot System Test Suite")
    print("=" * 60)

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    try:
        test_user_modes()
        test_command_permissions()
        test_config_loading()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nPEPPER bot system is ready for deployment!")
        print("\nNext steps:")
        print("1. Set environment variables (PEPPER_PRIME_TOKEN, FACTORYLM_BOT_TOKEN)")
        print("2. Run: python -m pepper.gateway")
        print("3. Test with Telegram: /start")

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        raise


if __name__ == "__main__":
    main()
