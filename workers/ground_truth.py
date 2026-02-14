"""
GROUND TRUTH SYSTEM
===================
Prevents hallucination by checking actual state.

Sources:
- Plane API (tasks, status)
- Server processes (what's actually running)
- File system (what files exist)
- Git commits (what code was deployed)
- systemd services (what services are active)

NEVER trust conversation memory alone.
ALWAYS verify against ground truth.
"""

import os
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class GroundTruth:
    """
    Single source of truth - what's ACTUALLY happening
    
    Not what we talked about.
    Not what we planned.
    What EXISTS and RUNS.
    """
    
    def __init__(self):
        # Plane configuration
        self.plane_url = os.getenv("PLANE_URL", "http://localhost:8070")
        self.plane_token = os.getenv("PLANE_API_KEY", "")
        self.plane_workspace = os.getenv("PLANE_WORKSPACE", "factorylm")
        self.plane_project = os.getenv("PLANE_PROJECT_ID", "")
        
        # Services to monitor
        self.services = [
            "clawdbot",
            "master-of-puppets",
            "master-of-puppets-beat",
            "remoteme",
            "plc-copilot",
            "nginx"
        ]
        
        # Important files
        self.important_files = [
            "/opt/remoteme/backend/main.py",
            "/opt/master_of_puppets/celery_app.py",
            "/root/jarvis-workspace/missions/REMOTEME_PRIME_DIRECTIVE.md",
        ]
        
        # Workspaces
        self.workspaces = [
            "/root/jarvis-workspace",
            "/opt/remoteme",
            "/opt/master_of_puppets"
        ]
    
    def get_current_state(self) -> Dict:
        """
        Get ACTUAL state from all sources.
        
        This is what should be consulted before answering
        "What did I do?" or "What's the status?"
        """
        
        state = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": self._get_running_services(),
            "docker": self._get_docker_containers(),
            "files": self._get_deployed_files(),
            "git": self._get_git_state(),
            "disk": self._get_disk_usage(),
            "memory": self._get_memory_usage(),
        }
        
        # Only add Plane tasks if configured
        if self.plane_token:
            state["tasks"] = self._get_tasks_from_plane()
        
        return state
    
    def _get_running_services(self) -> Dict:
        """Get actually running systemd services"""
        
        running = {}
        
        for service in self.services:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                running[service] = {
                    "status": result.stdout.strip(),
                    "active": result.returncode == 0
                }
                
            except Exception as e:
                running[service] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return running
    
    def _get_docker_containers(self) -> Dict:
        """Get running Docker containers"""
        
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.Image}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            containers = {}
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        containers[parts[0]] = {
                            "status": parts[1],
                            "image": parts[2]
                        }
            
            return containers
            
        except Exception as e:
            return {"error": str(e)}
    
    def _get_deployed_files(self) -> Dict:
        """Get files that actually exist"""
        
        files = {}
        
        for filepath in self.important_files:
            path = Path(filepath)
            
            if path.exists():
                stat = path.stat()
                files[filepath] = {
                    "exists": True,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            else:
                files[filepath] = {"exists": False}
        
        return files
    
    def _get_git_state(self) -> Dict:
        """Get actual git state for workspaces"""
        
        git_states = {}
        
        for workspace in self.workspaces:
            if not Path(workspace).exists():
                continue
                
            try:
                # Current branch
                branch = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    cwd=workspace,
                    timeout=5
                ).stdout.strip()
                
                # Last commit
                commit = subprocess.run(
                    ["git", "log", "-1", "--format=%H|%s|%ai"],
                    capture_output=True,
                    text=True,
                    cwd=workspace,
                    timeout=5
                ).stdout.strip()
                
                if commit and "|" in commit:
                    commit_hash, message, date = commit.split("|", 2)
                    git_states[workspace] = {
                        "branch": branch or "unknown",
                        "last_commit": {
                            "hash": commit_hash[:7],
                            "message": message[:50],
                            "date": date
                        }
                    }
                else:
                    git_states[workspace] = {"branch": branch or "not a git repo"}
                    
            except Exception as e:
                git_states[workspace] = {"error": str(e)}
        
        return git_states
    
    def _get_disk_usage(self) -> Dict:
        """Get disk usage"""
        
        try:
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                return {
                    "total": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "percent": parts[4]
                }
                
        except Exception as e:
            return {"error": str(e)}
        
        return {}
    
    def _get_memory_usage(self) -> Dict:
        """Get memory usage"""
        
        try:
            result = subprocess.run(
                ["free", "-h"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line.startswith("Mem:"):
                    parts = line.split()
                    return {
                        "total": parts[1],
                        "used": parts[2],
                        "available": parts[6] if len(parts) > 6 else parts[3]
                    }
                    
        except Exception as e:
            return {"error": str(e)}
        
        return {}
    
    def _get_tasks_from_plane(self) -> Dict:
        """Get actual task status from Plane board"""
        
        if not self.plane_token or not self.plane_project:
            return {"error": "Plane not configured"}
        
        try:
            response = requests.get(
                f"{self.plane_url}/api/v1/workspaces/{self.plane_workspace}/projects/{self.plane_project}/issues/",
                headers={"Authorization": f"Bearer {self.plane_token}"},
                timeout=10
            )
            
            if response.status_code != 200:
                return {"error": f"Plane API error: {response.status_code}"}
            
            issues = response.json()
            
            # Organize by state
            tasks = {
                "backlog": [],
                "todo": [],
                "in_progress": [],
                "done": [],
                "cancelled": []
            }
            
            for issue in issues:
                state_name = issue.get("state", {}).get("name", "backlog").lower()
                state_key = state_name.replace(" ", "_")
                
                task = {
                    "id": issue.get("id"),
                    "name": issue.get("name"),
                    "priority": issue.get("priority"),
                }
                
                if state_key in tasks:
                    tasks[state_key].append(task)
                else:
                    tasks["backlog"].append(task)
            
            return tasks
            
        except Exception as e:
            return {"error": str(e)}
    
    def format_summary(self, state: Dict = None) -> str:
        """Format ground truth as human-readable summary"""
        
        if state is None:
            state = self.get_current_state()
        
        lines = ["**GROUND TRUTH** (actual state, not conversation memory)", ""]
        
        # Services
        services = state.get("services", {})
        active_count = sum(1 for s in services.values() if s.get("active"))
        lines.append(f"**Services:** {active_count}/{len(services)} running")
        for name, info in services.items():
            status = "✅" if info.get("active") else "❌"
            lines.append(f"  {status} {name}: {info.get('status', 'unknown')}")
        
        lines.append("")
        
        # Docker
        docker = state.get("docker", {})
        if docker and "error" not in docker:
            lines.append(f"**Docker:** {len(docker)} containers")
        
        # Files
        files = state.get("files", {})
        existing = sum(1 for f in files.values() if f.get("exists"))
        lines.append(f"**Key Files:** {existing}/{len(files)} exist")
        
        # Disk/Memory
        disk = state.get("disk", {})
        mem = state.get("memory", {})
        if disk:
            lines.append(f"**Disk:** {disk.get('percent', '?')} used")
        if mem:
            lines.append(f"**RAM:** {mem.get('used', '?')} / {mem.get('total', '?')}")
        
        return "\n".join(lines)


def is_status_question(message: str) -> bool:
    """Detect if user is asking about status/state"""
    
    message_lower = message.lower()
    
    status_patterns = [
        "what did",
        "what have",
        "what's running",
        "what's deployed",
        "what's the status",
        "is it working",
        "did you",
        "have you",
        "show me",
        "what exists",
        "ground truth",
        "actual state"
    ]
    
    return any(pattern in message_lower for pattern in status_patterns)


# Singleton instance
_ground_truth = None

def get_ground_truth() -> GroundTruth:
    """Get or create ground truth instance"""
    global _ground_truth
    if _ground_truth is None:
        _ground_truth = GroundTruth()
    return _ground_truth


# Quick test
if __name__ == "__main__":
    gt = GroundTruth()
    state = gt.get_current_state()
    print(gt.format_summary(state))
