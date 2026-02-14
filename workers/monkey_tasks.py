"""
THE MONKEY - Celery Tasks
=========================
Governor and token budget enforcer.
Tracks usage, enforces limits, and manages the swarm.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
import sys
sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, token_tracker, with_celery_tracing
from observability import traced


# State storage
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
BUDGET_FILE = STATE_DIR / "token_budget.json"
USAGE_LOG = STATE_DIR / "usage_log.jsonl"


class Monkey(BaseAgent):
    """The Monkey - governor and budget enforcer."""
    
    def __init__(self):
        super().__init__("Monkey")
        self._init_budget()
    
    def _init_budget(self):
        """Initialize budget file."""
        if not BUDGET_FILE.exists():
            budget = {
                "daily_limit": 50000,
                "hourly_limit": 5000,
                "daily_used": 0,
                "hourly_used": 0,
                "last_daily_reset": datetime.now().isoformat(),
                "last_hourly_reset": datetime.now().isoformat(),
                "alert_threshold": 0.8,
            }
            self._save_budget(budget)
    
    def _load_budget(self) -> dict:
        with open(BUDGET_FILE, 'r') as f:
            return json.load(f)
    
    def _save_budget(self, budget: dict):
        with open(BUDGET_FILE, 'w') as f:
            json.dump(budget, f, indent=2)
    
    def _check_reset(self, budget: dict) -> dict:
        """Check if budget counters need reset."""
        now = datetime.now()
        
        # Daily reset
        last_daily = datetime.fromisoformat(budget["last_daily_reset"])
        if (now - last_daily) >= timedelta(days=1):
            budget["daily_used"] = 0
            budget["last_daily_reset"] = now.isoformat()
        
        # Hourly reset
        last_hourly = datetime.fromisoformat(budget["last_hourly_reset"])
        if (now - last_hourly) >= timedelta(hours=1):
            budget["hourly_used"] = 0
            budget["last_hourly_reset"] = now.isoformat()
        
        return budget
    
    def track_usage(self, task_id: str, agent: str, tokens: int) -> dict:
        """Track token usage for a task."""
        budget = self._check_reset(self._load_budget())
        
        budget["daily_used"] += tokens
        budget["hourly_used"] += tokens
        self._save_budget(budget)
        
        # Log usage
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "agent": agent,
            "tokens": tokens,
        }
        with open(USAGE_LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        # Check alerts
        alerts = []
        if budget["daily_used"] / budget["daily_limit"] >= budget["alert_threshold"]:
            alerts.append(f"Daily budget at {budget['daily_used']}/{budget['daily_limit']}")
        if budget["hourly_used"] / budget["hourly_limit"] >= budget["alert_threshold"]:
            alerts.append(f"Hourly budget at {budget['hourly_used']}/{budget['hourly_limit']}")
        
        return {
            "tracked": True,
            "daily_remaining": budget["daily_limit"] - budget["daily_used"],
            "hourly_remaining": budget["hourly_limit"] - budget["hourly_used"],
            "alerts": alerts,
        }
    
    def get_budget_status(self) -> dict:
        """Get current budget status."""
        budget = self._check_reset(self._load_budget())
        
        return {
            "daily": {
                "used": budget["daily_used"],
                "limit": budget["daily_limit"],
                "remaining": budget["daily_limit"] - budget["daily_used"],
                "percent": round(budget["daily_used"] / budget["daily_limit"] * 100, 1)
            },
            "hourly": {
                "used": budget["hourly_used"],
                "limit": budget["hourly_limit"],
                "remaining": budget["hourly_limit"] - budget["hourly_used"],
                "percent": round(budget["hourly_used"] / budget["hourly_limit"] * 100, 1)
            }
        }
    
    def can_execute(self) -> tuple[bool, str]:
        """Check if budget allows execution."""
        budget = self._check_reset(self._load_budget())
        
        if budget["daily_used"] >= budget["daily_limit"]:
            return False, "Daily budget exhausted"
        if budget["hourly_used"] >= budget["hourly_limit"]:
            return False, "Hourly budget exhausted"
        return True, "OK"


monkey = Monkey()


@app.task(bind=True, name='monkey.track_usage')
@with_celery_tracing("monkey.track_usage")
@traced(name="monkey.track_usage", layer="execution")
def track_usage(self, task_id: str, agent: str, tokens: int) -> dict:
    """Track token usage for a task."""
    return monkey.track_usage(task_id, agent, tokens)


@app.task(bind=True, name='monkey.get_budget_status')
@with_celery_tracing("monkey.get_budget_status")
@traced(name="monkey.get_budget_status", layer="orchestration")
def get_budget_status(self) -> dict:
    """Get current budget status."""
    return monkey.get_budget_status()


@app.task(bind=True, name='monkey.can_execute')
@with_celery_tracing("monkey.can_execute")
@traced(name="monkey.can_execute", layer="orchestration")
def can_execute(self) -> dict:
    """Check if budget allows execution."""
    allowed, reason = monkey.can_execute()
    return {"allowed": allowed, "reason": reason}


@app.task(bind=True, name='monkey.health_check')
@with_celery_tracing("monkey.health_check")
@traced(name="monkey.health_check", layer="execution")
def health_check(self) -> dict:
    """Periodic health check (runs every 5 minutes via Beat)."""
    status = monkey.get_budget_status()
    
    # TODO: Check all agent health, send alerts if needed
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "budget": status
    }


@app.task(bind=True, name='monkey.health')
@with_celery_tracing("monkey.health")
@traced(name="monkey.health", layer="execution")
def health(self) -> dict:
    """Simple health check."""
    return {"status": "ok", "agent": "Monkey"}
