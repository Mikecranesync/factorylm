# PRD-005: Factory I/O + Micro 820 Integration Layer
## Phase 1.5: Real Hardware Bridge for FactoryLM

**Domain:** factorylm.com
**GitHub:** github.com/factorylm/plc-client
**Product:** FactoryLM Factory I/O Integration
**Version:** 0.3.1
**Depends On:** PRD-001 (core), PRD-003 (plc-client base)
**Status:** PRE-BUILD - Hardware Integration Phase

---

## Executive Summary

This PRD extends the PLC Client (PRD-003) to work specifically with a **Factory I/O - Micro 820** setup. It provides:

- Concrete Modbus register mapping matching CCW configuration
- Factory I/O scene-aware data interpretation
- Real-time state reading from live hardware
- Mock mode for development without hardware
- Integration point for Voice HMI

**This is the bridge between simulation and the HMI.**

---

## Architecture

```
┌─────────────────┐    Modbus TCP    ┌──────────────┐    Modbus TCP    ┌──────────────────┐
│  Factory I/O    │◄────────────────►│  Micro 820   │◄────────────────►│  FactoryLM HMI   │
│  (Simulation)   │    Port 502      │  (PLC)       │    Port 502      │  (Python)        │
└─────────────────┘                  └──────────────┘                  └──────────────────┘
      ▲                                    ▲                                    │
      │                                    │                                    │
      └────────── Physical I/O ────────────┘                                    │
           (Virtual sensors/motors)                                             │
                                                                               │
                              ┌─────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  LLM (GROQ/Claude)  │
                    │  "Why is motor hot?"│
                    └─────────────────────┘
```

---

## Modbus Register Map (Must Match CCW Config)

These addresses MUST match what you configure in CCW:

### Holding Registers (Read/Write)

| Address | Variable Name | Type | Scale | Description |
|---------|--------------|------|-------|-------------|
| 100 | motor_speed | INT | 1 | Motor speed 0-100% |
| 101 | motor_current | INT | 10 | Current in 0.1A (25 = 2.5A) |
| 102 | temperature | INT | 10 | Temp in 0.1C (650 = 65.0C) |
| 103 | pressure | INT | 1 | Pressure in PSI |
| 104 | conveyor_speed | INT | 1 | Conveyor belt speed % |
| 105 | error_code | INT | 1 | Active error code (0=none) |

### Coils (Read/Write - Boolean)

| Address | Variable Name | Description |
|---------|--------------|-------------|
| 0 | motor_running | TRUE if motor is running |
| 1 | motor_stopped | TRUE if motor is stopped |
| 2 | fault_alarm | TRUE if fault active |
| 3 | conveyor_running | TRUE if conveyor running |
| 4 | sensor_1_active | Part detected at sensor 1 |
| 5 | sensor_2_active | Part detected at sensor 2 |
| 6 | e_stop_active | Emergency stop pressed |

### Discrete Inputs (Read-Only)

| Address | Variable Name | Description |
|---------|--------------|-------------|
| 0 | start_button | Start button pressed |
| 1 | stop_button | Stop button pressed |
| 2 | reset_button | Reset button pressed |

---

## Implementation Requirements

### 1. FactoryIO_Micro820_Client (extends Micro820PLC)

```python
class FactoryIOMicro820(Micro820PLC):
    """
    Specialized client for Factory I/O + Micro 820 setup.
    Knows about Factory I/O scene semantics.
    """

    # Register map matching CCW configuration
    REGISTERS = {
        "motor_speed": 100,
        "motor_current": 101,
        "temperature": 102,
        "pressure": 103,
        "conveyor_speed": 104,
        "error_code": 105,
    }

    COILS = {
        "motor_running": 0,
        "motor_stopped": 1,
        "fault_alarm": 2,
        "conveyor_running": 3,
        "sensor_1": 4,
        "sensor_2": 5,
        "e_stop": 6,
    }

    SCALE_FACTORS = {
        "motor_current": 10,  # Divide by 10
        "temperature": 10,    # Divide by 10
    }

    def read_state(self) -> FactoryState:
        """Read all registers and return interpreted state"""
        pass

    def interpret_error_code(self, code: int) -> str:
        """Convert error code to human-readable message"""
        ERROR_CODES = {
            0: "No error",
            1: "Motor overload",
            2: "Temperature high",
            3: "Conveyor jam",
            4: "Sensor failure",
            5: "Communication loss",
        }
        return ERROR_CODES.get(code, f"Unknown error {code}")
```

### 2. FactoryState (Extended MachineState)

```python
@dataclass
class FactoryState(MachineState):
    """Extended state for Factory I/O scenes"""
    conveyor_speed: int = 0
    conveyor_running: bool = False
    sensor_1_active: bool = False
    sensor_2_active: bool = False
    e_stop_active: bool = False
    error_code: int = 0
    error_message: str = ""
    scene_name: str = "sorting_station"  # Factory I/O scene

    def to_llm_context(self) -> str:
        """Format state for LLM prompt injection"""
        return f"""
Current Factory State:
- Motor: {'RUNNING at ' + str(self.motor_speed) + '%' if self.motor_running else 'STOPPED'}
- Motor Current: {self.motor_current}A
- Temperature: {self.temperature}C
- Pressure: {self.pressure} PSI
- Conveyor: {'RUNNING at ' + str(self.conveyor_speed) + '%' if self.conveyor_running else 'STOPPED'}
- Sensors: S1={'PART' if self.sensor_1_active else 'clear'}, S2={'PART' if self.sensor_2_active else 'clear'}
- E-Stop: {'ENGAGED!' if self.e_stop_active else 'Clear'}
- Errors: {self.error_message if self.error_code else 'None'}
"""
```

### 3. Connection Manager

```python
class PLCConnectionManager:
    """Manages connection to Micro 820 with reconnection logic"""

    def __init__(self, host: str, port: int = 502,
                 retry_count: int = 3, retry_delay: float = 1.0):
        self.host = host
        self.port = port
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.connected = False
        self.last_error = None

    def ensure_connected(self) -> bool:
        """Connect or reconnect if needed"""
        pass

    def read_with_retry(self, func: Callable) -> Any:
        """Execute read function with automatic retry"""
        pass
```

### 4. Factory Function Update

```python
def create_plc_client(plc_type: str, host: str, port: int = 502) -> BasePLCClient:
    """
    Factory function for PLC clients

    plc_types:
    - "factoryio_micro820" - Factory I/O + Micro 820 combo
    - "micro820" - Generic Micro 820 (use PRD-003)
    - "mock" - Mock PLC for testing
    """
    if plc_type == "factoryio_micro820":
        return FactoryIOMicro820(host, port)
    elif plc_type == "micro820":
        return Micro820PLC(host, port)
    elif plc_type == "mock":
        return MockPLC()
    else:
        raise ValueError(f"Unknown PLC type: {plc_type}")
```

---

## Testing Strategy

### Without Hardware (Mock Mode)
```python
# Uses MockPLC - no network needed
plc = create_plc_client("mock", "")
state = plc.read_state()
assert state.motor_speed >= 0
```

### With Hardware (Integration Test)
```python
# Requires running Factory I/O + Micro 820
# Skip in CI, run manually
@pytest.mark.hardware
def test_live_connection():
    plc = create_plc_client("factoryio_micro820", "192.168.1.100")
    state = plc.read_state()
    assert state.timestamp > 0
```

---

## Configuration (.env)

```bash
# PLC Configuration
PLC_TYPE=factoryio_micro820
PLC_HOST=192.168.1.100
PLC_PORT=502
PLC_TIMEOUT=5
PLC_RETRY_COUNT=3

# Factory I/O Scene
FACTORY_IO_SCENE=sorting_station

# LLM (from PRD-001)
LLM_PROVIDER=groq
GROQ_API_KEY=your-key-here
```

---

## Completion Criteria

- [ ] FactoryIOMicro820 client implemented
- [ ] Register map matches CCW configuration
- [ ] FactoryState dataclass with Factory I/O semantics
- [ ] Connection manager with retry logic
- [ ] Error code interpretation
- [ ] Mock mode working
- [ ] Unit tests passing
- [ ] Integration test (with hardware) documented
- [ ] .env.example updated
- [ ] README with Factory I/O setup instructions

---

## Success Criteria

```
FACTORYLM_FACTORYIO_COMPLETE

- Can read live state from Factory I/O via Micro 820
- Register map matches CCW configuration
- Error codes interpreted correctly
- Connection resilient to network issues
- Ready for Voice HMI integration

Example:
plc = create_plc_client("factoryio_micro820", "192.168.1.100")
state = plc.read_state()
print(state.to_llm_context())
# "Motor: RUNNING at 75%, Temperature: 62.5C..."
```

---

## Ralph Loop Instructions

```text
You are building the Factory I/O + Micro 820 integration layer.

HOMEWORK PHASE:
1. Review PRD-003 (base PLC client)
2. Study pymodbus register/coil reading
3. Understand scaled value handling
4. Document findings in HOMEWORK.md

DESIGN PHASE:
1. Verify register map matches the user's CCW config
2. Plan error code mapping
3. Design reconnection strategy
4. Document in DESIGN.md

EXECUTION PHASE:
1. Extend Micro820PLC with Factory I/O specifics
2. Implement FactoryState dataclass
3. Add error code interpretation
4. Create connection manager
5. Update factory function
6. Write unit tests with MockPLC
7. Document hardware setup steps
8. When criteria met, output success summary

CRITICAL:
- Register addresses MUST match CCW config (100-105, coils 0-6)
- Scale factors MUST be applied (temperature/10, current/10)
- Connection retry logic REQUIRED
- MockPLC MUST simulate Factory I/O behavior

When complete, append "FACTORYLM_FACTORYIO_COMPLETE" to end of this PRD.
```

---

## Next Steps After This PRD

1. **Voice HMI (PRD-002)**: Use FactoryIOMicro820 client for live data
2. **Web Dashboard (PRD-004)**: Real-time gauges from live PLC
3. **ML Training (Phase 4)**: Historical data from Factory I/O runs

---

**BUILD AFTER PRD-003 or IN PARALLEL. Provides real hardware connectivity.**
