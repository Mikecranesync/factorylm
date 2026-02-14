# 🔧 Recursive Learning Loop Repairs

> Identified issues and fixes for worker self-improvement cycles.

---

## Current State Analysis

### ✅ Working
- Celery app configured with 22 workers
- Redis broker connected
- Evolution tasks exist (`evolution_tasks.py`)
- Polish tasks exist (`polish_tasks.py`)

### ❌ Issues Found

1. **Hammurabi not wired to worker outputs**
   - Workers produce artifacts but bypass quality gates
   - No LLM-as-judge integration

2. **Evolution cycle not triggered**
   - `evolution_tasks.py` exists but not scheduled in beat
   - No feedback loop from judgments to prompts

3. **No persistent brain storage**
   - Artifacts go to local state files
   - Should flow to Neon DB (Mike's Brain)

4. **Missing Prometheus (training data capture)**
   - Processes undocumented
   - No input/output logging for future AI training

---

## Repair Plan

### Phase 1: Wire Hammurabi to All Workers

**File to create:** `/opt/master_of_puppets/workers/quality_gate.py`

```python
"""
Quality Gate - Wraps all worker outputs through Hammurabi
"""
from functools import wraps
from workers.hammurabi import hammurabi

def quality_gated(artifact_type: str, min_score: float = 0.7):
    """
    Decorator to run worker outputs through Hammurabi.
    
    Usage:
        @app.task
        @quality_gated("document")
        def generate_sop(topic):
            return weaver.create_sop(topic)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get raw output
            result = await func(*args, **kwargs)
            
            # Judge it
            judgment = await hammurabi.judge(result, artifact_type)
            
            if judgment.passed:
                # Archive to brain
                await archive_to_brain(result, judgment)
                return result
            else:
                # Try to improve
                improved, final_judgment = await hammurabi.judge_and_improve(
                    result, artifact_type
                )
                await archive_to_brain(improved, final_judgment)
                return improved
        
        return wrapper
    return decorator
```

### Phase 2: Schedule Evolution Cycle

**Add to celery_app.py beat_schedule:**

```python
app.conf.beat_schedule = {
    # ... existing schedules ...
    
    'evolution-daily': {
        'task': 'workers.evolution_tasks.run_evolution_cycle',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
    'hammurabi-stats-hourly': {
        'task': 'workers.hammurabi_tasks.report_stats',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

### Phase 3: Connect to Mike's Brain (Neon)

**Add to base_worker.py:**

```python
import asyncpg

NEON_URL = os.getenv('NEON_DATABASE_URL')

async def archive_to_brain(artifact: str, judgment: Verdict):
    """Archive judged artifact to Neon database."""
    conn = await asyncpg.connect(NEON_URL)
    try:
        await conn.execute('''
            INSERT INTO artifacts (
                content, artifact_type, quality_score, 
                judgment, created_at
            ) VALUES ($1, $2, $3, $4, NOW())
        ''', artifact, judgment.artifact_type, judgment.score, 
            judgment.judgment.value)
    finally:
        await conn.close()
```

### Phase 4: Add Prometheus (Training Data Capture)

**File to create:** `/opt/master_of_puppets/workers/prometheus_tasks.py`

```python
"""
PROMETHEUS - The Trainer
Captures all processes as training data for future AI.
"""
import json
from datetime import datetime
from pathlib import Path

TRAINING_DATA_DIR = Path("/opt/master_of_puppets/training_data")
TRAINING_DATA_DIR.mkdir(exist_ok=True)

def capture_process(
    input_text: str,
    process_steps: list,
    output: str,
    success: bool,
    metadata: dict = None
):
    """
    Capture a complete process as training data.
    
    Format matches OpenAI fine-tuning JSONL:
    {"messages": [{"role": "user", "content": input}, 
                  {"role": "assistant", "content": output}]}
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "input": input_text,
        "process": process_steps,
        "output": output,
        "success": success,
        "metadata": metadata or {}
    }
    
    # Append to daily JSONL file
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = TRAINING_DATA_DIR / f"training_{date_str}.jsonl"
    
    with open(output_file, 'a') as f:
        f.write(json.dumps(record) + '\n')
    
    return record
```

---

## Implementation Order

1. **TODAY:** Create `quality_gate.py` wrapper
2. **TODAY:** Add Hammurabi tasks to beat schedule
3. **THIS WEEK:** Set up Neon DB connection (needs Mike to create)
4. **THIS WEEK:** Deploy Prometheus training capture
5. **NEXT WEEK:** Wire all 22 workers through quality gate

---

## Quick Test

```python
# Test the recursive improvement loop
from workers.hammurabi import hammurabi
import asyncio

async def test():
    # Bad output (should fail and improve)
    bad = "The implementation leverages paradigm architecture."
    improved, judgment = await hammurabi.judge_and_improve(bad, "response")
    print(f"Original: {bad}")
    print(f"Improved: {improved}")
    print(f"Score: {judgment.score}")

asyncio.run(test())
```

---

*Repairs documented by Archimedes. Implementation pending Mike's approval.*
