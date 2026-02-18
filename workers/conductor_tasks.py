"""
THE CONDUCTOR - Celery Tasks
============================
Routes tasks to appropriate agents and orchestrates workflows.
Converted from HTTP server (port 8096) to Celery worker.
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from celery import group, chain, chord

# Import from parent
import sys
sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_retry, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call

# Config paths
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)

CONDUCTOR_STATE = STATE_DIR / "conductor_state.json"
APPROVAL_QUEUE = STATE_DIR / "approval_queue.json"
PRIORITY_MATRIX = STATE_DIR / "priority_matrix.json"

# Agent routing map
AGENT_ROUTES = {
    # Alert types
    "drift_alert": ["manual_hunter", "alarm_triage", "watchman", "weaver"],
    "alarm": ["alarm_triage", "manual_hunter"],
    "anomaly": ["watchman", "alarm_triage"],
    
    # Search types
    "manual_search": ["manual_hunter"],
    "code_search": ["cartographer"],
    
    # Documentation
    "document": ["weaver"],
    "procedure": ["weaver"],
    
    # Monitoring
    "health_check": ["watchman"],
    "system_status": ["watchman"],
    
    # Tracking
    "log_work": ["workflow_tracker"],
    "track_progress": ["workflow_tracker"],
}


class Conductor(BaseAgent):
    """The Conductor - orchestrates all agent workflows."""
    
    def __init__(self):
        super().__init__("Conductor")
        self._init_files()
    
    def _init_files(self):
        """Initialize state files."""
        if not CONDUCTOR_STATE.exists():
            state = {
                "started": datetime.now().isoformat(),
                "cycles_completed": 0,
                "tasks_routed": 0,
                "workflows_approved": 0,
                "workflows_rejected": 0,
            }
            self._save_json(CONDUCTOR_STATE, state)
        
        if not APPROVAL_QUEUE.exists():
            self._save_json(APPROVAL_QUEUE, {"pending": [], "approved": [], "rejected": []})
        
        if not PRIORITY_MATRIX.exists():
            self._save_json(PRIORITY_MATRIX, {"items": [], "last_calculated": None})
    
    def _load_json(self, path: Path) -> dict:
        with open(path, 'r') as f:
            return json.load(f)
    
    def _save_json(self, path: Path, data: dict):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def route_task(self, task_type: str, payload: dict) -> List[str]:
        """Determine which agents should handle a task."""
        agents = AGENT_ROUTES.get(task_type, [])
        
        if not agents:
            # Default routing based on keywords
            content = json.dumps(payload).lower()
            if "alarm" in content or "fault" in content:
                agents = ["alarm_triage"]
            elif "manual" in content or "search" in content:
                agents = ["manual_hunter"]
            elif "document" in content or "procedure" in content:
                agents = ["weaver"]
            else:
                agents = ["workflow_tracker"]  # Log everything by default
        
        self.logger.info(f"Routing {task_type} to agents: {agents}")
        return agents
    
    def get_status(self) -> dict:
        """Get conductor status."""
        state = self._load_json(CONDUCTOR_STATE)
        queue = self._load_json(APPROVAL_QUEUE)
        
        return {
            "conductor": "THE CONDUCTOR (Master of Puppets)",
            "mode": "Celery Worker",
            "cycles_completed": state.get("cycles_completed", 0),
            "tasks_routed": state.get("tasks_routed", 0),
            "workflows_approved": state.get("workflows_approved", 0),
            "pending_approvals": len(queue.get("pending", [])),
        }


# Global conductor instance
conductor = Conductor()


@app.task(bind=True, name='conductor.route_task')
@with_celery_tracing("conductor.route_task")
@traced(name="conductor.route_task", layer="orchestration")
@with_token_tracking('conductor')
def route_task(self, task_type: str, payload: dict) -> dict:
    """
    Route a task to the appropriate agent(s).
    Returns list of agents that will handle the task.
    """
    conductor.log_start('route_task', task_type=task_type)
    
    try:
        agents = conductor.route_task(task_type, payload)
        
        # Update state
        state = conductor._load_json(CONDUCTOR_STATE)
        state["tasks_routed"] = state.get("tasks_routed", 0) + 1
        state["last_routed"] = datetime.now().isoformat()
        conductor._save_json(CONDUCTOR_STATE, state)
        
        return {
            "status": "routed",
            "task_type": task_type,
            "agents": agents,
            "task_id": self.request.id,
        }
    except Exception as e:
        conductor.log_error('route_task', e)
        raise


@app.task(bind=True, name='conductor.handle_drift_alert')
@with_token_tracking('conductor')
def handle_drift_alert(self, sensor: str, magnitude: float, plc_vendor: str, 
                       related_metrics: List[str] = None) -> dict:
    """
    Handle a drift alert by orchestrating multiple agents in parallel.
    This is the main workflow for anomaly detection.
    """
    conductor.log_start('handle_drift_alert', sensor=sensor, magnitude=magnitude)
    
    alert_data = {
        "sensor": sensor,
        "magnitude": magnitude,
        "plc_vendor": plc_vendor,
        "related_metrics": related_metrics or [],
        "timestamp": datetime.now().isoformat(),
        "alert_id": self.request.id,
    }
    
    # Import agent tasks (deferred to avoid circular imports)
    from workers import manual_hunter_tasks, alarm_triage_tasks, watchman_tasks, weaver_tasks
    
    # Create parallel task group
    workflow = group(
        manual_hunter_tasks.search_manuals.s(
            query=f"{sensor} troubleshooting {plc_vendor}",
            plc_vendor=plc_vendor
        ),
        alarm_triage_tasks.triage_alarm.s(
            code=f"DRIFT_{sensor}",
            equipment=sensor,
            note=f"Drift magnitude: {magnitude}σ"
        ),
        watchman_tasks.check_correlations.s(
            sensor=sensor,
            related_metrics=related_metrics or []
        ),
    )
    
    # Execute in parallel and collect results
    result = workflow.apply_async()
    
    return {
        "status": "workflow_started",
        "alert": alert_data,
        "workflow_id": result.id,
        "agents_invoked": ["manual_hunter", "alarm_triage", "watchman"],
        "message": "Drift alert workflow started. Results will be aggregated."
    }


@app.task(bind=True, name='conductor.get_status')
@with_celery_tracing("get_status")
@traced(name="get_status", layer="execution")
def get_status(self) -> dict:
    """Get conductor status."""
    return conductor.get_status()


@app.task(bind=True, name='conductor.approve_workflow')
@with_celery_tracing("approve_workflow")
@traced(name="approve_workflow", layer="execution")
def approve_workflow(self, token: str) -> dict:
    """Approve a pending workflow."""
    queue = conductor._load_json(APPROVAL_QUEUE)
    state = conductor._load_json(CONDUCTOR_STATE)
    
    for i, req in enumerate(queue["pending"]):
        if req["id"] == token:
            req["status"] = "APPROVED"
            req["approved_at"] = datetime.now().isoformat()
            
            queue["approved"].append(req)
            queue["pending"].pop(i)
            conductor._save_json(APPROVAL_QUEUE, queue)
            
            state["workflows_approved"] = state.get("workflows_approved", 0) + 1
            state["cycles_completed"] = state.get("cycles_completed", 0) + 1
            conductor._save_json(CONDUCTOR_STATE, state)
            
            return {"status": "APPROVED", "workflow": req.get("workflow_id")}
    
    return {"error": "Token not found"}


@app.task(bind=True, name='conductor.reject_workflow')
@with_celery_tracing("reject_workflow")
@traced(name="reject_workflow", layer="execution")
def reject_workflow(self, token: str, reason: str = "") -> dict:
    """Reject a pending workflow."""
    queue = conductor._load_json(APPROVAL_QUEUE)
    state = conductor._load_json(CONDUCTOR_STATE)
    
    for i, req in enumerate(queue["pending"]):
        if req["id"] == token:
            req["status"] = "REJECTED"
            req["rejected_at"] = datetime.now().isoformat()
            req["reason"] = reason
            
            queue["rejected"].append(req)
            queue["pending"].pop(i)
            conductor._save_json(APPROVAL_QUEUE, queue)
            
            state["workflows_rejected"] = state.get("workflows_rejected", 0) + 1
            conductor._save_json(CONDUCTOR_STATE, state)
            
            return {"status": "REJECTED", "reason": reason}
    
    return {"error": "Token not found"}


@app.task(bind=True, name='conductor.handle_jira_task')
@with_celery_tracing("conductor.handle_jira_task")
@traced(name="conductor.handle_jira_task", layer="orchestration")
@track_llm_call("gemini-pro")
@with_token_tracking('conductor')
def handle_jira_task(self, task_spec: Dict) -> Dict:
    """
    Handle a task routed from Jira via the Monkey Dispatcher.
    Orchestrates appropriate agents based on task content.
    """
    conductor.log_start('handle_jira_task', jira_key=task_spec.get('jira_key'))
    
    summary = task_spec.get("summary", "")
    description = task_spec.get("description", "")
    jira_key = task_spec.get("jira_key", "unknown")
    
    results = []
    tokens_used = 0
    
    # Determine what needs to be done based on summary/description
    text = f"{summary} {description}".lower()
    
    # Search for documentation?
    if any(kw in text for kw in ["search", "find", "manual", "documentation", "procedure"]):
        from workers.manual_hunter_tasks import search_manuals
        result = search_manuals.delay(summary, limit=5).get(timeout=60)
        results.append({"agent": "manual_hunter", "result": result})
        tokens_used += result.get("tokens_used", 0)
    
    # Generate a report?
    if any(kw in text for kw in ["report", "summary", "document", "write"]):
        from workers.weaver_tasks import generate_report
        result = generate_report.delay(task_spec).get(timeout=120)
        results.append({"agent": "weaver", "result": result})
        tokens_used += result.get("tokens_used", 0)
    
    # Check system health?
    if any(kw in text for kw in ["health", "status", "check", "monitor"]):
        from workers.watchman_tasks import run_health_check
        result = run_health_check.delay().get(timeout=60)
        results.append({"agent": "watchman", "result": result})
        tokens_used += result.get("tokens_used", 0)
    
    # If no specific action identified, do a general search
    if not results:
        from workers.manual_hunter_tasks import search_manuals
        result = search_manuals.delay(summary, limit=3).get(timeout=60)
        results.append({"agent": "manual_hunter", "result": result})
        tokens_used += result.get("tokens_used", 0)
    
    # Compile response
    output = {
        "jira_key": jira_key,
        "summary": f"Processed task with {len(results)} agent(s)",
        "details": "\n".join([
            f"- {r['agent']}: {r['result'].get('summary', 'completed')}"
            for r in results
        ]),
        "agent_results": results,
        "tokens_used": tokens_used,
    }
    
    conductor.log_complete('handle_jira_task', output)
    return output
