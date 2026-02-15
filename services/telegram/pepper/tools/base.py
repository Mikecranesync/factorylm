"""
Base Tool System for PEPPER

Provides abstract base class for all tools with permission checking,
execution context, and result types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class UserMode(Enum):
    """User access modes for PEPPER"""
    GOD = "god"      # Mike - unrestricted access
    DEMO = "demo"    # Customers - guardrailed
    ANY = "any"      # Available to all users


class ToolResultStatus(Enum):
    """Tool execution result status"""
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


@dataclass
class ToolContext:
    """Context passed to tool execution"""
    user_id: int
    chat_id: int
    mode: UserMode
    active_twin: str
    session_data: Dict[str, Any]
    username: Optional[str] = None

    @property
    def is_god_mode(self) -> bool:
        """Check if user is in God Mode"""
        return self.mode == UserMode.GOD

    @property
    def is_demo_mode(self) -> bool:
        """Check if user is in Demo Mode"""
        return self.mode == UserMode.DEMO


@dataclass
class ToolResult:
    """Result from tool execution"""
    status: ToolResultStatus
    data: Any = None
    error: Optional[str] = None
    suggested_action: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @property
    def is_success(self) -> bool:
        """Check if execution was successful"""
        return self.status == ToolResultStatus.SUCCESS

    @property
    def is_blocked(self) -> bool:
        """Check if execution was blocked by guardrails"""
        return self.status == ToolResultStatus.BLOCKED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "suggested_action": self.suggested_action,
            "metadata": self.metadata or {}
        }


class GuardrailViolation(Exception):
    """Raised when a guardrail blocks an operation"""

    def __init__(self, message: str, suggested_action: Optional[str] = None):
        super().__init__(message)
        self.suggested_action = suggested_action


class BaseTool(ABC):
    """Abstract base class for all PEPPER tools"""

    name: str = ""
    description: str = ""
    required_mode: UserMode = UserMode.ANY

    def __init__(self):
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} must define 'name'")
        if not self.description:
            raise ValueError(f"{self.__class__.__name__} must define 'description'")

    def check_permission(self, mode: UserMode) -> bool:
        """
        Check if the given user mode has permission to use this tool.

        Args:
            mode: The user's current mode

        Returns:
            True if permitted, False otherwise
        """
        if self.required_mode == UserMode.ANY:
            return True
        return mode == self.required_mode

    async def execute_with_checks(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """
        Execute the tool with permission and error handling.

        Args:
            params: Tool parameters
            context: Execution context

        Returns:
            ToolResult with status and data/error
        """
        # Check permissions
        if not self.check_permission(context.mode):
            return ToolResult(
                status=ToolResultStatus.BLOCKED,
                error=f"Tool '{self.name}' requires {self.required_mode.value} mode",
                suggested_action=(
                    "This action requires elevated permissions. "
                    "Contact Mike if you need this capability."
                )
            )

        # Execute with error handling
        try:
            result = await self.execute(params, context)
            return result
        except GuardrailViolation as e:
            return ToolResult(
                status=ToolResultStatus.BLOCKED,
                error=str(e),
                suggested_action=e.suggested_action
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Tool execution failed: {str(e)}"
            )

    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """
        Execute the tool logic.

        Args:
            params: Tool-specific parameters
            context: Execution context

        Returns:
            ToolResult with execution outcome
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this tool's parameters.

        Returns:
            JSON schema dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "required_mode": self.required_mode.value,
            "parameters": self._get_parameter_schema()
        }

    def _get_parameter_schema(self) -> Dict[str, Any]:
        """
        Override this to provide parameter schema.

        Returns:
            Parameter schema dictionary
        """
        return {"type": "object", "properties": {}}


class ToolRegistry:
    """Registry for all available tools"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(name)

    def get_available_tools(self, mode: UserMode) -> List[BaseTool]:
        """Get all tools available for a given mode"""
        return [
            tool for tool in self._tools.values()
            if tool.check_permission(mode)
        ]

    def list_all(self) -> List[str]:
        """List all registered tool names"""
        return list(self._tools.keys())
