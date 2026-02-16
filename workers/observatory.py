#!/usr/bin/env python3
"""
PHARAOH'S OBSERVATORY 👁️
========================
See everything. Touch nothing.

Run directly for CLI view:
    python observatory.py

Or import for programmatic access:
    from observatory import get_dashboard
"""

import json
import requests
from datetime import datetime
from typing import Dict, Any
import redis
import os

# Config
FLOWER_URL = "http://localhost:5555"
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

redis_client = redis.from_url(REDIS_URL)


def get_flower_workers() -> Dict[str, Any]:
    """Get worker status from Flower."""
    try:
        resp = requests.get(f"{FLOWER_URL}/api/workers?status=true", timeout=5)
        return resp.json() if resp.ok else {}
    except:
        return {}


def get_flower_tasks(limit: int = 20) -> Dict[str, Any]:
    """Get recent tasks from Flower."""
    try:
        resp = requests.get(f"{FLOWER_URL}/api/tasks?limit={limit}", timeout=5)
        return resp.json() if resp.ok else {}
    except:
        return {}


def get_foreman_logs() -> Dict[str, Any]:
    """Get Foreman's logs from Redis."""
    def get_log(key: str, limit: int = 5):
        items = redis_client.lrange(key, 0, limit - 1)
        return [json.loads(x) for x in items]
    
    last_health = redis_client.get("foreman:last_health_check")
    
    return {
        "shifts": get_log("foreman:shift_log"),
        "health_checks": get_log("foreman:health_log"),
        "reviews": get_log("foreman:review_log"),
        "last_health": json.loads(last_health) if last_health else None
    }


def get_pending_artifacts() -> int:
    """Get count of artifacts waiting for judgment."""
    return redis_client.llen("artifacts:pending")


def get_dashboard() -> Dict[str, Any]:
    """
    Get complete Observatory dashboard.
    Read-only view of system state.
    """
    workers = get_flower_workers()
    tasks = get_flower_tasks()
    foreman = get_foreman_logs()
    
    # Calculate task stats
    task_stats = {"total": 0, "succeeded": 0, "failed": 0, "pending": 0}
    for task_id, task in tasks.items():
        task_stats["total"] += 1
        state = task.get("state", "UNKNOWN")
        if state == "SUCCESS":
            task_stats["succeeded"] += 1
        elif state == "FAILURE":
            task_stats["failed"] += 1
        elif state in ("PENDING", "RECEIVED", "STARTED"):
            task_stats["pending"] += 1
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "workers": {
            "online": list(workers.keys()),
            "count": len(workers),
            "healthy": all(workers.values()) if workers else False
        },
        "tasks": task_stats,
        "queues": {
            "pending_artifacts": get_pending_artifacts()
        },
        "foreman": foreman,
        "flower_url": FLOWER_URL
    }


def format_dashboard(data: Dict[str, Any]) -> str:
    """Format dashboard for human-readable output."""
    lines = [
        "👁️ PHARAOH'S OBSERVATORY",
        "=" * 40,
        f"📅 {data['timestamp']}",
        "",
        "🏭 WORKERS",
        f"  Online: {data['workers']['count']}",
        f"  Healthy: {'✅' if data['workers']['healthy'] else '❌'}",
        f"  Names: {', '.join(data['workers']['online']) or 'None'}",
        "",
        "📋 TASKS (recent 20)",
        f"  Total: {data['tasks']['total']}",
        f"  Succeeded: {data['tasks']['succeeded']} ✅",
        f"  Failed: {data['tasks']['failed']} ❌",
        f"  Pending: {data['tasks']['pending']} ⏳",
        "",
        "📦 QUEUES",
        f"  Pending Artifacts: {data['queues']['pending_artifacts']}",
        "",
        "👷 FOREMAN LOGS",
    ]
    
    if data['foreman']['last_health']:
        lh = data['foreman']['last_health']
        lines.append(f"  Last Health Check: {lh.get('timestamp', 'N/A')}")
        lines.append(f"  Healthy: {'✅' if lh.get('healthy') else '❌'}")
    
    lines.extend([
        "",
        f"🌸 Flower: {data['flower_url']}",
        "=" * 40,
    ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    dashboard = get_dashboard()
    print(format_dashboard(dashboard))
    print("\n📊 Raw JSON:")
    print(json.dumps(dashboard, indent=2, default=str))
