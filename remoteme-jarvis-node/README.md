# Jarvis Node

A small FastAPI server that turns any machine into a remotely-controllable node
on the FactoryLM Tailscale network. It exposes shell execution, screenshots,
file read/write, system info, desktop notifications, and a message queue so that
Jarvis (the Telegram bot / orchestrator) and Claude Code can drive a laptop from
anywhere on the tailnet. Every endpoint is gated behind a bearer token and the
node is meant to bind to its Tailscale IP only — never the public internet.

---

## Security (read this first)

This node can run arbitrary shell commands and read/write files. Two rules are
non-negotiable:

1. **Always set `JARVIS_TOKEN`.** Without it the node *refuses to serve* — every
   endpoint except `/health` returns `503`. With it, every request must send
   `Authorization: Bearer <JARVIS_TOKEN>` or it gets `401`. The token is compared
   with `secrets.compare_digest` (timing-safe).
2. **Always bind to the Tailscale IP, never `0.0.0.0` on an untrusted network.**
   The provided launchers auto-detect the Tailscale IPv4 and bind to it; they
   fall back to `127.0.0.1` (local-only) if Tailscale is down.

Generate a token once and use the **same value** on every machine that needs to
talk to each other:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Store it in Doppler (`factorylm/prd → JARVIS_TOKEN`) and/or set it in each
machine's environment.

---

## Quick start

There are two ways to run a node:

| Script | What it does | Use for |
|--------|--------------|---------|
| `install.bat` / `install.sh` | Installs deps, generates a token if unset, detects the Tailscale IP, and runs the node **in the foreground** | Quick start, testing, travel laptop |
| `install-node.sh` | Installs the node as an **always-on background service** (launchd on macOS, systemd `--user` on Linux) with auto-restart | CHARLIE / ALPHA / BRAVO and any always-on host |

### Windows (PLC laptop, travel laptop)

```bat
cd remoteme-jarvis-node
install.bat
```

`install.bat` prints a generated token if `JARVIS_TOKEN` is not already set —
copy it and set it as a System Environment Variable so it persists across
reboots, and set the **same** value on whatever machine will call this node.

### macOS / Linux (foreground)

```bash
cd remoteme-jarvis-node
./install.sh
```

### macOS / Linux (always-on service)

```bash
cd remoteme-jarvis-node
./install-node.sh   # installs + starts a launchd/systemd service, then health-checks
```

The service launcher (`run-node.sh`) is **fail-closed**: if `JARVIS_TOKEN` is
neither in the environment nor retrievable from Doppler, it refuses to start.

---

## Fleet topology

```
                         Tailscale tailnet (100.x.x.x)
                                     │
   ┌──────────────┬──────────────┬───┴──────────┬──────────────┐
   │              │              │              │              │
 CHARLIE        ALPHA          BRAVO        PLC laptop     Travel laptop
 (Mac mini)    (Mac mini)    (Mac mini)     (Windows)       (Windows)
 install-      install-      install-       install.bat     install.bat
 node.sh       node.sh       node.sh
   │              │              │              │              │
   └──────────────┴──────────────┴──────────────┴──────────────┘
                                     │
                       jarvis_node_client.py  /  Jarvis bot
                  (sends Authorization: Bearer $JARVIS_TOKEN)
```

All nodes share one `JARVIS_TOKEN`. Callers use `workers/jarvis_node_client.py`,
which reads `JARVIS_TOKEN` from the environment and attaches it to every request.

---

## Endpoint reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/health` | public | Liveness + capability flags (works even with no token set) |
| GET  | `/` | token | Service banner: machine name, version, endpoint list |
| GET  | `/system-info` | token | Hostname, platform, CPU/memory/disk (psutil) |
| GET  | `/processes?top=N` | token | Top N processes by memory |
| POST | `/shell` | token | Run a shell command (`{command, timeout, cwd}`) |
| GET  | `/screenshot?monitor=N` | token | Capture screen as base64 PNG (mss) |
| POST | `/files/read` | token | Read a file (`{path}`) |
| POST | `/files/write` | token | Write a file (`{path, content}`) |
| GET  | `/files/list?path=...` | token | List a directory |
| POST | `/notify` | token | Desktop notification (`{title, message, type}`) |
| POST | `/messages` | token | Queue a message for `jarvis` / `claude-code` |
| GET  | `/messages?for=...` | token | Drain queued messages for a recipient |
| GET  | `/messages/peek?for=...` | token | Peek without draining |

### Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_TOKEN` | *(unset → 503)* | **Required.** Bearer token for all requests |
| `JARVIS_PORT` | `8765` | Listen port |
| `JARVIS_MACHINE_NAME` | hostname | Friendly name reported in `/health` and `/` |
| `JARVIS_WORKSPACE` | `~/jarvis-workspace` | Working directory created on startup |

---

## Verify it's working

```bash
# Liveness (no token needed)
curl http://<tailscale-ip>:8765/health

# Authenticated call
curl -H "Authorization: Bearer $JARVIS_TOKEN" http://<tailscale-ip>:8765/system-info

# Without a token you should get 401 (or 503 if the node has no token configured)
curl -i http://<tailscale-ip>:8765/system-info
```
