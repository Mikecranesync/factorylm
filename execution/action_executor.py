"""
Action Executor - Celery Tasks
===============================
Executes actions autonomously or with human approval.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
import json
from pathlib import Path

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking

# State storage
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
EXECUTION_LOG = STATE_DIR / "execution_log.jsonl"
PENDING_APPROVALS = STATE_DIR / "pending_approvals.json"

# Action whitelist configuration
CONFIG_DIR = Path("/opt/master_of_puppets/config")
WHITELIST_FILE = CONFIG_DIR / "action_whitelist.json"

# Default whitelist
DEFAULT_WHITELIST = {
    "auto_approve": [
        "log_event",
        "send_alert",
        "update_status",
        "record_metric",
        "create_report",
    ],
    "require_approval": [
        "shutdown_equipment",
        "modify_setpoint",
        "change_plc_program",
        "create_work_order",
        "send_external_notification",
    ],
    "deny": [
        "delete_data",
        "format_drive",
        "drop_table",
    ]
}


class ActionExecutor(BaseAgent):
    """Executes actions with whitelist enforcement."""
    
    def __init__(self):
        super().__init__("ActionExecutor")
        self._init_config()
    
    def _init_config(self):
        """Initialize whitelist config."""
        if not WHITELIST_FILE.exists():
            CONFIG_DIR.mkdir(exist_ok=True)
            with open(WHITELIST_FILE, 'w') as f:
                json.dump(DEFAULT_WHITELIST, f, indent=2)
        
        if not PENDING_APPROVALS.exists():
            with open(PENDING_APPROVALS, 'w') as f:
                json.dump({"pending": []}, f, indent=2)
    
    def _load_whitelist(self) -> dict:
        with open(WHITELIST_FILE, 'r') as f:
            return json.load(f)
    
    def _load_pending(self) -> dict:
        with open(PENDING_APPROVALS, 'r') as f:
            return json.load(f)
    
    def _save_pending(self, data: dict):
        with open(PENDING_APPROVALS, 'w') as f:
            json.dump(data, f, indent=2)
    
    def check_action(self, action: str) -> str:
        """Check if action is allowed, needs approval, or denied."""
        whitelist = self._load_whitelist()
        
        if action in whitelist.get("deny", []):
            return "denied"
        if action in whitelist.get("auto_approve", []):
            return "auto"
        if action in whitelist.get("require_approval", []):
            return "approval_required"
        
        # Unknown actions require approval by default
        return "approval_required"
    
    def execute_action(self, action: str, params: dict, 
                      force: bool = False) -> Dict:
        """
        Execute an action based on whitelist rules.
        
        Args:
            action: Action name
            params: Action parameters
            force: Skip approval check (for pre-approved actions)
        """
        permission = self.check_action(action)
        
        if permission == "denied":
            self._log_execution(action, params, "denied", "Action is on deny list")
            return {
                "status": "denied",
                "action": action,
                "reason": "Action is on deny list"
            }
        
        if permission == "approval_required" and not force:
            # Create approval request
            return self._request_approval(action, params)
        
        # Execute the action
        return self._do_execute(action, params)
    
    def _do_execute(self, action: str, params: dict) -> Dict:
        """Actually execute the action."""
        self.logger.info(f"Executing action: {action}")
        
        # Map actions to handlers
        handlers = {
            "log_event": self._handle_log_event,
            "send_alert": self._handle_send_alert,
            "update_status": self._handle_update_status,
            "record_metric": self._handle_record_metric,
            "create_report": self._handle_create_report,
            "create_work_order": self._handle_create_work_order,
            "send_external_notification": self._handle_send_notification,
        }
        
        handler = handlers.get(action)
        if handler:
            try:
                result = handler(params)
                self._log_execution(action, params, "success", result)
                return {
                    "status": "executed",
                    "action": action,
                    "result": result
                }
            except Exception as e:
                self._log_execution(action, params, "error", str(e))
                return {
                    "status": "error",
                    "action": action,
                    "error": str(e)
                }
        else:
            self._log_execution(action, params, "unknown", "No handler found")
            return {
                "status": "unknown_action",
                "action": action,
                "message": "No handler registered for this action"
            }
    
    def _request_approval(self, action: str, params: dict) -> Dict:
        """Create an approval request."""
        pending = self._load_pending()
        
        request_id = f"{action}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        request = {
            "id": request_id,
            "action": action,
            "params": params,
            "requested_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "status": "pending",
        }
        
        pending["pending"].append(request)
        self._save_pending(pending)
        
        self._log_execution(action, params, "pending_approval", request_id)
        
        # TODO: Send notification to Mike via Telegram
        
        return {
            "status": "pending_approval",
            "request_id": request_id,
            "action": action,
            "message": "Action requires approval. Waiting for human verification."
        }
    
    def approve_action(self, request_id: str) -> Dict:
        """Approve a pending action."""
        pending = self._load_pending()
        
        for i, req in enumerate(pending["pending"]):
            if req["id"] == request_id:
                # Execute the action
                result = self._do_execute(req["action"], req["params"])
                
                # Remove from pending
                pending["pending"].pop(i)
                self._save_pending(pending)
                
                return {
                    "status": "approved_and_executed",
                    "request_id": request_id,
                    "execution_result": result
                }
        
        return {"error": "Request not found", "request_id": request_id}
    
    def reject_action(self, request_id: str, reason: str = "") -> Dict:
        """Reject a pending action."""
        pending = self._load_pending()
        
        for i, req in enumerate(pending["pending"]):
            if req["id"] == request_id:
                self._log_execution(req["action"], req["params"], "rejected", reason)
                pending["pending"].pop(i)
                self._save_pending(pending)
                
                return {
                    "status": "rejected",
                    "request_id": request_id,
                    "reason": reason
                }
        
        return {"error": "Request not found", "request_id": request_id}
    
    def get_pending(self) -> List[Dict]:
        """Get pending approval requests."""
        pending = self._load_pending()
        return pending.get("pending", [])
    
    def _log_execution(self, action: str, params: dict, status: str, details: Any):
        """Log execution to file."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "params": params,
            "status": status,
            "details": str(details)[:500],
        }
        with open(EXECUTION_LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    # Action handlers
    def _handle_log_event(self, params: dict) -> dict:
        """Log an event."""
        self.logger.info(f"Event: {params}")
        return {"logged": True}
    
    def _handle_send_alert(self, params: dict) -> dict:
        """Send an alert (internal)."""
        # Would integrate with alerting system
        return {"alert_sent": True, "message": params.get("message")}
    
    def _handle_update_status(self, params: dict) -> dict:
        """Update a status."""
        return {"status_updated": True, "target": params.get("target")}
    
    def _handle_record_metric(self, params: dict) -> dict:
        """Record a metric."""
        return {"recorded": True, "metric": params.get("name")}
    
    def _handle_create_report(self, params: dict) -> dict:
        """Create a report."""
        return {"report_created": True, "title": params.get("title")}
    
    def _handle_create_work_order(self, params: dict) -> dict:
        """Create a work order in CMMS."""
        from integrations.atlas_cmms import get_client
        client = get_client()
        result = client.create_work_order(
            title=params.get("title", "Auto-generated WO"),
            description=params.get("description", ""),
            priority=params.get("priority", "MEDIUM")
        )
        return result
    
    def _handle_send_notification(self, params: dict) -> dict:
        """Send external notification."""
        # Would integrate with Mautic/email
        return {"notification_sent": True, "to": params.get("to")}


executor = ActionExecutor()


@app.task(bind=True, name='executor.execute')
@with_token_tracking('executor')
def execute(self, action: str, params: dict, force: bool = False) -> Dict:
    """
    Execute an action with whitelist enforcement.
    
    Args:
        action: Action name
        params: Action parameters
        force: Skip approval (only for pre-approved actions)
    """
    executor.log_start('execute', action=action)
    result = executor.execute_action(action, params, force)
    executor.log_complete('execute', result)
    return result


@app.task(bind=True, name='executor.approve')
def approve(self, request_id: str) -> Dict:
    """Approve a pending action."""
    return executor.approve_action(request_id)


@app.task(bind=True, name='executor.reject')
def reject(self, request_id: str, reason: str = "") -> Dict:
    """Reject a pending action."""
    return executor.reject_action(request_id, reason)


@app.task(bind=True, name='executor.pending')
def pending(self) -> List[Dict]:
    """Get pending approval requests."""
    return executor.get_pending()


@app.task(bind=True, name='executor.check')
def check(self, action: str) -> Dict:
    """Check if an action would be allowed."""
    permission = executor.check_action(action)
    return {"action": action, "permission": permission}


@app.task(bind=True, name='executor.health')
def health(self) -> Dict:
    """Health check."""
    return {
        "status": "ok",
        "agent": "ActionExecutor",
        "pending_approvals": len(executor.get_pending())
    }
