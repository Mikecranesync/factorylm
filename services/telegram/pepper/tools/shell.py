"""
Shell Tool for PEPPER

Execute shell commands and scripts with guardrails.
God Mode: Full access
Demo Mode: Blocked
"""

import asyncio
from typing import Any, Dict, Optional
import httpx

from .base import BaseTool, ToolContext, ToolResult, ToolResultStatus, UserMode
from .guardrails import GuardrailEngine


class ShellTool(BaseTool):
    """Shell command execution (God Mode only)"""

    name = "shell"
    description = "Execute shell commands and scripts on local or remote nodes"
    required_mode = UserMode.GOD

    # Node endpoints for remote execution
    NODES = {
        "plc_laptop": "http://100.72.2.99:8765",
        "travel_laptop": "http://100.83.251.23:8765",
        "vps": "http://100.68.120.99:8765",
        "local": "local"
    }

    def __init__(self):
        super().__init__()
        self.guardrails = GuardrailEngine()

    def _get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["execute", "run_script"],
                    "description": "Shell operation to perform"
                },
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "script_path": {
                    "type": "string",
                    "description": "Path to script file (for run_script)"
                },
                "node": {
                    "type": "string",
                    "enum": list(NODES.keys()),
                    "description": "Target node for execution (default: local)"
                },
                "timeout": {
                    "type": "number",
                    "description": "Execution timeout in seconds (default: 30)"
                }
            },
            "required": ["operation"]
        }

    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute shell operation"""
        operation = params.get("operation")

        if not operation:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: operation"
            )

        # Route to specific operation
        if operation == "execute":
            return await self._execute_command(params, context)
        elif operation == "run_script":
            return await self._run_script(params, context)
        else:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unknown operation: {operation}"
            )

    async def _execute_command(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute shell command"""
        command = params.get("command")
        node = params.get("node", "local")
        timeout = params.get("timeout", 30)

        if not command:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: command"
            )

        try:
            # Check guardrails (even for God mode, for logging)
            if context.is_demo_mode:
                self.guardrails.check_shell_access(command, context.user_id)

            # Execute locally or remotely
            if node == "local":
                result = await self._execute_local(command, timeout)
            else:
                result = await self._execute_remote(command, node, timeout)

            return result

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to execute command: {str(e)}"
            )

    async def _execute_local(
        self,
        command: str,
        timeout: int
    ) -> ToolResult:
        """Execute command on local system"""
        try:
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    status=ToolResultStatus.TIMEOUT,
                    error=f"Command timed out after {timeout} seconds"
                )

            # Parse output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "exit_code": process.returncode,
                    "node": "local"
                },
                metadata={
                    "operation": "execute",
                    "command": command,
                    "timeout": timeout
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Local execution failed: {str(e)}"
            )

    async def _execute_remote(
        self,
        command: str,
        node: str,
        timeout: int
    ) -> ToolResult:
        """Execute command on remote node"""
        endpoint = self.NODES.get(node)
        if not endpoint or endpoint == "local":
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Invalid node: {node}"
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{endpoint}/shell",
                    json={
                        "command": command,
                        "timeout": timeout
                    },
                    timeout=timeout + 5  # Extra buffer for network
                )

                if response.status_code != 200:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Remote execution failed: {response.text}"
                    )

                result = response.json()
                result["node"] = node

                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=result,
                    metadata={
                        "operation": "execute",
                        "command": command,
                        "timeout": timeout,
                        "endpoint": endpoint
                    }
                )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error=f"Remote command timed out after {timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Remote execution failed: {str(e)}"
            )

    async def _run_script(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute script file"""
        script_path = params.get("script_path")
        node = params.get("node", "local")
        timeout = params.get("timeout", 60)

        if not script_path:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameter: script_path"
            )

        try:
            # Determine script interpreter
            if script_path.endswith(".py"):
                command = f"python {script_path}"
            elif script_path.endswith(".sh"):
                command = f"bash {script_path}"
            elif script_path.endswith(".ps1"):
                command = f"powershell -File {script_path}"
            elif script_path.endswith(".bat"):
                command = script_path
            else:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Unsupported script type: {script_path}"
                )

            # Execute as command
            return await self._execute_command(
                {
                    "command": command,
                    "node": node,
                    "timeout": timeout
                },
                context
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to run script: {str(e)}"
            )

    async def check_node_health(self, node: str) -> Dict[str, Any]:
        """
        Check if a remote node is accessible.

        Args:
            node: Node name

        Returns:
            Health status dictionary
        """
        endpoint = self.NODES.get(node)
        if not endpoint or endpoint == "local":
            return {"node": node, "status": "local", "accessible": True}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{endpoint}/health",
                    timeout=5
                )
                return {
                    "node": node,
                    "status": "online" if response.status_code == 200 else "error",
                    "accessible": response.status_code == 200,
                    "endpoint": endpoint
                }
        except:
            return {
                "node": node,
                "status": "offline",
                "accessible": False,
                "endpoint": endpoint
            }
