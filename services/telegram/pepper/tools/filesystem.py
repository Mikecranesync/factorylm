"""
Filesystem Tool for PEPPER

File operations with guardrails for Demo Mode.
God Mode: Full access
Demo Mode: Blocked
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import glob

from .base import BaseTool, ToolContext, ToolResult, ToolResultStatus, UserMode
from .guardrails import GuardrailEngine


class FilesystemTool(BaseTool):
    """Filesystem operations (God Mode only)"""

    name = "filesystem"
    description = "Read, write, search, and list files and directories"
    required_mode = UserMode.GOD

    def __init__(self):
        super().__init__()
        self.guardrails = GuardrailEngine()

    def _get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "search", "list"],
                    "description": "Filesystem operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write operation)"
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern for search operation"
                }
            },
            "required": ["operation", "path"]
        }

    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Execute filesystem operation"""
        operation = params.get("operation")
        path = params.get("path")

        if not operation or not path:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Missing required parameters: operation and path"
            )

        # Route to specific operation
        operations = {
            "read": self._read_file,
            "write": self._write_file,
            "search": self._search_files,
            "list": self._list_directory,
        }

        handler = operations.get(operation)
        if not handler:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unknown operation: {operation}"
            )

        return await handler(params, context)

    async def _read_file(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Read file contents"""
        path = params["path"]

        try:
            # Check access (would enforce in demo mode)
            if context.is_demo_mode:
                self.guardrails.check_file_access(path, "read", context.user_id)

            # Read file
            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"File not found: {path}"
                )

            if not file_path.is_file():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Path is not a file: {path}"
                )

            content = file_path.read_text(encoding="utf-8")

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "path": str(file_path),
                    "content": content,
                    "size": file_path.stat().st_size,
                },
                metadata={
                    "operation": "read",
                    "file_type": file_path.suffix
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to read file: {str(e)}"
            )

    async def _write_file(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Write content to file"""
        path = params["path"]
        content = params.get("content", "")

        try:
            # Check access
            if context.is_demo_mode:
                self.guardrails.check_file_access(path, "write", context.user_id)

            # Write file
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file if it exists
            backup_path = None
            if file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                backup_path.write_text(file_path.read_text(), encoding="utf-8")

            file_path.write_text(content, encoding="utf-8")

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "backup": str(backup_path) if backup_path else None
                },
                metadata={
                    "operation": "write",
                    "created_backup": backup_path is not None
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to write file: {str(e)}"
            )

    async def _search_files(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """Search for files matching pattern"""
        pattern = params.get("pattern", params.get("path", ""))

        try:
            # Search files
            matches = glob.glob(pattern, recursive=True)

            # Filter out inaccessible paths in demo mode
            if context.is_demo_mode:
                accessible = []
                for match in matches:
                    try:
                        self.guardrails.check_file_access(match, "read", context.user_id)
                        accessible.append(match)
                    except:
                        pass
                matches = accessible

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "pattern": pattern,
                    "matches": matches,
                    "count": len(matches)
                },
                metadata={
                    "operation": "search"
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to search files: {str(e)}"
            )

    async def _list_directory(
        self,
        params: Dict[str, Any],
        context: ToolContext
    ) -> ToolResult:
        """List directory contents"""
        path = params["path"]

        try:
            # Check access
            if context.is_demo_mode:
                self.guardrails.check_file_access(path, "read", context.user_id)

            # List directory
            dir_path = Path(path)
            if not dir_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Directory not found: {path}"
                )

            if not dir_path.is_dir():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Path is not a directory: {path}"
                )

            entries = []
            for item in dir_path.iterdir():
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "path": str(dir_path),
                    "entries": entries,
                    "count": len(entries)
                },
                metadata={
                    "operation": "list"
                }
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list directory: {str(e)}"
            )
