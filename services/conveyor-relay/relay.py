"""
Conveyor Relay — Public API for live conveyor control.

Thin FastAPI relay on the VPS that proxies commands to the conveyor-lab
backend on the PLC laptop and streams the webcam MJPEG feed.

Endpoints:
    POST /api/command   — Forward/reverse/stop/set_speed
    GET  /api/status    — Current conveyor state
    GET  /api/stream    — Proxied MJPEG webcam stream
    GET  /              — Embeddable HTML control page

Usage:
    CONVEYOR_BACKEND_URL=http://100.72.2.99:3001 \
    WEBCAM_URL=http://100.72.2.99:8081/stream \
    uvicorn relay:app --host 0.0.0.0 --port 8400
"""

import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("conveyor-relay")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONVEYOR_BACKEND_URL = os.getenv("CONVEYOR_BACKEND_URL", "http://100.72.2.99:3001")
WEBCAM_URL = os.getenv("WEBCAM_URL", "http://100.72.2.99:8081/stream")
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "3"))
PORT = int(os.getenv("PORT", "8400"))

STATIC_DIR = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------

_last_command: dict[str, float] = {}
_command_count: int = 0

VALID_ACTIONS = {"forward", "reverse", "stop", "set_speed"}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="FactoryLM Conveyor Relay", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CommandRequest(BaseModel):
    action: str = Field(..., description="forward | reverse | stop | set_speed")
    value: float | None = Field(None, description="Speed in Hz (0-60) for set_speed")


class CommandResponse(BaseModel):
    success: bool
    action: str
    status: dict | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    last = _last_command.get(ip, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _last_command[ip] = now
    return True


async def _proxy_command(action: str, value: float | None = None) -> dict:
    """Translate relay actions to conveyor-lab backend API calls."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        if action == "forward":
            # Set direction forward, set speed, then start
            await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "set_direction", "value": "forward"},
            )
            speed = value if value is not None else 30
            await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "set_speed", "value": speed},
            )
            resp = await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "start"},
            )
        elif action == "reverse":
            await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "set_direction", "value": "reverse"},
            )
            speed = value if value is not None else 30
            await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "set_speed", "value": speed},
            )
            resp = await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "start"},
            )
        elif action == "stop":
            resp = await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "stop"},
            )
        elif action == "set_speed":
            resp = await http.post(
                f"{CONVEYOR_BACKEND_URL}/api/command",
                json={"action": "set_speed", "value": value},
            )
        else:
            raise HTTPException(400, f"Unknown action: {action}")

        if resp.status_code != 200:
            raise HTTPException(502, f"Backend returned {resp.status_code}")
        return resp.json()


async def _proxy_status() -> dict:
    """Fetch current status from conveyor-lab backend."""
    async with httpx.AsyncClient(timeout=5.0) as http:
        try:
            resp = await http.get(f"{CONVEYOR_BACKEND_URL}/api/status")
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Backend returned {resp.status_code}"}
        except httpx.ConnectError:
            return {"runState": "offline", "error": "Backend unreachable"}
        except httpx.TimeoutException:
            return {"runState": "offline", "error": "Backend timeout"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def control_page():
    """Serve the embeddable HTML control page."""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "Control page not found")
    return FileResponse(index, media_type="text/html")


@app.post("/api/command", response_model=CommandResponse)
async def send_command(cmd: CommandRequest, request: Request):
    """Send a command to the conveyor. Rate-limited to 1 per 3 sec per IP."""
    global _command_count

    if cmd.action not in VALID_ACTIONS:
        raise HTTPException(400, f"Invalid action. Must be one of: {VALID_ACTIONS}")

    if cmd.action == "set_speed":
        if cmd.value is None:
            raise HTTPException(400, "value required for set_speed")
        if not 0 <= cmd.value <= 60:
            raise HTTPException(400, "Speed must be between 0 and 60 Hz")

    ip = _get_client_ip(request)
    if not _check_rate_limit(ip):
        raise HTTPException(429, f"Rate limited. Wait {RATE_LIMIT_SECONDS}s between commands.")

    try:
        result = await _proxy_command(cmd.action, cmd.value)
        _command_count += 1
        logger.info("Command #%d from %s: %s %s", _command_count, ip, cmd.action, cmd.value or "")
        return CommandResponse(
            success=True,
            action=cmd.action,
            status=result.get("status"),
            message=f"Command #{_command_count} executed",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error proxying command")
        raise HTTPException(502, f"Backend error: {str(e)[:100]}")


@app.get("/api/status")
async def get_status():
    """Get current conveyor status + relay stats."""
    status = await _proxy_status()
    status["commandCount"] = _command_count
    return status


@app.get("/api/stream")
async def stream_webcam():
    """Proxy the MJPEG stream from the PLC laptop webcam."""
    async def generate():
        async with httpx.AsyncClient(timeout=None) as http:
            try:
                async with http.stream("GET", WEBCAM_URL) as resp:
                    async for chunk in resp.aiter_bytes(chunk_size=4096):
                        yield chunk
            except httpx.ConnectError:
                logger.error("Cannot connect to webcam at %s", WEBCAM_URL)
            except Exception:
                logger.exception("Webcam stream error")

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/health")
async def health():
    """Health check for the relay itself."""
    return {
        "status": "ok",
        "service": "conveyor-relay",
        "commandCount": _command_count,
        "backendUrl": CONVEYOR_BACKEND_URL,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Conveyor Relay on port %d", PORT)
    logger.info("  Backend: %s", CONVEYOR_BACKEND_URL)
    logger.info("  Webcam:  %s", WEBCAM_URL)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
