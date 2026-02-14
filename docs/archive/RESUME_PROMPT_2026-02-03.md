# FactoryLM Session Resume Prompt

**Last Updated:** 2026-02-03
**Device:** Travel Laptop (Miguelomaniac)

---

## ACTIVE MISSION: Catapult Lakeland Demo

**DEMO DATE:** Tuesday, February 10th, 2026 @ 12:00-1:30 PM
**Days Remaining:** 7

**Demo Flow:** Phone → Telegram → VPS → PLC Laptop → Micro 820 → LLM → Response

---

## SESSION SUMMARY (Feb 2-3)

### Completed Today:
1. **DevOps Status Review** - Analyzed all memory, GitHub commits, and project state
2. **Git Sync** - Committed and pushed all local work to GitHub (commit `3cb2971`)
   - Merged local development with remote monorepo structure
   - Added: `core/`, `plc-client-factoryio/`, `My-Ralph/`, `scripts/diagnosis_service.py`
3. **Raspberry Pi Zero-Touch Deployment Plan** - Created complete guide for field deployment
   - Plan file: `C:\Users\hharp\.claude\plans\serene-tickling-valley.md`
   - Created `scripts/pi-setup/firstrun.sh` for manual Tailscale setup
4. **Balena Cloud Setup** - Connected to existing fleet `factorylm-edge` (ID: 2332816)
   - API Key: `[SET IN DOPPLER: BALENA_API_KEY]`
   - Dashboard: https://dashboard.balena-cloud.com/fleets/2332816

### In Progress:
- **Balena CLI installation failed** on Windows (native module compilation issues)
- **Alternative:** Use Balena Dashboard to download pre-configured Pi image

---

## NETWORK CONFIGURATION

| Device | Tailscale IP | Service | Status |
|--------|--------------|---------|--------|
| VPS (Jarvis) | 100.68.120.99 | Telegram Bot | Unknown |
| Travel Laptop | 100.83.251.23 | Jarvis Node:8765 | Current |
| PLC Laptop | 100.72.2.99 | Jarvis Node:8765 | Unknown |

**WiFi Credentials (for Pi provisioning):**
- SSID: `hharperson2000`
- Password: `[REDACTED — see Doppler]`

---

## KEY FILES

| File | Purpose |
|------|---------|
| `scripts/diagnosis_service.py` | Main demo service - bridges Telegram→PLC→LLM |
| `scripts/FACTORYLM_INTEGRATION.md` | Clawdbot routing configuration |
| `scripts/pi-setup/firstrun.sh` | Raspberry Pi auto-setup script |
| `C:\Users\hharp\.claude\plans\serene-tickling-valley.md` | Pi deployment plan |
| `C:\Users\hharp\.claude\plans\witty-noodling-plum.md` | Master demo mission plan |

---

## COMPONENT STATUS

### Production Ready (Green)
- ✅ LLM Core (`core/`) - 148 tests passing
- ✅ PLC Client (`plc-client-factoryio/`) - Full Modbus TCP integration
- ✅ Landing Page - Live at factorylm.com

### Needs Deployment (Yellow)
- 🟡 `diagnosis_service.py` - Created locally, needs to deploy to VPS
- 🟡 Clawdbot routing - Needs factory keyword configuration
- 🟡 Raspberry Pi image - Use Balena Dashboard method

### Not Started (Red)
- ❌ End-to-end test (Telegram → VPS → PLC → LLM)
- ❌ Backup demo video
- ❌ Pitch deck

---

## NEXT ACTIONS

1. **Use Balena Dashboard** to create Pi image:
   - Go to: https://dashboard.balena-cloud.com/fleets/2332816
   - Click "Add device"
   - Configure WiFi: `hharperson2000` / `[REDACTED — see Doppler]`
   - Download and flash with Etcher

2. **Deploy diagnosis_service.py to VPS**:
   ```bash
   scp scripts/diagnosis_service.py root@100.68.120.99:/opt/factorylm/
   ssh root@100.68.120.99 "pip install fastapi uvicorn && cd /opt/factorylm && uvicorn diagnosis_service:app --host 0.0.0.0 --port 8200"
   ```

3. **Configure Clawdbot** to route factory questions to localhost:8200

4. **Test end-to-end** via Telegram

---

## GITHUB STATUS

- **Repo:** `Mikecranesync/factorylm`
- **Branch:** `main`
- **Latest Commit:** `3cb2971` - "Merge remote main with local development"
- **Status:** Pushed and up-to-date

---

## RESUME COMMAND

To continue this session, tell Claude:

```
Read RESUME_PROMPT.md and continue where we left off.
Current task: Create Balena Pi image via dashboard, then deploy diagnosis_service.py to VPS.
```
