# Honeycomb OpenTelemetry — OpenClaw Bot Tracing

Distributed tracing for all 3 OpenClaw bot instances via [Honeycomb](https://www.honeycomb.io/) (free tier: **20M events/month**).

> **This complements the existing Axiom observability setup.** Axiom handles log aggregation via Vector shippers; Honeycomb adds distributed tracing (request latency, dependency graphs, error waterfall).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Honeycomb Cloud                              │
│                    https://ui.honeycomb.io                            │
│                                                                      │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│   │ openclaw-ultron  │  │openclaw-jarvis-  │  │openclaw-jarvis-  │  │
│   │    (dataset)     │  │ legacy (dataset) │  │  local (dataset) │  │
│   └────────▲─────────┘  └────────▲─────────┘  └────────▲─────────┘  │
└────────────┼─────────────────────┼─────────────────────┼─────────────┘
             │ OTLP/HTTP           │ OTLP/HTTP           │ OTLP/HTTP
             │ (protobuf)          │ (protobuf)          │ (protobuf)
             │                     │                     │
┌────────────┴───────┐  ┌─────────┴──────────┐  ┌───────┴────────────┐
│   DO VPS (ultron)  │  │ Hostinger (jarvis- │  │  Windows Local     │
│                    │  │      legacy)       │  │  (jarvis-local)    │
│  openclaw service  │  │  clawdbot service  │  │  openclaw.ps1      │
│  systemd + Node.js │  │  systemd + Node.js │  │  PowerShell        │
│                    │  │                    │  │                    │
│  tracing.js loaded │  │  tracing.js loaded │  │  tracing.js loaded │
│  via NODE_OPTIONS  │  │  via NODE_OPTIONS  │  │  via NODE_OPTIONS  │
└────────────────────┘  └────────────────────┘  └────────────────────┘
```

### How It Works

1. `tracing.js` is loaded **before** the openclaw process via `NODE_OPTIONS=-r /path/to/tracing.js`
2. It initializes the OpenTelemetry SDK with auto-instrumentation (HTTP, Express, DNS, etc.)
3. Spans are exported via OTLP/HTTP (protobuf) to `https://api.honeycomb.io:443`
4. Each instance identifies itself with a unique `OTEL_SERVICE_NAME` and resource attributes

---

## Setup

### Step 1: Sign Up for Honeycomb

1. Go to **https://ui.honeycomb.io/signup**
2. Create a free account (no credit card required)
3. Free tier includes **20M events/month** — more than enough for 3 bot instances

### Step 2: Create an API Key

1. In Honeycomb UI → **Account** → **Team Settings** → **API Keys**
2. Click **Create API Key**
3. Check **"Can create datasets"** (required — datasets are auto-created per service name)
4. Copy the key (starts with `hcaik_...`)
5. Store it securely — you'll need it for each instance setup

### Step 3: Run Setup Scripts

#### 🖥️ Local Windows (jarvis-local)

```powershell
cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\scripts\honeycomb

# Run the setup (prompts for API key)
.\setup-local.ps1 -ApiKey "hcaik_your_key_here"

# Restart your terminal, then start openclaw
openclaw
```

#### 🐧 DO VPS (ultron)

SSH into the VPS, copy the scripts, then:

```bash
# Copy scripts to the server (from your local machine)
scp scripts/honeycomb/* root@ultron-ip:/tmp/honeycomb/

# SSH in and run
ssh root@ultron-ip
cd /tmp/honeycomb
bash setup-vps.sh \
  --instance-name ultron \
  --api-key "hcaik_your_key_here" \
  --service-name openclaw
```

#### 🐧 Hostinger VPS (jarvis-legacy)

```bash
# Copy scripts to the server
scp scripts/honeycomb/* root@jarvis-ip:/tmp/honeycomb/

# SSH in and run
ssh root@jarvis-ip
cd /tmp/honeycomb
bash setup-vps.sh \
  --instance-name jarvis-legacy \
  --api-key "hcaik_your_key_here" \
  --service-name clawdbot
```

### Step 4: Verify Data in Honeycomb

1. After setup, send a test message to each bot via Telegram
2. Wait ~60 seconds for spans to flush
3. Go to **https://ui.honeycomb.io**
4. You should see 3 datasets:
   - `openclaw-ultron`
   - `openclaw-jarvis-legacy`
   - `openclaw-jarvis-local`
5. Click into any dataset → **New Query** → **Run** to see traces

---

## Files Reference

| File | Purpose |
|------|---------|
| `tracing.js` | OTel bootstrap — loaded via `NODE_OPTIONS=-r` |
| `install-deps.sh` | Install OTel npm packages globally (Linux) |
| `install-deps.ps1` | Install OTel npm packages globally (Windows) |
| `setup-vps.sh` | Full setup for Linux VPS instances |
| `setup-local.ps1` | Full setup for Windows local instance |
| `README.md` | This file |

---

## Troubleshooting

### No data appearing in Honeycomb

1. **Check the tracing init message in logs:**
   ```bash
   # VPS
   journalctl -u openclaw --no-pager -n 30 | grep tracing

   # Windows — look in console output for:
   # [tracing] ✓  OpenTelemetry started → https://api.honeycomb.io:443
   ```

2. **If you see "HONEYCOMB_API_KEY is not set":**
   - VPS: Check `systemctl show openclaw -p Environment`
   - Windows: Check `echo $env:HONEYCOMB_API_KEY`

3. **If you see "Failed to load OpenTelemetry packages":**
   - Run the install-deps script again
   - Check `npm ls -g @opentelemetry/sdk-node`

4. **If tracing starts but no data in Honeycomb:**
   - Verify the API key: `curl -v https://api.honeycomb.io/1/events/test -H "X-Honeycomb-Team: YOUR_KEY" -d '{}'`
   - Check firewall allows outbound HTTPS to `api.honeycomb.io:443`
   - Wait 2-3 minutes — there's a batching delay

5. **NODE_OPTIONS conflicts:**
   - If openclaw already uses `NODE_OPTIONS`, append rather than replace:
     ```bash
     # Linux: combine values
     Environment=NODE_OPTIONS=--existing-flag -r /root/.openclaw/tracing.js
     ```
     ```powershell
     # Windows: append
     $existing = [System.Environment]::GetEnvironmentVariable("NODE_OPTIONS", "User")
     [System.Environment]::SetEnvironmentVariable("NODE_OPTIONS", "$existing -r C:\Users\hharp\.openclaw\tracing.js", "User")
     ```

### High event volume / approaching 20M limit

- The `@opentelemetry/instrumentation-fs` is already disabled in `tracing.js`
- To further reduce volume, disable DNS instrumentation:
  ```js
  // In tracing.js, uncomment:
  '@opentelemetry/instrumentation-dns': { enabled: false },
  ```
- Monitor usage at: Honeycomb UI → **Account** → **Usage**

### Relationship to Axiom

| Concern | Axiom | Honeycomb |
|---------|-------|-----------|
| **What** | Logs (stdout/stderr) | Distributed traces (spans) |
| **How** | Vector log shipper | OTel SDK in-process |
| **Best for** | Searching log text, alerts | Latency analysis, error waterfalls, dependency maps |
| **Cost** | Separate plan | Free 20M events/month |

Both run simultaneously. They do not interfere with each other.

---

## Environment Variables Reference

| Variable | Example | Description |
|----------|---------|-------------|
| `HONEYCOMB_API_KEY` | `hcaik_abc123...` | Honeycomb ingest API key |
| `OTEL_SERVICE_NAME` | `openclaw-ultron` | Unique name per instance (becomes the dataset) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://api.honeycomb.io:443` | OTLP collector endpoint |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | Wire format |
| `OTEL_EXPORTER_OTLP_HEADERS` | `x-honeycomb-team=hcaik_...` | Auth header for OTLP |
| `OTEL_INSTANCE_NAME` | `ultron` | Human-friendly instance tag |
| `OTEL_DEPLOYMENT_ENVIRONMENT` | `production` | Environment tag |
| `NODE_OPTIONS` | `-r /root/.openclaw/tracing.js` | Preloads the tracing bootstrap |
