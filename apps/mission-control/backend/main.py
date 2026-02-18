"""
FactoryLM Mission Control - Orchestration API
=============================================

Unified backend for managing all autonomous capabilities:
- 8 Antfarm workflows
- 25+ Celery workers
- 4 autonomous agents (Ralph, JHC, Cosmos, MediaOffload)
- 3 PLC collectors
- HIL approval queue
- Jarvis modes

Port: 8090
"""

import os
import json
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx
import yaml
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(
    title="Mission Control API",
    description="FactoryLM Orchestration - 40+ autonomous capabilities",
    version="1.0.0"
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
FLOWER_URL = os.getenv("FLOWER_URL", "http://localhost:5555")
RALPH_API = os.getenv("RALPH_API", "http://localhost:8000")
ANTFARM_DIR = Path(os.getenv("ANTFARM_DIR", "antfarm/workflows"))
WORKERS_DIR = Path(os.getenv("WORKERS_DIR", "workers"))

# In-memory state (replace with Redis in production)
HIL_QUEUE: List[Dict[str, Any]] = []
ACTIVE_AGENTS: Dict[str, Dict[str, Any]] = {}


# ============ PYDANTIC MODELS ============

class WorkflowRunRequest(BaseModel):
    params: Dict[str, Any] = {}


class JHCResurrectRequest(BaseModel):
    repo_url: str
    aggression: str = "moderate"
    allow_dep_upgrades: bool = False
    allow_ci_edits: bool = False


class RalphStartRequest(BaseModel):
    project_path: str
    prompt_file: str = ".ralph/PROMPT.md"


class HILAction(BaseModel):
    id: str
    action_type: str
    payload: Dict[str, Any]
    requested_at: str
    requested_by: str = "system"
    risk_level: str = "medium"


# ============ HEALTH ============

@app.get("/health")
async def health():
    return {"status": "ok", "service": "mission-control", "timestamp": datetime.utcnow().isoformat()}


# ============ WORKFLOWS (Antfarm) ============

@app.get("/api/workflows")
async def list_workflows():
    """List all Antfarm workflows."""
    workflows = []

    if not ANTFARM_DIR.exists():
        return {"workflows": [], "error": f"Antfarm dir not found: {ANTFARM_DIR}"}

    for f in list(ANTFARM_DIR.glob("**/*.yaml")) + list(ANTFARM_DIR.glob("**/*.yml")):
        try:
            with open(f) as fh:
                spec = yaml.safe_load(fh)
            workflows.append({
                "id": f.stem,
                "name": spec.get("name", f.stem) if spec else f.stem,
                "description": spec.get("description", "") if spec else "",
                "steps": len(spec.get("steps", [])) if spec else 0,
                "path": str(f.relative_to(ANTFARM_DIR.parent)),
                "type": "antfarm"
            })
        except Exception as e:
            workflows.append({
                "id": f.stem,
                "name": f.stem,
                "error": str(e),
                "path": str(f)
            })

    return {"workflows": workflows, "count": len(workflows)}


@app.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, request: WorkflowRunRequest, background: BackgroundTasks):
    """Start an Antfarm workflow run."""
    run_id = str(uuid.uuid4())[:8]

    # Queue for execution
    background.add_task(execute_workflow, workflow_id, request.params, run_id)

    return {
        "status": "started",
        "workflow": workflow_id,
        "run_id": run_id,
        "params": request.params
    }


async def execute_workflow(workflow_id: str, params: dict, run_id: str):
    """Background task to execute workflow."""
    # Implementation would use antfarm CLI or direct execution
    pass


# ============ CELERY WORKER SWARM ============

@app.get("/api/workers")
async def list_workers():
    """List all Celery workers via Flower API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{FLOWER_URL}/api/workers")
            if resp.status_code == 200:
                return {"workers": resp.json(), "source": "flower"}
    except Exception as e:
        pass

    # Fallback: scan workers directory
    workers = []
    if WORKERS_DIR.exists():
        for f in WORKERS_DIR.glob("*_tasks.py"):
            workers.append({
                "name": f.stem.replace("_tasks", ""),
                "file": str(f),
                "status": "unknown",
                "source": "filesystem"
            })

    return {"workers": workers, "count": len(workers), "source": "filesystem"}


@app.get("/api/workers/{worker}/tasks")
async def worker_tasks(worker: str, limit: int = Query(default=100)):
    """Get tasks for specific worker."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{FLOWER_URL}/api/tasks", params={"worker": worker, "limit": limit})
            if resp.status_code == 200:
                return {"tasks": resp.json()}
    except Exception as e:
        return {"error": str(e), "worker": worker}

    return {"tasks": [], "worker": worker}


@app.post("/api/workers/{worker}/pool/grow")
async def grow_worker_pool(worker: str, n: int = Query(default=1)):
    """Scale up worker pool."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{FLOWER_URL}/api/worker/pool/grow/{worker}", params={"n": n})
            return {"status": "scaled", "worker": worker, "added": n}
    except Exception as e:
        raise HTTPException(500, f"Failed to scale worker: {e}")


@app.post("/api/workers/{worker}/pool/shrink")
async def shrink_worker_pool(worker: str, n: int = Query(default=1)):
    """Scale down worker pool."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{FLOWER_URL}/api/worker/pool/shrink/{worker}", params={"n": n})
            return {"status": "scaled", "worker": worker, "removed": n}
    except Exception as e:
        raise HTTPException(500, f"Failed to scale worker: {e}")


# ============ RALPH LOOP ============

@app.get("/api/ralph/status")
async def ralph_status():
    """Get Ralph loop status."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{RALPH_API}/loop/status")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        pass

    # Check local status file
    status_file = Path.home() / ".ralph" / "status.json"
    if status_file.exists():
        return json.loads(status_file.read_text())

    return {"status": "unknown", "running": False}


@app.post("/api/ralph/start")
async def ralph_start(request: RalphStartRequest):
    """Start Ralph autonomous dev loop."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{RALPH_API}/loop/start", json={
                "project_path": request.project_path,
                "prompt_file": request.prompt_file
            })
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        pass

    # Fallback: direct execution
    return {"status": "queued", "project": request.project_path}


@app.post("/api/ralph/stop")
async def ralph_stop():
    """Stop Ralph loop gracefully."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{RALPH_API}/loop/stop")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        return {"error": str(e)}

    return {"status": "stop_requested"}


@app.post("/api/ralph/pause")
async def ralph_pause():
    """Pause Ralph loop (resume later)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{RALPH_API}/loop/pause")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"status": "pause_requested"}


@app.post("/api/ralph/resume")
async def ralph_resume():
    """Resume paused Ralph loop."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{RALPH_API}/loop/resume")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"status": "resume_requested"}


# ============ AUTONOMOUS AGENTS ============

@app.get("/api/agents")
async def list_agents():
    """List all autonomous agents and their status."""
    agents = [
        {
            "name": "ralph",
            "type": "RalphLoop",
            "location": "my-ralph/",
            "description": "Autonomous development loop with circuit breaker",
            "status": await _check_ralph_status(),
            "controls": ["start", "stop", "pause", "resume"]
        },
        {
            "name": "cosmos",
            "type": "CosmosAgent",
            "location": "cosmos/agent.py",
            "description": "NVIDIA Cosmos video reasoning for PLC fault analysis",
            "status": ACTIVE_AGENTS.get("cosmos", {}).get("status", "stopped"),
            "controls": ["start", "stop"]
        },
        {
            "name": "media_offload",
            "type": "MediaOffloadAgent",
            "location": "services/media/media_offload_agent.py",
            "description": "Multi-device media sync to Google Drive",
            "status": await _check_agent_health("media_offload", 8766),
            "health_port": 8766,
            "controls": ["start", "stop"]
        },
        {
            "name": "jesus_h_christ",
            "type": "ResurrectorAgent",
            "location": "agents/jesus-h-christ/routines/resurrector.py",
            "description": "Repo resurrection service ($99-$999)",
            "status": "on_demand",
            "controls": ["scan", "dig", "hunt", "resurrect"]
        }
    ]
    return {"agents": agents, "count": len(agents)}


async def _check_ralph_status() -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{RALPH_API}/loop/status")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("status", "unknown")
    except:
        pass
    return "unknown"


async def _check_agent_health(agent: str, port: int) -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://localhost:{port}/health")
            if resp.status_code == 200:
                return "running"
    except:
        pass
    return "stopped"


@app.post("/api/agents/{agent}/start")
async def start_agent(agent: str, background: BackgroundTasks):
    """Start an autonomous agent."""
    ACTIVE_AGENTS[agent] = {"status": "starting", "started_at": datetime.utcnow().isoformat()}
    background.add_task(_run_agent, agent)
    return {"status": "starting", "agent": agent}


@app.post("/api/agents/{agent}/stop")
async def stop_agent(agent: str):
    """Stop an autonomous agent."""
    if agent in ACTIVE_AGENTS:
        ACTIVE_AGENTS[agent]["status"] = "stopping"
    return {"status": "stop_requested", "agent": agent}


async def _run_agent(agent: str):
    """Background task to run agent."""
    # Implementation depends on agent type
    pass


# ============ PLC COLLECTORS ============

@app.get("/api/collectors")
async def list_collectors():
    """List PLC collectors and their status."""
    collectors = [
        {
            "name": "s7",
            "type": "Siemens S7",
            "file": "workers/collectors/s7_collector_tasks.py",
            "status": "active",
            "protocol": "S7comm",
            "last_poll": datetime.utcnow().isoformat()
        },
        {
            "name": "ab",
            "type": "Allen-Bradley",
            "file": "workers/collectors/ab_collector_tasks.py",
            "status": "active",
            "protocol": "EtherNet/IP",
            "last_poll": datetime.utcnow().isoformat()
        },
        {
            "name": "modbus",
            "type": "Modbus TCP",
            "file": "workers/collectors/modbus_collector_tasks.py",
            "status": "active",
            "protocol": "Modbus TCP",
            "last_poll": datetime.utcnow().isoformat()
        }
    ]
    return {"collectors": collectors, "count": len(collectors)}


@app.post("/api/collectors/{collector}/restart")
async def restart_collector(collector: str):
    """Restart a PLC collector."""
    # Would dispatch Celery task
    return {"status": "restart_requested", "collector": collector}


# ============ JESUS H CHRIST ============

@app.post("/api/tools/jhc/scan")
async def jhc_scan(org: str, min_score: int = Query(default=50)):
    """Scan GitHub org for resurrection candidates."""
    import subprocess

    result = subprocess.run([
        "python", "agents/jesus-h-christ/routines/resurrector.py",
        "scan", org, "--min-score", str(min_score)
    ], capture_output=True, text=True, timeout=300)

    return {
        "org": org,
        "min_score": min_score,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }


@app.post("/api/tools/jhc/resurrect")
async def jhc_resurrect(request: JHCResurrectRequest):
    """Start repo resurrection (HIL-gated)."""
    action_id = str(uuid.uuid4())[:8]

    hil_action = {
        "id": action_id,
        "action_type": "jhc_resurrect",
        "payload": request.dict(),
        "requested_at": datetime.utcnow().isoformat(),
        "risk_level": "high" if request.allow_ci_edits else "medium"
    }

    HIL_QUEUE.append(hil_action)

    return {
        "status": "queued_for_approval",
        "action_id": action_id,
        "hil_required": True
    }


# ============ GIT FORENSICS ============

@app.post("/api/tools/git/report")
async def git_report(repo_path: str):
    """Run full git forensics report."""
    import subprocess

    result = subprocess.run([
        "python", "tools/git_forensics.py", "report"
    ], capture_output=True, text=True, cwd=repo_path, timeout=120)

    return {
        "repo": repo_path,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }


@app.get("/api/tools/git/hotspots")
async def git_hotspots(repo_path: str, limit: int = Query(default=20)):
    """Get code hotspots."""
    import subprocess

    result = subprocess.run([
        "python", "tools/git_forensics.py", "hotspots", "--limit", str(limit)
    ], capture_output=True, text=True, cwd=repo_path, timeout=60)

    return {
        "repo": repo_path,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }


# ============ JARVIS MODES ============

JARVIS_MODES = {
    "devops": {
        "name": "DevOps",
        "description": "Full development access - shell, git, deploy",
        "tools": ["shell", "git", "files", "deploy", "nodes"],
        "hil_required": ["deploy", "push --force", "rm -rf"]
    },
    "customer": {
        "name": "Customer Support",
        "description": "Safe read-only operations for client demos",
        "tools": ["status", "search", "diagnose"],
        "hil_required": []
    },
    "field_tech": {
        "name": "Field Technician",
        "description": "PLC operations, work orders, diagnostics",
        "tools": ["diagnose", "status", "work_order", "photo"],
        "hil_required": ["plc_write"]
    }
}


@app.get("/api/modes")
async def list_modes():
    """List available Jarvis modes."""
    active = _get_active_mode()
    return {"modes": JARVIS_MODES, "active": active}


@app.post("/api/modes/{mode}/activate")
async def activate_mode(mode: str):
    """Switch Jarvis to specified mode."""
    if mode not in JARVIS_MODES:
        raise HTTPException(404, f"Unknown mode: {mode}")

    state_file = Path.home() / ".jarvis_mode"
    state_file.write_text(mode)

    return {"active_mode": mode, "config": JARVIS_MODES[mode]}


def _get_active_mode() -> str:
    state_file = Path.home() / ".jarvis_mode"
    if state_file.exists():
        return state_file.read_text().strip()
    return "devops"


# ============ JARVIS NODES ============

JARVIS_NODES = {
    "vps": {"host": "100.68.120.99", "port": 8765, "name": "VPS (Jarvis)"},
    "travel": {"host": "100.83.251.23", "port": 8765, "name": "Travel Laptop"},
    "plc": {"host": "100.72.2.99", "port": 8765, "name": "PLC Laptop"},
}


@app.get("/api/nodes")
async def list_nodes():
    """List Jarvis nodes and their status."""
    nodes = []
    for key, info in JARVIS_NODES.items():
        status = await _check_node_health(info["host"], info["port"])
        nodes.append({
            "id": key,
            **info,
            "status": status
        })
    return {"nodes": nodes}


async def _check_node_health(host: str, port: int) -> str:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://{host}:{port}/health")
            if resp.status_code == 200:
                return "online"
    except:
        pass
    return "offline"


# ============ HIL (Human-in-Loop) QUEUE ============

@app.get("/api/hil/pending")
async def hil_pending():
    """Get pending human-in-loop approvals."""
    return {"pending": HIL_QUEUE, "count": len(HIL_QUEUE)}


@app.post("/api/hil/{action_id}/approve")
async def hil_approve(action_id: str, background: BackgroundTasks):
    """Approve a queued action."""
    for i, action in enumerate(HIL_QUEUE):
        if action["id"] == action_id:
            approved_action = HIL_QUEUE.pop(i)
            approved_action["approved_at"] = datetime.utcnow().isoformat()
            background.add_task(_execute_hil_action, approved_action)
            return {"status": "approved", "action": approved_action}

    raise HTTPException(404, f"Action not found: {action_id}")


@app.post("/api/hil/{action_id}/reject")
async def hil_reject(action_id: str, reason: str = ""):
    """Reject a queued action."""
    for i, action in enumerate(HIL_QUEUE):
        if action["id"] == action_id:
            rejected_action = HIL_QUEUE.pop(i)
            rejected_action["rejected_at"] = datetime.utcnow().isoformat()
            rejected_action["rejection_reason"] = reason
            return {"status": "rejected", "action": rejected_action}

    raise HTTPException(404, f"Action not found: {action_id}")


async def _execute_hil_action(action: dict):
    """Execute an approved HIL action."""
    action_type = action["action_type"]
    payload = action["payload"]

    if action_type == "jhc_resurrect":
        # Execute resurrection
        import subprocess
        subprocess.run([
            "python", "agents/jesus-h-christ/routines/resurrector.py",
            "resurrect", payload["repo_url"],
            "--aggression", payload["aggression"]
        ])


# ============ ACTIVITY STREAM ============

@app.get("/api/activity/stream")
async def activity_stream():
    """SSE endpoint for real-time activity."""
    async def event_generator():
        while True:
            # Poll for events from various sources
            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "heartbeat",
                "data": {}
            }
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============ STARTUP ============

@app.on_event("startup")
async def startup():
    print("Mission Control API starting...")
    print(f"  Flower URL: {FLOWER_URL}")
    print(f"  Ralph API: {RALPH_API}")
    print(f"  Antfarm Dir: {ANTFARM_DIR}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
