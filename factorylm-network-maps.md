# FactoryLM — Network Maps & Resource Topology

**Generated:** 2026-02-17  
**Repo:** [github.com/Mikecranesync/factorylm](https://github.com/Mikecranesync/factorylm)

---

## 1. Physical Network & Tailscale Mesh

All machines connected via Tailscale mesh VPN.

```mermaid
flowchart TB
    subgraph tailscale["TAILSCALE MESH VPN"]
        direction TB

        subgraph vps["VPS - DigitalOcean (100.68.120.99)"]
            remoteme["RemoteMe API :8100"]
            friday["Friday Bot (Telegram)"]
            n8n["n8n Workflows :5678"]
            flowise["Flowise LLM Flows :3000"]
            mop["Master of Puppets (Celery)"]
            plane["Plane PM :8000"]
            openclaw_u["OpenClaw ultron Bot"]
        end

        subgraph laptop["Travel Laptop (100.83.251.23)"]
            claude_code["Claude Code + Antfarm"]
            caps_client["Capabilities API Client"]
            factorylm_dev["FactoryLM Monorepo Dev"]
            openclaw_l["OpenClaw jarvis-local Bot"]
            jarvis_node_t["Jarvis Node :8765"]
        end

        subgraph plclaptop["PLC Laptop (100.72.2.99)"]
            factoryio["Factory I/O Simulation"]
            micro820["Allen-Bradley Micro 820 PLC"]
            jarvis_node_p["Jarvis Node :8765"]
        end

        subgraph hetzner["Hetzner VPS (46.225.103.156)"]
            hetzner_pending["Pending Migration Setup"]
        end

        subgraph hostinger["Hostinger VPS (72.60.175.144) — DECOMMISSIONING"]
            legacy_bot["jarvis-legacy Bot"]
            rivet_pro["Rivet-PRO"]
        end
    end

    subgraph mobile["Mobile (Mike's Phone)"]
        telegram_app["Telegram App"]
    end

    telegram_app -->|"@UltronVPS_bot"| openclaw_u
    telegram_app -->|"@TravelLaptop_bot"| openclaw_l
    telegram_app -->|"@FridayAssistBot"| friday

    claude_code -->|"SSH/Tailscale"| remoteme
    caps_client -->|"HTTP :8765"| jarvis_node_p
    jarvis_node_p -->|"Modbus TCP :502"| micro820
    jarvis_node_p -->|"Modbus TCP"| factoryio
```

### Machine Inventory

| Machine | Tailscale IP | Role | Key Services |
|---------|-------------|------|-------------|
| **DO VPS** | 100.68.120.99 | Production server | RemoteMe, Friday Bot, n8n, Flowise, Plane, OpenClaw ultron |
| **Travel Laptop** | 100.83.251.23 | Development | Claude Code, Antfarm, OpenClaw jarvis-local |
| **PLC Laptop** | 100.72.2.99 | Hardware interface | Factory I/O, Micro 820 PLC, Jarvis Node |
| **Hetzner VPS** | 46.225.103.156 | Migration target | Fresh — pending setup |
| **Hostinger VPS** | 72.60.175.144 | Legacy (decommissioning) | jarvis-legacy, Rivet-PRO |

---

## 2. 4-Layer Intelligence Stack & LLM Routing

Intelligence flows **downward** — the goal is LESS AI over time.

```mermaid
flowchart TB
    query["Incoming Query (Telegram/WhatsApp)"]

    query --> router["Message Router"]

    router --> L0
    router --> L1
    router --> L2
    router --> L3

    subgraph L0["LAYER 0 — Deterministic Code + KB (<100ms, $0)"]
        vectordb["Vector DB (semantic search)"]
        workflows["Workflow Engine (captured patterns)"]
        logicgates["Logic Gates (pattern-matched)"]
        plane_kb["Plane (task orchestration)"]
        wiseflow["Wiseflow (auto-indexing)"]
    end

    subgraph L1["LAYER 1 — Edge LLM (0.5-1s, free)"]
        qwen["Qwen 0.5B (on Raspberry Pi)"]
        tinyllama["TinyLlama (on VPS Ollama)"]
    end

    subgraph L2["LAYER 2 — Local GPU (2-3s, electricity only)"]
        llama70b["Llama 70B (local GPU server)"]
        ollama["Ollama (qwen2.5, tinyllama on VPS)"]
    end

    subgraph L3["LAYER 3 — Cloud AI (1-2s, $$)"]
        groq["Groq (llama-3.3-70b) — FREE"]
        claude["Anthropic Claude Sonnet/Opus — $$$"]
        deepseek["DeepSeek Chat — $"]
        gemini["Google Gemini 2.5 Flash — $"]
        openrouter["OpenRouter — pay-per-use"]
    end

    L0 -->|"confidence > 0.9"| instant_answer["Instant Answer"]
    L1 -->|"simple commands"| answer1["Edge Response"]
    L2 -->|"medium complexity"| answer2["Local Response"]
    L3 -->|"novel / complex"| answer3["Cloud Response"]
```

### Routing Logic (Pseudocode)

```python
def route_query(query, context):
    kb_result = knowledge_base.search(query)
    if kb_result.confidence > 0.9:
        return kb_result                    # Layer 0 — instant, free

    workflow = plane.match_workflow(query)
    if workflow:
        return workflow.execute()           # Layer 0 — instant, free

    if is_simple_command(query):
        return edge_llm.process(query)      # Layer 1 — 0.5s, free

    if gpu_server.available:
        return gpu_server.process(query)    # Layer 2 — 2-3s, electricity

    if cloud.available and not air_gapped:
        return cloud.process(query)         # Layer 3 — 1-2s, $$$
```

---

## 3. External Services & API Dependency Map

```mermaid
flowchart LR
    subgraph secrets["SECRET MANAGEMENT"]
        doppler["Doppler (5 projects)"]
    end

    subgraph observability["OBSERVABILITY"]
        axiom["Axiom (logs via Vector)"]
        honeycomb["Honeycomb (traces via OTel)"]
    end

    subgraph llm_providers["LLM PROVIDERS"]
        groq["Groq API (free)"]
        anthropic["Anthropic API"]
        deepseek_api["DeepSeek API"]
        gemini_api["Google Gemini API"]
        openrouter_api["OpenRouter API"]
        ollama_local["Ollama (local models)"]
    end

    subgraph messaging["MESSAGING"]
        telegram_api["Telegram Bot API"]
        whatsapp["WhatsApp (planned)"]
    end

    subgraph infra["INFRASTRUCTURE"]
        tailscale["Tailscale Mesh VPN"]
        github["GitHub (CI + repos)"]
        neon_pg["Neon PostgreSQL"]
        supabase["Supabase BaaS"]
    end

    subgraph cmms_ext["MAINTENANCE"]
        atlas_cmms["Atlas CMMS API"]
    end

    subgraph services["FACTORYLM SERVICES"]
        core["core/ (LLM abstraction)"]
        plc_modbus["plc-modbus (FastAPI)"]
        plc_copilot["plc-copilot (Telegram bot)"]
        openclaw["OpenClaw Bots (3 instances)"]
        my_ralph["My-Ralph (dev loop)"]
        cosmos_agent["Cosmos Agent (stub)"]
    end

    core --> groq
    core --> anthropic
    core --> deepseek_api

    plc_copilot --> telegram_api
    plc_copilot --> gemini_api
    plc_copilot --> atlas_cmms

    openclaw --> groq
    openclaw --> anthropic
    openclaw --> openrouter_api
    openclaw --> gemini_api
    openclaw --> ollama_local
    openclaw --> telegram_api

    my_ralph --> neon_pg
    my_ralph --> supabase
    my_ralph --> github

    plc_modbus --> honeycomb
    plc_copilot --> honeycomb
    openclaw --> honeycomb
    openclaw --> axiom

    doppler -.->|"injects env vars"| core
    doppler -.->|"injects env vars"| plc_modbus
    doppler -.->|"injects env vars"| plc_copilot
    doppler -.->|"injects env vars"| openclaw

    tailscale -.->|"connects machines"| plc_modbus
```

### Environment Variables by Service

| Service | Required Env Vars |
|---------|------------------|
| **core/** | `GROQ_API_KEY`, `CLAUDE_API_KEY` (opt), `DEEPSEEK_API_KEY` (opt) |
| **plc-modbus/** | `PLC_HOST`, `PLC_PORT`, `HONEYCOMB_API_KEY` (opt) |
| **plc-copilot/** | `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `CMMS_API_URL`, `CMMS_USERNAME`, `CMMS_PASSWORD` |
| **OpenClaw** | `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `HONEYCOMB_API_KEY`, `AXIOM_TOKEN` |

### Doppler Projects

| Project | Covers |
|---------|--------|
| `factorylm-core` | LLM abstraction layer |
| `factorylm-plc` | PLC Modbus service |
| `factorylm-copilot` | Telegram photo bot |
| `factorylm-infra` | Shared infra keys (Axiom, Honeycomb) |
| `openclaw` | OpenClaw bot instances |

---

## 4. PLC Data Flow — Telegram → Diagnosis → PLC

End-to-end path for a diagnostic query.

```mermaid
sequenceDiagram
    participant User as Mike (Telegram)
    participant Bot as Friday Bot / OpenClaw (VPS)
    participant Router as LLM Router
    participant Caps as Capabilities API
    participant JNode as Jarvis Node (PLC Laptop)
    participant PLC as Micro 820 PLC
    participant LLM as LLM (Claude/Groq)
    participant HC as Honeycomb Traces

    User->>Bot: "Why is the conveyor stopped?"
    Bot->>Router: Classify intent + pick tier
    Router->>Caps: factory.diagnose(query)
    Caps->>JNode: HTTP GET /plc/read (Tailscale :8765)
    JNode->>PLC: Modbus TCP read_coils, read_registers (:502)
    PLC-->>JNode: Tag values (E-STOP=1, Motor=0, Fault=23)
    JNode-->>Caps: PLC state JSON
    Caps->>LLM: "Interpret these PLC values: ..."
    LLM-->>Caps: "E-STOP is triggered. Fault 23 = overtemp"
    Caps-->>Bot: Diagnosis response
    Bot-->>User: "🔴 E-STOP triggered. Fault 23: overtemp on conveyor motor"
    Bot->>HC: Export trace spans (OTLP/HTTP)
```

### Supported PLC Protocols

| Protocol | Devices | Status |
|----------|---------|--------|
| Modbus TCP/RTU | Universal | ✅ Working |
| EtherNet/IP | Allen-Bradley | Planned |
| Siemens S7 | S7-300/400/1200/1500 | Planned |
| OPC UA | Universal | Planned |

---

## 5. Observability Pipeline

Two systems: **Axiom** (logs) + **Honeycomb** (traces).

```mermaid
flowchart TB
    subgraph services["INSTRUMENTED SERVICES"]
        oc_ultron["OpenClaw ultron (Node.js)"]
        oc_legacy["OpenClaw jarvis-legacy (Node.js)"]
        oc_local["OpenClaw jarvis-local (Node.js)"]
        plc_mod["plc-modbus (Python/FastAPI)"]
        plc_cop["plc-copilot (Python)"]
    end

    subgraph tracing_sdk["TRACING INSTRUMENTATION"]
        nodejs_otel["tracing.js (NODE_OPTIONS preload)"]
        python_otel["factorylm.observability.init_tracing()"]
    end

    subgraph log_shippers["LOG SHIPPERS"]
        vector_do["Vector (DO VPS systemd)"]
        vector_host["Vector (Hostinger systemd)"]
        ps_shipper["PowerShell Shipper (Windows)"]
    end

    subgraph backends["OBSERVABILITY BACKENDS"]
        honeycomb["Honeycomb (20M events/mo free)"]
        axiom["Axiom (APL query engine)"]
    end

    subgraph datasets_hc["HONEYCOMB DATASETS"]
        ds_ultron["openclaw-ultron"]
        ds_legacy["openclaw-jarvis-legacy"]
        ds_local["openclaw-jarvis-local"]
        ds_plc["plc-modbus"]
        ds_cop["plc-copilot"]
    end

    subgraph datasets_ax["AXIOM DATASETS"]
        ax_logs["factorylm-logs"]
    end

    oc_ultron --> nodejs_otel
    oc_legacy --> nodejs_otel
    oc_local --> nodejs_otel
    plc_mod --> python_otel
    plc_cop --> python_otel

    nodejs_otel -->|"OTLP/HTTP protobuf"| honeycomb
    python_otel -->|"OTLP/HTTP"| honeycomb

    honeycomb --> ds_ultron
    honeycomb --> ds_legacy
    honeycomb --> ds_local
    honeycomb --> ds_plc
    honeycomb --> ds_cop

    oc_ultron -->|stdout| vector_do
    oc_legacy -->|stdout| vector_host
    oc_local -->|stdout| ps_shipper
    plc_mod -->|stdout| vector_do

    vector_do -->|"HTTP ingest"| axiom
    vector_host -->|"HTTP ingest"| axiom
    ps_shipper -->|"HTTP ingest"| axiom

    axiom --> ax_logs
```

### Quick Health Checks

```bash
# Check tracing (plc-modbus)
curl http://localhost:8000/api/tracing-health

# Check VPS log shippers
ssh root@100.68.120.99 "systemctl status vector"

# Verify Honeycomb key
curl https://api.honeycomb.io/1/events/test \
  -H "X-Honeycomb-Team: $HONEYCOMB_API_KEY" -d '{}'
```

---

## 6. Monorepo Component Maturity Map

```mermaid
flowchart TB
    subgraph production["✅ PRODUCTION"]
        core["core/ (Python)\n148 tests\nGroq/Claude/DeepSeek clients"]
        ralph["my-ralph/ (Bash+Python)\n321 tests\nAutonomous dev loop"]
    end

    subgraph working["✅ WORKING"]
        plc_modbus["services/plc-modbus/ (Python)\nFastAPI + Modbus TCP\nMicro 820 + FactoryIO + Mock"]
        plc_copilot["services/plc-copilot/ (Python)\nTelegram bot\nGemini Vision + Atlas CMMS"]
        diagnosis["services/diagnosis/ (Python)\nPLC to LLM bridge\nuvicorn :8200"]
        pi_edge["plc-modbus/factorylm-edge/\nRaspberry Pi edge server"]
    end

    subgraph forked["⚠️ FORKED / PARTIAL"]
        cmms_api["apps/cmms/api/\nJava Spring Boot\n650 .java files"]
        cmms_fe["apps/cmms/frontend/\nReact 18 + MUI + TS\n169 .ts files"]
        portal["apps/portal/\nExpress.js\nVPS brain viewer"]
        cosmos["cosmos/agent.py\nNVIDIA Cosmos stub"]
    end

    subgraph placeholder["🔴 PLACEHOLDER (NOT_IMPLEMENTED.md)"]
        dashboard["apps/dashboard/"]
        web["apps/web/"]
        svc_api["services/api/"]
        assistant["services/assistant/"]
        auth["packages/auth/"]
        db["packages/db/"]
        ui["packages/ui/"]
    end

    subgraph deprecated["⛔ DEPRECATED"]
        plc_v1["plc-client/ (V1)"]
        plc_v2["plc-client-factoryio/ (V2)"]
    end

    plc_modbus -->|"uses"| core
    plc_copilot -->|"uses"| core
    diagnosis -->|"uses"| core
    pi_edge -->|"uses"| plc_modbus
    cmms_fe -->|"calls"| cmms_api
    plc_copilot -->|"calls"| cmms_api

    plc_v1 -.->|"superseded by"| plc_modbus
    plc_v2 -.->|"superseded by"| plc_modbus
```

### Test Commands

```bash
cd core && pytest                    # 148 tests
cd my-ralph && npm test              # 321 tests
cd services/plc-modbus && pytest     # 162 tests
```

---

## 7. Voltron Architecture (PLANNED)

Distributed Matrix + Nodes system — not yet implemented.

```mermaid
flowchart TB
    subgraph matrix["MATRIX (VPS)"]
        tg_bot["Telegram Bot"]
        llm_router["LLM Router (Tier 1/2)"]
        node_reg["Node Registry"]
        pg["PostgreSQL (memory, state)"]
    end

    tg_bot --> llm_router
    llm_router --> node_reg
    node_reg --> pg

    subgraph nodes["DISTRIBUTED NODES"]
        plc_node["Node: plc-micro820\n(Laptop → Modbus TCP)\nread_coils, read_registers"]
        vps_node["Node: vps-worker\n(DO VPS)\nsearch_kb, run_diagnostic"]
        dev_node["Node: dev-local\n(Laptop)\nAll tools (dev mode)"]
    end

    node_reg -->|"task dispatch"| plc_node
    node_reg -->|"task dispatch"| vps_node
    node_reg -->|"task dispatch"| dev_node

    plc_node -->|"heartbeat"| node_reg
    vps_node -->|"heartbeat"| node_reg
    dev_node -->|"heartbeat"| node_reg
```

Each node has immutable `soul.md` (identity) and `policy.yaml` (allowed tools, read-only PLC constraint).

---

*Generated from the FactoryLM monorepo — [README.md](https://github.com/Mikecranesync/factorylm/blob/main/README.md) is the canonical vision.*
