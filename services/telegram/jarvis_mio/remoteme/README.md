# RemoteMe - @JarvisMIO_bot Backend

AI-powered remote computer control via Telegram.

## Bot Identity

| Field | Value |
|-------|-------|
| **Bot Name** | JarvisVPS |
| **Username** | @JarvisMIO_bot |
| **Bot ID** | 8387943893 |

## Architecture

```
Telegram (@JarvisMIO_bot)
    ↓ webhook POST /telegram/webhook
FastAPI Backend (port 8100)
    ↓ Claude Haiku parses command
Node Client
    ↓ HTTP calls
Jarvis Nodes (laptops via Tailscale)
    - plc-laptop: 100.72.2.99:8765
    - travel-laptop: 100.83.251.23:8765
```

## Features

- **Screenshot** - Capture remote laptop screens
- **Shell** - Execute commands on remote laptops
- **Interpret** - Natural language → Open Interpreter automation
- **Click/Type** - Mouse and keyboard control
- **User Tracking** - SQLite database for usage analytics

## Supported Commands

| Command | Example | Description |
|---------|---------|-------------|
| screenshot | "screenshot" / "ss" | Take screenshot |
| shell | "run dir" / "shell ls" | Execute command |
| interpret | "open chrome and go to google" | AI automation |
| click | "click at 500, 300" | Mouse click |
| type | "type hello world" | Keyboard input |

## Setup

### 1. Install dependencies
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Run server
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8100
```

### 4. Set webhook
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-domain.com/telegram/webhook"
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /telegram/webhook | Telegram webhook handler |
| GET | /health | Health check |
| POST | /commands/execute | Manual command execution |
| GET | /nodes/status | Check node connectivity |

## Systemd Service

```bash
# Copy service file
sudo cp systemd/remoteme.service /etc/systemd/system/

# Enable and start
sudo systemctl enable remoteme
sudo systemctl start remoteme

# Check status
sudo systemctl status remoteme
```

## Database Schema

| Table | Purpose |
|-------|---------|
| `users` | Telegram users, subscription status |
| `nodes` | Registered computers |
| `commands` | Execution history |
| `usage_logs` | Daily usage tracking |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| TELEGRAM_BOT_TOKEN | Yes | Bot token from @BotFather |
| ANTHROPIC_API_KEY | Yes | For Claude command parsing |
| PLC_LAPTOP_IP | Yes | Tailscale IP of PLC laptop |
| TRAVEL_LAPTOP_IP | No | Tailscale IP of travel laptop |
| RATE_LIMIT_PER_MINUTE | No | Rate limit (default: 10) |

## Related Repos

- [remoteme-jarvis-node](https://github.com/Mikecranesync/remoteme-jarvis-node) - Laptop client (jarvis_node.py)

## License

Proprietary - FactoryLM
