"""
Guardrail Engine for PEPPER Demo Mode

Implements security boundaries and access control for demo users.
Enforces path restrictions, command filtering, and rate limiting.
"""

import re
from pathlib import Path
from typing import Any, List, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

from .base import GuardrailViolation


class GuardrailEngine:
    """Access control and safety guardrails for Demo Mode"""

    # File system restrictions
    BLOCKED_PATHS = [
        "/root/",
        "/etc/",
        "/var/",
        "/home/",
        "*.env*",
        "*secrets*",
        "*password*",
        "*key*",
        "*.pem",
        "*.key",
        "/sys/",
        "/proc/",
        "C:/Windows/",
        "C:/Program Files/",
    ]

    ALLOWED_PATHS = [
        "/knowledge_base/",
        "/procedures/",
        "/manuals/",
        "/documentation/",
        "/work_orders/",
        "/equipment/",
    ]

    # Shell command restrictions
    BLOCKED_COMMANDS = [
        "rm",
        "del",
        "format",
        "shutdown",
        "reboot",
        "kill",
        "pkill",
        "sudo",
        "chmod",
        "chown",
        "dd",
        "mkfs",
        ">",  # Redirect (can overwrite files)
        ">>",
        "|",  # Pipe (can chain dangerous commands)
    ]

    ALLOWED_COMMANDS = [
        "ls",
        "dir",
        "cat",
        "type",
        "grep",
        "find",
        "echo",
        "pwd",
        "cd",
    ]

    # PLC write restrictions
    PROTECTED_PLC_TAGS = [
        "ESTOP",
        "SAFETY",
        "INTERLOCK",
        "EMERGENCY",
        "SHUTDOWN",
    ]

    # Database restrictions
    PROTECTED_TABLES = [
        "users",
        "permissions",
        "audit_log",
        "system_config",
    ]

    # Rate limiting
    MAX_ACTIONS_PER_MINUTE = 10
    MAX_ACTIONS_PER_HOUR = 100

    def __init__(self):
        self._action_tracker: dict = defaultdict(list)

    def check_file_access(
        self,
        path: str,
        operation: str,
        user_id: int
    ) -> bool:
        """
        Check if file access is permitted.

        Args:
            path: File path to access
            operation: Operation type (read/write/delete)
            user_id: User ID for logging

        Returns:
            True if permitted

        Raises:
            GuardrailViolation: If access is blocked
        """
        # Normalize path
        normalized_path = str(Path(path).resolve())

        # Check blocked paths
        for blocked in self.BLOCKED_PATHS:
            if self._path_matches(normalized_path, blocked):
                raise GuardrailViolation(
                    f"Access to '{path}' is restricted for security reasons.",
                    suggested_action=(
                        "Demo mode can only access documentation, procedures, "
                        "and work order directories. Contact Mike if you need "
                        "access to system files."
                    )
                )

        # Write operations require explicit allowed path
        if operation in ["write", "delete"]:
            allowed = any(
                self._path_matches(normalized_path, allowed_path)
                for allowed_path in self.ALLOWED_PATHS
            )
            if not allowed:
                raise GuardrailViolation(
                    f"Write access to '{path}' is not permitted in demo mode.",
                    suggested_action=(
                        "You can only modify files in work order and "
                        "documentation directories. System files are read-only."
                    )
                )

        return True

    def check_shell_access(self, command: str, user_id: int) -> bool:
        """
        Check if shell command is permitted.

        Args:
            command: Shell command to execute
            user_id: User ID for logging

        Returns:
            True if permitted

        Raises:
            GuardrailViolation: If command is blocked
        """
        # Check for blocked commands
        for blocked in self.BLOCKED_COMMANDS:
            if blocked in command.lower():
                raise GuardrailViolation(
                    f"Command contains blocked operation: '{blocked}'",
                    suggested_action=(
                        "Demo mode only allows read-only commands like 'ls', "
                        "'cat', and 'grep'. Contact Mike for system administration."
                    )
                )

        # Require at least one allowed command
        has_allowed = any(
            allowed in command.lower()
            for allowed in self.ALLOWED_COMMANDS
        )

        if not has_allowed:
            raise GuardrailViolation(
                "Command not recognized as safe for demo mode.",
                suggested_action=(
                    "Please use standard read-only commands. "
                    "For complex operations, contact Mike."
                )
            )

        return True

    def check_plc_write(
        self,
        tag: str,
        value: Any,
        user_id: int
    ) -> bool:
        """
        Check if PLC write is permitted.

        Args:
            tag: PLC tag name
            value: Value to write
            user_id: User ID for logging

        Returns:
            True if permitted

        Raises:
            GuardrailViolation: If write is blocked
        """
        # Check protected tags
        tag_upper = tag.upper()
        for protected in self.PROTECTED_PLC_TAGS:
            if protected in tag_upper:
                raise GuardrailViolation(
                    f"Cannot modify safety-critical tag '{tag}'",
                    suggested_action=(
                        "Safety and emergency stop controls are read-only "
                        "in demo mode. Contact Mike for emergency operations."
                    )
                )

        # Additional safety check: no boolean writes to safety-related tags
        if isinstance(value, bool) and any(
            keyword in tag_upper
            for keyword in ["STOP", "ENABLE", "DISABLE", "ACTIVE"]
        ):
            raise GuardrailViolation(
                f"Cannot change state of control tag '{tag}' in demo mode",
                suggested_action=(
                    "Control system state changes require operator approval. "
                    "Use read-only diagnosis features instead."
                )
            )

        return True

    def check_database_access(
        self,
        table: str,
        operation: str,
        user_id: int,
        record_id: Optional[int] = None
    ) -> bool:
        """
        Check if database access is permitted.

        Args:
            table: Database table name
            operation: Operation (select/insert/update/delete)
            user_id: User ID for logging
            record_id: Optional record ID for ownership check

        Returns:
            True if permitted

        Raises:
            GuardrailViolation: If access is blocked
        """
        # Check protected tables
        if table.lower() in self.PROTECTED_TABLES:
            if operation.lower() in ["update", "delete", "insert"]:
                raise GuardrailViolation(
                    f"Cannot modify protected table '{table}'",
                    suggested_action=(
                        "System tables are read-only in demo mode. "
                        "Contact Mike for user or permission changes."
                    )
                )

        # Work orders: can only modify own records
        if table.lower() == "work_orders" and operation.lower() in ["update", "delete"]:
            # Would need to verify record ownership here
            # This is a placeholder for the actual ownership check
            pass

        return True

    def check_rate_limit(
        self,
        user_id: int,
        action_count: int = 1
    ) -> bool:
        """
        Check if user is within rate limits.

        Args:
            user_id: User ID to check
            action_count: Number of actions (default 1)

        Returns:
            True if within limits

        Raises:
            GuardrailViolation: If rate limit exceeded
        """
        now = datetime.now()
        user_actions = self._action_tracker[user_id]

        # Clean old actions
        user_actions = [
            timestamp for timestamp in user_actions
            if now - timestamp < timedelta(hours=1)
        ]
        self._action_tracker[user_id] = user_actions

        # Check per-minute limit
        recent_actions = [
            timestamp for timestamp in user_actions
            if now - timestamp < timedelta(minutes=1)
        ]
        if len(recent_actions) + action_count > self.MAX_ACTIONS_PER_MINUTE:
            raise GuardrailViolation(
                "Rate limit exceeded: too many actions per minute",
                suggested_action=(
                    f"Please wait a moment. Demo mode is limited to "
                    f"{self.MAX_ACTIONS_PER_MINUTE} actions per minute."
                )
            )

        # Check per-hour limit
        if len(user_actions) + action_count > self.MAX_ACTIONS_PER_HOUR:
            raise GuardrailViolation(
                "Rate limit exceeded: too many actions per hour",
                suggested_action=(
                    f"You've reached the demo limit of "
                    f"{self.MAX_ACTIONS_PER_HOUR} actions per hour. "
                    "Contact Mike if you need extended access."
                )
            )

        # Record action
        for _ in range(action_count):
            user_actions.append(now)

        return True

    def _path_matches(self, path: str, pattern: str) -> bool:
        """
        Check if path matches pattern (supports wildcards).

        Args:
            path: Path to check
            pattern: Pattern with wildcards

        Returns:
            True if path matches pattern
        """
        # Convert glob pattern to regex
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        return bool(re.match(regex_pattern, path, re.IGNORECASE))

    def validate_work_order_ownership(
        self,
        work_order_id: int,
        user_id: int,
        user_records: Set[int]
    ) -> bool:
        """
        Validate that user owns the work order.

        Args:
            work_order_id: Work order ID
            user_id: User ID
            user_records: Set of work order IDs owned by user

        Returns:
            True if user owns the record

        Raises:
            GuardrailViolation: If user doesn't own the record
        """
        if work_order_id not in user_records:
            raise GuardrailViolation(
                f"You can only modify your own work orders.",
                suggested_action=(
                    "Demo users can only update work orders they created. "
                    "Contact Mike if you need to modify other records."
                )
            )
        return True

    def check_equipment_write(
        self,
        equipment_id: str,
        operation: str,
        user_id: int
    ) -> bool:
        """
        Check if equipment modification is permitted.

        Args:
            equipment_id: Equipment identifier
            operation: Operation type
            user_id: User ID

        Returns:
            True if permitted

        Raises:
            GuardrailViolation: If operation is blocked
        """
        # Demo mode: read-only for equipment
        if operation.lower() in ["update", "delete", "control"]:
            raise GuardrailViolation(
                "Equipment control is read-only in demo mode.",
                suggested_action=(
                    "You can view equipment status and diagnostics. "
                    "Contact Mike for equipment control operations."
                )
            )
        return True
