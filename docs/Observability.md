# Observability Guide

> **Two systems, one goal:** see what's happening across every FactoryLM service in real time.

---

## 1. Overview

FactoryLM uses a **two-system observability stack**:

| Concern | Tool | What it captures |
|---------|------|-----------------|
| **Logs** | [Axiom](https://axiom.co) | Structured stdout/stderr from all services via Vector shippers |
| **Traces** | [Honeycomb](https://honeycomb.io) | Distributed traces (spans, latency, error waterfalls) via OpenTelemetry SDKs |

**Why two systems?**
- Logs answer "what happened" — searchable text, alerts on patterns.
- Traces answer "how long did it take and where did it slow down" — request waterfalls, dependency graphs, P99 latency.

Both run simultaneously and do not interfere with each other.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Observability Backends                         │
│                                                                             │
│   ┌───────────────────────┐          ┌────────────────────────────────────┐ │
│   │       Axiom           │          │           Honeycomb                │ │
│   │   (Log Aggregation)   │          │     (Distributed Tracing)         │ │
│   │                       │          │                                    │ │
│   │  Dataset:             │          │  Datasets (auto-created):         │ │
│   │    factorylm-logs     │          │    openclaw-ultron                │ │
│   │                       │          │    openclaw-jarvis-legacy         │ │
│   │                       │          │    openclaw-jarvis-local          │ │
│   │                       │          │    plc-modbus                     │ │
│   │                       │          │    plc-copilot                    │ │
│   └───────────▲───────────┘          └──────────▲─────────▲─────────────┘ │
└───────────────┼──────────────────────────────────┼─────────┼───────────────┘
                │                                  │         │
         Vector shipper                     OTLP/HTTP    OTLP/HTTP
         (stdout → Axiom)                  (protobuf)   (protobuf)
                │                                  │         │
┌───────────────┼──────────────────────────────────┼─────────┼───────────────┐
│               │            Services              │         │               │
│               │                                  │         │               │
│  ┌────────────┴──────────┐  ┌────────────────────┴───┐  ┌──┴────────────┐ │
│  │  OpenClaw Instances   │  │   plc-modbus (Python)  │  │ plc-copilot   │ │
│  │  (Node.js)            │  │   FastAPI backend      │  │ (Python)      │ │
│  │                       │  │                        │  │ Telegram bot  │ │
│  │  tracing.js loaded    │  │  factorylm.observ-     │  │ factorylm.    │ │
│  │  via NODE_OPTIONS     │  │  ability module        │  │ observability │ │
│  │                       │  │                        │  │ module        │ │
│  │  ultron / jarvis-     │  │  init_tracing(         │  │ init_tracing( │ │
│  │  legacy / jarvis-     │  │    "plc-modbus")       │  │  "plc-copilot"│ │
│  │  local                │  │                        │  │  )            │ │
│  └───────────────────────┘  └────────────────────────┘  └───────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Axiom (Logs)

### What it does
Axiom ingests structured logs from all services. [Vector](https://vector.dev/) shippers run on each host, tailing stdout/stderr and forwarding to Axiom's ingest API.

### Dataset
- **`factorylm-logs`** — all services log here, tagged by `service` field.

### Querying logs
1. Go to [app.axiom.co](https://app.axiom.co) → **Datasets** → `factorylm-logs`
2. Use APL (Axiom Processing Language):
   ```
   ['factorylm-logs']
   | where service == "plc-modbus"
   | where severity == "error"
   | order by _time desc
   | take 50
   ```

### Dashboard
Axiom dashboards are configured in the Axiom UI. Check the team's shared dashboards for pre-built views.

---

## 4. Honeycomb (Traces)

### What it does
Honeycomb receives OpenTelemetry spans from all instrumented services. Each service creates a **dataset** automatically (named after `OTEL_SERVICE_NAME`).

### SDK approach

| Language | Services | SDK |
|----------|----------|-----|
| **Node.js** | OpenClaw (3 instances) | `@opentelemetry/sdk-node` auto-instrumentation via `tracing.js` |
| **Python** | plc-modbus, plc-copilot | `factorylm.observability` module (manual spans) |

### Datasets
Datasets are auto-created by Honeycomb when the first span arrives:
- `openclaw-ultron`, `openclaw-jarvis-legacy`, `openclaw-jarvis-local` — Node.js bots
- `plc-modbus` — PLC Modbus FastAPI service
- `plc-copilot` — Telegram photo-to-CMMS bot

### Free tier limits
- **20 million events/month** (more than enough for current usage)
- Monitor at: Honeycomb UI → **Account** → **Usage**

### Viewing traces
1. Go to [ui.honeycomb.io](https://ui.honeycomb.io)
2. Select a dataset (e.g. `plc-modbus`)
3. **New Query** → Run to see recent traces
4. Click any trace to see the span waterfall

---

## 5. Python Instrumentation — `factorylm.observability`

### Installation

```bash
# Install core with OTel support
pip install -e "core/[otel]"

# Or install OTel packages manually
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

> **Graceful fallback:** If OTel packages are not installed, all helpers become no-ops. The application will never crash due to missing tracing dependencies.

### Quick start

```python
from factorylm.observability import init_tracing

# Call once at startup — reads HONEYCOMB_API_KEY from env
init_tracing("my-service")
```

### Decorating functions with spans

```python
from factorylm.observability import traced

@traced
def sync_work():
    """Automatically wrapped in a span named 'sync_work'."""
    ...

@traced(span_name="gemini-vision-call")
async def analyze_image(data: bytes):
    """Custom span name."""
    ...
```

### Manual spans

```python
from factorylm.observability import create_span

with create_span("expensive-operation", {"input_size": "1024"}):
    result = do_heavy_computation()
```

### Structured events

```python
from factorylm.observability import record_event

record_event("deploy", {
    "sha": "abc123",
    "deployer": "mike",
})
# Automatically includes service_name, repo_name, environment
```

### Health check

```python
from factorylm.observability import tracing_health

status = tracing_health()
# {"enabled": True, "service_name": "plc-modbus", "endpoint": "https://api.honeycomb.io:443", ...}
```

---

## 6. Node.js Instrumentation

The OpenClaw bot instances use `scripts/honeycomb/tracing.js`, loaded before the process starts via `NODE_OPTIONS=-r /path/to/tracing.js`.

### Setup scripts
| Script | Platform | Purpose |
|--------|----------|---------|
| `scripts/honeycomb/setup-vps.sh` | Linux VPS | Installs deps, copies tracing.js, configures systemd |
| `scripts/honeycomb/setup-local.ps1` | Windows | Installs deps, copies tracing.js, sets env vars |
| `scripts/honeycomb/install-deps.sh` | Linux | Installs OTel npm packages globally |
| `scripts/honeycomb/install-deps.ps1` | Windows | Installs OTel npm packages globally |

### How it works
1. `tracing.js` checks for `HONEYCOMB_API_KEY` — if missing, tracing is disabled (no crash)
2. Initialises `@opentelemetry/sdk-node` with auto-instrumentation (HTTP, Express, DNS)
3. Exports spans via OTLP/HTTP to `https://api.honeycomb.io:443`
4. Each instance identifies itself via `OTEL_SERVICE_NAME` resource attribute

Full details: [`scripts/honeycomb/README.md`](../scripts/honeycomb/README.md)

---

## 7. Environment Variables

| Variable | Used by | Example | Description |
|----------|---------|---------|-------------|
| `HONEYCOMB_API_KEY` | All | `hcaik_abc123...` | Honeycomb ingest API key |
| `OTEL_SERVICE_NAME` | All | `plc-modbus` | Service name (becomes dataset in Honeycomb) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | All | `https://api.honeycomb.io:443` | OTLP collector endpoint |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Node.js | `http/protobuf` | Wire format (Python always uses HTTP) |
| `OTEL_EXPORTER_OTLP_HEADERS` | Node.js | `x-honeycomb-team=hcaik_...` | Auth header (Python sets this internally) |
| `OTEL_DEPLOYMENT_ENVIRONMENT` | All | `production` | Environment tag on all spans |
| `OTEL_INSTANCE_NAME` | Node.js | `ultron` | Human-friendly instance tag |
| `NODE_OPTIONS` | Node.js | `-r /root/.openclaw/tracing.js` | Preloads the tracing bootstrap |
| `AXIOM_API_KEY` | Vector | `xaat_...` | Axiom ingest API key |
| `AXIOM_DATASET` | Vector | `factorylm-logs` | Target Axiom dataset |

---

## 8. Doppler Integration

All API keys (`HONEYCOMB_API_KEY`, `AXIOM_API_KEY`) should be stored in **Doppler** and injected at runtime. Never hard-code secrets.

- See [docs/Config.md](Config.md) for Doppler setup and project configuration.
- Doppler project: `factorylm`
- Environments: `development`, `staging`, `production`

To run a service with Doppler-injected secrets:
```bash
doppler run --project factorylm --config production -- python -m uvicorn backend.main:app
```

---

## 9. Runbooks

### "No traces appearing in Honeycomb"

1. **Check the API key:**
   ```bash
   echo $HONEYCOMB_API_KEY          # should start with hcaik_
   ```
2. **Check the init log message:**
   - Python: look for `[observability] ✓ Tracing started`
   - Node.js: look for `[tracing] ✓  OpenTelemetry started`
3. **Verify the key works:**
   ```bash
   curl -v https://api.honeycomb.io/1/events/test \
     -H "X-Honeycomb-Team: $HONEYCOMB_API_KEY" \
     -d '{}'
   ```
   Should return `200 OK`.
4. **Check firewall:** outbound HTTPS to `api.honeycomb.io:443` must be allowed.
5. **Wait 2–3 minutes:** spans are batched before export.

### "High event volume / approaching 20M limit"

1. Check usage: Honeycomb UI → **Account** → **Usage**
2. **Python:** Remove `@traced` from high-frequency functions, use sampling.
3. **Node.js:** Disable noisy auto-instrumentations in `tracing.js`:
   ```js
   '@opentelemetry/instrumentation-fs': { enabled: false },
   '@opentelemetry/instrumentation-dns': { enabled: false },
   ```
4. Consider adding a sampling ratio via `OTEL_TRACES_SAMPLER_ARG` (e.g. `0.1` for 10%).

### "Service not reporting"

1. **Check if OTel packages are installed:**
   ```bash
   # Python
   pip show opentelemetry-api

   # Node.js
   npm ls -g @opentelemetry/sdk-node
   ```
2. **Check the health endpoint (plc-modbus):**
   ```bash
   curl http://localhost:8000/api/tracing-health
   # Returns: {"enabled": true, "service_name": "plc-modbus", ...}
   ```
3. **If `enabled: false`:** the API key is missing or OTel packages aren't installed.
4. **Restart the service** after setting environment variables.

---

## 10. Cost Management

### Honeycomb free tier
- **20 million events/month** — shared across all datasets
- No credit card required
- Data retention: 60 days

### Tips to reduce volume
1. **Don't trace health checks** in production (or sample them heavily)
2. **Disable noisy auto-instrumentations** (fs, dns) in Node.js `tracing.js`
3. **Use `@traced` selectively** — only on business-critical functions
4. **Batch size:** the default `BatchSpanProcessor` batches spans efficiently
5. **Monitor monthly usage:** set a Honeycomb budget alert at 15M events

### Axiom costs
Axiom pricing is separate. Vector shippers are configured to only forward `INFO` and above by default to limit log volume.

---

## Quick Reference

```bash
# Check if tracing is working (plc-modbus)
curl http://localhost:8000/api/tracing-health

# Install Python OTel packages
pip install -e "core/[otel]"

# Verify Honeycomb connectivity
curl https://api.honeycomb.io/1/events/test \
  -H "X-Honeycomb-Team: $HONEYCOMB_API_KEY" -d '{}'
```
