"""
Base Worker - Common functionality for all agents
==================================================
Provides logging, retry logic, error handling, token tracking,
and FULL OBSERVABILITY tracing (LangFuse + OpenTelemetry).
"""

import logging
import time
import functools
from datetime import datetime
from typing import Any, Callable, Optional
import json
import os
import sys

# Add parent directory for observability imports
sys.path.insert(0, '/opt/master_of_puppets')

from observability import (
    traced, TraceContext, generate_trace_id, 
    get_trace_id_from_context, LANGFUSE_ENABLED,
    track_llm_call, track_api_call
)
from observability.metrics import write_celery_task, write_llm_call

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class TokenTracker:
    """Track token usage for budget enforcement."""
    
    def __init__(self):
        self.daily_budget = 50000  # Default daily budget
        self.hourly_budget = 5000  # Default hourly budget
        self._usage = {'daily': 0, 'hourly': 0, 'last_reset': datetime.utcnow()}
    
    def track(self, tokens: int, task_id: str, agent: str) -> dict:
        """Record token usage and return budget status."""
        now = datetime.utcnow()
        
        # Reset hourly counter if needed
        if (now - self._usage['last_reset']).seconds >= 3600:
            self._usage['hourly'] = 0
            self._usage['last_reset'] = now
        
        self._usage['daily'] += tokens
        self._usage['hourly'] += tokens
        
        return {
            'task_id': task_id,
            'agent': agent,
            'tokens_used': tokens,
            'daily_used': self._usage['daily'],
            'hourly_used': self._usage['hourly'],
            'daily_remaining': self.daily_budget - self._usage['daily'],
            'hourly_remaining': self.hourly_budget - self._usage['hourly'],
        }
    
    def can_execute(self) -> tuple[bool, str]:
        """Check if budget allows task execution."""
        if self._usage['daily'] >= self.daily_budget:
            return False, 'Daily budget exceeded'
        if self._usage['hourly'] >= self.hourly_budget:
            return False, 'Hourly budget exceeded'
        return True, 'OK'


# Global token tracker instance
token_tracker = TokenTracker()


def with_retry(max_retries: int = 3, delay: float = 1.0):
    """Decorator for automatic retry with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait_time = delay * (2 ** attempt)
                    logging.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator


def with_token_tracking(agent_name: str):
    """Decorator to track token usage for a task."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Check budget before execution
            can_run, reason = token_tracker.can_execute()
            if not can_run:
                logging.error(f"Task blocked: {reason}")
                return {'error': reason, 'blocked': True}
            
            # Execute task
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            
            # Estimate tokens (actual tracking would come from API response)
            estimated_tokens = kwargs.get('_tokens_used', 100)
            task_id = kwargs.get('_task_id', 'unknown')
            
            # Track usage
            usage = token_tracker.track(estimated_tokens, task_id, agent_name)
            logging.info(f"Token usage: {json.dumps(usage)}")
            
            return result
        return wrapper
    return decorator


def with_celery_tracing(task_name: str = None):
    """Decorator to automatically trace Celery task execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Extract Celery task context
            self = args[0] if args and hasattr(args[0], 'request') else None
            actual_task_name = task_name or (self.request.task if self else func.__name__)
            
            # Set up trace context
            trace_id = get_trace_id_from_context(self) if self else generate_trace_id()
            TraceContext.set(trace_id=trace_id)
            
            start_time = time.time()
            status = "success"
            error = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Write Celery-specific metrics
                queue_name = 'direct'  # Default for direct calls
                if self and hasattr(self, 'request') and self.request:
                    delivery_info = getattr(self.request, 'delivery_info', {}) or {}
                    queue_name = delivery_info.get('routing_key', 'default')
                
                worker_id = os.getenv('WORKER_ID', 'unknown')
                
                write_celery_task(actual_task_name, status, duration_ms, queue_name, worker_id)
                
                TraceContext.clear()
        
        return wrapper
    return decorator


class BaseAgent:
    """Base class for all agents in the swarm."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
    
    def log_start(self, task: str, **kwargs):
        """Log task start."""
        self.logger.info(f"Starting: {task} | params: {kwargs}")
    
    def log_complete(self, task: str, result: Any):
        """Log task completion."""
        self.logger.info(f"Completed: {task} | result_type: {type(result).__name__}")
    
    def log_error(self, task: str, error: Exception):
        """Log task error."""
        self.logger.error(f"Failed: {task} | error: {error}")
    
    @traced(layer="execution")
    def execute(self, task: str, **kwargs) -> Any:
        """Execute a task with logging, error handling, and FULL OBSERVABILITY."""
        trace_id = kwargs.pop('_trace_id', None) or generate_trace_id()
        TraceContext.set(trace_id=trace_id)
        
        self.log_start(task, **kwargs)
        start_time = time.time()
        
        try:
            method = getattr(self, f'do_{task}', None)
            if not method:
                raise NotImplementedError(f"Task '{task}' not implemented")
            result = method(**kwargs)
            
            # Log to observability system
            elapsed_ms = (time.time() - start_time) * 1000
            self._trace_execution(trace_id, task, "success", elapsed_ms, kwargs, result)
            
            self.log_complete(task, result)
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self._trace_execution(trace_id, task, "error", elapsed_ms, kwargs, error=str(e))
            self.log_error(task, e)
            raise
        finally:
            TraceContext.clear()
    
    def _trace_execution(self, trace_id: str, task: str, status: str, 
                         duration_ms: float, input_data: dict, 
                         output_data: Any = None, error: str = None):
        """Log execution trace to observability system."""
        from observability import _log_trace
        
        _log_trace(
            trace_id=trace_id,
            name=f"{self.name}.{task}",
            layer="execution",
            status=status,
            duration_ms=duration_ms,
            input={"task": task, "params_count": len(input_data)},
            output={"type": type(output_data).__name__} if output_data else None,
            error=error,
        )
