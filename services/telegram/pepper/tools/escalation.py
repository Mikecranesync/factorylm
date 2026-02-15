"""
Escalation Tool for PEPPER

Escalate issues to Mike (Tier 3 support).
Demo Mode: Can request escalation and callbacks
God Mode: Not needed (Mike is God Mode)
"""

from typing import Any, Dict, Optional
from datetime import datetime
import httpx

from .base import BaseTool, ToolContext, ToolResult, ToolResultStatus, UserMode
from .guardrails import GuardrailEngine


class EscalationTool(BaseTool):
    """Escalation to Mike (Demo Mode)"""

    name = "escalation"
    description = "Escalate issues to Mike or request callback"
    required_mode = UserMode.DEMO  # Only demo users need escalation

    # Notification endpoints
    TELEGRAM_BOT_URL = "http://100.68.120.99:9000/api/notify"
    SMS_API_URL = "http://100.68.120.99:9000/api/sms"

    # Mike's contact info (from knowledge base)
    MIKE_TELEGRAM_ID = "123456789"  # Replace with actual ID
    MIKE_PHONE = "+1234567890"  # Replace with actual number

    def __init__(self):
        super().__init__()
        self.guardrails = GuardrailEngine()

    def _get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["escalate_to_mike", "request_callback"],
                    "description": "Escalation operation"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation"
                },
                "context": {
                    "type": "object",
                    "description": "Additional context (chat history, equipment state, etc.)"
                },
                "phone": {
                    "type": "string",
                    "description": "Phone number for callback (for request_callback)"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Escalation urgency level"
                }
            },
            "required": ["operation", "reason"]
        }

    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute escalation operation"""
        operation = params.get("operation")

        if not operation:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: operation"
            )

        # Route to specific operation
        if operation == "escalate_to_mike":
            return await self._escalate_to_mike(params, context)
        elif operation == "request_callback":
            return await self._request_callback(params, context)
        else:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unknown operation: {operation}"
            )

    async def _escalate_to_mike(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Escalate issue to Mike"""
        reason = params.get("reason")
        additional_context = params.get("context", {})
        urgency = params.get("urgency", "medium")

        try:
            # Check rate limiting
            self.guardrails.check_rate_limit(context.user_id, 1)

            # Build escalation message
            message = self._format_escalation_message(
                reason=reason,
                user_id=context.user_id,
                username=context.username,
                chat_id=context.chat_id,
                urgency=urgency,
                context=additional_context
            )

            # Send notification to Mike via Telegram
            notification_sent = await self._send_telegram_notification(
                chat_id=self.MIKE_TELEGRAM_ID,
                message=message,
                urgency=urgency
            )

            if not notification_sent:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Failed to send escalation notification"
                )

            # Log escalation
            await self._log_escalation(
                user_id=context.user_id,
                reason=reason,
                urgency=urgency
            )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "escalated": True,
                    "reason": reason,
                    "urgency": urgency,
                    "timestamp": datetime.now().isoformat(),
                    "notification_method": "telegram"
                },
                metadata={
                    "operation": "escalate_to_mike",
                    "user_id": context.user_id
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Escalation failed: {str(e)}"
            )

    async def _request_callback(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Request callback from Mike"""
        reason = params.get("reason")
        phone = params.get("phone")
        urgency = params.get("urgency", "medium")

        if not phone:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: phone"
            )

        try:
            # Check rate limiting
            self.guardrails.check_rate_limit(context.user_id, 1)

            # Build callback request message
            message = self._format_callback_message(
                reason=reason,
                user_id=context.user_id,
                username=context.username,
                phone=phone,
                urgency=urgency
            )

            # Send notification to Mike
            notification_sent = await self._send_telegram_notification(
                chat_id=self.MIKE_TELEGRAM_ID,
                message=message,
                urgency=urgency
            )

            if not notification_sent:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Failed to send callback request"
                )

            # Log callback request
            await self._log_escalation(
                user_id=context.user_id,
                reason=f"Callback request: {reason}",
                urgency=urgency
            )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "callback_requested": True,
                    "phone": phone,
                    "reason": reason,
                    "urgency": urgency,
                    "timestamp": datetime.now().isoformat()
                },
                metadata={
                    "operation": "request_callback",
                    "user_id": context.user_id
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Callback request failed: {str(e)}"
            )

    def _format_escalation_message(
        self,
        reason: str,
        user_id: int,
        username: Optional[str],
        chat_id: int,
        urgency: str,
        context: Dict[str, Any]
    ) -> str:
        """Format escalation notification message"""
        urgency_emoji = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🚨",
            "critical": "🔴"
        }

        lines = [
            f"{urgency_emoji.get(urgency, '⚠️')} **ESCALATION: {urgency.upper()}**",
            "",
            f"**User:** {username or f'User {user_id}'} (ID: {user_id})",
            f"**Chat:** {chat_id}",
            f"**Reason:** {reason}",
            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]

        if context:
            lines.append("**Context:**")
            for key, value in context.items():
                lines.append(f"- {key}: {value}")

        lines.append("")
        lines.append("React to acknowledge or reply to respond.")

        return "\n".join(lines)

    def _format_callback_message(
        self,
        reason: str,
        user_id: int,
        username: Optional[str],
        phone: str,
        urgency: str
    ) -> str:
        """Format callback request message"""
        urgency_emoji = {
            "low": "📞",
            "medium": "☎️",
            "high": "📱",
            "critical": "🚨"
        }

        lines = [
            f"{urgency_emoji.get(urgency, '☎️')} **CALLBACK REQUEST: {urgency.upper()}**",
            "",
            f"**User:** {username or f'User {user_id}'} (ID: {user_id})",
            f"**Phone:** {phone}",
            f"**Reason:** {reason}",
            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "User is requesting a callback from you."
        ]

        return "\n".join(lines)

    async def _send_telegram_notification(
        self,
        chat_id: str,
        message: str,
        urgency: str
    ) -> bool:
        """
        Send notification via Telegram.

        Args:
            chat_id: Telegram chat ID
            message: Message to send
            urgency: Urgency level

        Returns:
            True if sent successfully
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TELEGRAM_BOT_URL,
                    json={
                        "chat_id": chat_id,
                        "message": message,
                        "parse_mode": "Markdown",
                        "disable_notification": urgency == "low"
                    },
                    timeout=10
                )
                return response.status_code == 200

        except Exception:
            return False

    async def _log_escalation(
        self,
        user_id: int,
        reason: str,
        urgency: str
    ) -> None:
        """
        Log escalation to audit trail.

        Args:
            user_id: User ID
            reason: Escalation reason
            urgency: Urgency level
        """
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "http://100.68.120.99:8080/api/v1/audit/escalations",
                    json={
                        "user_id": user_id,
                        "reason": reason,
                        "urgency": urgency,
                        "timestamp": datetime.now().isoformat()
                    },
                    timeout=5
                )
        except:
            # Log failure silently - don't block escalation
            pass
