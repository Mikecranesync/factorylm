"""
🐒 MONKEY DISPATCHER
====================
The Monkey = Task poller + router + budget enforcer (NOT executor)

Supports both Trello (default) and Jira as task sources.

Workflow:
1. Poll Trello/Jira every 5min for autonomous tasks
2. Check token budget (pause if exhausted)
3. Route task to correct automaton via Celery
4. Wait for automaton result
5. Update task with results
6. Track tokens used
7. Move task to "Done"
8. Pick next task

The Monkey ROUTES tasks, doesn't execute them.
Automatons execute via Celery tasks.
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_celery_tracing
from observability import traced, track_llm_call, track_api_call
from config.network_topology import should_route_to_maintenance_llm
from workers.notify import notify_monkey_completion

logger = logging.getLogger(__name__)

# Budget config
DAILY_TOKEN_BUDGET = int(os.getenv("DAILY_TOKEN_BUDGET", 100000))
STATE_DIR = Path("/opt/master_of_puppets/state")
STATE_DIR.mkdir(exist_ok=True)
MONKEY_STATE = STATE_DIR / "monkey_state.json"

# Task type patterns (regex → automaton mapping)
TASK_PATTERNS = [
    (r"search.*(manual|documentation|kb)", "manual_hunter"),
    (r"(drift|anomaly|alert)", "conductor"),
    (r"(write|generate|create).*(report|summary|document)", "weaver"),
    (r"(build|create|configure).*(collector|integration)", "cartographer"),
    (r"(monitor|health|status|check)", "watchman"),
    (r"(alarm|fault|error).*(triage|analyze)", "alarm_triage"),
    (r"(workflow|process|automate)", "workflow_tracker"),
    # Maintenance LLM patterns
    (r"(plc|modbus|allen.bradley|siemens|maintenance|troubleshoot)", "maintenance_llm"),
]


class MonkeyDispatcher(BaseAgent):
    """
    The Monkey - Central task dispatcher.
    Routes Jira tasks to appropriate automatons.
    """
    
    def __init__(self):
        super().__init__("MonkeyDispatcher")
        self._init_state()
    
    def _init_state(self):
        """Initialize state file."""
        if not MONKEY_STATE.exists():
            state = {
                "started": datetime.now().isoformat(),
                "tasks_dispatched": 0,
                "tasks_completed": 0,
                "tokens_used_today": 0,
                "budget_date": datetime.now().strftime("%Y-%m-%d"),
                "last_poll": None,
                "active_tasks": {},  # task_key -> automaton
            }
            self._save_state(state)
    
    def _load_state(self) -> Dict:
        try:
            with open(MONKEY_STATE, 'r') as f:
                return json.load(f)
        except:
            self._init_state()
            return self._load_state()
    
    def _save_state(self, state: Dict):
        with open(MONKEY_STATE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def _reset_daily_budget(self, state: Dict) -> Dict:
        """Reset budget if new day."""
        today = datetime.now().strftime("%Y-%m-%d")
        if state.get("budget_date") != today:
            state["budget_date"] = today
            state["tokens_used_today"] = 0
            self.logger.info(f"Reset daily budget for {today}")
        return state
    
    def check_budget(self) -> Tuple[bool, int]:
        """Check if we have budget remaining. Returns (has_budget, remaining)."""
        state = self._load_state()
        state = self._reset_daily_budget(state)
        self._save_state(state)
        
        remaining = DAILY_TOKEN_BUDGET - state["tokens_used_today"]
        return remaining > 0, remaining
    
    def use_tokens(self, count: int):
        """Record token usage."""
        state = self._load_state()
        state["tokens_used_today"] += count
        self._save_state(state)
    
    def classify_task(self, task: Dict) -> str:
        """
        Classify task to determine which automaton should handle it.
        Returns automaton name.
        """
        text = f"{task.get('summary', '')} {task.get('description', '')}".lower()
        labels = [l.lower() for l in task.get("labels", [])]
        
        # Check labels first (explicit routing)
        label_map = {
            "manual-search": "manual_hunter",
            "drift-alert": "conductor",
            "report": "weaver",
            "collector": "cartographer",
            "health-check": "watchman",
            "alarm": "alarm_triage",
            "maintenance": "maintenance_llm",
            "plc": "maintenance_llm",
            "troubleshoot": "maintenance_llm",
        }
        for label, automaton in label_map.items():
            if label in labels:
                return automaton
        
        # Check if this should route to maintenance LLM based on network topology
        if should_route_to_maintenance_llm(text):
            return "maintenance_llm"
        
        # Pattern matching on text
        for pattern, automaton in TASK_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return automaton
        
        # Default to conductor (general orchestrator)
        return "conductor"
    
    def route_to_automaton(self, automaton: str, task: Dict) -> Optional[object]:
        """
        Route task to the appropriate automaton via Celery.
        Returns the AsyncResult.
        """
        task_spec = {
            "jira_key": task["key"],
            "summary": task["summary"],
            "description": task.get("description", ""),
            "priority": task.get("priority", "Medium"),
            "labels": task.get("labels", []),
            "source": "jira",
        }
        
        # Import and dispatch to correct automaton
        if automaton == "manual_hunter":
            from workers.manual_hunter_tasks import search_manuals
            query = task["summary"]
            return search_manuals.delay(query, limit=5)
        
        elif automaton == "conductor":
            from workers.conductor_tasks import handle_jira_task
            return handle_jira_task.delay(task_spec)
        
        elif automaton == "weaver":
            from workers.weaver_tasks import generate_report
            return generate_report.delay(task_spec)
        
        elif automaton == "cartographer":
            from workers.cartographer_tasks import build_collector
            return build_collector.delay(task_spec)
        
        elif automaton == "watchman":
            from workers.watchman_tasks import run_health_check
            return run_health_check.delay()
        
        elif automaton == "alarm_triage":
            from workers.alarm_triage_tasks import triage_alarm
            return triage_alarm.delay(task_spec)
        
        elif automaton == "workflow_tracker":
            from workers.workflow_tracker_tasks import track_workflow
            return track_workflow.delay(task_spec)
        
        elif automaton == "maintenance_llm":
            from workers.maintenance_llm_tasks import maintenance_llm_query
            prompt = f"{task['summary']} - {task.get('description', '')}"
            context = "maintenance"
            # Determine context based on task content
            if "troubleshoot" in task.get("summary", "").lower():
                context = "troubleshoot"
            elif "analysis" in task.get("summary", "").lower():
                context = "analysis"
            elif "document" in task.get("summary", "").lower():
                context = "documentation"
            
            return maintenance_llm_query.delay(prompt, context)
        
        else:
            self.logger.warning(f"Unknown automaton: {automaton}")
            return None
    
    def update_jira(self, task_key: str, result: Dict, automaton: str):
        """Update Jira with result."""
        from integrations.jira import get_client
        client = get_client()
        
        # Format comment
        summary = result.get("summary", "Task completed")
        details = result.get("details", "")
        tokens = result.get("tokens_used", 0)
        
        comment = f"""🤖 **Automaton Result** ({automaton})

**Summary:** {summary}

{f"**Details:**{chr(10)}{details}" if details else ""}

---
_Tokens used: {tokens} | Processed by Master of Puppets_
"""
        
        # Add comment
        client.add_comment(task_key, comment)
        
        # Transition to Done
        client.transition_issue(task_key, "Done")
        
        # Track tokens
        if tokens > 0:
            self.use_tokens(tokens)
    
    def poll_trello_and_dispatch(self) -> Dict:
        """
        Trello dispatch cycle:
        1. Check budget
        2. Poll Trello for autonomous tasks
        3. Route each task to automaton
        4. Collect results
        5. Update Trello
        """
        self.log_start("poll_trello_and_dispatch")
        
        # Check budget
        has_budget, remaining = self.check_budget()
        if not has_budget:
            self.logger.warning(f"Token budget exhausted. Pausing dispatch.")
            return {
                "status": "paused",
                "reason": "budget_exhausted",
                "tokens_remaining": 0,
            }
        
        # Poll Trello
        from integrations.trello import health_check, get_autonomous_tasks, move_card, add_comment
        
        health = health_check()
        if health.get("status") != "ok":
            self.logger.warning(f"Trello not available: {health}")
            return {"status": "trello_unavailable", "health": health}
        
        tasks = get_autonomous_tasks()
        if not tasks:
            self.logger.info("No autonomous tasks in Trello")
            return {"status": "idle", "tasks": 0}
        
        results = []
        state = self._load_state()
        
        for task in tasks:
            task_key = task["key"]
            
            # Skip if already active
            if task_key in state.get("active_tasks", {}):
                continue
            
            # Convert Trello task to standard format
            task_spec = {
                "key": task_key,
                "id": task["id"],
                "summary": task["name"],
                "description": task.get("description", ""),
                "priority": "Medium",
                "labels": task.get("labels", []),
                "source": "trello",
            }
            
            # Classify and route
            automaton = self.classify_task(task_spec)
            self.logger.info(f"Routing {task_key} ({task['name'][:30]}...) to {automaton}")
            
            # Move to In Progress
            move_card(task["id"], "in_progress")
            
            # Mark as active
            state["active_tasks"][task_key] = automaton
            state["tasks_dispatched"] += 1
            self._save_state(state)
            
            try:
                # Dispatch to automaton with completion callback
                async_result = self.route_to_automaton(automaton, task_spec)
                
                if async_result:
                    # Chain: automaton task → polish cycle → move to done
                    from celery import chain
                    from workers.polish_tasks import run_polish_cycle
                    
                    # Create task info for polish cycle
                    polish_task_info = {
                        "id": task["id"],
                        "name": task["name"],
                        "automaton": automaton,
                        "trello_card_id": task["id"],
                    }
                    
                    # Set up completion callback
                    completion_task = app.send_task(
                        'monkey.on_task_complete',
                        args=[task["id"], task["name"], automaton],
                        countdown=30  # Wait 30s then check completion
                    )
                    
                    results.append({
                        "task": task_key,
                        "name": task["name"],
                        "automaton": automaton,
                        "status": "dispatched",
                        "task_id": str(async_result.id),
                        "completion_task_id": str(completion_task.id),
                    })
                    
                    # Add "in progress" comment
                    add_comment(task["id"], f"🚀 Dispatched to {automaton}...\nTask ID: {async_result.id}")
                    
                    state["tasks_completed"] += 1
                else:
                    results.append({
                        "task": task_key,
                        "status": "routing_failed",
                    })
                    move_card(task["id"], "blocked")
                    
            except Exception as e:
                self.logger.error(f"Task {task_key} failed: {e}")
                # Add error comment
                add_comment(task["id"], f"❌ Dispatch failed: {str(e)}")
                # Move to blocked
                move_card(task["id"], "blocked")
                results.append({
                    "task": task_key,
                    "status": "error",
                    "error": str(e),
                })
            
            finally:
                # Remove from active (task runs async)
                state["active_tasks"].pop(task_key, None)
                state["last_poll"] = datetime.now().isoformat()
                self._save_state(state)
        
        return {
            "status": "completed",
            "source": "trello",
            "tasks_processed": len(results),
            "results": results,
            "tokens_remaining": remaining,
        }

    def poll_and_dispatch(self) -> Dict:
        """
        Main dispatch cycle (Jira fallback):
        1. Check budget
        2. Poll Jira for tasks
        3. Route each task to automaton
        4. Collect results
        5. Update Jira
        """
        self.log_start("poll_and_dispatch")
        
        # Check budget
        has_budget, remaining = self.check_budget()
        if not has_budget:
            self.logger.warning(f"Token budget exhausted. Pausing dispatch.")
            return {
                "status": "paused",
                "reason": "budget_exhausted",
                "tokens_remaining": 0,
            }
        
        # Poll Jira
        from integrations.jira import get_client
        client = get_client()
        
        health = client.health_check()
        if health.get("status") != "ok":
            self.logger.warning(f"Jira not available: {health}")
            return {"status": "jira_unavailable", "health": health}
        
        tasks = client.get_todo_tasks(max_results=5)
        if not tasks:
            self.logger.info("No tasks in To Do queue")
            return {"status": "idle", "tasks": 0}
        
        results = []
        state = self._load_state()
        
        for task in tasks:
            task_key = task["key"]
            
            # Skip if already active
            if task_key in state.get("active_tasks", {}):
                continue
            
            # Classify and route
            automaton = self.classify_task(task)
            self.logger.info(f"Routing {task_key} to {automaton}")
            
            # Mark as active
            state["active_tasks"][task_key] = automaton
            state["tasks_dispatched"] += 1
            self._save_state(state)
            
            try:
                # Dispatch to automaton
                async_result = self.route_to_automaton(automaton, task)
                
                if async_result:
                    # Wait for result (with timeout)
                    result = async_result.get(timeout=300)  # 5 min timeout
                    
                    # Update Jira
                    self.update_jira(task_key, result, automaton)
                    
                    state["tasks_completed"] += 1
                    
                    # Notify Mike of completion
                    notify_monkey_completion(
                        task_name=task.get("summary", task_key),
                        result=result.get("summary", "Task completed"),
                        automaton=automaton
                    )
                    
                    results.append({
                        "task": task_key,
                        "automaton": automaton,
                        "status": "completed",
                        "tokens": result.get("tokens_used", 0),
                    })
                else:
                    results.append({
                        "task": task_key,
                        "status": "routing_failed",
                    })
                    
            except Exception as e:
                self.logger.error(f"Task {task_key} failed: {e}")
                # Add error comment to Jira
                client.add_comment(task_key, f"❌ Task failed: {str(e)}")
                results.append({
                    "task": task_key,
                    "status": "error",
                    "error": str(e),
                })
            
            finally:
                # Remove from active
                state["active_tasks"].pop(task_key, None)
                state["last_poll"] = datetime.now().isoformat()
                self._save_state(state)
        
        return {
            "status": "completed",
            "tasks_processed": len(results),
            "results": results,
            "tokens_remaining": remaining,
        }
    
    def get_stats(self) -> Dict:
        """Get dispatcher statistics."""
        state = self._load_state()
        has_budget, remaining = self.check_budget()
        
        return {
            "tasks_dispatched": state.get("tasks_dispatched", 0),
            "tasks_completed": state.get("tasks_completed", 0),
            "tokens_used_today": state.get("tokens_used_today", 0),
            "tokens_remaining": remaining,
            "budget_exhausted": not has_budget,
            "active_tasks": len(state.get("active_tasks", {})),
            "last_poll": state.get("last_poll"),
        }


dispatcher = MonkeyDispatcher()


# ============== CELERY TASKS ==============

@app.task(bind=True, name='monkey.run_cycle')
@with_celery_tracing("run_cycle")
@traced(name="run_cycle", layer="execution")
def run_cycle(self, source: str = "trello") -> Dict:
    """
    Main Monkey dispatch cycle.
    Called by Celery Beat every 5 minutes.
    
    Args:
        source: "trello" (default) or "jira"
    """
    if source == "trello":
        return dispatcher.poll_trello_and_dispatch()
    else:
        return dispatcher.poll_and_dispatch()


@app.task(bind=True, name='monkey.check_budget')
@with_celery_tracing("check_budget")
@traced(name="check_budget", layer="execution")
def check_budget(self) -> Dict:
    """Check remaining token budget."""
    has_budget, remaining = dispatcher.check_budget()
    return {
        "has_budget": has_budget,
        "remaining": remaining,
        "daily_limit": DAILY_TOKEN_BUDGET,
    }


@app.task(bind=True, name='monkey.stats')
@with_celery_tracing("stats")
@traced(name="stats", layer="execution")
def stats(self) -> Dict:
    """Get Monkey dispatcher statistics."""
    return dispatcher.get_stats()


@app.task(bind=True, name='monkey.manual_dispatch')
@with_celery_tracing("manual_dispatch")
@traced(name="manual_dispatch", layer="orchestration")
def manual_dispatch(self, task_key: str, automaton: str = None) -> Dict:
    """
    Manually dispatch a specific Jira task.
    If automaton not specified, auto-classify.
    """
    from integrations.jira import get_client
    client = get_client()
    
    # Get task from Jira
    issue = client.get_issue(task_key)
    if "error" in issue:
        return {"error": f"Could not fetch {task_key}: {issue['error']}"}
    
    task = {
        "key": task_key,
        "id": issue["id"],
        "summary": issue["fields"]["summary"],
        "description": issue["fields"].get("description", ""),
        "priority": issue["fields"]["priority"]["name"] if issue["fields"].get("priority") else "Medium",
        "labels": issue["fields"].get("labels", []),
    }
    
    # Auto-classify if not specified
    if not automaton:
        automaton = dispatcher.classify_task(task)
    
    # Dispatch
    async_result = dispatcher.route_to_automaton(automaton, task)
    if not async_result:
        return {"error": f"Failed to route to {automaton}"}
    
    # Wait for result
    result = async_result.get(timeout=300)
    
    # Update Jira
    dispatcher.update_jira(task_key, result, automaton)
    
    return {
        "task": task_key,
        "automaton": automaton,
        "result": result,
    }


@app.task(bind=True, name='monkey.on_task_complete')
@with_celery_tracing("on_task_complete")
@traced(name="on_task_complete", layer="orchestration")
def on_task_complete(self, trello_card_id: str, task_name: str, automaton: str) -> Dict:
    """
    Called after a task completes. Runs polish cycle then moves to Done.
    
    Steps:
    1. Run tech debt scan
    2. Fix what we can
    3. Polish outputs (3 passes)
    4. Move card to Done
    5. Add completion comment
    """
    from integrations.trello import move_card, add_comment
    from workers.polish_tasks import polish_agent
    
    logger.info(f"Running completion handler for {task_name}")
    
    # Run polish cycle
    task_info = {
        "id": trello_card_id,
        "name": task_name,
        "automaton": automaton,
    }
    
    polish_result = polish_agent.run_polish_cycle(task_info, polish_passes=3)
    
    # Build completion comment
    debt_fixed = polish_result.get('debt_fixed', 0)
    debt_logged = polish_result.get('debt_logged', 0)
    
    comment = f"""✅ **Task Complete**

🤖 Automaton: {automaton}
🧹 Tech debt fixed: {debt_fixed}
📝 Issues logged: {debt_logged}
✨ Polish passes: 3

_Processed by Master of Puppets_"""
    
    # Add comment and move to Done
    add_comment(trello_card_id, comment)
    move_card(trello_card_id, "done")
    
    # Notify Mike
    notify_monkey_completion(
        task_name=task_name,
        result=f"Fixed {debt_fixed} tech debt items, logged {debt_logged} issues",
        automaton=automaton
    )
    
    logger.info(f"Task {task_name} moved to Done")
    
    return {
        "task": task_name,
        "card_id": trello_card_id,
        "status": "done",
        "polish_result": polish_result,
    }
