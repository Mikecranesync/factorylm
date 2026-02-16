"""
WORKFLOW TRACKER - Celery Tasks
================================
Logs all work done by the swarm for auditing and learning.
Uses PostgreSQL for persistent storage and querying.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import sys
sys.path.insert(0, '/opt/master_of_puppets')
from celery_app import app
from workers.base_worker import BaseAgent, with_token_tracking, with_celery_tracing
from observability import traced, track_llm_call, track_api_call


# Database connection
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "rivet"),
    "user": os.getenv("POSTGRES_USER", "rivet"),
    "password": os.getenv("POSTGRES_PASSWORD", "rivet_factory_2025!"),
}

# Fallback log file
LOG_DIR = Path("/opt/master_of_puppets/logs")
LOG_DIR.mkdir(exist_ok=True)
WORK_LOG = LOG_DIR / "work_log.jsonl"


class WorkflowTracker(BaseAgent):
    """Tracks all work done by agents using PostgreSQL."""
    
    def __init__(self):
        super().__init__("WorkflowTracker")
        self.conn = None
        self._ensure_table()
    
    def _get_connection(self):
        """Get or create database connection."""
        if self.conn is None or self.conn.closed:
            try:
                import psycopg2
                self.conn = psycopg2.connect(**DB_CONFIG)
            except Exception as e:
                self.logger.error(f"DB connection failed: {e}")
                return None
        return self.conn
    
    def _ensure_table(self):
        """Create work_log table if it doesn't exist."""
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS work_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    task_id VARCHAR(100),
                    agent VARCHAR(50) NOT NULL,
                    success BOOLEAN DEFAULT TRUE,
                    tokens_used INTEGER DEFAULT 0,
                    result_summary TEXT,
                    metadata JSONB
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_work_log_agent ON work_log(agent)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_work_log_timestamp ON work_log(timestamp)")
            conn.commit()
            cur.close()
        except Exception as e:
            self.logger.warning(f"Table creation skipped: {e}")
            conn.rollback()
    
    def log_work(self, task_id: str, agent: str, result: dict, 
                 tokens_used: int = 0, success: bool = True) -> dict:
        """Log a completed task to PostgreSQL."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "agent": agent,
            "success": success,
            "tokens_used": tokens_used,
            "result_summary": str(result)[:500],
        }
        
        conn = self._get_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO work_log (task_id, agent, success, tokens_used, result_summary)
                    VALUES (%s, %s, %s, %s, %s)
                """, (task_id, agent, success, tokens_used, entry["result_summary"]))
                conn.commit()
                cur.close()
                self.logger.info(f"Logged work: {agent}/{task_id}")
            except Exception as e:
                self.logger.error(f"DB log failed: {e}")
                conn.rollback()
                # Fallback to file
                with open(WORK_LOG, 'a') as f:
                    f.write(json.dumps(entry) + '\n')
        else:
            # Fallback to file
            with open(WORK_LOG, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        
        return entry
    
    def get_stats(self, hours: int = 24) -> dict:
        """Get work statistics from PostgreSQL."""
        conn = self._get_connection()
        if not conn:
            return {"error": "No database connection"}
        
        try:
            cur = conn.cursor()
            since = datetime.now() - timedelta(hours=hours)
            
            cur.execute("""
                SELECT 
                    COUNT(*) as total_tasks,
                    COUNT(CASE WHEN success THEN 1 END) as successful,
                    SUM(tokens_used) as total_tokens,
                    COUNT(DISTINCT agent) as agents_active
                FROM work_log
                WHERE timestamp > %s
            """, (since,))
            row = cur.fetchone()
            
            cur.execute("""
                SELECT agent, COUNT(*) as tasks
                FROM work_log
                WHERE timestamp > %s
                GROUP BY agent
                ORDER BY tasks DESC
            """, (since,))
            by_agent = {r[0]: r[1] for r in cur.fetchall()}
            
            cur.close()
            
            return {
                "period_hours": hours,
                "total_tasks": row[0] or 0,
                "successful": row[1] or 0,
                "total_tokens": row[2] or 0,
                "agents_active": row[3] or 0,
                "by_agent": by_agent,
            }
        except Exception as e:
            self.logger.error(f"Stats query failed: {e}")
            return {"error": str(e)}


workflow_tracker = WorkflowTracker()


@app.task(bind=True, name='workflow_tracker.log_work')
@with_celery_tracing("log_work")
@traced(name="log_work", layer="execution")
def log_work(self, task_id: str, agent: str, result: dict,
             tokens_used: int = 0, success: bool = True) -> dict:
    """
    Log completed work for auditing.
    
    Args:
        task_id: Celery task ID
        agent: Agent that performed the work
        result: Task result (will be summarized)
        tokens_used: API tokens consumed
        success: Whether task succeeded
    """
    return workflow_tracker.log_work(task_id, agent, result, tokens_used, success)


@app.task(bind=True, name='workflow_tracker.get_stats')
@with_celery_tracing("get_stats")
@traced(name="get_stats", layer="execution")
def get_stats(self, hours: int = 24) -> dict:
    """Get work statistics."""
    return workflow_tracker.get_stats(hours)


@app.task(bind=True, name='workflow_tracker.health')
@with_celery_tracing("health")
@traced(name="health", layer="execution")
def health(self) -> dict:
    """Health check."""
    return {"status": "ok", "agent": "WorkflowTracker"}
