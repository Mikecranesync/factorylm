# Unified PLC I/O Adapter (factorylm-io)

> Future architecture plan for a unified multi-protocol PLC I/O layer.
> Consolidates the best ideas from 6 implementations into one clean design.
> Created 2026-03-02 during V1 consolidation.

## Why This Exists

The FactoryLM repo had 6 overlapping PLC communication implementations:

1. `services/plc-modbus/` — Modbus TCP backend + dashboard (now V1 demo)
2. `services/telegram/io_adapter.py` — HTTP-based PLC reader
3. `services/jarvis-telegram/` — Telegram bot with Claude bridge
4. `services/discord-adapter/` — Discord bot with tag reading + VFD control
5. `packages/factorylm-cli/` — 3 sync drivers (Modbus, EtherNet/IP, S7)
6. `services/factorylm-discord-layer/` — Agent fleet Discord relay

`plc-modbus` was chosen as V1. This document captures the unified adapter
architecture that would replace all of them in V2.

---

## Architecture

```
                    ┌─────────────────────────┐
                    │     IODaemon (async)     │
                    │  - tag cache (in-memory) │
                    │  - poll scheduler        │
                    │  - event bus             │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │  Modbus    │ │ EtherNet/ │ │    S7     │
        │  Driver    │ │ IP Driver │ │  Driver   │
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
              │              │              │
         pymodbus        pycomm3        snap7
              │              │              │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │ Micro 820  │ │  Logix    │ │  S7-1200  │
        │ Port 502   │ │ Port 44818│ │  Port 102 │
        └───────────┘ └───────────┘ └───────────┘

        ┌─────────────────────────────────────────┐
        │           HTTP Gateway Driver           │
        │   (wraps any REST API as a TagDriver)   │
        └─────────────┬───────────────────────────┘
                      │
                 Any HTTP endpoint
                 (e.g., plc-modbus /api/plc/io)
```

## Core Abstractions

### TagDriver ABC

Stolen from `factorylm-cli/plc/` — the cleanest abstraction we had.

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class TagDriver(ABC):
    """Base class for all PLC protocol drivers."""

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def read_tags(self, names: list[str]) -> Dict[str, Any]: ...

    @abstractmethod
    async def write_tag(self, name: str, value: Any) -> bool: ...

    @abstractmethod
    async def discover_tags(self) -> list[str]: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @property
    @abstractmethod
    def protocol(self) -> str: ...
```

### Driver Wrapping Strategy

The `factorylm-cli` drivers are synchronous. Wrap them with `asyncio.to_thread`:

```python
class AsyncModbusDriver(TagDriver):
    """Async wrapper around sync ModbusTCPClient."""

    def __init__(self, host: str, port: int = 502):
        self._sync = ModbusTCPClient(host=host, port=port)

    async def connect(self) -> bool:
        return await asyncio.to_thread(self._sync.connect)

    async def read_tags(self, names: list[str]) -> Dict[str, Any]:
        return await asyncio.to_thread(self._sync.read_tags, names)
```

### IODaemon

Central coordinator that manages drivers, caches tags, and emits events.

```python
class IODaemon:
    """Manages multiple PLC connections, caches tags, emits events."""

    def __init__(self):
        self.drivers: Dict[str, TagDriver] = {}
        self.tag_cache: Dict[str, TagValue] = {}
        self.event_bus = EventBus()

    async def add_device(self, name: str, driver: TagDriver) -> None: ...
    async def remove_device(self, name: str) -> None: ...
    async def poll_once(self) -> Dict[str, Any]: ...
    async def run(self, interval: float = 1.0) -> None: ...
```

## Tag Normalization

Different PLCs use different naming. Normalize to a common vocabulary.

```python
KNOWN_ALIASES = {
    # Micro 820 Modbus coils
    "coil_0": "conveyor.run",
    "coil_1": "emitter.run",
    "coil_2": "sensor.start",
    "coil_3": "sensor.end",
    "coil_4": "remote.run_command",
    # Micro 820 Modbus registers
    "hr_100": "counter.item_count",
    "hr_101": "motor.speed",
    "hr_102": "motor.current",
    # EtherNet/IP (Logix) tags
    "Program:MainProgram.ConveyorRun": "conveyor.run",
    "Program:MainProgram.MotorSpeed": "motor.speed",
    # Siemens S7 (DB addresses)
    "DB1.DBX0.0": "conveyor.run",
    "DB1.DBW2": "motor.speed",
}
```

## Multi-Protocol Scanner

Combines the network scanner from `plc-modbus` with the EtherNet/IP discovery from `discovery_daemon.py`:

```python
async def scan_subnet(subnet: str = "192.168.1") -> list[DiscoveredDevice]:
    """Scan for all known PLC protocols in parallel."""
    results = await asyncio.gather(
        scan_modbus(subnet, port=502),        # pymodbus probe
        scan_ethernetip(subnet, port=44818),  # pycomm3 probe
        scan_s7(subnet, port=102),            # snap7 probe
    )
    return merge_results(results)
```

## HTTP Gateway Driver

Stolen from `telegram/io_adapter.py` — the idea that any REST API can be a tag source.

```python
class HTTPGatewayDriver(TagDriver):
    """Reads tags from any HTTP endpoint that returns JSON."""

    def __init__(self, base_url: str, tags_path: str = "/api/plc/io"):
        self._base_url = base_url
        self._tags_path = tags_path
        self._session: Optional[httpx.AsyncClient] = None

    async def read_tags(self, names: list[str]) -> Dict[str, Any]:
        resp = await self._session.get(f"{self._base_url}{self._tags_path}")
        data = resp.json()
        # Flatten nested response into tag dict
        return self._extract_tags(data, names)
```

This lets any adapter (Telegram, Discord, CLI) read tags from the plc-modbus
backend without knowing Modbus at all.

---

## Stolen Patterns Table

| Pattern | Source | Why It's Good |
|---------|--------|---------------|
| BasePLCClient ABC | `factorylm-cli/plc/` | Clean 6-method interface, works for all protocols |
| EtherNet/IP driver | `factorylm-cli/plc/enip.py` | Production pycomm3 wrapper with tag discovery |
| S7 driver | `factorylm-cli/plc/s7.py` | Production snap7 wrapper for Siemens |
| Factory pattern | `factorylm-cli/plc/` | `create_client(protocol, host)` returns correct driver |
| HTTP gateway | `telegram/io_adapter.py` | Any REST endpoint becomes a tag source |
| Multi-node routing | `telegram/telegram_router.py` | Per-chat sticky routing to cluster nodes |
| Background fault polling | `telegram/factorylm_bot.py` | 5s poll loop with proactive alerts on state change |
| Rich embeds | `discord-adapter/embeds.py` | Confidence bars, color-coded status formatting |
| Scheduled reports | `discord-adapter/tasks.py` | DST-aware daily health + progress reports |
| Claude CLI bridge | `jarvis-telegram/integrations/` | Route messages to Claude subprocess |
| Groq vision | `jarvis-telegram/integrations/` | Fast fault diagnosis from equipment photos |
| CMMS work orders | `jarvis-telegram/handlers/photo.py` | Photo → structured maintenance request |
| Agent fleet relay | `factorylm-discord-layer/` | HTTP → Discord webhook with rate limiting |
| TagStore (SQLite) | `factorylm-cli/store/` | Persistent tag history with incidents + insights |
| Typer CLI | `factorylm-cli/` | `factorylm tags`, `factorylm connect` commands |
| TOML config | `factorylm-cli/config.py` | `~/.factorylm/config.toml` with env overrides |
| MockPLC | `plc-modbus/src/` | 368-line simulation for hardware-free demos |
| SSE streaming | `plc-modbus/backend/` | Real-time tag updates to browser dashboards |

## Implementation Estimate

| Agent | Scope | Lines |
|-------|-------|-------|
| Agent 1 | TagDriver ABC + 3 async drivers + factory | ~350 |
| Agent 2 | IODaemon + tag cache + event bus + scanner | ~350 |
| Agent 3 | HTTP gateway driver + CLI commands + tests | ~250 |
| **Total** | | **~950** |

## Prerequisites

- V1 demo (`plc-modbus`) running and stable
- Existing unit tests passing
- `factorylm-cli` driver code available in `docs/archive/factorylm-cli/`

## File Structure (Proposed)

```
packages/factorylm-io/
├── src/factorylm_io/
│   ├── __init__.py
│   ├── drivers/
│   │   ├── __init__.py
│   │   ├── base.py          # TagDriver ABC
│   │   ├── modbus.py        # AsyncModbusDriver
│   │   ├── ethernetip.py    # AsyncEtherNetIPDriver
│   │   ├── s7.py            # AsyncS7Driver
│   │   ├── http_gateway.py  # HTTPGatewayDriver
│   │   └── factory.py       # create_driver()
│   ├── daemon.py             # IODaemon
│   ├── tags.py               # TagValue, KNOWN_ALIASES, normalization
│   ├── scanner.py            # Multi-protocol subnet scanner
│   └── events.py             # EventBus
├── tests/
│   ├── test_drivers.py
│   ├── test_daemon.py
│   └── test_scanner.py
└── pyproject.toml
```
