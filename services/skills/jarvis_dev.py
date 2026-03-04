"""JarvisDevSkill - Remote development capabilities via Telegram.

Enables:
- Shell command execution on VPS and remote nodes
- File read/write/search
- Git operations
- Development workflow from anywhere

Commands:
  /jarvis shell <cmd>     - Execute shell command
  /jarvis read <path>     - Read file contents
  /jarvis write <path>    - Write file (next message = content)
  /jarvis git <cmd>       - Git operations
  /jarvis nodes           - List available Jarvis nodes
  /jarvis exec <node> <cmd> - Execute on specific node
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import httpx
from pathlib import Path
from typing import Optional, Dict, Any

from openclaw.messages.models import InboundMessage, OutboundMessage
from openclaw.skills.base import Skill, SkillContext
from openclaw.types import Intent

logger = logging.getLogger(__name__)

# Jarvis node registry
JARVIS_NODES = {
    "vps": {"host": "localhost", "port": 8765, "name": "VPS (Jarvis)"},
    "travel": {"host": "100.83.251.23", "port": 8765, "name": "Travel Laptop"},
    "plc": {"host": "100.72.2.99", "port": 8765, "name": "PLC Laptop"},
}

# Authorized users (Telegram user IDs)
AUTHORIZED_USERS = {
    "8445149012",  # Mike
}


class JarvisDevService:
    """Core dev service for shell/file operations."""

    def __init__(self):
        self.pending_writes: Dict[str, str] = {}  # user_id -> filepath
        self.http = httpx.AsyncClient(timeout=30.0)

    async def execute_shell(self, command: str, cwd: str = None, timeout: int = 60) -> Dict[str, Any]:
        """Execute shell command locally."""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode()[-4000:],  # Truncate for Telegram
                "stderr": stderr.decode()[-1000:],
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_remote(self, node: str, command: str, timeout: int = 60) -> Dict[str, Any]:
        """Execute command on remote Jarvis node."""
        if node not in JARVIS_NODES:
            return {"success": False, "error": f"Unknown node: {node}"}

        node_info = JARVIS_NODES[node]
        url = f"http://{node_info['host']}:{node_info['port']}/shell"

        try:
            resp = await self.http.post(url, json={
                "command": command,
                "timeout": timeout
            })
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": data.get("returncode", 1) == 0,
                    "stdout": data.get("stdout", "")[-4000:],
                    "stderr": data.get("stderr", ""),
                    "node": node_info["name"],
                }
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except httpx.ConnectError:
            return {"success": False, "error": f"{node_info['name']} offline"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, filepath: str, limit: int = 100) -> Dict[str, Any]:
        """Read file contents."""
        try:
            p = Path(filepath).expanduser()
            if not p.exists():
                return {"success": False, "error": "File not found"}
            if p.is_dir():
                files = list(p.iterdir())[:50]
                return {
                    "success": True,
                    "type": "directory",
                    "contents": [f.name for f in files],
                }

            content = p.read_text()
            lines = content.split("\n")
            if len(lines) > limit:
                content = "\n".join(lines[:limit]) + f"\n... ({len(lines) - limit} more lines)"

            return {
                "success": True,
                "type": "file",
                "path": str(p),
                "contents": content[-4000:],  # Truncate for Telegram
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, filepath: str, content: str) -> Dict[str, Any]:
        """Write content to file."""
        try:
            p = Path(filepath).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return {"success": True, "path": str(p), "bytes": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_nodes(self) -> str:
        """List available Jarvis nodes."""
        lines = ["Jarvis Nodes:"]
        for key, info in JARVIS_NODES.items():
            lines.append(f"  {key}: {info['name']} ({info['host']}:{info['port']})")
        return "\n".join(lines)


# Singleton
_service: Optional[JarvisDevService] = None

def get_jarvis_dev_service() -> JarvisDevService:
    global _service
    if _service is None:
        _service = JarvisDevService()
    return _service


class JarvisDevSkill(Skill):
    """Skill for /jarvis commands."""

    def intents(self):
        return [Intent.JARVIS]

    def name(self):
        return "jarvis_dev"

    async def handle(self, message: InboundMessage, context: SkillContext) -> OutboundMessage:
        user_id = str(message.user_id)

        # Auth check
        if user_id not in AUTHORIZED_USERS:
            return OutboundMessage(text="Unauthorized. Contact admin.")

        text = message.text or ""
        service = get_jarvis_dev_service()

        # Check for pending write
        if user_id in service.pending_writes:
            filepath = service.pending_writes.pop(user_id)
            result = service.write_file(filepath, text)
            if result["success"]:
                return OutboundMessage(text=f"Written {result['bytes']} bytes to {result['path']}")
            else:
                return OutboundMessage(text=f"Write failed: {result['error']}")

        # Parse command
        if not text.startswith("/jarvis"):
            return OutboundMessage(text="Use /jarvis <command>")

        parts = text[7:].strip().split(None, 1)
        if not parts:
            return OutboundMessage(text=self._help())

        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Route commands
        if cmd == "shell" or cmd == "sh":
            if not args:
                return OutboundMessage(text="Usage: /jarvis shell <command>")
            result = await service.execute_shell(args)
            return self._format_shell_result(result)

        elif cmd == "read" or cmd == "cat":
            if not args:
                return OutboundMessage(text="Usage: /jarvis read <path>")
            result = service.read_file(args)
            return self._format_read_result(result)

        elif cmd == "write":
            if not args:
                return OutboundMessage(text="Usage: /jarvis write <path>\nThen send content in next message")
            service.pending_writes[user_id] = args
            return OutboundMessage(text=f"Ready to write to {args}\nSend content now:")

        elif cmd == "git":
            if not args:
                return OutboundMessage(text="Usage: /jarvis git <git command>")
            result = await service.execute_shell(f"git {args}")
            return self._format_shell_result(result)

        elif cmd == "nodes":
            return OutboundMessage(text=service.list_nodes())

        elif cmd == "exec":
            exec_parts = args.split(None, 1)
            if len(exec_parts) < 2:
                return OutboundMessage(text="Usage: /jarvis exec <node> <command>")
            node, remote_cmd = exec_parts
            result = await service.execute_remote(node, remote_cmd)
            return self._format_shell_result(result, node)

        elif cmd == "help":
            return OutboundMessage(text=self._help())

        else:
            # Treat as shell command
            result = await service.execute_shell(text[7:].strip())
            return self._format_shell_result(result)

    def _format_shell_result(self, result: dict, node: str = None) -> OutboundMessage:
        if result.get("error"):
            return OutboundMessage(text=f"Error: {result['error']}")

        prefix = f"[{result.get('node', 'VPS')}] " if node or result.get('node') else ""
        output = result.get("stdout", "").strip()
        stderr = result.get("stderr", "").strip()

        if stderr:
            output = f"{output}\n\nSTDERR:\n{stderr}"

        if not output:
            output = "(no output)"

        status = "OK" if result["success"] else f"FAIL (exit {result.get('returncode', '?')})"
        return OutboundMessage(text=f"{prefix}{status}\n```\n{output}\n```")

    def _format_read_result(self, result: dict) -> OutboundMessage:
        if not result["success"]:
            return OutboundMessage(text=f"Error: {result['error']}")

        if result["type"] == "directory":
            files = "\n".join(result["contents"])
            return OutboundMessage(text=f"Directory contents:\n{files}")

        return OutboundMessage(text=f"{result['path']}:\n```\n{result['contents']}\n```")

    def _help(self) -> str:
        return """Jarvis Dev Commands:

/jarvis shell <cmd>   - Execute shell command
/jarvis read <path>   - Read file/directory
/jarvis write <path>  - Write file (send content next)
/jarvis git <cmd>     - Git operations
/jarvis nodes         - List Jarvis nodes
/jarvis exec <node> <cmd> - Run on remote node

Examples:
  /jarvis shell ls -la
  /jarvis read /opt/openclaw
  /jarvis git status
  /jarvis exec travel python --version
"""
