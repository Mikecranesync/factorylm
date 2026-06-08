"""
Jarvis Node - FastAPI MCP Server
================================
A FastAPI server running on the laptop that provides:
- Shell command execution
- Screenshot capture
- File operations
- System info
- Notifications
- Message queue for Jarvis <-> Claude Code communication

Run with: uvicorn jarvis_node:app --host 0.0.0.0 --port 8765
"""

import os
import sys
import secrets
import base64
import socket
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from collections import deque

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Optional imports with fallbacks
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import mss
    import mss.tools
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

# Configuration
MACHINE_NAME = os.getenv("JARVIS_MACHINE_NAME", socket.gethostname())
PORT = int(os.getenv("JARVIS_PORT", "8765"))

# Bearer token guarding every endpoint. Only "/health" stays public so uptime
# probes work on an unconfigured node; everything else (including "/", which would
# otherwise leak the machine name + endpoint list) requires the token.
# Fail-closed: if JARVIS_TOKEN is unset, protected endpoints return 503 rather than
# running wide open. Provisioned in Doppler factorylm/prd; injected by run-node.sh.
JARVIS_TOKEN = os.getenv("JARVIS_TOKEN", "")
PUBLIC_PATHS = {"/health"}
WORKSPACE = Path(os.getenv("JARVIS_WORKSPACE", Path.home() / "jarvis-workspace"))

# Ensure workspace exists
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Message queue for Jarvis <-> Claude Code
message_queue: Dict[str, deque] = {
    "jarvis": deque(maxlen=100),
    "claude-code": deque(maxlen=100),
}

# ============================================================================
# Pydantic Models
# ============================================================================

class ShellRequest(BaseModel):
    command: str
    timeout: int = 30
    cwd: Optional[str] = None

class ShellResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int

class FileReadRequest(BaseModel):
    path: str

class FileWriteRequest(BaseModel):
    path: str
    content: str

class NotifyRequest(BaseModel):
    title: str = "Jarvis"
    message: str
    type: str = "toast"  # toast, alert, fullscreen

class MessageRequest(BaseModel):
    sender: str  # "jarvis" or "claude-code"
    recipient: str  # "jarvis" or "claude-code"
    content: str
    metadata: Optional[Dict[str, Any]] = None

class Message(BaseModel):
    sender: str
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Jarvis Node",
    description="FastAPI MCP Server for remote laptop control",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_bearer_token(request: Request, call_next):
    """Bearer-token gate. Every path except PUBLIC_PATHS (and CORS preflight)
    requires `Authorization: Bearer <JARVIS_TOKEN>`. Fail-closed when unset."""
    if request.method != "OPTIONS" and request.url.path not in PUBLIC_PATHS:
        if not JARVIS_TOKEN:
            return JSONResponse(
                {"detail": "JARVIS_TOKEN not configured on this node"}, status_code=503
            )
        provided = request.headers.get("authorization", "")
        if not secrets.compare_digest(provided, f"Bearer {JARVIS_TOKEN}"):
            return JSONResponse(
                {"detail": "missing or invalid bearer token"}, status_code=401
            )
    return await call_next(request)

# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "jarvis-node",
        "machine": MACHINE_NAME,
        "version": "1.0.0",
        "endpoints": ["/health", "/shell", "/screenshot", "/files", "/notify", "/messages", "/system-info", "/processes"]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "machine": MACHINE_NAME,
        "timestamp": datetime.now().isoformat(),
        "capabilities": {
            "shell": True,
            "screenshot": HAS_MSS,
            "files": True,
            "notify": True,
            "messages": True,
            "system_info": HAS_PSUTIL,
            "processes": HAS_PSUTIL,
        }
    }

@app.get("/system-info")
async def system_info():
    info = {
        "hostname": socket.gethostname(),
        "machine_name": MACHINE_NAME,
        "platform": sys.platform,
        "python_version": sys.version,
    }

    if HAS_PSUTIL:
        info.update({
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "memory_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
            "disk_free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
            "disk_percent": psutil.disk_usage('/').percent,
        })

    return info

@app.get("/processes")
async def get_processes(top: int = Query(default=10, le=50)):
    if not HAS_PSUTIL:
        raise HTTPException(500, "psutil not installed")

    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
        try:
            pinfo = proc.info
            processes.append({
                "pid": pinfo['pid'],
                "name": pinfo['name'],
                "memory_mb": round(pinfo['memory_info'].rss / (1024**2), 1) if pinfo['memory_info'] else 0,
                "cpu_percent": pinfo['cpu_percent'] or 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Sort by memory usage
    processes.sort(key=lambda x: x['memory_mb'], reverse=True)
    return processes[:top]

# ============================================================================
# Shell Execution
# ============================================================================

@app.post("/shell", response_model=ShellResponse)
async def execute_shell(request: ShellRequest):
    """Execute a shell command and return the result"""
    start_time = datetime.now()

    try:
        # Use PowerShell on Windows, bash on Unix
        if sys.platform == "win32":
            shell_cmd = ["powershell", "-Command", request.command]
        else:
            shell_cmd = ["bash", "-c", request.command]

        result = subprocess.run(
            shell_cmd,
            capture_output=True,
            text=True,
            timeout=request.timeout,
            cwd=request.cwd,
        )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return ShellResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            duration_ms=duration_ms
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(408, f"Command timed out after {request.timeout}s")
    except Exception as e:
        raise HTTPException(500, str(e))

# ============================================================================
# Screenshot
# ============================================================================

@app.get("/screenshot")
async def take_screenshot(monitor: int = Query(default=0)):
    """Capture a screenshot and return as base64"""
    if not HAS_MSS:
        raise HTTPException(500, "mss not installed - run: pip install mss")

    try:
        with mss.mss() as sct:
            # Get monitor (0 = all monitors, 1+ = specific monitor)
            if monitor >= len(sct.monitors):
                monitor = 0

            screenshot = sct.grab(sct.monitors[monitor])

            # Convert to PNG bytes
            png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)

            # Encode as base64
            image_base64 = base64.b64encode(png_bytes).decode('utf-8')

            return {
                "image_base64": image_base64,
                "size": [screenshot.width, screenshot.height],
                "monitor": monitor,
                "format": "png"
            }

    except Exception as e:
        raise HTTPException(500, f"Screenshot failed: {str(e)}")

# ============================================================================
# File Operations
# ============================================================================

@app.post("/files/read")
async def read_file(request: FileReadRequest):
    """Read a file and return its contents"""
    path = Path(request.path)

    if not path.exists():
        raise HTTPException(404, f"File not found: {request.path}")

    if not path.is_file():
        raise HTTPException(400, f"Not a file: {request.path}")

    try:
        content = path.read_text(encoding='utf-8')
        return {
            "path": str(path),
            "content": content,
            "size": path.stat().st_size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        }
    except UnicodeDecodeError:
        # Try reading as binary and base64 encode
        content = base64.b64encode(path.read_bytes()).decode('utf-8')
        return {
            "path": str(path),
            "content_base64": content,
            "size": path.stat().st_size,
            "encoding": "base64"
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/files/write")
async def write_file(request: FileWriteRequest):
    """Write content to a file"""
    path = Path(request.path)

    try:
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(request.content, encoding='utf-8')

        return {
            "success": True,
            "path": str(path),
            "size": path.stat().st_size
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/files/list")
async def list_files(path: str = Query(default=".")):
    """List files in a directory"""
    dir_path = Path(path)

    if not dir_path.exists():
        raise HTTPException(404, f"Directory not found: {path}")

    if not dir_path.is_dir():
        raise HTTPException(400, f"Not a directory: {path}")

    files = []
    for item in dir_path.iterdir():
        try:
            files.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            })
        except PermissionError:
            files.append({"name": item.name, "type": "unknown", "error": "permission denied"})

    return {"path": str(dir_path), "files": files}

# ============================================================================
# Notifications
# ============================================================================

@app.post("/notify")
async def send_notification(request: NotifyRequest):
    """Send a notification to the desktop"""

    if sys.platform == "win32":
        if request.type == "toast":
            # Use PowerShell for toast notification
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastText02">
                        <text id="1">{request.title}</text>
                        <text id="2">{request.message}</text>
                    </binding>
                </visual>
            </toast>
"@
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Jarvis").Show($toast)
            '''

            try:
                subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)
                return {"success": True, "type": "toast"}
            except Exception as e:
                # Fallback to scheduled task alert
                pass

        if request.type in ["alert", "fullscreen"]:
            # Use the existing JarvisAlert scheduled task if available
            try:
                subprocess.run(["schtasks", "/run", "/tn", "JarvisAlert"], capture_output=True, timeout=5)
                return {"success": True, "type": "alert"}
            except:
                pass

        # Final fallback: msg command
        try:
            subprocess.run(["msg", "*", f"{request.title}: {request.message}"], capture_output=True, timeout=5)
            return {"success": True, "type": "msg"}
        except:
            return {"success": False, "error": "No notification method available"}

    else:
        # Linux/Mac - try notify-send
        try:
            subprocess.run(["notify-send", request.title, request.message], timeout=5)
            return {"success": True, "type": "notify-send"}
        except:
            return {"success": False, "error": "notify-send not available"}

# ============================================================================
# Message Queue (Jarvis <-> Claude Code)
# ============================================================================

@app.post("/messages")
async def send_message(request: MessageRequest):
    """Send a message to the queue"""
    if request.recipient not in message_queue:
        raise HTTPException(400, f"Unknown recipient: {request.recipient}")

    message = Message(
        sender=request.sender,
        content=request.content,
        timestamp=datetime.now().isoformat(),
        metadata=request.metadata
    )

    message_queue[request.recipient].append(message.dict())

    return {"success": True, "queued_for": request.recipient}

@app.get("/messages")
async def get_messages(recipient: str = Query(..., alias="for")):
    """Get messages for a recipient"""
    if recipient not in message_queue:
        raise HTTPException(400, f"Unknown recipient: {recipient}")

    messages = list(message_queue[recipient])
    message_queue[recipient].clear()

    return {"recipient": recipient, "messages": messages, "count": len(messages)}

@app.get("/messages/peek")
async def peek_messages(recipient: str = Query(..., alias="for")):
    """Peek at messages without clearing the queue"""
    if recipient not in message_queue:
        raise HTTPException(400, f"Unknown recipient: {recipient}")

    messages = list(message_queue[recipient])
    return {"recipient": recipient, "messages": messages, "count": len(messages)}

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Jarvis Node on {MACHINE_NAME}:{PORT}")
    print(f"Workspace: {WORKSPACE}")
    print(f"Capabilities: psutil={HAS_PSUTIL}, mss={HAS_MSS}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
