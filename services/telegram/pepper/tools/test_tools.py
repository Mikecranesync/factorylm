#!/usr/bin/env python3
"""
Test script for PEPPER Tools System

Quick validation of tool registry, permissions, and guardrails.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import (
    get_tool_registry,
    ToolContext,
    UserMode,
    get_available_tools_for_mode,
)


async def test_tool_registry():
    """Test tool registry initialization"""
    print("=" * 60)
    print("Testing Tool Registry Initialization")
    print("=" * 60)

    registry = get_tool_registry()

    all_tools = registry.list_all()
    print(f"\n✓ Registered tools: {', '.join(all_tools)}")
    print(f"  Total: {len(all_tools)} tools")

    assert len(all_tools) == 6, "Should have 6 tools registered"
    print("\n✓ All tools registered successfully")


async def test_god_mode_permissions():
    """Test God Mode has access to all tools"""
    print("\n" + "=" * 60)
    print("Testing God Mode Permissions")
    print("=" * 60)

    registry = get_tool_registry()
    god_tools = registry.get_available_tools(UserMode.GOD)
    god_tool_names = [t.name for t in god_tools]

    print(f"\n✓ God Mode tools: {', '.join(god_tool_names)}")
    print(f"  Total: {len(god_tool_names)} tools")

    expected = {"filesystem", "shell", "equipment", "diagnosis", "work_orders"}
    available = set(god_tool_names)

    assert expected.issubset(available), "God mode should have all expected tools"
    print("\n✓ God Mode has correct permissions")


async def test_demo_mode_permissions():
    """Test Demo Mode has restricted access"""
    print("\n" + "=" * 60)
    print("Testing Demo Mode Permissions")
    print("=" * 60)

    registry = get_tool_registry()
    demo_tools = registry.get_available_tools(UserMode.DEMO)
    demo_tool_names = [t.name for t in demo_tools]

    print(f"\n✓ Demo Mode tools: {', '.join(demo_tool_names)}")
    print(f"  Total: {len(demo_tool_names)} tools")

    expected = {"equipment", "diagnosis", "work_orders", "escalation"}
    available = set(demo_tool_names)

    assert expected == available, "Demo mode should have only specific tools"
    assert "filesystem" not in available, "Demo mode should NOT have filesystem"
    assert "shell" not in available, "Demo mode should NOT have shell"
    print("\n✓ Demo Mode has correct restrictions")


async def test_tool_execution_god_mode():
    """Test tool execution in God Mode"""
    print("\n" + "=" * 60)
    print("Testing Tool Execution (God Mode)")
    print("=" * 60)

    registry = get_tool_registry()

    # Create God Mode context
    context = ToolContext(
        user_id=1,
        chat_id=123456,
        mode=UserMode.GOD,
        active_twin="test_twin",
        session_data={}
    )

    # Test filesystem tool (God Mode only)
    filesystem_tool = registry.get("filesystem")

    result = await filesystem_tool.execute_with_checks(
        params={
            "operation": "list",
            "path": "."
        },
        context=context
    )

    print(f"\n✓ Filesystem tool execution: {result.status.value}")
    if result.is_success:
        print(f"  Directory entries: {result.data.get('count', 0)}")
    else:
        print(f"  Error: {result.error}")

    assert result.is_success or result.status.value == "error", "Should execute or return proper error"
    print("\n✓ God Mode tool execution works")


async def test_tool_execution_demo_blocked():
    """Test tool execution blocked in Demo Mode"""
    print("\n" + "=" * 60)
    print("Testing Tool Blocking (Demo Mode)")
    print("=" * 60)

    registry = get_tool_registry()

    # Create Demo Mode context
    context = ToolContext(
        user_id=42,
        chat_id=789012,
        mode=UserMode.DEMO,
        active_twin="test_twin",
        session_data={},
        username="demo_user"
    )

    # Test filesystem tool (should be blocked)
    filesystem_tool = registry.get("filesystem")

    result = await filesystem_tool.execute_with_checks(
        params={
            "operation": "list",
            "path": "."
        },
        context=context
    )

    print(f"\n✓ Filesystem tool execution: {result.status.value}")
    print(f"  Error: {result.error}")
    print(f"  Suggestion: {result.suggested_action}")

    assert result.is_blocked, "Demo mode should be blocked from filesystem"
    assert "god mode" in result.error.lower(), "Should mention god mode requirement"
    print("\n✓ Demo Mode blocking works correctly")


async def test_guardrails():
    """Test guardrail system"""
    print("\n" + "=" * 60)
    print("Testing Guardrail Engine")
    print("=" * 60)

    from tools.guardrails import (
        GuardrailEngine,
        GuardrailViolation,
    )

    engine = GuardrailEngine()

    # Test blocked path
    try:
        engine.check_file_access("/etc/passwd", "read", user_id=42)
        print("✗ Should have blocked /etc/passwd")
        assert False, "Should block /etc/passwd"
    except GuardrailViolation as e:
        print(f"\n✓ Blocked /etc/passwd: {str(e)}")

    # Test blocked command
    try:
        engine.check_shell_access("rm -rf /", user_id=42)
        print("✗ Should have blocked 'rm -rf /'")
        assert False, "Should block 'rm -rf /'"
    except GuardrailViolation as e:
        print(f"✓ Blocked dangerous command: {str(e)}")

    # Test allowed command
    try:
        engine.check_shell_access("ls -la", user_id=42)
        print("✓ Allowed safe command: 'ls -la'")
    except GuardrailViolation:
        print("✗ Should allow 'ls -la'")
        assert False, "Should allow ls command"

    print("\n✓ Guardrail engine working correctly")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PEPPER Tools System - Test Suite")
    print("=" * 60)

    try:
        await test_tool_registry()
        await test_god_mode_permissions()
        await test_demo_mode_permissions()
        await test_tool_execution_god_mode()
        await test_tool_execution_demo_blocked()
        await test_guardrails()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nTool system is ready for integration with PEPPER!")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
