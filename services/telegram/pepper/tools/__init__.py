"""
PEPPER Tools System

Comprehensive toolset with God Mode and Demo Mode access control.

Tools:
- filesystem: File operations (God Mode only)
- shell: Command execution (God Mode only)
- equipment: Equipment status and diagnostics (Both modes, read-only)
- diagnosis: AI fault diagnosis (Both modes)
- work_orders: Work order management (Demo: own only, God: all)
- escalation: Escalate to Mike (Demo Mode only)

Usage:
    from pepper.tools import get_tool_registry, ToolContext, UserMode

    # Initialize registry
    registry = get_tool_registry(
        groq_api_key="...",
        claude_api_key="..."
    )

    # Execute tool
    context = ToolContext(
        user_id=12345,
        chat_id=67890,
        mode=UserMode.DEMO,
        active_twin="conveyor_01",
        session_data={}
    )

    tool = registry.get("equipment")
    result = await tool.execute_with_checks(
        params={"operation": "get_status", "equipment_id": "conveyor_01"},
        context=context
    )

    if result.is_success:
        print(result.data)
    else:
        print(f"Error: {result.error}")
"""

from typing import Optional

from .base import (
    BaseTool,
    ToolContext,
    ToolResult,
    ToolResultStatus,
    ToolRegistry,
    UserMode,
    GuardrailViolation,
)

from .guardrails import GuardrailEngine

from .filesystem import FilesystemTool
from .shell import ShellTool
from .equipment import EquipmentTool
from .diagnosis import DiagnosisTool
from .work_orders import WorkOrdersTool
from .escalation import EscalationTool


__all__ = [
    # Base types
    "BaseTool",
    "ToolContext",
    "ToolResult",
    "ToolResultStatus",
    "ToolRegistry",
    "UserMode",
    "GuardrailViolation",
    # Guardrails
    "GuardrailEngine",
    # Tools
    "FilesystemTool",
    "ShellTool",
    "EquipmentTool",
    "DiagnosisTool",
    "WorkOrdersTool",
    "EscalationTool",
    # Registry builder
    "get_tool_registry",
]


def get_tool_registry(
    groq_api_key: Optional[str] = None,
    claude_api_key: Optional[str] = None
) -> ToolRegistry:
    """
    Get configured tool registry with all tools.

    Args:
        groq_api_key: Groq API key for diagnosis
        claude_api_key: Claude API key for diagnosis

    Returns:
        ToolRegistry with all tools registered
    """
    registry = ToolRegistry()

    # Register all tools
    registry.register(FilesystemTool())
    registry.register(ShellTool())
    registry.register(EquipmentTool())
    registry.register(DiagnosisTool(groq_api_key, claude_api_key))
    registry.register(WorkOrdersTool())
    registry.register(EscalationTool())

    return registry


def get_available_tools_for_mode(mode: UserMode) -> list[str]:
    """
    Get list of tool names available for a specific mode.

    Args:
        mode: User mode (GOD or DEMO)

    Returns:
        List of tool names
    """
    registry = get_tool_registry()
    tools = registry.get_available_tools(mode)
    return [tool.name for tool in tools]


# Tool availability by mode
GOD_MODE_TOOLS = [
    "filesystem",
    "shell",
    "equipment",
    "diagnosis",
    "work_orders",
]

DEMO_MODE_TOOLS = [
    "equipment",
    "diagnosis",
    "work_orders",
    "escalation",
]


__version__ = "1.0.0"
