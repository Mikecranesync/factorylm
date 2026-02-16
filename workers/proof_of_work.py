"""
PROOF OF WORK SYSTEM
Every task must provide evidence - lying is impossible

Created: 2026-02-02
"""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional, Dict, Any
import hashlib

class ProofOfWork:
    """
    Automatic evidence collection for every task
    
    Every task completion includes:
    1. BEFORE state
    2. ACTION taken (command + output)
    3. AFTER state
    4. VERIFICATION (test showing it works)
    5. DIFF (what changed)
    """
    
    def __init__(self):
        self.evidence_dir = Path("/root/jarvis-workspace/evidence")
        self.evidence_dir.mkdir(exist_ok=True)
    
    def capture_task_evidence(
        self,
        task_name: str,
        action: Callable,
        verification: Optional[Callable] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute task + capture full evidence chain
        """
        
        task_id = f"{self._slugify(task_name)}_{int(datetime.utcnow().timestamp())}"
        evidence = {
            "task": task_name,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }
        
        # Step 1: Capture BEFORE state
        print(f"📸 Capturing BEFORE state for: {task_name}")
        evidence["before"] = self._capture_state(task_name)
        
        # Step 2: Execute action + capture output
        print(f"⚡ Executing action: {task_name}")
        evidence["action"] = self._execute_with_logging(action)
        
        # Step 3: Capture AFTER state
        print(f"📸 Capturing AFTER state for: {task_name}")
        evidence["after"] = self._capture_state(task_name)
        
        # Step 4: Run verification (if provided)
        if verification:
            print(f"✅ Running verification for: {task_name}")
            evidence["verification"] = self._run_verification(verification)
        
        # Step 5: Calculate diff
        evidence["changes"] = self._diff_states(evidence["before"], evidence["after"])
        
        # Step 6: Generate evidence report
        evidence["report"] = self._generate_report(evidence)
        
        # Step 7: Save evidence (immutable)
        self._save_evidence(task_id, evidence)
        
        # Step 8: Print summary
        self._print_summary(evidence)
        
        return evidence
    
    def _slugify(self, text: str) -> str:
        """Convert text to slug"""
        return text.lower().replace(" ", "_").replace("-", "_")[:50]
    
    def _capture_state(self, task_name: str) -> Dict:
        """Capture current system state"""
        
        state = {
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Git state
        try:
            result = subprocess.run(
                ["git", "-C", "/root/jarvis-workspace", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10
            )
            state["git_commit"] = result.stdout.strip()[:8]
        except:
            state["git_commit"] = "unknown"
        
        # Docker containers
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}:{{.Status}}"],
                capture_output=True, text=True, timeout=10
            )
            state["containers"] = result.stdout.strip().split("\n") if result.stdout.strip() else []
            state["container_count"] = len(state["containers"])
        except:
            state["containers"] = []
            state["container_count"] = 0
        
        # Services
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "-q"],
                capture_output=True, text=True, timeout=10
            )
            services = [s.split()[0] for s in result.stdout.strip().split("\n") if s]
            state["services"] = [s for s in services if any(k in s for k in ["clawdbot", "master", "remoteme", "plane"])]
        except:
            state["services"] = []
        
        # Disk usage
        try:
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                state["disk_used"] = parts[2] if len(parts) > 2 else "unknown"
                state["disk_free"] = parts[3] if len(parts) > 3 else "unknown"
        except:
            state["disk_used"] = "unknown"
            state["disk_free"] = "unknown"
        
        # Memory
        try:
            result = subprocess.run(
                ["free", "-h"],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                state["mem_used"] = parts[2] if len(parts) > 2 else "unknown"
                state["mem_free"] = parts[3] if len(parts) > 3 else "unknown"
        except:
            state["mem_used"] = "unknown"
            state["mem_free"] = "unknown"
        
        return state
    
    def _execute_with_logging(self, action: Callable) -> Dict:
        """Execute action and capture ALL output"""
        
        log = {
            "start_time": datetime.utcnow().isoformat(),
            "stdout": [],
            "stderr": [],
            "return_code": None,
            "exception": None
        }
        
        try:
            if callable(action):
                result = action()
                if isinstance(result, subprocess.CompletedProcess):
                    log["stdout"] = result.stdout.split("\n") if result.stdout else []
                    log["stderr"] = result.stderr.split("\n") if result.stderr else []
                    log["return_code"] = result.returncode
                else:
                    log["result"] = str(result)
                    log["return_code"] = 0
            elif isinstance(action, str):
                result = subprocess.run(
                    action,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                log["stdout"] = result.stdout.split("\n") if result.stdout else []
                log["stderr"] = result.stderr.split("\n") if result.stderr else []
                log["return_code"] = result.returncode
        except Exception as e:
            log["exception"] = str(e)
            log["return_code"] = -1
        
        log["end_time"] = datetime.utcnow().isoformat()
        log["success"] = log["return_code"] == 0
        
        return log
    
    def _run_verification(self, verification: Callable) -> Dict:
        """Run verification test"""
        
        verify_log = {
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            result = verification()
            verify_log["success"] = bool(result)
            verify_log["details"] = str(result)
        except Exception as e:
            verify_log["success"] = False
            verify_log["error"] = str(e)
        
        return verify_log
    
    def _diff_states(self, before: Dict, after: Dict) -> list:
        """Calculate differences between states"""
        
        changes = []
        
        # Compare common keys
        all_keys = set(before.keys()) | set(after.keys())
        
        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            
            if before_val != after_val:
                changes.append({
                    "field": key,
                    "before": before_val,
                    "after": after_val
                })
        
        return changes
    
    def _generate_report(self, evidence: Dict) -> str:
        """Generate markdown evidence report"""
        
        report = f"""# Task Evidence Report

## Task: {evidence['task']}
**Task ID:** `{evidence['task_id']}`
**Timestamp:** {evidence['timestamp']}

---

## BEFORE State
- Git commit: `{evidence['before'].get('git_commit', 'N/A')}`
- Containers: {evidence['before'].get('container_count', 0)}
- Services: {', '.join(evidence['before'].get('services', [])) or 'None tracked'}
- Disk: {evidence['before'].get('disk_used', 'N/A')} used
- Memory: {evidence['before'].get('mem_used', 'N/A')} used

---

## ACTION Taken
**Success:** {'✅ YES' if evidence['action']['success'] else '❌ NO'}
**Return Code:** {evidence['action']['return_code']}

### Output:
```
{chr(10).join(evidence['action'].get('stdout', [])[:20])}
```

### Errors:
```
{chr(10).join(evidence['action'].get('stderr', [])[:10])}
```

---

## AFTER State
- Git commit: `{evidence['after'].get('git_commit', 'N/A')}`
- Containers: {evidence['after'].get('container_count', 0)}
- Services: {', '.join(evidence['after'].get('services', [])) or 'None tracked'}
- Disk: {evidence['after'].get('disk_used', 'N/A')} used
- Memory: {evidence['after'].get('mem_used', 'N/A')} used

---

## CHANGES Detected
"""
        
        if evidence['changes']:
            for change in evidence['changes']:
                report += f"- **{change['field']}:** `{change['before']}` → `{change['after']}`\n"
        else:
            report += "- No changes detected\n"
        
        report += "\n---\n\n"
        
        # Verification
        if "verification" in evidence:
            status = '✅ PASSED' if evidence['verification']['success'] else '❌ FAILED'
            report += f"""## VERIFICATION
**Status:** {status}
**Details:** {evidence['verification'].get('details', 'N/A')}

---

"""
        
        # Final verdict
        report += "## VERDICT\n"
        
        all_success = (
            evidence['action']['success'] and
            (evidence.get('verification', {}).get('success', True))
        )
        
        if all_success:
            report += "✅ **TASK COMPLETED SUCCESSFULLY**\n\n"
            report += "Evidence confirms task completion."
        else:
            report += "❌ **TASK FAILED**\n\n"
            report += "Evidence shows task did not complete successfully."
        
        return report
    
    def _save_evidence(self, task_id: str, evidence: Dict):
        """Save evidence (immutable)"""
        
        # Save JSON
        evidence_file = self.evidence_dir / f"{task_id}.json"
        # Don't include the report in JSON to avoid duplication
        evidence_json = {k: v for k, v in evidence.items() if k != 'report'}
        evidence_file.write_text(json.dumps(evidence_json, indent=2, default=str))
        
        # Save markdown report
        report_file = self.evidence_dir / f"{task_id}.md"
        report_file.write_text(evidence["report"])
        
        # Git commit (immutable record)
        try:
            subprocess.run([
                "git", "-C", str(self.evidence_dir.parent),
                "add", str(evidence_file), str(report_file)
            ], capture_output=True, timeout=10)
            subprocess.run([
                "git", "-C", str(self.evidence_dir.parent),
                "commit", "-m", f"Evidence: {task_id}"
            ], capture_output=True, timeout=10)
        except:
            pass  # Git commit is best-effort
        
        print(f"📁 Evidence saved: {evidence_file}")
    
    def _print_summary(self, evidence: Dict):
        """Print summary to console"""
        
        success = evidence['action']['success']
        
        print("\n" + "="*50)
        print(f"📋 PROOF OF WORK: {evidence['task']}")
        print("="*50)
        print(f"Status: {'✅ SUCCESS' if success else '❌ FAILED'}")
        print(f"Task ID: {evidence['task_id']}")
        
        if evidence['changes']:
            print("\nChanges detected:")
            for change in evidence['changes'][:5]:
                print(f"  • {change['field']}: {change['before']} → {change['after']}")
        
        if evidence.get('verification'):
            v = evidence['verification']
            print(f"\nVerification: {'✅ PASSED' if v['success'] else '❌ FAILED'}")
        
        print("="*50 + "\n")


# Convenience function for quick use
def prove_task(task_name: str, command: str, verify_command: str = None) -> Dict:
    """
    Quick proof of work for shell commands
    
    Usage:
        prove_task("Enable OTEL", "clawdbot plugins enable diagnostics-otel")
    """
    
    pow = ProofOfWork()
    
    def action():
        return subprocess.run(command, shell=True, capture_output=True, text=True)
    
    verification = None
    if verify_command:
        def verification():
            result = subprocess.run(verify_command, shell=True, capture_output=True, text=True)
            return result.returncode == 0
    
    return pow.capture_task_evidence(task_name, action, verification)


if __name__ == "__main__":
    # Test the system
    evidence = prove_task(
        "Test Proof of Work System",
        "echo 'Hello from Proof of Work!'",
        "echo 'Verification passed'"
    )
    print(f"\nEvidence saved to: /root/jarvis-workspace/evidence/{evidence['task_id']}.md")
