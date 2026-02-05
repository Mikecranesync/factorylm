"""
System Health Monitor - Celery Tasks
=====================================
24/7 health monitoring with auto-restart and daily summaries.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
from pathlib import Path
import subprocess

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent

# State storage
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
HEALTH_STATE = STATE_DIR / "health_state.json"
HEALTH_LOG = STATE_DIR / "health_log.jsonl"

# Services to monitor
CMMS_TOKEN = os.getenv("CMMS_TOKEN", "")

SERVICES = {
    "redis": {"type": "tcp", "host": "localhost", "port": 6379},
    "postgres": {"type": "tcp", "host": "localhost", "port": 5432},
    "flowise": {"type": "http", "url": "http://localhost:3001/api/v1/ping"},
    "n8n": {"type": "http", "url": "http://localhost:5678/healthz"},
}

# Docker containers to monitor
CONTAINERS = [
    "infra_redis_1",
    "infra_postgres_1",
    "flowise",
    "n8n",
]


class SystemHealthMonitor(BaseAgent):
    """Monitors system health and auto-restarts services."""
    
    def __init__(self):
        super().__init__("SystemHealthMonitor")
        self._init_state()
    
    def _init_state(self):
        """Initialize state file."""
        if not HEALTH_STATE.exists():
            state = {
                "started": datetime.now().isoformat(),
                "checks_performed": 0,
                "failures_detected": 0,
                "auto_restarts": 0,
                "last_check": None,
                "last_daily_summary": None,
            }
            self._save_state(state)
    
    def _load_state(self) -> dict:
        with open(HEALTH_STATE, 'r') as f:
            return json.load(f)
    
    def _save_state(self, state: dict):
        with open(HEALTH_STATE, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _log_health(self, entry: dict):
        """Log health check to file."""
        entry["timestamp"] = datetime.now().isoformat()
        with open(HEALTH_LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def check_tcp(self, host: str, port: int) -> bool:
        """Check if TCP port is open."""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def check_http(self, url: str, method: str = "GET", headers: dict = None) -> bool:
        """Check if HTTP endpoint responds."""
        import requests
        try:
            if method == "POST":
                resp = requests.post(url, json={}, headers=headers, timeout=10)
            else:
                resp = requests.get(url, headers=headers, timeout=10)
            return resp.ok
        except Exception:
            return False
    
    def check_container(self, name: str) -> Dict:
        """Check Docker container status."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}}", name],
                capture_output=True, text=True, timeout=10
            )
            status = result.stdout.strip()
            return {"name": name, "status": status, "running": status == "running"}
        except Exception as e:
            return {"name": name, "status": "error", "running": False, "error": str(e)}
    
    def check_celery_workers(self) -> Dict:
        """Check Celery worker status."""
        try:
            from celery_app import app
            inspect = app.control.inspect()
            active = inspect.active()
            stats = inspect.stats()
            
            if active is None:
                return {"status": "no_workers", "workers": 0}
            
            return {
                "status": "ok",
                "workers": len(active),
                "worker_names": list(active.keys()),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def check_all_services(self) -> Dict:
        """Check all monitored services."""
        results = {"services": {}, "containers": {}, "celery": {}}
        failed = []
        
        # Check services
        for name, config in SERVICES.items():
            if config["type"] == "tcp":
                ok = self.check_tcp(config["host"], config["port"])
            else:
                ok = self.check_http(
                    config["url"],
                    method=config.get("method", "GET"),
                    headers=config.get("headers")
                )
            
            results["services"][name] = {"healthy": ok}
            if not ok:
                failed.append(f"service:{name}")
        
        # Check containers
        for name in CONTAINERS:
            status = self.check_container(name)
            results["containers"][name] = status
            if not status.get("running"):
                failed.append(f"container:{name}")
        
        # Check Celery
        results["celery"] = self.check_celery_workers()
        if results["celery"].get("status") != "ok":
            failed.append("celery:workers")
        
        # Update state
        state = self._load_state()
        state["checks_performed"] += 1
        state["last_check"] = datetime.now().isoformat()
        if failed:
            state["failures_detected"] += len(failed)
        self._save_state(state)
        
        # Log
        self._log_health({
            "type": "health_check",
            "failed": failed,
            "summary": results
        })
        
        return {
            "healthy": len(failed) == 0,
            "failed": failed,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }
    
    def restart_container(self, name: str) -> Dict:
        """Restart a Docker container."""
        try:
            result = subprocess.run(
                ["docker", "restart", name],
                capture_output=True, text=True, timeout=60
            )
            
            state = self._load_state()
            state["auto_restarts"] += 1
            self._save_state(state)
            
            self._log_health({
                "type": "auto_restart",
                "container": name,
                "success": result.returncode == 0,
            })
            
            return {
                "restarted": result.returncode == 0,
                "container": name,
                "output": result.stdout
            }
        except Exception as e:
            return {"restarted": False, "error": str(e)}
    
    def generate_daily_summary(self) -> Dict:
        """Generate daily health summary."""
        state = self._load_state()
        
        # Read recent health logs
        recent_failures = []
        if HEALTH_LOG.exists():
            try:
                with open(HEALTH_LOG, 'r') as f:
                    for line in f:
                        entry = json.loads(line)
                        if entry.get("failed"):
                            recent_failures.extend(entry["failed"])
            except Exception:
                pass
        
        summary = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "checks_performed": state.get("checks_performed", 0),
            "failures_detected": state.get("failures_detected", 0),
            "auto_restarts": state.get("auto_restarts", 0),
            "unique_failures": list(set(recent_failures)),
            "uptime_start": state.get("started"),
        }
        
        # Update last summary time
        state["last_daily_summary"] = datetime.now().isoformat()
        self._save_state(state)
        
        return summary
    
    def get_stats(self) -> Dict:
        """Get health monitor statistics."""
        return self._load_state()


monitor = SystemHealthMonitor()


@app.task(bind=True, name='health_monitor.check_all')
def check_all(self) -> Dict:
    """
    Check health of all services, containers, and workers.
    Run this every 5 minutes via Celery Beat.
    """
    monitor.log_start('check_all')
    result = monitor.check_all_services()
    monitor.log_complete('check_all', result)
    
    # Auto-restart failed containers
    if result.get("failed"):
        for item in result["failed"]:
            if item.startswith("container:"):
                container_name = item.split(":", 1)[1]
                monitor.restart_container(container_name)
    
    return result


@app.task(bind=True, name='health_monitor.daily_summary')
def daily_summary(self) -> Dict:
    """Generate daily health summary. Run once per day."""
    monitor.log_start('daily_summary')
    result = monitor.generate_daily_summary()
    monitor.log_complete('daily_summary', result)
    
    # TODO: Send summary to Mike via Telegram
    
    return result


@app.task(bind=True, name='health_monitor.restart_container')
def restart_container(self, name: str) -> Dict:
    """Manually restart a container."""
    return monitor.restart_container(name)


@app.task(bind=True, name='health_monitor.stats')
def stats(self) -> Dict:
    """Get health monitor statistics."""
    return monitor.get_stats()


@app.task(bind=True, name='health_monitor.health')
def health(self) -> Dict:
    """Health check."""
    s = monitor.get_stats()
    return {
        "status": "ok",
        "agent": "SystemHealthMonitor",
        "checks_performed": s.get("checks_performed", 0),
        "failures_detected": s.get("failures_detected", 0),
    }
