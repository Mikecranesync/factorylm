# FactoryLM Fault Injector

Inject faults into Factory I/O to test the Telegram bot (Gus) diagnosis system.

## Overview

This tool allows you to create specific fault conditions in Factory I/O via Modbus TCP,
then observe how the FactoryLM system (Matrix API → Demo UI → Telegram Bot) responds.

## Architecture

```
Travel Laptop (You)                    PLC Laptop (100.72.2.99)
┌─────────────────────┐                ┌──────────────────────────┐
│ fault_injector/     │  Modbus TCP    │  Factory I/O             │
│ run_fault_scenario  │───────────────►│  (Modbus Server :502)    │
└─────────────────────┘                │           │              │
         │                             │           ▼              │
         │ HTTP                        │  factoryio_bridge.py     │
         │                             │           │              │
         ▼                             │           ▼              │
┌─────────────────────┐                │  Matrix API (:8000)      │
│ watch.py            │◄───────────────│           │              │
│ (monitor tags)      │                │           ▼              │
└─────────────────────┘                │  Demo UI (:8080)         │
                                       └──────────────────────────┘
                                                   │
                                                   │ HTTP
VPS (100.68.120.99)                               ▼
┌─────────────────────┐                ┌──────────────────────────┐
│ Telegram Bot (Gus)  │◄───────────────│  /api/diagnose           │
│ @UltronVPS_bot      │                │  AI Fault Analysis       │
└─────────────────────┘                └──────────────────────────┘
         ▲
         │ Telegram
┌─────────────────────┐
│ Mike's Phone        │
│ "What's wrong?"     │
└─────────────────────┘
```

## Quick Start

### 1. List Available Scenarios

```bash
python tools/fault_injector/run_fault_scenario.py --list
```

Output:
```
Available Fault Scenarios:
--------------------------------------------------
  motor_overload       - Motor Overload
                         Motor drawing excessive current (12A vs 10A limit)

  overheat             - Overheating
                         Temperature sensor reading 85C (limit is 80C)

  sensor_jam           - Sensor Jam / Conveyor Blockage
                         Sensor 1 blocked continuously - box stuck on conveyor

  low_pressure         - Low Pressure
                         Pneumatic pressure dropped to 50 PSI (limit is 70 PSI)

  emergency_stop       - Emergency Stop
                         E-stop button pressed - all motion stopped

  sensor_failure       - Sensor Failure
                         Both sensors showing offline/disconnected

  normal               - Normal Operation
                         Clear all faults and run normally
```

### 2. Inject a Fault

```bash
# Inject a sensor jam fault (holds for 30 seconds by default)
python tools/fault_injector/run_fault_scenario.py --scenario sensor_jam
```

### 3. Test with Telegram

While the fault is active, send this to @UltronVPS_bot:

> "What's wrong with the equipment?"

Gus should respond with something like:

> "Here's what I found (850ms):
> Conveyor jam detected at Sensor 1. The sensor has been continuously
> blocked which indicates a box or material is stuck on the conveyor.
>
> Active faults: conveyor_jam
>
> — Analysis by llama-3.3-70b"

### 4. Clear Faults

```bash
python tools/fault_injector/run_fault_scenario.py --scenario normal
```

## Advanced Usage

### Watch Mode

Monitor the system in real-time while testing:

```bash
# Terminal 1: Watch tags
python tools/fault_injector/watch.py

# Terminal 2: Inject fault
python tools/fault_injector/run_fault_scenario.py --scenario motor_overload --hold 60
```

### Custom Hold Time

```bash
# Hold the fault for 2 minutes
python tools/fault_injector/run_fault_scenario.py --scenario overheat --hold 120
```

### Skip Prerequisite Checks

```bash
python tools/fault_injector/run_fault_scenario.py --scenario sensor_jam --skip-checks
```

## End-to-End Test Recipe

### Recipe 1: Sensor Jam Detection

1. **Start watch** (Terminal 1):
   ```bash
   python tools/fault_injector/watch.py
   ```

2. **Inject fault** (Terminal 2):
   ```bash
   python tools/fault_injector/run_fault_scenario.py --scenario sensor_jam
   ```

3. **Test Telegram** (Phone):
   - Send: "What's wrong?"
   - Expect: "Conveyor jam detected" + recovery steps

4. **Clear fault**:
   ```bash
   python tools/fault_injector/run_fault_scenario.py --scenario normal
   ```

5. **Verify recovery** (Phone):
   - Send: "Show me IO"
   - Expect: "Running smooth. No alarms, no problems."

### Recipe 2: Multiple Fault Types

```bash
# Test each fault type
for scenario in motor_overload overheat low_pressure emergency_stop sensor_failure; do
  echo "Testing: $scenario"
  python tools/fault_injector/run_fault_scenario.py --scenario $scenario --hold 15
  sleep 5
done

# Clear all
python tools/fault_injector/run_fault_scenario.py --scenario normal
```

## Files

| File | Purpose |
|------|---------|
| `run_fault_scenario.py` | Main CLI entry point |
| `scenarios.py` | Fault scenario definitions |
| `modbus_control.py` | Direct Modbus TCP control |
| `remote.py` | SSH/Jarvis remote control |
| `watch.py` | Real-time system monitor |
| `config.py` | Environment configuration |

## Configuration

Set these environment variables to customize:

```bash
export PLC_HOST="100.72.2.99"      # PLC laptop IP
export MODBUS_PORT="502"            # Modbus TCP port
export FAULT_HOLD_SECONDS="30"      # Default hold time
export SSH_USER="hharp"             # SSH username
```

## Troubleshooting

### "Modbus connection failed"

- Ensure Factory I/O is running with Modbus server enabled
- Check: `netstat -an | findstr :502` on PLC laptop
- Verify Tailscale connectivity: `ping 100.72.2.99`

### "Jarvis Node not available"

- Start Jarvis node on PLC laptop:
  ```bash
  ssh hharp@100.72.2.99 "cd remoteme-jarvis-node && python jarvis_node.py"
  ```

### "Factory I/O not responding to Modbus writes"

- Open Factory I/O → Edit → Options → Modbus Server
- Ensure "Enable Modbus TCP/IP Server" is checked
- Verify address 0 for coils, 100 for registers

## Future Enhancements

- [ ] Random fault injection mode
- [ ] Fault sequence playback (multiple faults in order)
- [ ] Web UI for scenario control
- [ ] Integration with computer-use models for GUI automation
