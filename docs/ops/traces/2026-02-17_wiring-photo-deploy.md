# Deploy: Wiring Photo Pipeline to VPS

| Field | Value |
|-------|-------|
| **Trace ID** | TRC-2026-02-17-001 |
| **Date** | 2026-02-17 |
| **Author** | Claude Code (Travel Laptop) |
| **Status** | draft |
| **Branch** | fix/estop-incident-creation → main |

## What Changed

Phase 2+3 of the wiring reconstruction system:
- Telegram photo handler (KB enrichment + wiring reconstruction)
- 4-stage KB enrichment pipeline (ingest → augment → synthesize → upsert)
- KnowledgeConnector (dual-write to rivet + neon)
- Intent classifier (6 intents)
- Antfarm workflow (4 agents)

## Pre-Deploy Checklist

- [ ] Branch merged to main
- [ ] SSH access to VPS verified
- [ ] Decide deployment target (Gus bot vs Jarvis/OpenClaw)

## Deployment Steps

### Option A: Deploy as Gus Bot (standalone)

Gus (`factorylm_bot.py`) is the factory assistant bot with the new photo handler.
This is the simplest path — standalone bot alongside Jarvis.

```bash
# 1. SSH to VPS
ssh -i ~/.ssh/id_ed25519 root@100.68.120.99

# 2. Clone or update the monorepo
cd /opt
git clone https://github.com/Mikecranesync/factorylm.git factorylm-monorepo 2>/dev/null || true
cd /opt/factorylm-monorepo
git fetch origin main
git checkout main
git pull

# 3. Create venv and install deps
python3 -m venv .venv
source .venv/bin/activate

pip install python-telegram-bot httpx psycopg2-binary google-generativeai anthropic

# 4. Set environment variables (or use Doppler)
export GOOGLE_API_KEY="<your-gemini-key>"          # Required for vision OCR
export ANTHROPIC_API_KEY="<your-anthropic-key>"    # Fallback vision
export POSTGRES_HOST="localhost"                    # rivet DB
export POSTGRES_PORT="5432"
export POSTGRES_DB="rivet"
export POSTGRES_USER="rivet"
export POSTGRES_PASSWORD="<rivet-password>"
# Optional: NEON_DATABASE_URL for semantic search dual-write

# 5. Make openclaw importable
export PYTHONPATH="/opt/factorylm-monorepo:$PYTHONPATH"

# 6. Test imports
python3 -c "from openclaw.gateway.telegram import handle_photo; print('OK')"

# 7. Run the bot
python3 services/telegram/factorylm_bot.py
```

### Option B: Integrate into existing OpenClaw/Jarvis

Jarvis already handles photos via `_on_photo()` → Gemini. To add the wiring
enrichment pipeline alongside it:

```bash
# 1. SSH to VPS
ssh -i ~/.ssh/id_ed25519 root@100.68.120.99

# 2. Copy openclaw package to the OpenClaw installation
cd /opt/factorylm-monorepo  # (clone first per Option A steps 2-3)
cp -r openclaw/wiring /opt/openclaw/openclaw/wiring/
cp -r openclaw/connectors /opt/openclaw/openclaw/connectors/
cp -r openclaw/messages /opt/openclaw/openclaw/messages/
cp openclaw/types.py /opt/openclaw/openclaw/types.py

# 3. Install additional deps in OpenClaw venv
source /opt/openclaw/.venv/bin/activate
pip install psycopg2-binary

# 4. Restart
systemctl restart openclaw

# 5. Verify
journalctl -u openclaw -n 15 --no-pager
curl -s http://localhost:8340/
```

### Option C: Systemd service for Gus (production)

```ini
# /etc/systemd/system/factorylm-gus.service
[Unit]
Description=FactoryLM Gus Bot (Telegram)
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/factorylm-monorepo/.venv/bin/python services/telegram/factorylm_bot.py
Restart=always
RestartSec=10
WorkingDirectory=/opt/factorylm-monorepo
Environment=PYTHONPATH=/opt/factorylm-monorepo
Environment=HOME=/root
EnvironmentFile=/opt/factorylm-monorepo/.env

[Install]
WantedBy=multi-user.target
```

```bash
# Install and start
cp factorylm-gus.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable factorylm-gus
systemctl start factorylm-gus
journalctl -u factorylm-gus -f
```

## Post-Deploy Verification

```bash
# 1. Check service is running
systemctl status factorylm-gus  # (or openclaw)

# 2. Check logs for photo handler registration
journalctl -u factorylm-gus -n 30 | grep -i "photo handler"
# Expected: "Photo handler registered (wiring + KB enrichment)"

# 3. Send a test photo to Gus via Telegram
# Expected: immediate "Got it, parsing now..." reply
# Then: enrichment summary after 5-15s

# 4. Check KB write (if DB is connected)
psql -U rivet -d rivet -c "SELECT atom_id, vendor, product FROM knowledge_atoms ORDER BY atom_id DESC LIMIT 5;"
```

## Rollback

```bash
# Gus bot: just stop the service
systemctl stop factorylm-gus

# OpenClaw integration: revert to previous commit
cd /opt/openclaw
git checkout HEAD~1
systemctl restart openclaw
```

## Dependencies Summary

| Package | Purpose | Required |
|---------|---------|----------|
| python-telegram-bot | Telegram API | Yes |
| httpx | HTTP client (existing) | Yes |
| psycopg2-binary | PostgreSQL (KB connector) | For KB writes |
| google-generativeai | Gemini vision OCR | For enrichment |
| anthropic | Claude vision fallback | Optional |

## API Keys Needed

| Key | Source | Used For |
|-----|--------|----------|
| TELEGRAM_BOT_TOKEN | Hardcoded in bot | Gus bot auth |
| GOOGLE_API_KEY | Doppler / env | Vision OCR (enrichment) |
| ANTHROPIC_API_KEY | Doppler / env | Vision fallback |
| POSTGRES_PASSWORD | Doppler / env | rivet KB writes |
| NEON_DATABASE_URL | Doppler / env | Semantic search (optional) |

## Notes

- The photo handler gracefully degrades: if `openclaw` isn't importable, Gus runs text-only
- KB enrichment works without DB — vision runs, summary returned, upsert logs warning
- Gemini is already configured on the VPS (used by Jarvis for PHOTO intent)
- The `knowledge_atoms` schema migration runs automatically on first KnowledgeConnector connection
