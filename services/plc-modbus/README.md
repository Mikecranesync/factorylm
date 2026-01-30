# PLC Modbus Integration

Direct Modbus TCP communication with Allen-Bradley Micro 820 PLC for industrial automation.

## Overview

This service provides:
- Real-time I/O monitoring for Allen-Bradley PLCs
- FastAPI backend with network scanner
- Raspberry Pi edge device for Modbus TCP server
- Factory I/O simulation integration
- LLM-powered ST code generation

## Hardware Configuration

- **PLC:** Allen-Bradley Micro 820 (Firmware v12)
- **Protocol:** Modbus TCP on port 502
- **PLC IP:** 192.168.1.100
- **PC IP:** 192.168.1.50

## Quick Start

```bash
cd services/plc-modbus
pip install -r requirements.txt

# Real-time I/O monitor
python tools/plc_monitor.py

# Log state changes
python tools/plc_logger.py --duration 60

# Start API server
uvicorn backend.main:app --reload
```

## Directory Structure

```
plc-modbus/
├── backend/         # FastAPI server with network scanner
├── src/             # Core Modbus library (factorylm_plc)
├── tools/           # CLI tools (plc_monitor.py, plc_logger.py)
├── factorylm-edge/  # Raspberry Pi edge device
├── docs/            # Whitepaper, user manual
└── CLAUDE.md        # AI context file
```

## Source

Migrated from: [factorylm-plc-client](https://github.com/Mikecranesync/factorylm-plc-client)

## Related Services

See [ADAPTER_COMPARISON.md](../ADAPTER_COMPARISON.md) for comparison with `plc-copilot` service.

## Status

- [x] Migrated from source repo
- [ ] Integrated with monorepo build system
- [ ] Docker container
- [ ] Integrated with shared auth
