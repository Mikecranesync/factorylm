"""
Equipment Tool for PEPPER

Equipment status, diagnostics, and procedure search.
God Mode: Full access
Demo Mode: Read-only access
"""

from typing import Any, Dict, List, Optional
import httpx

from .base import BaseTool, ToolContext, ToolResult, ToolResultStatus, UserMode
from .guardrails import GuardrailEngine


class EquipmentTool(BaseTool):
    """Equipment operations (read-only for Demo, full for God)"""

    name = "equipment"
    description = "Get equipment status, faults, I/O state, and search procedures"
    required_mode = UserMode.ANY

    # Matrix API endpoint (Digital Twin backend)
    MATRIX_API_URL = "http://100.68.120.99:8080/api/v1"

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
                        "get_status",
                        "get_faults",
                        "get_io_panel",
                        "search_procedures",
                        "get_maintenance_history"
                    ],
                    "description": "Equipment operation to perform"
                },
                "equipment_id": {
                    "type": "string",
                    "description": "Equipment identifier (for status/faults operations)"
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for procedure search)"
                }
            },
            "required": ["operation"]
        }

    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute equipment operation"""
        operation = params.get("operation")

        if not operation:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: operation"
            )

        # Route to specific operation
        operations = {
            "get_status": self._get_status,
            "get_faults": self._get_faults,
            "get_io_panel": self._get_io_panel,
            "search_procedures": self._search_procedures,
            "get_maintenance_history": self._get_maintenance_history,
        }

        handler = operations.get(operation)
        if not handler:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unknown operation: {operation}"
            )

        return await handler(params, context)

    async def _get_status(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Get equipment status"""
        equipment_id = params.get("equipment_id")

        if not equipment_id:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: equipment_id"
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.MATRIX_API_URL}/equipment/{equipment_id}/status",
                    timeout=10
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to get equipment status: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "equipment_id": equipment_id,
                        "status": data.get("status"),
                        "state": data.get("state"),
                        "runtime": data.get("runtime"),
                        "last_update": data.get("last_update"),
                        "metrics": data.get("metrics", {})
                    },
                    metadata={
                        "operation": "get_status",
                        "source": "matrix_api"
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Equipment status request timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get equipment status: {str(e)}"
            )

    async def _get_faults(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Get equipment faults"""
        equipment_id = params.get("equipment_id")

        if not equipment_id:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: equipment_id"
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.MATRIX_API_URL}/equipment/{equipment_id}/faults",
                    timeout=10
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to get faults: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "equipment_id": equipment_id,
                        "active_faults": data.get("active_faults", []),
                        "fault_count": len(data.get("active_faults", [])),
                        "severity": data.get("max_severity"),
                        "last_fault": data.get("last_fault")
                    },
                    metadata={
                        "operation": "get_faults",
                        "source": "matrix_api"
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Fault query timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get faults: {str(e)}"
            )

    async def _get_io_panel(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Get current I/O panel state"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.MATRIX_API_URL}/io/panel",
                    timeout=10
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to get I/O panel: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "inputs": data.get("inputs", {}),
                        "outputs": data.get("outputs", {}),
                        "timestamp": data.get("timestamp")
                    },
                    metadata={
                        "operation": "get_io_panel",
                        "source": "matrix_api"
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="I/O panel request timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get I/O panel: {str(e)}"
            )

    async def _search_procedures(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Search equipment procedures and manuals"""
        query = params.get("query")

        if not query:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: query"
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.MATRIX_API_URL}/procedures/search",
                    params={"q": query},
                    timeout=10
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to search procedures: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "query": query,
                        "results": data.get("results", []),
                        "count": len(data.get("results", [])),
                        "categories": data.get("categories", [])
                    },
                    metadata={
                        "operation": "search_procedures",
                        "source": "matrix_api"
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Procedure search timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to search procedures: {str(e)}"
            )

    async def _get_maintenance_history(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Get equipment maintenance history"""
        equipment_id = params.get("equipment_id")

        if not equipment_id:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: equipment_id"
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.MATRIX_API_URL}/equipment/{equipment_id}/maintenance",
                    timeout=10
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Failed to get maintenance history: {response.text}"
                    )

                data = response.json()

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "equipment_id": equipment_id,
                        "history": data.get("history", []),
                        "next_scheduled": data.get("next_scheduled"),
                        "overdue": data.get("overdue", [])
                    },
                    metadata={
                        "operation": "get_maintenance_history",
                        "source": "matrix_api"
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Maintenance history request timed out"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get maintenance history: {str(e)}"
            )
