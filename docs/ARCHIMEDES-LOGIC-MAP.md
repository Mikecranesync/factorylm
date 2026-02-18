# 🎭 ARCHIMEDES (Master of Puppets) - Logic Map

> "Give me a lever long enough and a fulcrum on which to place it, and I shall move the world."

**Location:** `/opt/master_of_puppets/`
**Orchestration:** Celery + Redis
**Status:** Active (celerybeat-schedule present)

---

## 🏗️ Architecture Overview

```
                        ┌─────────────────────────────────────┐
                        │         MIKE (Human)                │
                        │    Voice/Text via Telegram          │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │         CLAWDBOT                    │
                        │    Natural Language Interface       │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ARCHIMEDES (Master of Puppets)                      │
│                              Celery Orchestrator                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│    ┌─────────────────┐                                                       │
│    │   CONDUCTOR     │ ◄─── Entry point, routes tasks to agents              │
│    └────────┬────────┘                                                       │
│             │                                                                 │
│    ┌────────┴────────┬────────────┬────────────┬────────────┐               │
│    ▼                 ▼            ▼            ▼            ▼               │
│ ┌──────────┐  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│ │ MANUAL   │  │  ALARM   │ │ WATCHMAN │ │ WEAVER   │ │CARTOGRAPH│          │
│ │ HUNTER   │  │  TRIAGE  │ │          │ │          │ │   ER     │          │
│ │          │  │          │ │ Health   │ │ Document │ │ Code     │          │
│ │ Search   │  │ Classify │ │ Monitor  │ │ Generate │ │ Map      │          │
│ │ manuals  │  │ alarms   │ │ systems  │ │ SOPs     │ │ repos    │          │
│ └──────────┘  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                               │
│    ┌────────────┬────────────┬────────────┬────────────┐                    │
│    ▼            ▼            ▼            ▼            ▼                    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│ │ WORKFLOW │ │  MONKEY  │ │ KEYMASTER│ │ SYNTHETIC│ │ EVOLUTION│           │
│ │ TRACKER  │ │ DISPATCH │ │          │ │  USERS   │ │          │           │
│ │          │ │          │ │ API key  │ │          │ │ Self-    │           │
│ │ Log work │ │ Chaos    │ │ rotation │ │ 24/7 KB  │ │ improve  │           │
│ │ progress │ │ testing  │ │ & audit  │ │ builder  │ │ workers  │           │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                               │
│    ┌────────────┬────────────┬────────────┬────────────┐                    │
│    ▼            ▼            ▼            ▼            ▼                    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│ │ CONTENT  │ │ GITHUB   │ │ ARTICLE  │ │  PHOTO   │ │  EDGE    │           │
│ │ CAPTURE  │ │ SCRUBBER │ │PUBLISHER │ │ ANALYZER │ │ GATEWAY  │           │
│ │          │ │          │ │          │ │          │ │          │           │
│ │ YouTube  │ │ Scan     │ │ Generate │ │ PLC      │ │ PLC      │           │
│ │ automate │ │ repos    │ │ papers   │ │ photos   │ │ comms    │           │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                               │
│    ┌────────────────────────────────────────────────────────────┐           │
│    │                    DATA COLLECTORS                          │           │
│    ├────────────┬────────────┬────────────┬────────────────────┤           │
│    │ S7 (Siemens)│ AB (Allen-B)│ MODBUS    │ Collector Manager  │           │
│    └────────────┴────────────┴────────────┴────────────────────┘           │
│                                                                               │
│    ┌────────────────────────────────────────────────────────────┐           │
│    │                    ANALYTICS LAYER                          │           │
│    ├────────────┬────────────┬────────────────────────────────┤           │
│    │ Baseline   │ Drift      │ Pattern                         │           │
│    │ Builder    │ Detector   │ Embedder                        │           │
│    └────────────┴────────────┴────────────────────────────────┘           │
│                                                                               │
│    ┌────────────────────────────────────────────────────────────┐           │
│    │                    EXECUTION & MONITORING                   │           │
│    ├────────────┬────────────────────────────────────────────┤           │
│    │ Action     │ System Health                                │           │
│    │ Executor   │ Monitor                                      │           │
│    └────────────┴────────────────────────────────────────────┘           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │           OUTPUTS                    │
                        ├─────────────────────────────────────┤
                        │ • Telegram notifications            │
                        │ • Generated documents (PLane)       │
                        │ • Knowledge base updates            │
                        │ • GitHub commits                    │
                        │ • API calls (LangChain/LangFuse)    │
                        │ • InfluxDB metrics                  │
                        └─────────────────────────────────────┘
```

---

## 🔄 Task Routing Matrix

| Task Type | Primary Agent | Secondary Agents |
|-----------|---------------|------------------|
| `drift_alert` | manual_hunter | alarm_triage, watchman, weaver |
| `alarm` | alarm_triage | manual_hunter |
| `anomaly` | watchman | alarm_triage |
| `manual_search` | manual_hunter | - |
| `code_search` | cartographer | - |
| `document` | weaver | - |
| `procedure` | weaver | - |
| `health_check` | watchman | - |
| `log_work` | workflow_tracker | - |

---

## 🧠 Worker Registry (22 Active)

### Core Workers
| Worker | File | Purpose |
|--------|------|---------|
| **Conductor** | `conductor_tasks.py` | Route tasks, orchestrate workflows |
| **Manual Hunter** | `manual_hunter_tasks.py` | Search equipment manuals |
| **Alarm Triage** | `alarm_triage_tasks.py` | Classify and prioritize alarms |
| **Watchman** | `watchman_tasks.py` | System health monitoring |
| **Weaver** | `weaver_tasks.py` | Generate documentation/SOPs |
| **Cartographer** | `cartographer_tasks.py` | Map code repositories |
| **Workflow Tracker** | `workflow_tracker_tasks.py` | Log work progress |

### Automation Workers
| Worker | File | Purpose |
|--------|------|---------|
| **Monkey Dispatcher** | `monkey_dispatcher.py` | Chaos testing coordination |
| **Monkey Tasks** | `monkey_tasks.py` | Execute chaos tests |
| **Evolution** | `evolution_tasks.py` | Self-improvement cycles |
| **Polish** | `polish_tasks.py` | Output refinement |

### Content Workers
| Worker | File | Purpose |
|--------|------|---------|
| **Content Capture** | `content_capture_tasks.py` | YouTube automation |
| **GitHub Scrubber** | `github_scrubber_tasks.py` | Continuous repo scanning |
| **Article Publisher** | `article_publisher_tasks.py` | Generate scientific articles |
| **Synthetic Users** | `synthetic_user_tasks.py` | 24/7 KB builder |

### Integration Workers
| Worker | File | Purpose |
|--------|------|---------|
| **Integration** | `integration_tasks.py` | External API integrations |
| **Maintenance LLM** | `maintenance_llm_tasks.py` | LLM-powered maintenance |
| **Photo Analyzer** | `photo_analyzer_tasks.py` | PLC photo analysis |
| **Edge Gateway** | `edge_gateway_tasks.py` | PLC communications |
| **Keymaster** | `keymaster_tasks.py` | API key rotation & audit |

### Data Collection Workers
| Worker | File | Purpose |
|--------|------|---------|
| **S7 Collector** | `s7_collector_tasks.py` | Siemens S7 protocol |
| **AB Collector** | `ab_collector_tasks.py` | Allen-Bradley EtherNet/IP |
| **Modbus Collector** | `modbus_collector_tasks.py` | Modbus TCP/RTU |

---

## 📊 Data Flow

```
INPUT SOURCES                    PROCESSING                      OUTPUTS
─────────────────────────────────────────────────────────────────────────
                                      
[Telegram]─────┐                ┌──────────────┐         ┌─────────────┐
               │                │              │         │ Telegram    │
[PLC Data]─────┼───────────────►│  CONDUCTOR   ├────────►│ Notifications│
               │                │              │         └─────────────┘
[GitHub]───────┤                └──────┬───────┘                
               │                       │                 ┌─────────────┐
[Edge Logs]────┤                ┌──────▼───────┐         │ PLane Docs  │
               │                │              │         │ (Notion)    │
[API Webhooks]─┤                │   WORKERS    ├────────►└─────────────┘
               │                │   (Celery)   │                
[Cron Beats]───┘                └──────┬───────┘         ┌─────────────┐
                                       │                 │ GitHub      │
                                ┌──────▼───────┐         │ Commits     │
                                │  ANALYTICS   ├────────►└─────────────┘
                                │              │                
                                └──────┬───────┘         ┌─────────────┐
                                       │                 │ InfluxDB    │
                                ┌──────▼───────┐         │ Metrics     │
                                │   HAMMURABI  ├────────►└─────────────┘
                                │   (Judge)    │                
                                └──────────────┘         ┌─────────────┐
                                                         │ Mike's Brain│
                                                    ────►│ (Neon DB)   │
                                                         └─────────────┘
```

---

## 🔧 Recursive Learning Loop

```
┌──────────────────────────────────────────────────────────────┐
│                    EVOLUTION CYCLE                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. PRODUCE                                                   │
│     Worker generates artifact (document, code, response)      │
│                           │                                   │
│                           ▼                                   │
│  2. JUDGE (Hammurabi)                                        │
│     Score artifact against quality standards                  │
│     • Quality: Is it good?                                    │
│     • Novelty: Is it new?                                     │
│     • Actionable: Does it trigger action?                     │
│                           │                                   │
│              ┌────────────┴────────────┐                     │
│              ▼                         ▼                     │
│         [PASS]                    [FAIL]                     │
│              │                         │                     │
│              ▼                         ▼                     │
│  3a. ARCHIVE                  3b. IMPROVE (Polish)           │
│      Store in brain               Refine with LLM            │
│      Update embeddings            Generate better version    │
│                                        │                     │
│                                        ▼                     │
│                               RE-JUDGE (loop max 3x)         │
│                                        │                     │
│                                        ▼                     │
│                               Archive best effort            │
│                                                               │
│  4. LEARN (Evolution)                                        │
│     Analyze patterns in judgments                            │
│     Update worker prompts                                    │
│     Improve future outputs                                   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔌 Integration Points

| System | Connection | Purpose |
|--------|------------|---------|
| **Redis** | `localhost:6379` | Celery broker + backend |
| **PostgreSQL** | `localhost:5432` | Persistent state |
| **InfluxDB** | `localhost:8086` | Time-series metrics |
| **Telegram** | Bot API | Notifications to Mike |
| **GitHub** | REST API | Repo scanning, commits |
| **PLane/Notion** | API | Document generation |
| **LangFuse** | API | LLM observability |
| **Flowise** | `localhost:3000` | Visual workflow builder |
| **n8n** | `localhost:5678` | Automation workflows |

---

## 🚀 Quick Commands

```bash
# Start Celery worker
cd /opt/master_of_puppets
celery -A celery_app worker --loglevel=info

# Start Celery beat (scheduled tasks)
celery -A celery_app beat --loglevel=info

# Monitor tasks
celery -A celery_app flower

# Check worker status
celery -A celery_app inspect active

# Test specific task
python -c "from workers.conductor_tasks import health_check; print(health_check.delay())"
```

---

## 📝 Next Steps

1. [ ] Wire Hammurabi into all worker output paths
2. [ ] Connect to Mike's Brain (Neon) for persistent storage
3. [ ] Add VCU (Visual Computer Use) as new worker
4. [ ] Implement Edison (idea extraction from logs)
5. [ ] Set up Prometheus (training data capture)

---

*Last updated: 2026-02-04*
