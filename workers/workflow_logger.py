"""
WORKFLOW LOGGER - Proof of Work for Voice→Code
===============================================
Logs every command, every execution, every result.
Creates immutable evidence trail.

Created: 2026-02-03
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess

class WorkflowLogger:
    """
    Logs all voice→code workflows with proof of work
    """
    
    def __init__(self):
        self.log_dir = Path("/root/jarvis-workspace/evidence/workflows")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.daily_log = self.log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        self.summary_file = self.log_dir / "WORKFLOW_SUMMARY.md"
    
    def log_workflow(
        self,
        input_type: str,  # "voice", "text", "telegram", "api"
        input_content: str,
        action_type: str,  # "code", "command", "file_write", "api_call"
        action_details: Dict[str, Any],
        output: Any,
        success: bool,
        duration_ms: Optional[float] = None,
        source: str = "clawdbot"
    ) -> Dict[str, Any]:
        """
        Log a workflow with full evidence chain
        """
        
        timestamp = datetime.now(timezone.utc)
        
        # Create evidence record
        record = {
            "id": hashlib.sha256(f"{timestamp.isoformat()}{input_content}".encode()).hexdigest()[:16],
            "timestamp": timestamp.isoformat(),
            "input": {
                "type": input_type,
                "content": input_content[:1000],  # Truncate for storage
                "hash": hashlib.sha256(input_content.encode()).hexdigest()[:16]
            },
            "action": {
                "type": action_type,
                "details": action_details
            },
            "output": {
                "success": success,
                "result": str(output)[:2000] if output else None,
                "duration_ms": duration_ms
            },
            "source": source,
            "proof": {
                "git_commit": self._get_git_commit(),
                "hostname": os.uname().nodename
            }
        }
        
        # Append to daily log
        with open(self.daily_log, "a") as f:
            f.write(json.dumps(record) + "\n")
        
        # Update summary
        self._update_summary(record)
        
        return record
    
    def _get_git_commit(self) -> str:
        """Get current git commit"""
        try:
            result = subprocess.run(
                ["git", "-C", "/root/jarvis-workspace", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()[:8]
        except:
            return "unknown"
    
    def _update_summary(self, record: Dict):
        """Update the daily summary markdown"""
        
        summary_line = f"| {record['timestamp'][:19]} | {record['input']['type']} | {record['action']['type']} | {'✅' if record['output']['success'] else '❌'} | {record['id']} |\n"
        
        # Check if summary exists, if not create header
        if not self.summary_file.exists():
            header = """# Workflow Evidence Summary

| Timestamp | Input | Action | Status | ID |
|-----------|-------|--------|--------|-------|
"""
            self.summary_file.write_text(header)
        
        # Append summary line
        with open(self.summary_file, "a") as f:
            f.write(summary_line)
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """Get statistics for today's workflows"""
        
        if not self.daily_log.exists():
            return {"total": 0, "success": 0, "failed": 0}
        
        total = 0
        success = 0
        
        with open(self.daily_log, "r") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    total += 1
                    if record.get("output", {}).get("success"):
                        success += 1
                except:
                    pass
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total": total,
            "success": success,
            "failed": total - success,
            "success_rate": f"{(success/total*100):.1f}%" if total > 0 else "N/A"
        }


# Global logger instance
_logger = None

def get_logger() -> WorkflowLogger:
    """Get singleton logger instance"""
    global _logger
    if _logger is None:
        _logger = WorkflowLogger()
    return _logger


def log_voice_to_code(
    voice_input: str,
    code_executed: str,
    result: Any,
    success: bool,
    duration_ms: float = None
) -> Dict[str, Any]:
    """
    Convenience function to log voice→code workflows
    """
    return get_logger().log_workflow(
        input_type="voice",
        input_content=voice_input,
        action_type="code",
        action_details={"code": code_executed},
        output=result,
        success=success,
        duration_ms=duration_ms
    )


def log_telegram_command(
    message: str,
    action: str,
    result: Any,
    success: bool,
    duration_ms: float = None
) -> Dict[str, Any]:
    """
    Log Telegram bot commands
    """
    return get_logger().log_workflow(
        input_type="telegram",
        input_content=message,
        action_type="command",
        action_details={"action": action},
        output=result,
        success=success,
        duration_ms=duration_ms
    )


if __name__ == "__main__":
    # Test the logger
    logger = get_logger()
    
    record = log_voice_to_code(
        voice_input="Show me memory usage",
        code_executed="free -h",
        result="Mem: 7.8Gi 4.6Gi 392Mi",
        success=True,
        duration_ms=150.5
    )
    
    print(f"Logged workflow: {record['id']}")
    print(f"Daily stats: {logger.get_daily_stats()}")
