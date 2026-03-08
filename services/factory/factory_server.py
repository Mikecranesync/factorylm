#!/usr/bin/env python3
"""
Factory Server — Live PLC Tag API for the FactoryLM Cluster
============================================================
Connects to the Modbus TCP server on the PLC laptop, polls live tag data
from the Sorting by Height scene, detects faults, and serves a REST API.

Runs on CHARLIE (192.168.1.12:8600).

Usage:
    python -m services.factory.factory_server
    MODBUS_HOST=100.72.2.99 python -m services.factory.factory_server
"""

import asyncio
import datetime
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from fastapi import FastAPI
from pymodbus.client import ModbusTcpClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODBUS_HOST = os.getenv("MODBUS_HOST", "192.168.1.20")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5020"))
POLL_INTERVAL_MS = int(os.getenv("POLL_INTERVAL_MS", "500"))
HISTORY_SIZE = int(os.getenv("HISTORY_SIZE", "100"))
SERVER_PORT = int(os.getenv("FACTORY_SERVER_PORT", "8600"))

# ---------------------------------------------------------------------------
# I/O Map — must match cookoff/modbus_server.py
# ---------------------------------------------------------------------------

SENSOR_NAMES = [
    "high_sensor", "low_sensor", "pallet_sensor", "loaded",
    "at_left_entry", "at_left_exit", "at_right_entry", "at_right_exit",
    "start_button", "reset_button", "stop_button", "e_stop",
    "auto_mode", "fio_running",
]

ACTUATOR_NAMES = [
    "conveyor_entry", "load", "unload", "transfer_left", "transfer_right",
    "conveyor_left", "conveyor_right", "start_light", "reset_light", "stop_light",
]

REGISTER_NAMES = ["counter"]

# ---------------------------------------------------------------------------
# Fault Detection (sorting-scene specific)
# ---------------------------------------------------------------------------


class FaultSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class Fault:
    code: str
    severity: FaultSeverity
    title: str
    description: str


_SEVERITY_ORDER = {
    FaultSeverity.EMERGENCY: 0,
    FaultSeverity.CRITICAL: 1,
    FaultSeverity.WARNING: 2,
    FaultSeverity.INFO: 3,
}


def detect_sorting_faults(
    tags: dict[str, Any],
    prev_tags: dict[str, Any] | None = None,
    stuck_counts: dict[str, int] | None = None,
) -> list[Fault]:
    """Analyze sorting-scene tags and return detected faults."""
    faults: list[Fault] = []

    if not tags:
        faults.append(Fault("CONN", FaultSeverity.CRITICAL,
                            "Modbus Disconnected",
                            "Cannot read tags from PLC laptop."))
        return faults

    e_stop = tags.get("e_stop", False)
    fio_running = tags.get("fio_running", False)
    conveyor_entry = tags.get("conveyor_entry", False)
    transfer_left = tags.get("transfer_left", False)
    transfer_right = tags.get("transfer_right", False)
    high_sensor = tags.get("high_sensor", False)
    low_sensor = tags.get("low_sensor", False)

    # EMERGENCY: E-Stop
    if e_stop:
        faults.append(Fault("E001", FaultSeverity.EMERGENCY,
                            "Emergency Stop Active",
                            "E-stop pressed. All motion halted."))

    # CRITICAL: Entry conveyor stopped while scene running
    if fio_running and not conveyor_entry and not e_stop:
        faults.append(Fault("C001", FaultSeverity.CRITICAL,
                            "Entry Conveyor Stopped",
                            "Factory I/O is running but entry conveyor is off."))

    # CRITICAL: Both diverters active simultaneously
    if transfer_left and transfer_right:
        faults.append(Fault("C002", FaultSeverity.CRITICAL,
                            "Diverter Conflict",
                            "Both left and right diverters active simultaneously."))

    # WARNING: Sensor stuck (item jam)
    if stuck_counts:
        for sensor in ("high_sensor", "low_sensor"):
            if stuck_counts.get(sensor, 0) > 10:
                faults.append(Fault("J001", FaultSeverity.WARNING,
                                    f"Possible Jam at {sensor}",
                                    f"{sensor} has been active for {stuck_counts[sensor]} consecutive polls."))

    # INFO states
    if not faults:
        if not fio_running:
            faults.append(Fault("IDLE", FaultSeverity.INFO,
                                "Factory I/O Not Running",
                                "Scene is stopped or paused."))
        else:
            faults.append(Fault("OK", FaultSeverity.INFO,
                                "System Running Normally",
                                "Sorting by Height scene operating normally."))

    faults.sort(key=lambda f: _SEVERITY_ORDER[f.severity])
    return faults


# ---------------------------------------------------------------------------
# Modbus Poller
# ---------------------------------------------------------------------------


class ModbusPoller:
    """Background poller that reads tags from the PLC laptop's Modbus server."""

    def __init__(self, host: str, port: int, interval_ms: int, history_size: int):
        self.host = host
        self.port = port
        self.interval_s = interval_ms / 1000.0
        self.history: deque[dict] = deque(maxlen=history_size)
        self.latest: dict[str, Any] | None = None
        self.connected = False
        self.total_polls = 0
        self.errors = 0
        self.start_time = 0.0
        self._task: asyncio.Task | None = None
        self._client: ModbusTcpClient | None = None
        self._stuck_counts: dict[str, int] = {}
        self._prev_tags: dict[str, Any] | None = None

    async def start(self):
        self.start_time = time.monotonic()
        self._task = asyncio.create_task(self._poll_loop())
        log.info("Poller started -> %s:%d (%.1f Hz)", self.host, self.port,
                 1.0 / self.interval_s)

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            self._client.close()
        log.info("Poller stopped. %d polls, %d errors", self.total_polls, self.errors)

    async def _poll_loop(self):
        while True:
            tags = await asyncio.to_thread(self._read_tags)
            self.total_polls += 1
            if tags:
                self.latest = tags
                self.history.append(tags)
                self.connected = True
                self._update_stuck_counts(tags)
            else:
                self.errors += 1
                self.connected = False

            if self.total_polls % 60 == 0:
                elapsed = time.monotonic() - self.start_time
                log.info("Poll #%d | connected=%s | errors=%d | uptime=%.0fs",
                         self.total_polls, self.connected, self.errors, elapsed)

            await asyncio.sleep(self.interval_s)

    def _read_tags(self) -> dict[str, Any] | None:
        """Blocking Modbus read — runs in thread."""
        if not self._client or not self._client.is_socket_open():
            self._client = ModbusTcpClient(self.host, port=self.port, timeout=3)
            if not self._client.connect():
                self._client = None
                return None
            log.info("Modbus connected to %s:%d", self.host, self.port)

        try:
            tags: dict[str, Any] = {
                "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            }

            # Sensors: FC1 (coils) addr 0-13
            result = self._client.read_coils(address=0, count=len(SENSOR_NAMES))
            if result.isError():
                self._client.close()
                self._client = None
                return None
            for i, name in enumerate(SENSOR_NAMES):
                tags[name] = bool(result.bits[i])

            # Actuators: FC2 (discrete inputs) addr 0-9
            result = self._client.read_discrete_inputs(address=0, count=len(ACTUATOR_NAMES))
            if result.isError():
                self._client.close()
                self._client = None
                return None
            for i, name in enumerate(ACTUATOR_NAMES):
                tags[name] = bool(result.bits[i])

            # Registers: FC3 (holding registers) addr 0
            result = self._client.read_holding_registers(address=0, count=len(REGISTER_NAMES))
            if not result.isError():
                for i, name in enumerate(REGISTER_NAMES):
                    tags[name] = result.registers[i]

            return tags
        except Exception as e:
            log.warning("Modbus read error: %s", e)
            self._client.close()
            self._client = None
            return None

    def _update_stuck_counts(self, tags: dict[str, Any]):
        for sensor in ("high_sensor", "low_sensor"):
            if tags.get(sensor, False):
                self._stuck_counts[sensor] = self._stuck_counts.get(sensor, 0) + 1
            else:
                self._stuck_counts[sensor] = 0

    @property
    def faults(self) -> list[Fault]:
        return detect_sorting_faults(self.latest or {}, self._prev_tags, self._stuck_counts)

    @property
    def uptime(self) -> float:
        return time.monotonic() - self.start_time if self.start_time else 0.0


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

poller: ModbusPoller | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global poller
    poller = ModbusPoller(MODBUS_HOST, MODBUS_PORT, POLL_INTERVAL_MS, HISTORY_SIZE)
    await poller.start()
    yield
    await poller.stop()


app = FastAPI(title="FactoryLM Factory Server", lifespan=lifespan)


@app.get("/")
def root():
    return {
        "service": "factory-server",
        "version": "1.0.0",
        "modbus_target": f"{MODBUS_HOST}:{MODBUS_PORT}",
        "endpoints": ["/health", "/api/tags/live", "/api/tags/history",
                       "/api/faults", "/api/state"],
    }


@app.get("/health")
def health():
    return {
        "connected": poller.connected if poller else False,
        "total_polls": poller.total_polls if poller else 0,
        "errors": poller.errors if poller else 0,
        "uptime_s": round(poller.uptime, 1) if poller else 0,
        "modbus_target": f"{MODBUS_HOST}:{MODBUS_PORT}",
    }


@app.get("/api/tags/live")
def tags_live():
    if not poller or not poller.latest:
        return {"error": "No data yet", "connected": False}
    return poller.latest


@app.get("/api/tags/history")
def tags_history(limit: int = 100):
    if not poller:
        return []
    entries = list(poller.history)
    return entries[-limit:]


@app.get("/api/faults")
def faults():
    if not poller:
        return []
    return [asdict(f) for f in poller.faults]


@app.get("/api/state")
def state():
    return {
        "tags": poller.latest if poller else None,
        "faults": [asdict(f) for f in poller.faults] if poller else [],
        "connected": poller.connected if poller else False,
        "poll_count": poller.total_polls if poller else 0,
        "uptime_s": round(poller.uptime, 1) if poller else 0,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
