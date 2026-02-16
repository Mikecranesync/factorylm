# FactoryLM Pilot Deployment Checklist

**Version:** 1.0
**Mode:** Read-Only (monitoring only, no PLC writes)
**Target:** Single conveyor cell with Allen-Bradley Micro820

---

## Pre-Deployment Requirements

### Customer Side
- [ ] Network access to PLC (Modbus TCP port 502)
- [ ] Static IP or DHCP reservation for gateway device
- [ ] Firewall rules: outbound HTTPS (443) for AI API
- [ ] Plant contact for installation coordination
- [ ] List of I/O tags to monitor (coils/registers)

### FactoryLM Side
- [ ] Tailscale account for VPN access
- [ ] NVIDIA API key (Llama 3.1 access)
- [ ] Gateway hardware (laptop, Pi, or industrial PC)
- [ ] Tested deployment package

---

## Phase 1: Gateway Installation (30 min)

### 1.1 Install Gateway Device

```bash
# Option A: Windows laptop/PC
# Download and install:
- Python 3.11+
- Git
- Tailscale

# Option B: Raspberry Pi
sudo apt update && sudo apt install -y python3 python3-pip git
curl -fsSL https://tailscale.com/install.sh | sh
```

### 1.2 Join Tailscale Network

```bash
# Authenticate with Tailscale
tailscale up

# Note the Tailscale IP (100.x.x.x)
tailscale ip -4
```

### 1.3 Clone FactoryLM

```bash
git clone https://github.com/Mikecranesync/factorylm.git
cd factorylm
pip install -r requirements.txt
```

### 1.4 Configure Environment

Create `.env` file:
```bash
# PLC Connection
PLC_HOST=192.168.1.100    # Customer's PLC IP
PLC_PORT=502

# AI API
NVIDIA_COSMOS_API_KEY=nvapi-xxxx

# Matrix API (if running locally)
MATRIX_DB=matrix.db
```

---

## Phase 2: PLC Connection Test (15 min)

### 2.1 Verify Modbus Connectivity

```bash
# Test Modbus TCP connection
python -c "
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('192.168.1.100', port=502)
print('Connected:', client.connect())
result = client.read_coils(0, 10)
print('Coils:', result.bits[:10] if not result.isError() else 'ERROR')
client.close()
"
```

Expected: `Connected: True` and coil values

### 2.2 Map PLC Tags

Document the customer's tag mapping:

| Address | Tag Name | Description | Type |
|---------|----------|-------------|------|
| Coil 0 | motor_running | Main motor status | BOOL |
| Coil 1 | conveyor_running | Conveyor status | BOOL |
| Coil 10 | fault_alarm | Fault active | BOOL |
| Coil 11 | e_stop | E-stop pressed | BOOL |
| Reg 0 | motor_speed | Motor speed % | INT |
| Reg 1 | motor_current | Motor amps x100 | INT |
| Reg 2 | temperature | Temp in C | INT |

### 2.3 Start Matrix API

```bash
cd services/matrix
python app.py

# Verify: http://localhost:8000/
```

### 2.4 Start Tag Bridge

```bash
cd sim
python factoryio_bridge.py --plc-host 192.168.1.100 --interval 1000

# Verify tags flowing in Matrix dashboard
```

---

## Phase 3: AI Diagnosis Test (10 min)

### 3.1 Start Demo UI

```bash
cd services/matrix
python demo_ui.py

# Open: http://localhost:8080
```

### 3.2 Verify Live Tags

- [ ] Tags refresh every 2 seconds
- [ ] Values match PLC HMI
- [ ] No connection errors

### 3.3 Test Diagnosis

1. Click "Diagnose" button
2. Verify response in < 10 seconds
3. Check latency displayed
4. Confirm AI model shown (Llama 3.1)

### 3.4 Simulate Fault (if possible)

1. Trigger a known fault on equipment
2. Verify fault detected in UI
3. Run diagnosis
4. Confirm AI identifies the issue

---

## Phase 4: Remote Access Setup (10 min)

### 4.1 Verify Tailscale Connection

From remote device:
```bash
# Ping gateway
ping 100.x.x.x

# Test Matrix API
curl http://100.x.x.x:8000/api/health

# Test Demo UI
curl http://100.x.x.x:8080/health
```

### 4.2 Configure Jarvis Node (Optional)

For remote shell access:
```bash
cd remoteme-jarvis-node
python jarvis_node.py

# Test: curl http://100.x.x.x:8765/health
```

---

## Phase 5: Handoff to Customer (15 min)

### 5.1 Document Access

Provide to customer:
- Tailscale IP: `100.x.x.x`
- Demo UI: `http://100.x.x.x:8080`
- Matrix Dashboard: `http://100.x.x.x:8000`

### 5.2 Training

- Show live tag display
- Demonstrate "Why stopped?" diagnosis
- Explain latency expectations (3-5 seconds)
- Review fault detection rules

### 5.3 Set Expectations

- **Read-only mode**: We don't write to PLC
- **AI is advisory**: Technician makes final decisions
- **Data stays local**: PLC data is processed locally, only AI queries go to cloud
- **Support contact**: [your contact info]

---

## Smoke Tests

Run these after any change:

```bash
# 1. Tags flowing
curl http://localhost:8000/api/tags?limit=1 | jq

# 2. Faults detected
curl http://localhost:8080/api/faults | jq

# 3. AI diagnosis works
curl -X POST http://localhost:8080/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the current status?"}' | jq

# 4. Latency acceptable
# Check latency_ms < 10000 in response
```

---

## Troubleshooting

### "Cannot connect to PLC"
- Verify PLC IP is reachable: `ping 192.168.1.100`
- Check firewall allows port 502
- Confirm Modbus TCP is enabled on PLC

### "No tags in Matrix"
- Verify bridge is running
- Check bridge console for errors
- Confirm PLC coil/register addresses

### "AI diagnosis timeout"
- Check NVIDIA API key is set
- Verify outbound HTTPS allowed
- Test API: `curl https://integrate.api.nvidia.com/v1/models`

### "Tailscale not connecting"
- Run `tailscale status`
- Re-authenticate: `tailscale up --reset`
- Check corporate firewall allows Tailscale

---

## Rollback Plan

If issues arise:
1. Stop all FactoryLM services
2. PLC continues operating normally (read-only mode = no impact)
3. Collect logs: `services/matrix/matrix.log`
4. Contact support

---

## Success Criteria

Pilot is successful when:
- [ ] Tags stream reliably for 24+ hours
- [ ] AI diagnosis returns in < 10 seconds
- [ ] Technician finds diagnosis helpful
- [ ] Zero impact to PLC operation
- [ ] Customer wants to expand

---

## Next Steps After Pilot

1. **Expand tag coverage** — Add more I/O points
2. **Add more cells** — Replicate to additional equipment
3. **Integrate with CMMS** — Auto-create work orders
4. **Add alerting** — Telegram/SMS on critical faults
5. **Train on site-specific faults** — Customize prompts

---

*FactoryLM v1 — "Text your factory, AI tells you what's wrong."*
