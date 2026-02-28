"""
FactoryLM Mission Control — Dev Monitoring Dashboard
=====================================================
Read-only dashboard showing all FactoryLM systems at a glance.
Designed for Tailnet access from phone/tablet/laptop.

Run: uvicorn app:app --host 0.0.0.0 --port 3000
"""

import asyncio
import os
import subprocess
import yaml
from pathlib import Path
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Mission Control", version="1.0.0")


# Ensure all JSON responses use UTF-8
@app.middleware("http")
async def utf8_json(request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response

def _ascii_safe(s: str) -> str:
    """Replace common Unicode chars with ASCII equivalents to avoid encoding issues."""
    return s.replace("\u2014", " -- ").replace("\u2013", " - ").replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NODES = [
    {"name": "VPS (Jarvis)", "ip": os.getenv("VPS_IP", "100.68.120.99"), "port": 8765},
    {"name": "Travel Laptop", "ip": os.getenv("TRAVEL_IP", "100.83.251.23"), "port": 8765},
    {"name": "PLC Laptop", "ip": os.getenv("PLC_IP", "100.72.2.99"), "port": 8765},
]

MATRIX_API = os.getenv("MATRIX_API", "http://100.72.2.99:8000")
OPENCLAW_URL = os.getenv("OPENCLAW_URL", "http://localhost:8340")
ANTFARM_DIR = os.getenv("ANTFARM_DIR", str(Path(__file__).parent.parent.parent / "antfarm" / "workflows"))

# Health monitor singleton
class HealthMonitor:
    _instance = None
    startup_time = datetime.now(timezone.utc)
    last_heartbeat = datetime.now(timezone.utc)
    guilds_count = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HealthMonitor, cls).__new__(cls)
        return cls._instance
    
    def update_heartbeat(self):
        self.last_heartbeat = datetime.now(timezone.utc)
    
    def update_guilds_count(self, count):
        self.guilds_count = count
    
    def get_uptime_seconds(self):
        return (datetime.now(timezone.utc) - self.startup_time).total_seconds()
    
    def get_uptime_human(self):
        seconds = self.get_uptime_seconds()
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        
        return ", ".join(parts)

health_monitor = HealthMonitor()

@app.get("/health")
async def health():
    """Enhanced health endpoint with uptime, guild count, and heartbeat tracking."""
    # Update heartbeat on each health check
    health_monitor.update_heartbeat()
    
    return {
        "status": "ok",
        "service": "mission-control-dashboard",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": health_monitor.get_uptime_seconds(),
        "uptime_human": health_monitor.get_uptime_human(),
        "guilds_count": health_monitor.guilds_count,
        "last_heartbeat": health_monitor.last_heartbeat.isoformat(),
        "version": "1.0.0"
    }

@app.post("/health/heartbeat")
async def update_heartbeat():
    """Update the heartbeat timestamp."""
    health_monitor.update_heartbeat()
    return {"status": "ok", "message": "Heartbeat updated", "timestamp": health_monitor.last_heartbeat.isoformat()}

@app.post("/health/guilds")
async def update_guilds_count(count: int):
    """Update the Discord guilds count."""
    health_monitor.update_guilds_count(count)
    return {"status": "ok", "message": f"Guilds count updated to {count}", "guilds_count": health_monitor.guilds_count}

@app.get("/api/nodes")
async def get_nodes():
    """Check health of all Tailnet nodes in parallel."""

    async def check_node(node):
        url = f"http://{node['ip']}:{node['port']}/health"
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(url)
                data = resp.json()
                return {
                    "name": node["name"],
                    "ip": node["ip"],
                    "status": "online",
                    "uptime": data.get("uptime", "?"),
                    "hostname": data.get("hostname", "?"),
                }
        except Exception:
            return {
                "name": node["name"],
                "ip": node["ip"],
                "status": "offline",
                "uptime": None,
                "hostname": None,
            }

    results = await asyncio.gather(*[check_node(n) for n in NODES])
    return results


@app.get("/api/tags")
async def get_tags():
    """Fetch latest PLC tags from Matrix API."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{MATRIX_API}/api/tags?limit=1")
            resp.raise_for_status()
            tags_list = resp.json()
            if tags_list:
                return tags_list[0] if isinstance(tags_list, list) else tags_list
            return {"error": "No tags available"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/workflows")
async def get_workflows():
    """List Antfarm workflows from disk."""
    workflows = []
    antfarm_path = Path(ANTFARM_DIR)
    if not antfarm_path.exists():
        return JSONResponse({"error": f"Antfarm directory not found: {ANTFARM_DIR}"})

    for wf_file in sorted(antfarm_path.glob("*/workflow.yml")):
        try:
            raw = wf_file.read_bytes().decode("utf-8")
            wf = yaml.safe_load(raw)
            workflows.append({
                "id": wf.get("id", wf_file.parent.name),
                "name": _ascii_safe(wf.get("name", wf_file.parent.name)),
                "description": _ascii_safe((wf.get("description") or "")[:120]),
                "agents": len(wf.get("agents", [])),
                "steps": len(wf.get("steps", [])),
            })
        except Exception as e:
            workflows.append({
                "id": wf_file.parent.name,
                "name": wf_file.parent.name,
                "description": f"Error reading: {e}",
                "agents": 0,
                "steps": 0,
            })
    return workflows


@app.get("/api/logs")
async def get_logs():
    """Fetch recent OpenClaw / Jarvis logs from systemd journal."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", "openclaw", "-n", "30", "--no-pager", "--output=short-iso"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [line for line in result.stdout.strip().split("\n") if line]
        return {"lines": lines, "count": len(lines)}
    except FileNotFoundError:
        return {"lines": ["(journalctl not available — not running on VPS)"], "count": 0}
    except Exception as e:
        return {"lines": [f"Error: {e}"], "count": 0}


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mission Control — FactoryLM</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            min-height: 100vh;
        }

        /* ---- Header ---- */
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 16px 24px;
            border-bottom: 2px solid #0f3460;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 20px; color: #00ff88; letter-spacing: 1px; }
        .header-right { display: flex; align-items: center; gap: 12px; }
        .header-time { color: #666; font-size: 13px; font-family: 'SF Mono', Monaco, monospace; }
        .pulse {
            width: 8px; height: 8px; border-radius: 50%; background: #00ff88;
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

        /* ---- Node Bar ---- */
        .node-bar {
            display: flex;
            gap: 12px;
            padding: 12px 24px;
            background: #0e0e16;
            border-bottom: 1px solid #1a1a2a;
            overflow-x: auto;
        }
        .node-card {
            flex: 1;
            min-width: 200px;
            background: #12121a;
            border: 1px solid #2a2a3a;
            border-radius: 10px;
            padding: 14px 18px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .node-dot {
            width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
        }
        .node-dot.online { background: #00ff88; box-shadow: 0 0 6px #00ff8866; }
        .node-dot.offline { background: #ff4444; box-shadow: 0 0 6px #ff444466; }
        .node-dot.checking { background: #888; animation: pulse 1s infinite; }
        .node-info { flex: 1; }
        .node-name { font-size: 13px; font-weight: 600; color: #fff; }
        .node-detail { font-size: 11px; color: #666; margin-top: 2px; }

        /* ---- Grid ---- */
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            padding: 16px 24px;
            max-width: 1600px;
            margin: 0 auto;
        }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }

        /* ---- Panels ---- */
        .panel {
            background: #12121a;
            border: 1px solid #2a2a3a;
            border-radius: 12px;
            overflow: hidden;
        }
        .panel-header {
            background: #1a1a2e;
            padding: 12px 18px;
            border-bottom: 1px solid #2a2a3a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-header h2 { font-size: 14px; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; }
        .panel-body { padding: 16px; }

        /* ---- Tags Grid ---- */
        .tag-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .tag-item {
            background: #1a1a2e;
            padding: 10px 14px;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .tag-name { color: #888; font-size: 12px; }
        .tag-value { font-weight: 600; font-size: 14px; }
        .tag-value.on { color: #00ff88; }
        .tag-value.off { color: #666; }
        .tag-value.warning { color: #ffaa00; }
        .tag-value.critical { color: #ff4444; }

        /* ---- Workflow List ---- */
        .wf-item {
            background: #1a1a2e;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .wf-name { font-size: 13px; font-weight: 600; color: #fff; }
        .wf-desc { font-size: 11px; color: #666; margin-top: 3px; }
        .wf-meta { text-align: right; flex-shrink: 0; }
        .wf-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            background: #00ff8820;
            color: #00ff88;
        }

        /* ---- Log Box ---- */
        .log-box {
            background: #0a0a0f;
            border-radius: 8px;
            padding: 14px;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            font-size: 11px;
            line-height: 1.7;
            max-height: 340px;
            overflow-y: auto;
            color: #aaa;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .log-line { padding: 1px 0; }
        .log-line:hover { background: #ffffff08; }

        /* ---- Status Badges ---- */
        .status-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }
        .status-ok { background: #00ff8820; color: #00ff88; }
        .status-warning { background: #ffaa0020; color: #ffaa00; }
        .status-error { background: #ff444420; color: #ff4444; }

        /* ---- Full-width panel ---- */
        .full-width {
            grid-column: 1 / -1;
        }

        /* ---- Footer ---- */
        .footer {
            text-align: center;
            padding: 16px;
            color: #333;
            font-size: 11px;
        }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <h1>MISSION CONTROL</h1>
        <div class="header-right">
            <span class="header-time" id="clock">--:--:--</span>
            <div class="pulse"></div>
        </div>
    </div>

    <!-- Node Health Bar -->
    <div class="node-bar" id="nodeBar">
        <div class="node-card">
            <div class="node-dot checking"></div>
            <div class="node-info">
                <div class="node-name">Checking nodes...</div>
            </div>
        </div>
    </div>

    <!-- Main Grid -->
    <div class="grid">
        <!-- PLC Live Tags -->
        <div class="panel">
            <div class="panel-header">
                <h2>PLC Live Tags</h2>
                <span id="tagStatus" class="status-badge status-ok">--</span>
            </div>
            <div class="panel-body">
                <div class="tag-grid" id="tagGrid">
                    <div class="tag-item"><span class="tag-name">Connecting...</span></div>
                </div>
            </div>
        </div>

        <!-- Antfarm Workflows -->
        <div class="panel">
            <div class="panel-header">
                <h2>Antfarm Workflows</h2>
                <span id="wfCount" class="status-badge status-ok">--</span>
            </div>
            <div class="panel-body" id="wfList">
                <div class="wf-item"><div class="wf-name">Loading...</div></div>
            </div>
        </div>

        <!-- Jarvis / OpenClaw Logs -->
        <div class="panel full-width">
            <div class="panel-header">
                <h2>Jarvis / OpenClaw Logs</h2>
                <span id="logCount" class="status-badge status-ok">--</span>
            </div>
            <div class="panel-body">
                <div class="log-box" id="logBox">Fetching logs...</div>
            </div>
        </div>
    </div>

    <div class="footer">
        FactoryLM Mission Control | Tailnet-only | Read-only
    </div>

    <script>
        // ---- Clock ----
        function updateClock() {
            document.getElementById('clock').textContent = new Date().toLocaleTimeString();
        }
        setInterval(updateClock, 1000);
        updateClock();

        // ---- Node Health ----
        async function fetchNodes() {
            try {
                const resp = await fetch('/api/nodes');
                const nodes = await resp.json();
                const bar = document.getElementById('nodeBar');
                bar.innerHTML = '';
                for (const node of nodes) {
                    const card = document.createElement('div');
                    card.className = 'node-card';
                    const detail = node.status === 'online'
                        ? `${node.ip} | up ${node.uptime || '?'}`
                        : `${node.ip} | unreachable`;
                    card.innerHTML = `
                        <div class="node-dot ${node.status}"></div>
                        <div class="node-info">
                            <div class="node-name">${node.name}</div>
                            <div class="node-detail">${detail}</div>
                        </div>
                    `;
                    bar.appendChild(card);
                }
            } catch (err) {
                console.error('Node fetch error:', err);
            }
        }

        // ---- PLC Tags ----
        const tagConfig = {
            motor_running: { label: 'Motor', type: 'bool' },
            motor_speed: { label: 'Motor Speed', type: 'percent' },
            motor_current: { label: 'Motor Current', type: 'amps' },
            temperature: { label: 'Temperature', type: 'temp', warn: 65, crit: 80 },
            pressure: { label: 'Pressure', type: 'psi', warn: 70, crit: 60 },
            conveyor_running: { label: 'Conveyor', type: 'bool' },
            conveyor_speed: { label: 'Conv. Speed', type: 'percent' },
            sensor_1: { label: 'Sensor 1', type: 'bool' },
            sensor_2: { label: 'Sensor 2', type: 'bool' },
            fault_alarm: { label: 'Fault Alarm', type: 'alarm' },
            e_stop: { label: 'E-Stop', type: 'estop' },
            error_code: { label: 'Error Code', type: 'int' }
        };

        function formatTagValue(key, value, config) {
            if (!config) return { text: String(value), cls: '' };
            switch (config.type) {
                case 'bool':
                    return { text: value ? 'RUNNING' : 'STOPPED', cls: value ? 'on' : 'off' };
                case 'percent':
                    return { text: value + '%', cls: '' };
                case 'amps':
                    return { text: parseFloat(value).toFixed(2) + ' A', cls: value > 5 ? 'critical' : '' };
                case 'temp':
                    let tc = '';
                    if (value > config.crit) tc = 'critical';
                    else if (value > config.warn) tc = 'warning';
                    return { text: parseFloat(value).toFixed(1) + ' C', cls: tc };
                case 'psi':
                    let pc = '';
                    if (value < config.crit) pc = 'critical';
                    else if (value < config.warn) pc = 'warning';
                    return { text: value + ' PSI', cls: pc };
                case 'alarm':
                    return { text: value ? 'ACTIVE' : 'Clear', cls: value ? 'critical' : 'on' };
                case 'estop':
                    return { text: value ? 'PRESSED' : 'Clear', cls: value ? 'critical' : 'on' };
                case 'int':
                    return { text: value || 'None', cls: value ? 'warning' : '' };
                default:
                    return { text: String(value), cls: '' };
            }
        }

        async function fetchTags() {
            try {
                const resp = await fetch('/api/tags');
                const tags = await resp.json();
                const badge = document.getElementById('tagStatus');

                if (tags.error) {
                    badge.textContent = 'OFFLINE';
                    badge.className = 'status-badge status-error';
                    document.getElementById('tagGrid').innerHTML =
                        '<div class="tag-item"><span class="tag-name" style="color:#ff4444;">PLC unreachable</span></div>';
                    return;
                }

                badge.textContent = 'LIVE';
                badge.className = 'status-badge status-ok';

                const grid = document.getElementById('tagGrid');
                grid.innerHTML = '';
                for (const [key, config] of Object.entries(tagConfig)) {
                    const value = tags[key];
                    if (value === undefined) continue;
                    const fmt = formatTagValue(key, value, config);
                    const item = document.createElement('div');
                    item.className = 'tag-item';
                    item.innerHTML = `
                        <span class="tag-name">${config.label}</span>
                        <span class="tag-value ${fmt.cls}">${fmt.text}</span>
                    `;
                    grid.appendChild(item);
                }
            } catch (err) {
                console.error('Tag fetch error:', err);
            }
        }

        // ---- Antfarm Workflows ----
        async function fetchWorkflows() {
            try {
                const resp = await fetch('/api/workflows');
                const workflows = await resp.json();
                const container = document.getElementById('wfList');
                const badge = document.getElementById('wfCount');

                if (workflows.error) {
                    container.innerHTML = `<div class="wf-item"><div class="wf-name" style="color:#ff4444;">${workflows.error}</div></div>`;
                    badge.textContent = '?';
                    badge.className = 'status-badge status-error';
                    return;
                }

                badge.textContent = workflows.length + ' workflows';
                badge.className = 'status-badge status-ok';

                container.innerHTML = '';
                for (const wf of workflows) {
                    const item = document.createElement('div');
                    item.className = 'wf-item';
                    item.innerHTML = `
                        <div>
                            <div class="wf-name">${wf.name}</div>
                            <div class="wf-desc">${wf.description}</div>
                        </div>
                        <div class="wf-meta">
                            <div class="wf-badge">${wf.agents} agents / ${wf.steps} steps</div>
                        </div>
                    `;
                    container.appendChild(item);
                }
            } catch (err) {
                console.error('Workflow fetch error:', err);
            }
        }

        // ---- Logs ----
        async function fetchLogs() {
            try {
                const resp = await fetch('/api/logs');
                const data = await resp.json();
                const box = document.getElementById('logBox');
                const badge = document.getElementById('logCount');

                badge.textContent = data.count + ' lines';
                badge.className = 'status-badge status-ok';

                box.innerHTML = '';
                for (const line of data.lines) {
                    const div = document.createElement('div');
                    div.className = 'log-line';
                    div.textContent = line;
                    box.appendChild(div);
                }
                box.scrollTop = box.scrollHeight;
            } catch (err) {
                console.error('Log fetch error:', err);
            }
        }

        // ---- Boot ----
        fetchNodes();
        fetchTags();
        fetchWorkflows();
        fetchLogs();

        // ---- Polling ----
        setInterval(fetchNodes, 5000);
        setInterval(fetchTags, 2000);
        setInterval(fetchLogs, 10000);
        // Workflows don't change often — refresh once per minute
        setInterval(fetchWorkflows, 60000);
    </script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("Mission Control starting on http://0.0.0.0:3000")
    uvicorn.run(app, host="0.0.0.0", port=3000)
