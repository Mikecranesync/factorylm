# FactoryLM PLC Client

Modbus TCP client for industrial PLCs. Provides a unified interface for reading machine state and controlling equipment.

## Installation

```bash
cd plc-client
pip install -r requirements.txt
```

## Quick Start

### Using MockPLC (for testing)

```python
from factorylm_plc import create_plc_client

# Create a mock PLC for testing
with create_plc_client("mock") as plc:
    # Read machine state
    state = plc.read_state()
    print(f"Temperature: {state.temperature}°C")
    print(f"Motor Running: {state.motor_running}")

    # Start the motor
    plc.start_motor()
    plc.set_motor_speed(1500)

    # Read updated state
    state = plc.read_state()
    print(f"Speed: {state.motor_speed} RPM")
```

### Using Real Micro820 PLC

```python
from factorylm_plc import create_plc_client

# Connect to real PLC
with create_plc_client("micro820", host="192.168.1.100") as plc:
    state = plc.read_state()

    if state.fault_alarm:
        print("FAULT DETECTED!")
    elif state.is_healthy():
        print(f"Healthy - Temp: {state.temperature}°C")
```

## Components

### MachineState

Standardized machine state dataclass:

```python
from factorylm_plc import MachineState

state = plc.read_state()

# Access fields
state.motor_speed      # RPM
state.motor_current    # Amps
state.temperature      # Celsius
state.pressure         # PSI
state.motor_running    # bool
state.motor_stopped    # bool
state.fault_alarm      # bool
state.timestamp        # Unix timestamp

# Serialize to dict (JSON-compatible)
data = state.to_dict()

# Check health
if state.is_healthy():
    print("Machine OK")
```

### BasePLCClient

Abstract base class for PLC implementations:

```python
from factorylm_plc import BasePLCClient

# All PLC clients implement these methods:
plc.connect()           # Connect to PLC
plc.disconnect()        # Disconnect
plc.is_connected()      # Check connection
plc.read_state()        # Read MachineState
plc.write_register(addr, value)  # Write register
plc.write_coil(addr, value)      # Write coil
```

### Factory Function

```python
from factorylm_plc import create_plc_client

# Create MockPLC
plc = create_plc_client("mock")

# Create Micro820PLC
plc = create_plc_client("micro820", host="192.168.1.100", port=502)
```

## Register Mapping (Micro820)

| Register | Address | Description |
|----------|---------|-------------|
| motor_speed | 100 | Motor speed in RPM |
| motor_current | 101 | Motor current in Amps |
| temperature | 102 | Temperature (scaled 10x) |
| pressure | 103 | Pressure in PSI |

| Coil | Address | Description |
|------|---------|-------------|
| motor_running | 0 | Motor is running |
| motor_stopped | 1 | Motor is stopped |
| fault_alarm | 2 | Fault/alarm active |

## Testing

```bash
# Run all tests (no hardware required)
pytest tests/ -v

# Run only unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/ --cov=src/factorylm_plc --cov-report=term-missing
```

## Project Structure

```
plc-client/
├── src/factorylm_plc/
│   ├── __init__.py      # Factory function, exports
│   ├── models.py        # MachineState dataclass
│   ├── config.py        # Configuration
│   ├── plc/
│   │   ├── base.py      # BasePLCClient abstract class
│   │   ├── micro820.py  # Micro820 implementation
│   │   └── mock_plc.py  # Mock for testing
│   └── modbus/
│       └── client.py    # ModbusTCPClient wrapper
├── tests/
│   ├── unit/            # Unit tests with mocks
│   └── integration/     # End-to-end tests
├── requirements.txt     # pymodbus==3.6.1
└── README.md
```

## License

Part of the FactoryLM project.
