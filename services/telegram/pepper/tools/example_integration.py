#!/usr/bin/env python3
"""
Example Integration: PEPPER Tools with Telegram Bot

Shows how to integrate the tools system with the PEPPER Telegram bot.
"""

import asyncio
import os
from typing import Dict, Optional

from pepper.tools import (
    get_tool_registry,
    ToolContext,
    ToolResult,
    UserMode,
)


class PepperBotExample:
    """Example PEPPER bot with tools integration"""

    def __init__(self):
        """Initialize bot with tool registry"""
        self.registry = get_tool_registry(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            claude_api_key=os.getenv("CLAUDE_API_KEY")
        )

        # User sessions (in-memory for example)
        self.sessions: Dict[int, dict] = {}

        # User modes (Mike is God Mode, others are Demo)
        self.MIKE_USER_ID = 1  # Replace with actual Mike's user ID
        self.user_modes: Dict[int, UserMode] = {}

    def get_user_mode(self, user_id: int) -> UserMode:
        """Get user's mode"""
        if user_id == self.MIKE_USER_ID:
            return UserMode.GOD
        return self.user_modes.get(user_id, UserMode.DEMO)

    def get_session(self, user_id: int) -> dict:
        """Get or create user session"""
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                "active_twin": None,
                "chat_history": [],
                "context": {}
            }
        return self.sessions[user_id]

    async def handle_message(
        self,
        user_id: int,
        chat_id: int,
        message: str,
        username: Optional[str] = None
    ) -> str:
        """
        Handle incoming message and route to appropriate tool.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message: User message
            username: Username (optional)

        Returns:
            Bot response
        """
        # Get user mode and session
        mode = self.get_user_mode(user_id)
        session = self.get_session(user_id)

        # Create tool context
        context = ToolContext(
            user_id=user_id,
            chat_id=chat_id,
            mode=mode,
            active_twin=session.get("active_twin", "factory"),
            session_data=session,
            username=username
        )

        # Parse message and route to tool
        if "status" in message.lower() and "equipment" in message.lower():
            return await self._handle_equipment_status(message, context)

        elif "diagnose" in message.lower() or "what's wrong" in message.lower():
            return await self._handle_diagnosis(message, context)

        elif "work order" in message.lower():
            return await self._handle_work_order(message, context)

        elif "escalate" in message.lower() or "help" in message.lower():
            return await self._handle_escalation(message, context)

        elif mode == UserMode.GOD and ("shell" in message.lower() or "run" in message.lower()):
            return await self._handle_shell(message, context)

        else:
            return await self._handle_general_query(message, context)

    async def _handle_equipment_status(
        self,
        message: str,
        context: ToolContext
    ) -> str:
        """Handle equipment status query"""
        # Extract equipment ID from message (simplified)
        equipment_id = self._extract_equipment_id(message)

        if not equipment_id:
            return "Which equipment would you like to check? (e.g., 'conveyor_01')"

        # Execute equipment tool
        tool = self.registry.get("equipment")
        result = await tool.execute_with_checks(
            params={
                "operation": "get_status",
                "equipment_id": equipment_id
            },
            context=context
        )

        return self._format_equipment_status(result)

    async def _handle_diagnosis(
        self,
        message: str,
        context: ToolContext
    ) -> str:
        """Handle diagnosis request"""
        # Extract question
        question = message.replace("diagnose", "").strip()

        if not question:
            return "What would you like me to diagnose?"

        # Execute diagnosis tool
        tool = self.registry.get("diagnosis")
        result = await tool.execute_with_checks(
            params={
                "operation": "diagnose",
                "question": question,
                "equipment_id": context.active_twin
            },
            context=context
        )

        return self._format_diagnosis(result)

    async def _handle_work_order(
        self,
        message: str,
        context: ToolContext
    ) -> str:
        """Handle work order operations"""
        if "create" in message.lower():
            # Create work order
            description = message.replace("create work order", "").strip()

            tool = self.registry.get("work_orders")
            result = await tool.execute_with_checks(
                params={
                    "operation": "create",
                    "description": description,
                    "equipment_id": context.active_twin,
                    "priority": "medium"
                },
                context=context
            )

            return self._format_work_order_created(result)

        elif "list" in message.lower():
            # List work orders
            tool = self.registry.get("work_orders")
            result = await tool.execute_with_checks(
                params={"operation": "list_my_work_orders"},
                context=context
            )

            return self._format_work_order_list(result)

        else:
            return "Work order commands: 'create work order [description]' or 'list work orders'"

    async def _handle_escalation(
        self,
        message: str,
        context: ToolContext
    ) -> str:
        """Handle escalation request"""
        if context.mode == UserMode.GOD:
            return "You're already in God Mode! No need to escalate."

        reason = message.replace("escalate", "").strip()

        tool = self.registry.get("escalation")
        result = await tool.execute_with_checks(
            params={
                "operation": "escalate_to_mike",
                "reason": reason or "User requested assistance",
                "urgency": "medium"
            },
            context=context
        )

        if result.is_success:
            return "✓ Escalated to Mike. He'll respond shortly."
        else:
            return f"Failed to escalate: {result.error}"

    async def _handle_shell(
        self,
        message: str,
        context: ToolContext
    ) -> str:
        """Handle shell command (God Mode only)"""
        # Extract command
        command = message.replace("shell", "").replace("run", "").strip()

        if not command:
            return "What command would you like to run?"

        tool = self.registry.get("shell")
        result = await tool.execute_with_checks(
            params={
                "operation": "execute",
                "command": command,
                "node": "local",
                "timeout": 30
            },
            context=context
        )

        if result.is_success:
            stdout = result.data.get("stdout", "")
            stderr = result.data.get("stderr", "")
            return f"```\n{stdout}\n{stderr}\n```"
        elif result.is_blocked:
            return f"❌ {result.error}\n💡 {result.suggested_action}"
        else:
            return f"Error: {result.error}"

    async def _handle_general_query(
        self,
        message: str,
        context: ToolContext
    ) -> str:
        """Handle general query with diagnosis tool"""
        tool = self.registry.get("diagnosis")
        result = await tool.execute_with_checks(
            params={
                "operation": "diagnose",
                "question": message
            },
            context=context
        )

        if result.is_success:
            return result.data.get("diagnosis", "I couldn't understand that.")
        else:
            return "I'm not sure how to help with that. Try asking about equipment status or diagnostics."

    def _extract_equipment_id(self, message: str) -> Optional[str]:
        """Extract equipment ID from message"""
        # Simplified extraction - in production, use NLP
        words = message.lower().split()
        for word in words:
            if word.startswith("conveyor") or word.startswith("motor") or word.startswith("pump"):
                return word
        return None

    def _format_equipment_status(self, result: ToolResult) -> str:
        """Format equipment status result"""
        if result.is_success:
            data = result.data
            return f"""
🏭 **Equipment Status**

**ID:** {data.get('equipment_id')}
**Status:** {data.get('status')}
**State:** {data.get('state')}
**Runtime:** {data.get('runtime', 'N/A')}

Last updated: {data.get('last_update', 'Unknown')}
"""
        elif result.is_blocked:
            return f"❌ {result.error}\n💡 {result.suggested_action}"
        else:
            return f"Error getting equipment status: {result.error}"

    def _format_diagnosis(self, result: ToolResult) -> str:
        """Format diagnosis result"""
        if result.is_success:
            return f"🔍 **Diagnosis**\n\n{result.data.get('diagnosis')}"
        else:
            return f"Error during diagnosis: {result.error}"

    def _format_work_order_created(self, result: ToolResult) -> str:
        """Format work order creation result"""
        if result.is_success:
            data = result.data
            return f"✓ Work Order Created: #{data.get('work_order_id')}\n\n{data.get('description')}"
        else:
            return f"Error creating work order: {result.error}"

    def _format_work_order_list(self, result: ToolResult) -> str:
        """Format work order list"""
        if result.is_success:
            wos = result.data.get("work_orders", [])
            if not wos:
                return "No work orders found."

            lines = ["📋 **Your Work Orders**\n"]
            for wo in wos:
                lines.append(f"#{wo.get('id')}: {wo.get('description')} ({wo.get('status')})")

            return "\n".join(lines)
        else:
            return f"Error listing work orders: {result.error}"


async def example_usage():
    """Example usage scenarios"""
    print("=" * 60)
    print("PEPPER Bot - Example Usage")
    print("=" * 60)

    bot = PepperBotExample()

    # Example 1: Demo user checks equipment status
    print("\n--- Example 1: Demo User Checks Equipment Status ---")
    response = await bot.handle_message(
        user_id=42,
        chat_id=123,
        message="What's the status of conveyor_01?",
        username="demo_user"
    )
    print(response)

    # Example 2: Demo user creates work order
    print("\n--- Example 2: Demo User Creates Work Order ---")
    response = await bot.handle_message(
        user_id=42,
        chat_id=123,
        message="create work order Conveyor running at low speed",
        username="demo_user"
    )
    print(response)

    # Example 3: Demo user tries shell command (blocked)
    print("\n--- Example 3: Demo User Tries Shell (Blocked) ---")
    response = await bot.handle_message(
        user_id=42,
        chat_id=123,
        message="shell ls -la",
        username="demo_user"
    )
    print(response)

    # Example 4: God user runs shell command (allowed)
    print("\n--- Example 4: God User Runs Shell (Allowed) ---")
    response = await bot.handle_message(
        user_id=1,  # Mike
        chat_id=456,
        message="shell pwd",
        username="mike"
    )
    print(response)

    # Example 5: Demo user escalates
    print("\n--- Example 5: Demo User Escalates ---")
    response = await bot.handle_message(
        user_id=42,
        chat_id=123,
        message="escalate Need help with critical fault",
        username="demo_user"
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(example_usage())
