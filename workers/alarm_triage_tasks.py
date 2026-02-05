"""
ALARM TRIAGE - Celery Tasks
===========================
Turns alarm codes into actionable troubleshooting checklists.
Converted from HTTP server (port 8091) to Celery worker.
"""

import sys
sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_retry, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call, track_api_call


class AlarmTriage(BaseAgent):
    """Converts alarms to troubleshooting checklists."""
    
    def __init__(self):
        super().__init__("AlarmTriage")
    
    def triage(self, code: str, equipment: str, note: str = "") -> dict:
        """Generate troubleshooting checklist for an alarm."""
        self.logger.info(f"Triaging alarm: {code} on {equipment}")
        
        # TODO: Integrate with AI for intelligent triage
        return {
            "alarm_code": code,
            "equipment": equipment,
            "note": note,
            "checklist": [
                "Check power supply to equipment",
                "Verify sensor connections",
                "Review recent parameter changes",
                "Check for environmental factors",
                "Review historical alarm patterns"
            ],
            "priority": "MEDIUM",
            "estimated_resolution_time": "30 minutes"
        }


alarm_triage = AlarmTriage()


@app.task(bind=True, name='alarm_triage.triage_alarm')
@with_token_tracking('alarm_triage')
def triage_alarm(self, code: str, equipment: str, note: str = "") -> dict:
    """
    Generate troubleshooting checklist for an alarm.
    
    Args:
        code: Alarm code (e.g., "F0001", "DRIFT_motor_3")
        equipment: Equipment identifier
        note: Additional context
    
    Returns:
        Prioritized troubleshooting checklist
    """
    alarm_triage.log_start('triage_alarm', code=code, equipment=equipment)
    
    try:
        result = alarm_triage.triage(code, equipment, note)
        alarm_triage.log_complete('triage_alarm', result)
        return result
    except Exception as e:
        alarm_triage.log_error('triage_alarm', e)
        raise


@app.task(bind=True, name='alarm_triage.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health(self) -> dict:
    """Health check."""
    return {"status": "ok", "agent": "AlarmTriage"}
