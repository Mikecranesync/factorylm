# FactoryLM PLC Client API Documentation

## Overview

The FactoryLM PLC Client library provides a Python interface for communicating with Allen-Bradley Micro 820 PLCs via Modbus TCP, with special support for Factory I/O integration.

## Installation

```bash
pip install factorylm-plc

# Or from source
cd plc-client-factoryio
pip install -e .
```

---

## Quick Start

```python
from factorylm_plc import create_plc_client

# Create client (mock for testing, or real hardware)
plc = create_plc_client(plc_type="mock")

with plc:
    # Read current state
    state = plc.read_state()
    print(state.to_llm_context())

    # Control motor
    plc.write_coil(0, True)   # Start motor
    plc.write_register(100, 75)  # Set speed to 75%
```

---

## Factory Function

### `create_plc_client()`

Creates a PLC client instance based on the specified type.

```python
def create_plc_client(
    plc_type: str = "mock",
    host: str = "192.168.1.100",
    port: int = 502,
    timeout: float = 5.0,
    retries: int = 3,
    scene_name: str = "sorting_station"
) -> BasePLCClient
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| plc_type | str | "mock" | PLC type: "mock", "micro820", "factoryio_micro820" |
| host | str | "192.168.1.100" | PLC IP address |
| port | int | 502 | Modbus TCP port |
| timeout | float | 5.0 | Connection timeout in seconds |
| retries | int | 3 | Number of retry attempts |
| scene_name | str | "sorting_station" | Factory I/O scene identifier |

**Returns:** `BasePLCClient` instance

**PLC Types:**
- `"mock"` - In-memory simulation for testing (no hardware needed)
- `"micro820"` - Generic Allen-Bradley Micro 820
- `"factoryio_micro820"` or `"factoryio"` - Factory I/O + Micro 820 combo

**Example:**
```python
# Testing without hardware
mock_plc = create_plc_client(plc_type="mock")

# Real hardware
real_plc = create_plc_client(
    plc_type="factoryio_micro820",
    host="192.168.1.100"
)
```

---

### `create_managed_client()`

Creates a PLC client wrapped in a connection manager with auto-reconnect.

```python
def create_managed_client(
    plc_type: str = "mock",
    host: str = "192.168.1.100",
    port: int = 502,
    auto_reconnect: bool = True,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> PLCConnectionManager
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| auto_reconnect | bool | True | Automatically reconnect on failure |
| max_retries | int | 3 | Max reconnection attempts |
| retry_delay | float | 1.0 | Delay between retries (seconds) |

**Returns:** `PLCConnectionManager` instance

---

## Classes

### `BasePLCClient` (Abstract)

Base class for all PLC clients. Defines the interface that all implementations must follow.

```python
from factorylm_plc.base import BasePLCClient
```

**Methods:**

#### `connect() -> bool`
Establish connection to the PLC.

#### `disconnect() -> None`
Close the connection.

#### `is_connected() -> bool`
Check if currently connected.

#### `read_state() -> MachineState`
Read current machine state from PLC.

#### `read_holding_registers(address: int, count: int) -> List[int]`
Read holding registers starting at address.

#### `read_coils(address: int, count: int) -> List[bool]`
Read coils starting at address.

#### `write_register(address: int, value: int) -> bool`
Write a value to a holding register.

#### `write_coil(address: int, value: bool) -> bool`
Write a value to a coil.

---

### `MockPLC`

In-memory PLC simulation for testing without hardware.

```python
from factorylm_plc import MockPLC

plc = MockPLC()
```

**Constructor:**
```python
MockPLC(
    initial_speed: int = 0,
    initial_temp: float = 25.0,
    initial_pressure: int = 100,
    scene_name: str = "sorting_station"
)
```

**Additional Methods:**

#### `start_motor(speed: int = 50) -> None`
Start motor at specified speed (0-100%).

#### `stop_motor() -> None`
Stop the motor.

#### `start_conveyor(speed: int = 50) -> None`
Start conveyor at specified speed.

#### `stop_conveyor() -> None`
Stop the conveyor.

#### `trigger_error(code: int) -> None`
Trigger an error condition.

#### `clear_error() -> None`
Clear any active error.

#### `trigger_estop() -> None`
Activate emergency stop.

#### `release_estop() -> None`
Release emergency stop.

#### `simulate_part_detection(sensor: int, detected: bool) -> None`
Simulate part detection on sensor 1 or 2.

**Behavior:**
- Temperature increases when motor is running
- Motor current is proportional to speed
- All changes are immediate and in-memory

---

### `Micro820PLC`

Client for Allen-Bradley Micro 820 PLC via Modbus TCP.

```python
from factorylm_plc import Micro820PLC

plc = Micro820PLC(
    host="192.168.1.100",
    port=502,
    timeout=5.0,
    retries=3
)
```

**Register Map:**
| Address | Name | Scale Factor |
|---------|------|--------------|
| 100 | motor_speed | 1 |
| 101 | motor_current | 10 (divide) |
| 102 | temperature | 10 (divide) |
| 103 | pressure | 1 |
| 104 | conveyor_speed | 1 |
| 105 | error_code | 1 |

**Coil Map:**
| Address | Name |
|---------|------|
| 0 | motor_running |
| 1 | motor_stopped |
| 2 | fault_alarm |
| 3 | conveyor_running |
| 4 | sensor_1_active |
| 5 | sensor_2_active |
| 6 | e_stop_active |

---

### `FactoryIOMicro820`

Specialized client for Factory I/O + Micro 820 integration.

```python
from factorylm_plc import FactoryIOMicro820

plc = FactoryIOMicro820(
    host="192.168.1.100",
    port=502,
    scene_name="sorting_station"
)
```

**Additional Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| scene_name | str | "sorting_station" | Factory I/O scene identifier |

**Error Code Interpretation:**
| Code | Message |
|------|---------|
| 0 | No error |
| 1 | Motor overload |
| 2 | Temperature high |
| 3 | Conveyor jam |
| 4 | Sensor failure |
| 5 | Communication loss |

---

### `PLCConnectionManager`

Wraps a PLC client with connection management and retry logic.

```python
from factorylm_plc import PLCConnectionManager

manager = PLCConnectionManager(
    client=plc,
    auto_reconnect=True,
    max_retries=3,
    retry_delay=1.0
)
```

**Methods:**

#### `ensure_connected() -> bool`
Ensure connection is established, reconnecting if needed.

#### `read_with_retry(func: Callable) -> Any`
Execute a read operation with automatic retry on failure.

#### `write_with_retry(func: Callable) -> bool`
Execute a write operation with automatic retry.

#### `get_status() -> Dict[str, Any]`
Get current connection status including:
- `connected`: bool
- `consecutive_failures`: int
- `last_error`: str or None

**Context Manager:**
```python
with manager:
    state = manager.client.read_state()
```

---

## Data Models

### `MachineState`

Base dataclass for machine state representation.

```python
from factorylm_plc import MachineState

@dataclass
class MachineState:
    motor_running: bool = False
    motor_speed: int = 0
    motor_current: float = 0.0
    temperature: float = 0.0
    pressure: int = 0
    fault_active: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
```

**Methods:**

#### `to_dict() -> Dict[str, Any]`
Convert to dictionary for JSON serialization.

#### `to_llm_context() -> str`
Format state for LLM prompt injection.

**Example Output:**
```
Current Machine State:
- Motor: RUNNING at 75%
- Motor Current: 2.5A
- Temperature: 45.0C
- Pressure: 100 PSI
- Fault: None
- Timestamp: 14:30:25
```

---

### `FactoryState`

Extended state for Factory I/O scenes (inherits from MachineState).

```python
from factorylm_plc import FactoryState

@dataclass
class FactoryState(MachineState):
    conveyor_speed: int = 0
    conveyor_running: bool = False
    sensor_1_active: bool = False
    sensor_2_active: bool = False
    e_stop_active: bool = False
    error_code: int = 0
    error_message: str = ""
    scene_name: str = "sorting_station"
```

**Methods:**

#### `interpret_error_code(code: int) -> str`
Convert error code to human-readable message.

#### `to_llm_context() -> str`
Format state for LLM prompt injection with Factory I/O details.

**Example Output:**
```
Current Factory State (sorting_station):
- Motor: RUNNING at 75%
- Motor Current: 2.5A
- Temperature: 45.0C
- Pressure: 100 PSI
- Conveyor: RUNNING at 50%
- Sensors: S1=PART, S2=clear
- E-Stop: Clear
- Errors: None
- Timestamp: 14:30:25
```

---

## Environment Variables

The library can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| PLC_TYPE | "mock" | PLC type to use |
| PLC_HOST | "192.168.1.100" | PLC IP address |
| PLC_PORT | "502" | Modbus TCP port |
| PLC_TIMEOUT | "5" | Connection timeout |
| PLC_RETRY_COUNT | "3" | Retry attempts |
| PLC_USE_MOCK | "false" | Force mock mode |
| FACTORY_IO_SCENE | "sorting_station" | Scene name |

**Example .env:**
```bash
PLC_TYPE=factoryio_micro820
PLC_HOST=192.168.1.100
PLC_PORT=502
PLC_TIMEOUT=5
PLC_USE_MOCK=false
```

---

## Error Handling

```python
from factorylm_plc import create_plc_client
from factorylm_plc.exceptions import (
    PLCConnectionError,
    PLCReadError,
    PLCWriteError
)

plc = create_plc_client(plc_type="factoryio_micro820", host="192.168.1.100")

try:
    with plc:
        state = plc.read_state()
except PLCConnectionError as e:
    print(f"Connection failed: {e}")
except PLCReadError as e:
    print(f"Read failed: {e}")
```

---

## LLM Integration Example

```python
from factorylm_plc import create_plc_client

plc = create_plc_client(plc_type="mock")

with plc:
    # Simulate some activity
    plc.write_coil(0, True)  # Start motor
    plc.write_register(100, 75)  # Set speed

    # Get state for LLM
    state = plc.read_state()

    # Format for LLM context injection
    context = state.to_llm_context()

    # Use in LLM prompt
    prompt = f"""
    {context}

    Question: Is the motor running efficiently?
    """
```

---

## Testing

All tests work without real hardware using MockPLC:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_mock_plc.py -v

# Run with coverage
pytest tests/ --cov=factorylm_plc --cov-report=term-missing
```

---

## Module Structure

```
factorylm_plc/
├── __init__.py          # Public API exports
├── base.py              # BasePLCClient abstract class
├── models.py            # MachineState, FactoryState dataclasses
├── mock_plc.py          # MockPLC implementation
├── modbus_client.py     # ModbusTCPClient wrapper
├── micro820.py          # Micro820PLC implementation
├── factory_io.py        # FactoryIOMicro820 implementation
├── connection_manager.py # PLCConnectionManager
└── factory.py           # create_plc_client factory function
```
