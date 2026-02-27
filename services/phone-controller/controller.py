#!/usr/bin/env python3
"""
Phone Controller — HTTP API for dispatching Claude Code tasks from Mike's phone.

Stdlib only. No pip install. No FastAPI. No spinning.

Usage:
    export CONTROLLER_TOKEN=factorylm2026
    python3 controller.py

Endpoints:
    GET  /health       — JSON health status
    POST /run          — dispatch a task {"task": "...", "repo": "..."}
    GET  /status/<id>  — check task status
    GET  /tasks        — list recent tasks
"""

import json
import os
import platform
import subprocess
import sys
import threading
import time
import uuid
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("CONTROLLER_PORT", 9876))
TOKEN = os.environ.get("CONTROLLER_TOKEN", "")
MAX_TASKS = 20
START_TIME = time.time()

# Task store: OrderedDict keeps insertion order, we trim to MAX_TASKS
tasks: OrderedDict = OrderedDict()
tasks_lock = threading.Lock()


def get_health():
    """Gather system health info using stdlib only."""
    info = {
        "status": "ok",
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "port": PORT,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "active_tasks": sum(1 for t in tasks.values() if t["status"] == "running"),
        "total_tasks": len(tasks),
    }

    # CPU load (macOS / Linux)
    try:
        load = os.getloadavg()
        info["load_avg"] = {"1m": load[0], "5m": load[1], "15m": load[2]}
    except (OSError, AttributeError):
        info["load_avg"] = "unavailable"

    # Disk usage
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        info["disk"] = {
            "total_gb": round(total / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "used_pct": round((1 - free / total) * 100, 1),
        }
    except (OSError, AttributeError):
        info["disk"] = "unavailable"

    return info


def trim_tasks():
    """Keep only the most recent MAX_TASKS entries."""
    while len(tasks) > MAX_TASKS:
        tasks.popitem(last=False)


def run_task_in_background(task_id, task_cmd, repo_path):
    """Execute a task in a subprocess and store the result."""
    try:
        result = subprocess.run(
            task_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max
            cwd=repo_path,
        )
        with tasks_lock:
            tasks[task_id]["status"] = "completed" if result.returncode == 0 else "failed"
            tasks[task_id]["exit_code"] = result.returncode
            tasks[task_id]["stdout"] = result.stdout[-5000:] if result.stdout else ""
            tasks[task_id]["stderr"] = result.stderr[-2000:] if result.stderr else ""
            tasks[task_id]["finished_at"] = time.time()
    except subprocess.TimeoutExpired:
        with tasks_lock:
            tasks[task_id]["status"] = "timeout"
            tasks[task_id]["finished_at"] = time.time()
    except Exception as e:
        with tasks_lock:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["stderr"] = str(e)
            tasks[task_id]["finished_at"] = time.time()


class Handler(BaseHTTPRequestHandler):
    """Simple HTTP request handler — no frameworks, no magic."""

    def log_message(self, format, *args):
        """Override to add timestamp."""
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")

    def send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def check_auth(self):
        """Check bearer token. Returns True if authorized."""
        if not TOKEN:
            return True  # No token set = open access (dev mode)
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {TOKEN}":
            return True
        self.send_json(401, {"error": "unauthorized", "hint": "Set Authorization: Bearer <token>"})
        return False

    def parse_path(self):
        """Split path into segments."""
        path = self.path.strip("/")
        return path.split("/") if path else []

    # --- GET routes ---

    def do_GET(self):
        segments = self.parse_path()

        if not segments or segments[0] == "health":
            self.send_json(200, get_health())

        elif segments[0] == "tasks":
            with tasks_lock:
                task_list = [
                    {
                        "id": tid,
                        "task": t["task"][:100],
                        "status": t["status"],
                        "created_at": t["created_at"],
                        "finished_at": t.get("finished_at"),
                    }
                    for tid, t in reversed(list(tasks.items()))
                ]
            self.send_json(200, {"tasks": task_list})

        elif segments[0] == "status" and len(segments) > 1:
            task_id = segments[1]
            with tasks_lock:
                task = tasks.get(task_id)
            if task:
                self.send_json(200, task)
            else:
                self.send_json(404, {"error": "task not found", "id": task_id})

        else:
            self.send_json(404, {"error": "not found", "path": self.path})

    # --- POST routes ---

    def do_POST(self):
        segments = self.parse_path()

        if segments and segments[0] == "run":
            if not self.check_auth():
                return

            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_json(400, {"error": "empty body", "hint": "POST JSON with 'task' field"})
                return

            try:
                body = json.loads(self.rfile.read(content_length))
            except json.JSONDecodeError:
                self.send_json(400, {"error": "invalid JSON"})
                return

            task_text = body.get("task", "").strip()
            if not task_text:
                self.send_json(400, {"error": "missing 'task' field"})
                return

            repo = body.get("repo", os.path.expanduser("~/factorylm"))
            use_claude = body.get("claude", True)

            # Build command
            if use_claude:
                # Escape single quotes in task text for shell safety
                safe_task = task_text.replace("'", "'\\''")
                cmd = f"claude --print '{safe_task}'"
            else:
                cmd = task_text

            # Create task entry
            task_id = uuid.uuid4().hex[:8]
            with tasks_lock:
                tasks[task_id] = {
                    "id": task_id,
                    "task": task_text,
                    "command": cmd,
                    "repo": repo,
                    "status": "running",
                    "created_at": time.time(),
                    "finished_at": None,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": None,
                }
                trim_tasks()

            # Run in background thread
            thread = threading.Thread(
                target=run_task_in_background,
                args=(task_id, cmd, repo),
                daemon=True,
            )
            thread.start()

            self.send_json(202, {
                "id": task_id,
                "status": "running",
                "message": f"Task dispatched. Check GET /status/{task_id}",
            })

        else:
            self.send_json(404, {"error": "not found", "hint": "POST to /run"})

    # --- OPTIONS (CORS preflight) ---

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()


def main():
    if not TOKEN:
        print("⚠  WARNING: CONTROLLER_TOKEN not set — running without auth")
        print("   Set it: export CONTROLLER_TOKEN=factorylm2026")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Phone Controller listening on 0.0.0.0:{PORT}")
    print(f"Health: http://localhost:{PORT}/health")
    print(f"Auth: {'enabled' if TOKEN else 'DISABLED (no token)'}")
    print("---")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
