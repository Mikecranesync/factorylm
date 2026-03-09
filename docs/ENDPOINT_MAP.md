# FactoryLM Endpoint Map

> Tagged reference for all data streams and API endpoints.
> Use tags like `[PLC-IO]` or `[DIAG-ASK]` to reference specific endpoints.

---

## Data Flow (the main pipeline)

```
Phone/Telegram
  |
  v
[GW-MSG] OpenClaw :8340/api/v1/message
  |
  v
[DIAG-ASK] Diagnosis :8200/diagnose
  |           |
  |           v
  |     [PLC-STATUS] plc-modbus :8001/api/plc/status
  |     [PLC-IO]     plc-modbus :8001/api/plc/io
  |           |
  |           v  (Modbus TCP :502 or MockPLC)
  |           Micro 820 + VFD + Conveyor
  |
  v
[LLM-ROUTE] llm-router :8100/v1/chat/completions
  |
  v  (Groq → DeepSeek → OpenRouter → Cerebras)
AI Diagnosis Response
```

---

## 1. plc-modbus — `:8001` (PLC Laptop `100.72.2.99`)

The hardware layer. Reads/writes the Micro 820 via Modbus TCP. Mock mode simulates everything.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[PLC-STATUS]` | GET | `/api/plc/status` | Connection state: `{connected, ip, port, last_seen}` |
| `[PLC-IO]` | GET | `/api/plc/io` | **All I/O**: coils (Conveyor, Emitter, SensorStart, SensorEnd, RunCommand), inputs (DI_00-DI_07), outputs (DO_00-DO_03), registers (ItemCount + 5 VFD regs), timestamp |
| `[PLC-CONNECT]` | POST | `/api/plc/connect` | Body: `{ip, port}`. Establishes Modbus TCP or MockPLC connection |
| `[PLC-WRITE]` | POST | `/api/plc/write-coil` | Body: `{address, value}`. Writable: 0,1,4,5,6,15,16,17 |
| `[PLC-FAULT]` | POST | `/api/plc/mock/fault` | Body: `{fault_type}`. Types: `overload`, `overheat`, `jam`, `sensor`, `estop`, `clear`. Mock mode only |
| `[PLC-SCAN]` | POST | `/api/setup/scan-network` | Scans subnet for Modbus devices on port 502 |
| `[PLC-DEVICES]` | GET | `/api/devices` | EtherNet/IP discovered devices list |
| `[PLC-TAGS]` | GET | `/api/devices/{ip}/tags` | Tags for a specific discovered device |
| `[PLC-STREAM]` | GET | `/api/stream` | **SSE** — pushes all device tags every 500ms |
| `[PLC-WS]` | WS | `/ws/io` | **WebSocket** — PLC I/O at 100ms intervals |
| `[PLC-HEALTH]` | GET | `/api/health` | `{status, version}` |
| `[PLC-DASH]` | GET | `/` | Pi Factory dashboard HTML (SSE-driven live tag browser) |

### `[PLC-IO]` Response Shape (the most important one)
```json
{
  "coils":     {"Conveyor": bool, "Emitter": bool, "SensorStart": bool, "SensorEnd": bool, "RunCommand": bool, "program_var_5": bool, "program_var_6": bool},
  "inputs":    {"DI_00": bool, "DI_01": bool, "DI_02": bool, "DI_03": bool, "DI_04": bool, "DI_05": bool, "DI_06": bool, "DI_07": bool},
  "outputs":   {"DO_00": bool, "DO_01": bool, "DO_03": bool},
  "registers": {"ItemCount": int, "register_101": int, "register_102": int, "register_103": int, "register_104": int, "register_105": int},
  "timestamp": "ISO-8601"
}
```

---

## 2. diagnosis — `:8200` (VPS or local)

The brain. Reads PLC state, formats it for an LLM, gets a diagnosis.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[DIAG-ASK]` | POST | `/diagnose` | Body: `{question}`. Returns `{question, diagnosis, plc_data, timestamp, latency_ms}`. Calls `[PLC-STATUS]` + `[PLC-IO]` + `[LLM-ROUTE]` (or direct Groq fallback) |
| `[DIAG-NET]` | GET | `/network` | Pings PLC laptop + travel laptop Jarvis nodes, reports online/offline |
| `[DIAG-FAULT]` | POST | `/fault-inject` | Body: `{fault_type}`. Proxies to `[PLC-FAULT]` |
| `[DIAG-SIM]` | GET | `/sim` | Simulation dashboard HTML (polls `[PLC-IO]`, calls `[DIAG-ASK]`, controls via `[PLC-WRITE]` + `[DIAG-FAULT]`) |
| `[DIAG-HEALTH]` | GET | `/health` | `{status, service, timestamp, llm_configured}` |

### `[DIAG-ASK]` Upstream Call Chain
```
1. GET  [PLC-STATUS]  → is PLC connected?
2. GET  [PLC-IO]      → read all coils + registers
3. format_plc_io_for_llm() → human-readable text
4. POST [LLM-ROUTE]   → try llm-router (8 providers)
   OR   direct Groq   → fallback if router is down
   OR   raw PLC text   → fallback if all LLMs fail
```

---

## 3. llm-router — `:8100` (VPS or local)

Multi-provider LLM gateway. Budget tracking, circuit breakers, task-type routing.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[LLM-ROUTE]` | POST | `/v1/chat/completions` | OpenAI-compatible. Body: `{model, messages, temperature, max_tokens, task_type, prefer_provider}`. Returns `{choices, usage, x_provider}` |
| `[LLM-HEALTH]` | GET | `/health` | All provider statuses: budget used/remaining, circuit state, API key present |
| `[LLM-STATS]` | GET | `/health/stats` | Redis usage stats |

### `[LLM-ROUTE]` Provider Priority by task_type
| task_type | Provider order |
|-----------|---------------|
| `fast` | groq-kimi → groq-llama70b → deepseek |
| `reasoning` | deepseek-reasoner → groq-qwen3 → openrouter-hermes |
| `structured` | groq-kimi → deepseek → groq-llama70b |
| `coding` | groq-kimi → deepseek → groq-qwen3 |
| (none) | round-robin all 8 providers |

---

## 4. matrix — `:8000` (PLC Laptop `100.72.2.99`)

Time-series tag store + incident tracker + Cosmos AI insights. SQLite backend.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[MTX-TAGS-POST]` | POST | `/api/tags` | Ingest structured tag snapshot. Auto-creates incident on fault/e-stop |
| `[MTX-TAGS-GET]` | GET | `/api/tags` | Query tags. Params: `limit`, `node_id` |
| `[MTX-LIVE-POST]` | POST | `/api/tags/live` | Ingest raw Micro 820 I/O JSON (any shape) |
| `[MTX-LIVE-GET]` | GET | `/api/tags/live` | Latest live I/O snapshot |
| `[MTX-INCIDENTS]` | GET | `/api/incidents` | Incident list. Params: `status`, `limit` |
| `[MTX-INCIDENT]` | GET | `/api/incidents/{id}` | Single incident + Cosmos insight |
| `[MTX-INSIGHTS]` | POST | `/api/insights` | Store Cosmos analysis for an incident |
| `[MTX-CLIPS]` | POST | `/api/video/clips` | Register video clip |
| `[MTX-CLIPS-GET]` | GET | `/api/video/clips` | Video clip list. Params: `status`, `limit` |
| `[MTX-ANALYSIS]` | POST | `/api/video/analyses` | Store video analysis |
| `[MTX-DASH]` | GET | `/` | Cosmos Cookoff dashboard HTML |
| `[MTX-VIDEO]` | GET | `/video` | Video log viewer HTML |

---

## 5. conveyor-relay — `:8400` (VPS `100.68.120.99`)

Public-facing proxy between internet and PLC laptop. Rate-limited (1 cmd / 3 sec).

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[RELAY-CMD]` | POST | `/api/command` | Body: `{action, value}`. Actions: `forward`, `reverse`, `stop`, `set_speed`. Proxies to conveyor-lab backend `:3001` |
| `[RELAY-STATUS]` | GET | `/api/status` | Proxied conveyor status + command count |
| `[RELAY-CAM]` | GET | `/api/stream` | **MJPEG stream** — proxies webcam from PLC laptop `:8081` |
| `[RELAY-HMI]` | GET | `/` | Full HMI page: webcam + I/O rack + current gauge + LM chat + demo scenario |
| `[RELAY-HEALTH]` | GET | `/api/health` | Relay liveness |

---

## 6. conveyor-lab backend — `:3001` (PLC Laptop)

VFD control + telemetry + run logging. Express + TypeScript + SQLite.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[CONV-STATUS]` | GET | `/api/status` | VFD state: frequency, current, direction, running, faultCode |
| `[CONV-CMD]` | POST | `/api/command` | Body: `{action, value, runId}`. Actions: `start`, `stop`, `set_speed`, `set_direction`, `clear_fault`, `inject_fault` |
| `[CONV-RUNS]` | GET | `/api/runs` | Run history. Params: `limit`, `offset`, `tags`, `dateFrom`, `dateTo` |
| `[CONV-RUN]` | GET | `/api/runs/:id` | Run detail + telemetry + analysis + feedback + media |
| `[CONV-RUN-NEW]` | POST | `/api/runs` | Create + start a run (requires Telegram auth) |
| `[CONV-RUN-STOP]` | POST | `/api/runs/:id/stop` | Stop active run |
| `[CONV-FEEDBACK]` | POST | `/api/runs/:id/feedback` | Rate/tag a run |
| `[CONV-ANALYSIS]` | POST | `/api/runs/:id/model-analysis` | Store Cosmos analysis |
| `[CONV-WS]` | WS | `/ws/telemetry` | **WebSocket** — VFD telemetry at 100ms. Events: `status`, `telemetry`, `runComplete`, `error` |

---

## 7. openclaw gateway — `:8340` (VPS `100.68.120.99`) **⚠️ DEPRECATED**

> **Replaced by:** Telegram polling bot on CHARLIE (`services/troubleshoot/adapters/telegram_bot.py`).
> No public endpoint needed — bot pulls messages via `run_polling()`.
> See `[TG-POLL]` below.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[GW-MSG]` | POST | `/api/v1/message` | **DEPRECATED** — was Telegram webhook entry point |
| `[GW-HEALTH]` | GET | `/` | **DEPRECATED** — service info |

### 7b. Telegram Polling Bot (CHARLIE `100.82.246.52`)

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[TG-POLL]` | — | — | Polling-based Telegram bot. No inbound endpoint — pulls messages from Telegram API directly. Runs `services/troubleshoot/adapters/telegram_bot.py` |

---

## 8. brain (Open Brain) — `:8500` (Charlie node `192.168.1.12`)

Mem0 memory layer. Pgvector + Gemini embeddings.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[BRAIN-INGEST]` | POST | `/ingest` | Header: `X-Brain-Key`. Body: `{content, source, tags, metadata}`. Extracts memories via Mem0 |
| `[BRAIN-HEALTH]` | GET | `/health` | Liveness |

---

## 9. jarvis-node — `:8765` (both laptops)

Remote control agent. Full shell access, screenshots, file I/O, notifications.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[JARVIS-HEALTH]` | GET | `/health` | Machine name + capabilities |
| `[JARVIS-SHELL]` | POST | `/shell` | Body: `{command, timeout, cwd}`. Returns `{stdout, stderr, exit_code, duration_ms}` |
| `[JARVIS-SYSINFO]` | GET | `/system-info` | CPU%, memory, disk |
| `[JARVIS-SCREEN]` | GET | `/screenshot` | Base64 PNG screenshot |
| `[JARVIS-READ]` | POST | `/files/read` | Read any file |
| `[JARVIS-WRITE]` | POST | `/files/write` | Write any file |
| `[JARVIS-LS]` | GET | `/files/list` | Directory listing |
| `[JARVIS-NOTIFY]` | POST | `/notify` | Desktop toast/alert |
| `[JARVIS-MSG]` | POST | `/messages` | Push to message queue |
| `[JARVIS-MSG-GET]` | GET | `/messages` | Drain message queue |

---

## 10. webcam — `:8081` (PLC Laptop)

OpenCV MJPEG server. 640x480 @ 30fps.

| Tag | Method | Path | What it does |
|-----|--------|------|-------------|
| `[CAM-STREAM]` | GET | `/stream` | `multipart/x-mixed-replace` — raw MJPEG frames |

---

## Real-Time Streams (non-REST)

| Tag | Protocol | Service | Path | Rate | Payload |
|-----|----------|---------|------|------|---------|
| `[PLC-STREAM]` | SSE | plc-modbus :8001 | `/api/stream` | 500ms | All device tags JSON |
| `[PLC-WS]` | WebSocket | plc-modbus :8001 | `/ws/io` | 100ms | Full IOResponse |
| `[CONV-WS]` | WebSocket | conveyor-lab :3001 | `/ws/telemetry` | 100ms | VFD status + telemetry |
| `[RELAY-CAM]` | MJPEG | conveyor-relay :8400 | `/api/stream` | 30fps | Proxied webcam frames |
| `[CAM-STREAM]` | MJPEG | webcam :8081 | `/stream` | 30fps | Raw webcam frames |

---

## Network Map (quick reference)

| Host | IP | Services |
|------|----|----------|
| VPS (Jarvis) | `100.68.120.99` | ~~`[GW-MSG]` :8340~~ (deprecated), `[RELAY-*]` :8400 |
| CHARLIE (Mac Mini) | `100.82.246.52` | `[TG-POLL]` (polling), `[BRAIN-*]` :8500, Qdrant |
| PLC Laptop | `100.72.2.99` | `[PLC-*]` :8001, `[MTX-*]` :8000, `[CONV-*]` :3001, `[CAM-STREAM]` :8081, `[JARVIS-*]` :8765 |
| Travel Laptop | `100.83.251.23` | `[JARVIS-*]` :8765, dev work |
| BRAVO (Mac Mini) | `192.168.1.11` | Ollama (local LLM) |
| CHARLIE (Mac Mini) | `192.168.1.12` | `[BRAIN-*]` :8500, Qdrant |
| Local sim | `localhost` | `[PLC-*]` :8001, `[DIAG-*]` :8200, `[LLM-*]` :8100 |
