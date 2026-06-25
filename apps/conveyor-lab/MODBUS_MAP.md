# Conveyor Lab Modbus Map

Factory I/O runs as a Modbus TCP server. Conveyor Lab can connect to it directly, or fall back to the simulator when auto-connect is disabled or unavailable.

## Connection

| Setting | Env Var | Default |
|---------|---------|---------|
| Host | `MODBUS_HOST` | `100.83.251.23` |
| Port | `MODBUS_PORT` | `502` |
| Unit ID | `MODBUS_UNIT_ID` | `1` |
| Auto-connect | `FACTORYIO_AUTO_CONNECT` | `true` |

## Coils

Digital outputs written by Conveyor Lab.

| Name | Address | Purpose |
|------|---------|---------|
| `CONVEYOR` | `0` | Conveyor belt on/off |
| `FORWARD` | `1` | Forward direction |
| `REVERSE` | `2` | Reverse direction |

## Discrete Inputs

Digital inputs read from Factory I/O.

| Name | Address | Purpose |
|------|---------|---------|
| `RUNNING` | `0` | Conveyor is running |
| `SENSOR_ENTRY` | `1` | Entry sensor |
| `SENSOR_EXIT` | `2` | Exit sensor |
| `AT_ENTRY` | `3` | Part at entry |
| `AT_EXIT` | `4` | Part at exit |

## Registers

The current basic scene does not map speed setpoints or analog readings to holding or input registers. The UI displays speed in hertz, but Factory I/O speed control is not wired to a register in the current map.

Add any future register mapping here before relying on it in the backend or UI.
