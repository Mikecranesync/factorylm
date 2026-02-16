"""
Collector Manager - Celery Tasks
=================================
Orchestrates all PLC collectors with health monitoring and auto-restart.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
from pathlib import Path

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from celery import group


# State storage
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
COLLECTOR_STATE = STATE_DIR / "collector_state.json"


class CollectorManager:
    """Manages all PLC data collectors."""
    
    def __init__(self):
        self.collectors = {
            "s7": "s7_collector.collect",
            "ab": "ab_collector.collect",
            "modbus": "modbus_collector.collect",
        }
        self.health_tasks = {
            "s7": "s7_collector.health",
            "ab": "ab_collector.health",
            "modbus": "modbus_collector.health",
        }
        self._init_state()
    
    def _init_state(self):
        """Initialize state file."""
        if not COLLECTOR_STATE.exists():
            state = {
                "started": datetime.now().isoformat(),
                "collectors": {
                    name: {
                        "enabled": True,
                        "last_success": None,
                        "last_error": None,
                        "consecutive_errors": 0,
                        "total_reads": 0,
                    }
                    for name in self.collectors
                }
            }
            self._save_state(state)
    
    def _load_state(self) -> dict:
        with open(COLLECTOR_STATE, 'r') as f:
            return json.load(f)
    
    def _save_state(self, state: dict):
        with open(COLLECTOR_STATE, 'w') as f:
            json.dump(state, f, indent=2)
    
    def record_success(self, collector_name: str):
        """Record successful collection."""
        state = self._load_state()
        if collector_name in state["collectors"]:
            state["collectors"][collector_name]["last_success"] = datetime.now().isoformat()
            state["collectors"][collector_name]["consecutive_errors"] = 0
            state["collectors"][collector_name]["total_reads"] += 1
        self._save_state(state)
    
    def record_error(self, collector_name: str, error: str):
        """Record collection error."""
        state = self._load_state()
        if collector_name in state["collectors"]:
            state["collectors"][collector_name]["last_error"] = {
                "time": datetime.now().isoformat(),
                "message": str(error)[:200]
            }
            state["collectors"][collector_name]["consecutive_errors"] += 1
        self._save_state(state)
    
    def should_alert(self, collector_name: str, threshold: int = 3) -> bool:
        """Check if consecutive errors exceed threshold."""
        state = self._load_state()
        if collector_name in state["collectors"]:
            return state["collectors"][collector_name]["consecutive_errors"] >= threshold
        return False
    
    def get_status(self) -> dict:
        """Get status of all collectors."""
        state = self._load_state()
        return {
            "manager": "CollectorManager",
            "collectors": state["collectors"],
            "started": state.get("started"),
        }
    
    def get_enabled_collectors(self) -> List[str]:
        """Get list of enabled collectors."""
        state = self._load_state()
        return [
            name for name, info in state["collectors"].items()
            if info.get("enabled", True)
        ]


# Global manager instance
manager = CollectorManager()


@app.task(bind=True, name='collector_manager.collect_all')
def collect_all(self) -> Dict[str, Any]:
    """
    Trigger collection from all enabled collectors.
    Called periodically by Celery Beat.
    """
    from collectors import s7_collector_tasks, ab_collector_tasks, modbus_collector_tasks
    
    enabled = manager.get_enabled_collectors()
    results = {}
    
    for name in enabled:
        try:
            if name == "s7":
                result = s7_collector_tasks.collect.delay()
            elif name == "ab":
                result = ab_collector_tasks.collect.delay()
            elif name == "modbus":
                result = modbus_collector_tasks.collect.delay()
            else:
                continue
            
            results[name] = {"task_id": result.id, "status": "submitted"}
            
        except Exception as e:
            results[name] = {"error": str(e)}
            manager.record_error(name, e)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "collectors_triggered": len(results),
        "results": results,
    }


@app.task(bind=True, name='collector_manager.health_check')
def health_check(self) -> Dict[str, Any]:
    """
    Check health of all collectors.
    Called periodically by Celery Beat.
    """
    from collectors import s7_collector_tasks, ab_collector_tasks, modbus_collector_tasks
    
    results = {}
    alerts = []
    
    # Check each collector
    for name in ["s7", "ab", "modbus"]:
        try:
            if name == "s7":
                result = s7_collector_tasks.health()
            elif name == "ab":
                result = ab_collector_tasks.health()
            elif name == "modbus":
                result = modbus_collector_tasks.health()
            
            results[name] = result
            
            # Check for consecutive errors
            if manager.should_alert(name):
                alerts.append(f"{name} collector has failed 3+ times consecutively")
                
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}
            manager.record_error(name, e)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "collectors": results,
        "alerts": alerts,
        "alert_count": len(alerts),
    }


@app.task(bind=True, name='collector_manager.status')
def status(self) -> Dict[str, Any]:
    """Get manager status."""
    return manager.get_status()


@app.task(bind=True, name='collector_manager.enable')
def enable(self, collector_name: str) -> Dict[str, Any]:
    """Enable a collector."""
    state = manager._load_state()
    if collector_name in state["collectors"]:
        state["collectors"][collector_name]["enabled"] = True
        manager._save_state(state)
        return {"status": "enabled", "collector": collector_name}
    return {"error": f"Unknown collector: {collector_name}"}


@app.task(bind=True, name='collector_manager.disable')
def disable(self, collector_name: str) -> Dict[str, Any]:
    """Disable a collector."""
    state = manager._load_state()
    if collector_name in state["collectors"]:
        state["collectors"][collector_name]["enabled"] = False
        manager._save_state(state)
        return {"status": "disabled", "collector": collector_name}
    return {"error": f"Unknown collector: {collector_name}"}


@app.task(bind=True, name='collector_manager.health')
def health(self) -> Dict[str, Any]:
    """Simple health check."""
    return {"status": "ok", "agent": "CollectorManager"}
