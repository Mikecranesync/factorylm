"""
Work Orders Tool for PEPPER

Create, update, and manage work orders.
God Mode: Full access to all work orders
Demo Mode: Can only access own work orders
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx

from .base import BaseTool, ToolContext, ToolResult, ToolResultStatus, UserMode
from .guardrails import GuardrailEngine


class WorkOrdersTool(BaseTool):
    """Work order management (Demo: own records only)"""

    name = "work_orders"
    description = "Create, update, list, and close work orders"
    required_mode = UserMode.ANY

    # Work order API endpoint
    WO_API_URL = "http://100.68.120.99:8080/api/v1/work_orders"

    def __init__(self):
        super().__init__()
        self.guardrails = GuardrailEngine()

    def _get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "create",
                        "update",
                        "list_my_work_orders",
                        "close",
                        "get_details"
                    ],
                    "description": "Work order operation"
                },
                "work_order_id": {
                    "type": "integer",
                    "description": "Work order ID (for update/close/get operations)"
                },
                "description": {
                    "type": "string",
                    "description": "Work order description (for create)"
                },
                "equipment_id": {
                    "type": "string",
                    "description": "Related equipment ID"
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "blocked", "completed", "closed"],
                    "description": "Work order status (for update)"
                },
                "notes": {
                    "type": "string",
                    "description": "Notes to add (for update)"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Work order priority"
                }
            },
            "required": ["operation"]
        }

    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute work order operation"""
        operation = params.get("operation")

        if not operation:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: operation"
            )

        # Route to specific operation
        operations = {
            "create": self._create_work_order,
            "update": self._update_work_order,
            "list_my_work_orders": self._list_my_work_orders,
            "close": self._close_work_order,
            "get_details": self._get_details,
        }

        handler = operations.get(operation)
        if not handler:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unknown operation: {operation}"
            )

        return await handler(params, context)

    async def _create_work_order(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Create new work order"""
        description = params.get("description")
        equipment_id = params.get("equipment_id")
        priority = params.get("priority", "medium")

        if not description:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: description"
            )

        try:
            # Check rate limiting for demo users
            if context.is_demo_mode:
                self.guardrails.check_rate_limit(context.user_id, 1)

            # Create work order
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.WO_API_URL,
                    json={
                        "description": description,
                        "equipment_id": equipment_id,
                        "priority": priority,
                        "created_by": context.user_id,
                        "status": "open",
                        "created_at": datetime.now().isoformat()
                    },
                    timeout=10
                )

                if response.status_code not in [200, 201]:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to create work order: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "work_order_id": data.get("id"),
                        "description": description,
                        "equipment_id": equipment_id,
                        "priority": priority,
                        "status": "open",
                        "created_at": data.get("created_at")
                    },
                    metadata={
                        "operation": "create",
                        "user_id": context.user_id
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Work order creation timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to create work order: {str(e)}"
            )

    async def _update_work_order(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Update existing work order"""
        work_order_id = params.get("work_order_id")
        status = params.get("status")
        notes = params.get("notes")

        if not work_order_id:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: work_order_id"
            )

        try:
            # Check ownership for demo users
            if context.is_demo_mode:
                # Get user's work orders to verify ownership
                user_wos = await self._get_user_work_orders(context.user_id)
                user_wo_ids = {wo["id"] for wo in user_wos}

                self.guardrails.validate_work_order_ownership(
                    work_order_id,
                    context.user_id,
                    user_wo_ids
                )

            # Update work order
            update_data = {}
            if status:
                update_data["status"] = status
            if notes:
                update_data["notes"] = notes
            update_data["updated_at"] = datetime.now().isoformat()

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.WO_API_URL}/{work_order_id}",
                    json=update_data,
                    timeout=10
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to update work order: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "work_order_id": work_order_id,
                        "status": data.get("status"),
                        "notes": data.get("notes"),
                        "updated_at": data.get("updated_at")
                    },
                    metadata={
                        "operation": "update",
                        "user_id": context.user_id
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Work order update timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to update work order: {str(e)}"
            )

    async def _list_my_work_orders(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """List user's work orders"""
        try:
            # Get work orders for user
            work_orders = await self._get_user_work_orders(context.user_id)

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "work_orders": work_orders,
                    "count": len(work_orders),
                    "user_id": context.user_id
                },
                metadata={
                    "operation": "list_my_work_orders"
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list work orders: {str(e)}"
            )

    async def _close_work_order(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Close work order"""
        work_order_id = params.get("work_order_id")

        if not work_order_id:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: work_order_id"
            )

        # Use update operation to set status to closed
        return await self._update_work_order(
            {
                "work_order_id": work_order_id,
                "status": "closed"
            },
            context
        )

    async def _get_details(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Get work order details"""
        work_order_id = params.get("work_order_id")

        if not work_order_id:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: work_order_id"
            )

        try:
            # Check ownership for demo users
            if context.is_demo_mode:
                user_wos = await self._get_user_work_orders(context.user_id)
                user_wo_ids = {wo["id"] for wo in user_wos}

                self.guardrails.validate_work_order_ownership(
                    work_order_id,
                    context.user_id,
                    user_wo_ids
                )

            # Get work order details
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.WO_API_URL}/{work_order_id}",
                    timeout=10
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to get work order: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=data,
                    metadata={
                        "operation": "get_details"
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Work order query timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get work order: {str(e)}"
            )

    async def _get_user_work_orders(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all work orders for a user.

        Args:
            user_id: User ID

        Returns:
            List of work orders
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.WO_API_URL,
                params={"created_by": user_id},
                timeout=10
            )

            if response.status_code != 200:
                return []

            data = response.json()
            return data.get("work_orders", [])
