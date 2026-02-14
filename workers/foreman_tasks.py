"""
FOREMAN - The Enforcer
======================
Named after the construction site supervisor who ensures workers:
1. Start on schedule
2. Don't stop working  
3. Produce useful artifacts
4. Polish before submission

"The foreman doesn't build the pyramid. He makes sure it gets built."
"""

from celery import shared_task
from celery_app import app
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
import os
import redis

# Redis for state tracking
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(REDIS_URL)


@shared_task(name='foreman.health')
def health():
    """Foreman health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "role": "foreman"
    }


@shared_task(name='foreman.start_shift')
def start_shift(worker_group: str = "all"):
    """
    Ensure workers start their shift on schedule.
    Called by Celery Beat at shift start times.
    """
    from celery.app.control import Inspect
    
    inspect = app.control.inspect()
    active = inspect.active() or {}
    registered = inspect.registered() or {}
    
    workers_online = list(active.keys())
    
    # Log shift start
    shift_log = {
        "event": "shift_start",
        "group": worker_group,
        "timestamp": datetime.utcnow().isoformat(),
        "workers_online": workers_online,
        "worker_count": len(workers_online)
    }
    
    # Store in Redis for Observatory
    redis_client.lpush("foreman:shift_log", json.dumps(shift_log))
    redis_client.ltrim("foreman:shift_log", 0, 99)  # Keep last 100
    
    return shift_log


@shared_task(name='foreman.health_check')
def health_check():
    """
    Check that workers haven't stopped working.
    Called every 5 minutes by Celery Beat.
    """
    from celery.app.control import Inspect
    
    inspect = app.control.inspect()
    
    # Get worker states
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    stats = inspect.stats() or {}
    
    worker_status = {}
    alerts = []
    
    for worker_name in stats.keys():
        active_tasks = len(active.get(worker_name, []))
        reserved_tasks = len(reserved.get(worker_name, []))
        worker_stats = stats.get(worker_name, {})
        
        worker_status[worker_name] = {
            "active_tasks": active_tasks,
            "reserved_tasks": reserved_tasks,
            "total_tasks": worker_stats.get('total', {}).get('total', 0),
            "uptime": worker_stats.get('uptime', 0)
        }
        
        # Alert if worker has no activity for too long
        # (This is simplified - real impl would track last task time)
        
    health_report = {
        "event": "health_check",
        "timestamp": datetime.utcnow().isoformat(),
        "workers": worker_status,
        "alerts": alerts,
        "healthy": len(alerts) == 0
    }
    
    # Store for Observatory
    redis_client.set("foreman:last_health_check", json.dumps(health_report))
    redis_client.lpush("foreman:health_log", json.dumps(health_report))
    redis_client.ltrim("foreman:health_log", 0, 99)
    
    return health_report


@shared_task(name='foreman.review_queue')
def review_queue():
    """
    Review artifacts waiting for judgment.
    Routes to Hammurabi for quality gate.
    """
    # Get pending artifacts from queue
    pending = redis_client.lrange("artifacts:pending", 0, -1)
    
    reviewed = 0
    passed = 0
    failed = 0
    
    for artifact_json in pending:
        try:
            artifact = json.loads(artifact_json)
            
            # Route to Hammurabi for judgment
            # (In real impl, this would call hammurabi.judge)
            
            reviewed += 1
            
        except json.JSONDecodeError:
            continue
    
    review_report = {
        "event": "queue_review",
        "timestamp": datetime.utcnow().isoformat(),
        "pending_count": len(pending),
        "reviewed": reviewed,
        "passed": passed,
        "failed": failed
    }
    
    redis_client.lpush("foreman:review_log", json.dumps(review_report))
    redis_client.ltrim("foreman:review_log", 0, 99)
    
    return review_report


@shared_task(name='foreman.enforce_polish')
def enforce_polish(artifact_id: str, current_polish_count: int = 0):
    """
    Enforce the 3x minimum polish rule.
    Artifacts must be polished at least 3 times before final judgment.
    """
    MIN_POLISH = 3
    
    if current_polish_count < MIN_POLISH:
        # Send back for more polish
        return {
            "artifact_id": artifact_id,
            "action": "polish_required",
            "current_count": current_polish_count,
            "required": MIN_POLISH,
            "remaining": MIN_POLISH - current_polish_count
        }
    else:
        # Ready for final judgment
        return {
            "artifact_id": artifact_id,
            "action": "ready_for_judgment",
            "polish_count": current_polish_count
        }


@shared_task(name='foreman.get_observatory_data')
def get_observatory_data():
    """
    Get all data for Pharaoh's Observatory.
    Read-only view of system state.
    """
    from celery.app.control import Inspect
    
    inspect = app.control.inspect()
    
    # Worker status
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    stats = inspect.stats() or {}
    
    # Recent logs from Redis
    shift_log = [json.loads(x) for x in redis_client.lrange("foreman:shift_log", 0, 9)]
    health_log = [json.loads(x) for x in redis_client.lrange("foreman:health_log", 0, 9)]
    review_log = [json.loads(x) for x in redis_client.lrange("foreman:review_log", 0, 9)]
    
    # Pending artifacts
    pending_count = redis_client.llen("artifacts:pending")
    
    # Last health check
    last_health = redis_client.get("foreman:last_health_check")
    last_health = json.loads(last_health) if last_health else None
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "workers": {
            "online": list(stats.keys()),
            "count": len(stats),
            "active_tasks": sum(len(v) for v in active.values()),
            "reserved_tasks": sum(len(v) for v in reserved.values())
        },
        "queues": {
            "pending_artifacts": pending_count
        },
        "recent": {
            "shifts": shift_log[:5],
            "health_checks": health_log[:5],
            "reviews": review_log[:5]
        },
        "last_health_check": last_health
    }


# ============================================
# BEAT SCHEDULE (Foreman's Clock)
# ============================================

FOREMAN_BEAT_SCHEDULE = {
    # Health check every 5 minutes
    'foreman-health-check': {
        'task': 'foreman.health_check',
        'schedule': timedelta(minutes=5),
    },
    
    # Queue review every 15 minutes
    'foreman-queue-review': {
        'task': 'foreman.review_queue',
        'schedule': timedelta(minutes=15),
    },
    
    # Morning shift start (6 AM UTC)
    'foreman-morning-shift': {
        'task': 'foreman.start_shift',
        'schedule': timedelta(hours=24),  # Once per day
        'args': ['morning']
    },
}


if __name__ == "__main__":
    # Test foreman
    print("Testing Foreman...")
    print(health())
    print(get_observatory_data())
