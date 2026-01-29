# PLC Copilot

Photo analysis → Work order creation for industrial maintenance.

## Overview
Telegram bot that:
1. Receives equipment photos from field technicians
2. Analyzes images using Gemini Vision AI
3. Creates work orders in CMMS automatically

## Features
- 📸 Photo intake via Telegram
- 🤖 AI-powered defect detection
- 📋 Automatic work order creation
- ⚡ Priority classification (LOW/MEDIUM/HIGH)
- 🏭 Asset identification

## Source
Migrated from: `/opt/plc-copilot/` (Rivet-PRO)

## Setup
```bash
cd services/plc-copilot
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python photo_to_cmms_bot.py
```

## Environment Variables
```
TELEGRAM_BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_key
CMMS_API_URL=https://your-cmms.com/api
CMMS_API_TOKEN=your_cmms_token
```

## Architecture
```
Telegram → Bot → Gemini Vision → CMMS API
   📸        🤖       👁️            📋
```

## Status
- [x] Copied from source
- [ ] Tests added
- [ ] Docker container
- [ ] Integrated with shared auth
