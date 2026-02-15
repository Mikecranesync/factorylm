"""
User Mode Management for PEPPER Bot

Defines three operational modes:
- GOD: Full system access for internal team
- DEMO: Guardrailed access for customer demonstrations
- BLOCKED: No access (future use for banned users)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class UserMode(Enum):
    """User access modes for PEPPER bot"""

    GOD = "god"      # Full access, no restrictions
    DEMO = "demo"    # Guardrailed customer access
    BLOCKED = "blocked"  # No access


@dataclass
class ModeConfig:
    """Configuration for each user mode"""

    mode: UserMode
    greeting: str
    system_prompt: str
    allowed_commands: List[str]
    max_requests_per_hour: Optional[int] = None
    allow_direct_plc_access: bool = False
    allow_system_commands: bool = False
    enable_debug_info: bool = False

    @classmethod
    def god_mode(cls) -> "ModeConfig":
        """Configuration for God Mode users (internal team)"""
        return cls(
            mode=UserMode.GOD,
            greeting="Hey boss. What do you need?",
            system_prompt=(
                "You are PEPPER, Mike's personal factory AI assistant. "
                "You have full system access. Be direct, technical, and efficient. "
                "Mike knows what he's doing - no hand-holding needed."
            ),
            allowed_commands=["*"],  # All commands allowed
            max_requests_per_hour=None,  # No rate limit
            allow_direct_plc_access=True,
            allow_system_commands=True,
            enable_debug_info=True,
        )

    @classmethod
    def demo_mode(cls) -> "ModeConfig":
        """Configuration for Demo Mode users (customers)"""
        return cls(
            mode=UserMode.DEMO,
            greeting="Hi! I'm Pepper, your maintenance assistant. How can I help?",
            system_prompt=(
                "You are PEPPER, a friendly factory maintenance assistant. "
                "Help users diagnose equipment issues, answer questions about factory operations, "
                "and provide maintenance guidance. Be helpful, professional, and safety-focused. "
                "Never execute system commands or access sensitive data."
            ),
            allowed_commands=[
                "/start",
                "/help",
                "/status",
                "/diagnose",
                "/equipment",
            ],
            max_requests_per_hour=30,
            allow_direct_plc_access=False,
            allow_system_commands=False,
            enable_debug_info=False,
        )

    @classmethod
    def blocked_mode(cls) -> "ModeConfig":
        """Configuration for blocked users"""
        return cls(
            mode=UserMode.BLOCKED,
            greeting="Access denied.",
            system_prompt="",
            allowed_commands=[],
            max_requests_per_hour=0,
            allow_direct_plc_access=False,
            allow_system_commands=False,
            enable_debug_info=False,
        )


# God Mode Users (internal team)
GOD_MODE_USERS = [
    8445149012,  # Mike Crane
]

# Blocked Users (can be populated from config)
BLOCKED_USERS: List[int] = []


def get_user_mode(user_id: int) -> UserMode:
    """
    Determine the user's access mode based on their Telegram user ID.

    Args:
        user_id: Telegram user ID

    Returns:
        UserMode enum value (GOD, DEMO, or BLOCKED)
    """
    if user_id in BLOCKED_USERS:
        logger.warning(f"Blocked user {user_id} attempted access")
        return UserMode.BLOCKED

    if user_id in GOD_MODE_USERS:
        logger.info(f"God mode user {user_id} authenticated")
        return UserMode.GOD

    logger.info(f"Demo mode user {user_id} authenticated")
    return UserMode.DEMO


def get_mode_config(user_id: int) -> ModeConfig:
    """
    Get the complete mode configuration for a user.

    Args:
        user_id: Telegram user ID

    Returns:
        ModeConfig instance with appropriate settings
    """
    mode = get_user_mode(user_id)

    if mode == UserMode.GOD:
        return ModeConfig.god_mode()
    elif mode == UserMode.DEMO:
        return ModeConfig.demo_mode()
    else:
        return ModeConfig.blocked_mode()


def is_command_allowed(user_id: int, command: str) -> bool:
    """
    Check if a user is allowed to execute a specific command.

    Args:
        user_id: Telegram user ID
        command: Command to check (e.g., "/status")

    Returns:
        True if command is allowed, False otherwise
    """
    config = get_mode_config(user_id)

    # Wildcard allows all commands
    if "*" in config.allowed_commands:
        return True

    # Check if command is in allowed list
    return command in config.allowed_commands
