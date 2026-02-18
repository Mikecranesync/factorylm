# 👁️ Pharaoh's Observatory - Agent Observability System

> "They wouldn't be building the pyramid if they didn't have foremen making sure they start on schedule, don't stop working, and produce useful artifacts that they polish at least three times before sending to the QA judge."
> — Mike, 2026-02-04

---

## The Concept

Mike sits atop the pyramid. Workers build beneath him. But Mike needs to SEE what's happening without disrupting the work.

```
                    👑
                   MIKE
                  (Pharaoh)
                    │
            ┌───────┴───────┐
            │  OBSERVATORY  │ ← See everything, touch nothing
            └───────┬───────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
    ┌───┴───┐   ┌───┴───┐   ┌───┴───┐
    │FOREMAN│   │FOREMAN│   │FOREMAN│ ← Enforce schedules
    └───┬───┘   └───┬───┘   └───┬───┘
        │           │           │
    ┌───┴───┐   ┌───┴───┐   ┌───┴───┐
    │WORKERS│   │WORKERS│   │WORKERS│ ← Produce artifacts
    └───┬───┘   └───┬───┘   └───┬───┘
        │           │           │
    ┌───┴───┐   ┌───┴───┐   ┌───┴───┐
    │POLISH │   │POLISH │   │POLISH │ ← 3x refinement
    └───┬───┘   └───┬───┘   └───┬───┘
        │           │           │
        └───────────┼───────────┘
                    │
            ┌───────┴───────┐
            │   HAMMURABI   │ ← LLM Judge
            │   (QA Gate)   │
            └───────┬───────┘
                    │
            ┌───────┴───────┐
            │    ARCHIVE    │ ← Mike's Brain
            └───────────────┘
```

---

## Industry Best Practices (Research Results)

### Celery Monitoring Tools

| Tool | Type | Best For |
|------|------|----------|
| **Flower** | Web UI | Real-time worker/task status |
| **Celery Insights** | Modern UI | Workflow graphs, websockets |
| **Leek** | Docker | Comprehensive task monitoring |
| **Grafana + Prometheus** | Dashboards | Metrics, alerting |
| **OpenTelemetry** | Instrumentation | Full distributed tracing |

### LLM Agent Observability

| Tool | Type | Best For |
|------|------|----------|
| **LangFuse** | Open source | LLM traces, prompts, costs |
| **LangSmith** | LangChain | Chain debugging |
| **Helicone** | Proxy | Request logging, caching |
| **Weights & Biases** | ML Ops | Experiment tracking |

---

## The Unified System

### 1. Spec → Judge → Template (Automatic Generation)

```yaml
# When you write a spec, you ALSO define:
spec:
  name: "generate_work_order"
  description: "Create CMMS work order from photo"
  
  # What "done" looks like
  acceptance_criteria:
    - Work order has asset ID
    - Work order has description
    - Work order has priority
    - Work order is valid JSON
  
  # Success metric (measurable)
  success_metric: "Work order passes CMMS validation"
  
  # AUTO-GENERATED: Judge criteria from acceptance_criteria
  judge:
    type: "llm"
    model: "claude-sonnet"
    criteria:
      - "Does output contain valid asset ID? (required)"
      - "Does output contain description > 10 chars? (required)"
      - "Does output contain priority 1-5? (required)"
      - "Is output valid JSON? (required)"
    min_score: 0.75
    
  # AUTO-GENERATED: Prompt template from spec
  template:
    system: "You are generating a CMMS work order..."
    user: "Create work order for: {input}"
```

**The insight:** When you write the spec, the judge criteria and prompt template are DERIVED automatically. They're not separate artifacts.

### 2. Foreman (Beat Scheduler + Enforcer)

```python
# celery_app.py beat_schedule

app.conf.beat_schedule = {
    # The Foreman ensures workers START on schedule
    'foreman-morning-shift': {
        'task': 'workers.foreman.start_shift',
        'schedule': crontab(hour=6, minute=0),
        'args': ['morning_workers']
    },
    
    # The Foreman checks workers HAVEN'T STOPPED
    'foreman-health-check': {
        'task': 'workers.foreman.health_check',
        'schedule': timedelta(minutes=5),
    },
    
    # The Foreman reviews ARTIFACTS produced
    'foreman-artifact-review': {
        'task': 'workers.foreman.review_queue',
        'schedule': timedelta(minutes=15),
    },
}
```

### 3. Polish Loop (3x Minimum)

```python
async def produce_artifact(task, input_data):
    """Worker produces artifact with mandatory polish loop."""
    
    # Initial production
    artifact = await worker.execute(task, input_data)
    
    # Polish loop (minimum 3x or until passing)
    for i in range(3):
        judgment = await hammurabi.judge(artifact, task.spec)
        
        if judgment.passed:
            break
        
        # Polish based on feedback
        artifact = await polish.improve(
            artifact, 
            judgment.suggestions,
            task.spec
        )
    
    # Final judgment
    final_judgment = await hammurabi.judge(artifact, task.spec)
    
    # Archive regardless (with quality score)
    await archive(artifact, final_judgment)
    
    return artifact, final_judgment
```

### 4. Observatory (Human-in-the-Loop Without Disruption)

```python
# observatory.py - Pharaoh's view

class Observatory:
    """
    Mike can see everything without disrupting the work.
    Read-only access to all worker activity.
    """
    
    def __init__(self):
        self.flower_url = "http://localhost:5555"
        self.langfuse = LangFuse()
        self.metrics = InfluxDB()
    
    def get_dashboard(self) -> dict:
        """Get current state of all workers."""
        return {
            "workers": self.get_worker_status(),
            "tasks": self.get_recent_tasks(),
            "artifacts": self.get_pending_artifacts(),
            "judgments": self.get_recent_judgments(),
            "metrics": self.get_key_metrics()
        }
    
    def get_worker_status(self) -> list:
        """Which workers are running, idle, stuck?"""
        # Query Flower API
        pass
    
    def get_pending_artifacts(self) -> list:
        """What's waiting for review/judgment?"""
        pass
    
    def get_recent_judgments(self) -> list:
        """What passed? What failed? Why?"""
        # Query LangFuse for judge traces
        pass
    
    # CRITICAL: Read-only. No commands that disrupt workers.
    # Mike observes. Foreman enforces.
```

---

## Implementation Stack

### For Celery Observability
```bash
# Install Flower (standard)
pip install flower
celery -A celery_app flower --port=5555

# Or Celery Insights (modern)
docker run -p 8555:8555 danyim/celery-insights
```

### For LLM Observability (LangFuse)
```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-xxx",
    secret_key="sk-xxx"
)

# Trace every LLM call
@langfuse.trace
async def judge_artifact(artifact, spec):
    response = await claude.complete(...)
    return response
```

### For Metrics (Grafana + InfluxDB)
```python
# Already have InfluxDB in stack
# Add Celery metrics exporter

from prometheus_client import Counter, Histogram

task_counter = Counter('celery_tasks_total', 'Total tasks', ['task_name', 'status'])
task_duration = Histogram('celery_task_duration_seconds', 'Task duration')
```

---

## The n8n Workflow Pattern

Mike's insight: "If I was making an n8n workflow, I'd put the judge in there."

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   TRIGGER   │────►│   EXECUTE   │────►│   JUDGE     │
│  (webhook)  │     │  (worker)   │     │  (LLM)      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │                     │
                              ┌─────▼─────┐         ┌─────▼─────┐
                              │   PASS    │         │   FAIL    │
                              │  Archive  │         │  Polish   │
                              └───────────┘         └─────┬─────┘
                                                          │
                                                    ┌─────▼─────┐
                                                    │  RE-JUDGE │
                                                    │ (loop 3x) │
                                                    └───────────┘
```

**In n8n/Flowise:** This becomes a visual workflow where the judge is a node, not code.

---

## Spec-Driven Development + Judge = Pydantic?

Mike asked about Pydantic. **YES.** The spec CAN BE a Pydantic model:

```python
from pydantic import BaseModel, Field, validator

class WorkOrderSpec(BaseModel):
    """
    This IS the spec, the validation, AND the judge criteria.
    """
    asset_id: str = Field(..., min_length=1, description="Asset identifier")
    description: str = Field(..., min_length=10, description="Work description")
    priority: int = Field(..., ge=1, le=5, description="Priority 1-5")
    
    # The spec IS the judge
    @validator('asset_id')
    def asset_must_exist(cls, v):
        # Could check against CMMS
        return v

# Usage
def judge_work_order(output: dict) -> bool:
    try:
        WorkOrderSpec(**output)
        return True  # Passes all criteria
    except ValidationError as e:
        return False  # Failed, here's why
```

**The insight:** Pydantic model = Spec = Judge = Validation. One artifact, multiple uses.

---

## Summary: The Complete Loop

```
1. SPEC WRITTEN (by Mike or derived from task)
   │
   ├──► Judge criteria (auto-generated)
   ├──► Prompt template (auto-generated)
   └──► Pydantic model (auto-generated)
   
2. FOREMAN SCHEDULES WORK (Celery Beat)
   │
   └──► Worker assigned, deadline set
   
3. WORKER EXECUTES
   │
   └──► Produces artifact
   
4. POLISH LOOP (3x minimum)
   │
   ├──► LLM reviews against spec
   ├──► Suggestions generated
   └──► Worker refines
   
5. HAMMURABI JUDGES (final gate)
   │
   ├──► PASS → Archive to Mike's Brain
   └──► FAIL → Flag for human review
   
6. OBSERVATORY (Mike's view)
   │
   ├──► See all activity (read-only)
   ├──► Review flagged items
   └──► Spot-check quality
   
7. METRICS LOGGED (LangFuse + InfluxDB)
   │
   └──► Cost, latency, quality scores
```

---

## Next Steps

1. [ ] Deploy Flower for Celery visibility
2. [ ] Set up LangFuse for LLM tracing
3. [ ] Create Pydantic spec models for common tasks
4. [ ] Build Observatory dashboard (Telegram or web)
5. [ ] Wire judge into n8n/Flowise workflows

---

*The Pharaoh sees all. The workers build. The pyramid rises.*
