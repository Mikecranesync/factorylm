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
from datetime import datetime, timezone
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

# ============ HEALTH ============

@app.get("/health")
async def health():
    """Enhanced health endpoint with uptime, guild count, and heartbeat tracking."""
    # Update heartbeat on each health check
    health_monitor.update_heartbeat()
    
    return {
        "status": "ok",
        "service": "mission-control",
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
async def update_guilds_count(count: int = Query(..., ge=0, description="Number of Discord guilds")):
    """Update the Discord guilds count."""
    health_monitor.update_guilds_count(count)
    return {"status": "ok", "message": f"Guilds count updated to {count}", "guilds_count": health_monitor.guilds_count}

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
                data = yaml.safe_load(fh)
                workflows.append({
                    "name": data.get("name", f.stem),
                    "path": str(f.relative_to(ANTFARM_DIR)),
                    "description": data.get("description", ""),
                    "agents": len(data.get("agents", [])),
                    "steps": len(data.get("steps", [])),
                })
        except Exception as e:
            workflows.append({
                "name": f.stem,
                "path": str(f.relative_to(ANTFARM_DIR)),
                "error": str(e),
            })

    return {"workflows": workflows}