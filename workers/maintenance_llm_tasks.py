"""
Maintenance LLM Tasks
=====================
Celery tasks for monitoring and interacting with the PLC Laptop Maintenance LLM.
"""

import os
import sys
from datetime import datetime, timedelta
import logging
from typing import Dict

# Add parent directory for imports
sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_celery_tracing
from observability import traced
from observability.metrics import write_metric
from integrations.maintenance_llm import check_maintenance_llm_health, call_maintenance_llm

logger = logging.getLogger(__name__)

class MaintenanceLLMMonitor(BaseAgent):
    """Monitor for PLC Laptop Maintenance LLM health and availability."""
    
    def __init__(self):
        super().__init__("MaintenanceLLMMonitor")
        self.consecutive_failures = 0
        self.last_alert_time = None
        self.alert_threshold_minutes = 15
    
    def check_health_and_alert(self) -> Dict:
        """
        Check maintenance LLM health and send alerts if needed.
        Tracks consecutive failures and alerts after threshold.
        """
        health = check_maintenance_llm_health()
        
        if health.get("status") == "ok":
            # Reset failure counter on success
            if self.consecutive_failures > 0:
                self.logger.info("Maintenance LLM back online - clearing failure count")
                self.consecutive_failures = 0
                self.last_alert_time = None
            
            return {
                "status": "healthy",
                "health": health,
                "consecutive_failures": 0
            }
        
        else:
            # Increment failure counter
            self.consecutive_failures += 1
            now = datetime.utcnow()
            
            # Check if we should send an alert
            should_alert = False
            time_since_first_failure_minutes = self.consecutive_failures * 5  # 5 min intervals
            
            if (time_since_first_failure_minutes >= self.alert_threshold_minutes and 
                (not self.last_alert_time or 
                 (now - self.last_alert_time).total_seconds() > 3600)):  # Max 1 alert per hour
                should_alert = True
                self.last_alert_time = now
            
            if should_alert:
                try:
                    # Send alert via Telegram
                    from integrations.telegram_alerts import send_alert
                    
                    alert_message = f"""🚨 **Maintenance LLM Alert**
                    
**Status:** PLC Laptop offline for {time_since_first_failure_minutes} minutes
**Endpoint:** 100.72.2.99:11434
**Error:** {health.get('result', {}).get('error', 'Unknown')}
**Consecutive Failures:** {self.consecutive_failures}

The Maintenance LLM on the PLC laptop is unreachable. This affects:
- PLC troubleshooting queries
- Maintenance guidance requests
- Allen-Bradley/Siemens fault analysis

Check if:
- PLC laptop is powered on
- Tailscale connection is active  
- Ollama service is running
"""
                    
                    send_alert(
                        title="Maintenance LLM Offline",
                        message=alert_message,
                        priority="high",
                        category="maintenance_llm"
                    )
                    
                    self.logger.warning(f"Sent maintenance LLM offline alert after {time_since_first_failure_minutes} minutes")
                    
                except Exception as e:
                    self.logger.error(f"Failed to send maintenance LLM alert: {e}")
            
            return {
                "status": "unhealthy", 
                "health": health,
                "consecutive_failures": self.consecutive_failures,
                "minutes_offline": time_since_first_failure_minutes,
                "alert_sent": should_alert
            }
    
    def test_inference(self) -> Dict:
        """Test the maintenance LLM with a simple query to verify functionality."""
        test_query = "What are the basic steps for troubleshooting a PLC communication fault?"
        
        result = call_maintenance_llm(test_query, "maintenance")
        
        if result.get("success"):
            return {
                "status": "inference_ok",
                "latency_ms": result.get("metrics", {}).get("latency_ms", 0),
                "tokens_used": result.get("metrics", {}).get("total_tokens", 0),
                "response_length": len(result.get("response", ""))
            }
        else:
            return {
                "status": "inference_failed",
                "error": result.get("error"),
                "message": result.get("message")
            }


# Global monitor instance
monitor = MaintenanceLLMMonitor()


@app.task(bind=True, name='maintenance_llm.health_check')
@with_celery_tracing("health_check")
@traced(name="health_check", layer="integration")
def maintenance_llm_health_check(self) -> Dict:
    """
    Health check task for maintenance LLM.
    Runs every 5 minutes via Celery Beat.
    """
    return monitor.check_health_and_alert()


@app.task(bind=True, name='maintenance_llm.test_inference')  
@with_celery_tracing("test_inference")
@traced(name="test_inference", layer="integration")
def maintenance_llm_test_inference(self) -> Dict:
    """
    Test inference task - verifies the LLM is responding correctly.
    Can be called manually or on a schedule.
    """
    return monitor.test_inference()


@app.task(bind=True, name='maintenance_llm.query')
@with_celery_tracing("query")
@traced(name="query", layer="orchestration")  
def maintenance_llm_query(self, prompt: str, context: str = "maintenance") -> Dict:
    """
    Execute a maintenance LLM query via Celery.
    Used by other tasks that need maintenance expertise.
    
    Args:
        prompt: The maintenance question/problem
        context: Context type (maintenance, troubleshoot, analysis, documentation)
    """
    result = call_maintenance_llm(prompt, context)
    
    # Add task metadata
    result["task_id"] = self.request.id
    result["queued_at"] = datetime.utcnow().isoformat()
    
    return result


@app.task(bind=True, name='maintenance_llm.bulk_analyze')
@with_celery_tracing("bulk_analyze") 
@traced(name="bulk_analyze", layer="orchestration")
def maintenance_llm_bulk_analyze(self, prompts: list, context: str = "analysis") -> Dict:
    """
    Analyze multiple maintenance issues in batch.
    Useful for processing multiple alarms or maintenance requests.
    
    Args:
        prompts: List of maintenance questions/problems
        context: Context type for all queries
    """
    results = []
    total_tokens = 0
    start_time = datetime.utcnow()
    
    for i, prompt in enumerate(prompts):
        try:
            result = call_maintenance_llm(prompt, context)
            results.append({
                "index": i,
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "success": result.get("success", False),
                "response": result.get("response"),
                "tokens": result.get("metrics", {}).get("total_tokens", 0),
                "error": result.get("error") if not result.get("success") else None
            })
            
            total_tokens += result.get("metrics", {}).get("total_tokens", 0)
            
        except Exception as e:
            logger.error(f"Failed to process prompt {i}: {e}")
            results.append({
                "index": i,
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "success": False,
                "error": str(e)
            })
    
    end_time = datetime.utcnow()
    duration_seconds = (end_time - start_time).total_seconds()
    
    # Write batch metrics
    try:
        write_metric(
            measurement="maintenance_llm_batch",
            tags={"context": context},
            fields={
                "prompts_count": len(prompts),
                "successful_count": sum(1 for r in results if r.get("success")),
                "failed_count": sum(1 for r in results if not r.get("success")),
                "total_tokens": total_tokens,
                "duration_seconds": duration_seconds,
                "tokens_per_second": total_tokens / max(duration_seconds, 0.1)
            }
        )
    except Exception as e:
        logger.warning(f"Failed to write batch metrics: {e}")
    
    return {
        "success": True,
        "prompts_processed": len(prompts),
        "results": results,
        "summary": {
            "total_prompts": len(prompts),
            "successful": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "total_tokens": total_tokens,
            "duration_seconds": round(duration_seconds, 2)
        },
        "task_id": self.request.id,
        "completed_at": end_time.isoformat()
    }