#!/usr/bin/env python3
"""FactoryLM PLC Universal Reader — NiceGUI web app.

Live tag browser, trend charts, and write panel for Micro820 (Modbus)
and S7-1200 (snap7) PLCs.  Reuses drivers from the factorylm monorepo.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

# ── Monorepo path so we can import the PLC drivers directly ──
_MONOREPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(_MONOREPO, "packages", "factorylm-cli", "src"))

from nicegui import app, run, ui  # noqa: E402

from factorylm.plc.modbus import (  # noqa: E402
    DEFAULT_COILS,
    DEFAULT_REGISTERS,
    SCALE_FACTORS,
    ModbusPLCClient,
)
from factorylm.plc.s7 import (  # noqa: E402
    DEFAULT_TAGS as S7_DEFAULT_TAGS,
    S7Client,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
logger = logging.getLogger("plc-reader")
logging.getLogger("httpx").setLevel(logging.WARNING)

# Tags that should never appear in the Write dropdown
READ_ONLY_TAGS = {"fault_alarm", "e_stop"}

# Default Jarvis Node URL (PLC Laptop bridge)
DEFAULT_BRIDGE_URL = "http://100.72.2.99:8765"

# Matrix API — same data source the Discord bot uses
MATRIX_API_URL = "http://100.72.2.99:8001"

STALE_THRESHOLD_S = 30  # seconds before data is considered stale


# ═══════════════════════════════════════════════════════════════════════
#  Machine State Monitor — change-driven logging & mode derivation
# ═══════════════════════════════════════════════════════════════════════
class MachineMode(Enum):
    OFFLINE = "OFFLINE"
    STALE = "STALE"
    E_STOP = "E_STOP"
    FAULT = "FAULT"
    RUNNING = "RUNNING"
    IDLE = "IDLE"


MACHINE_MODE_COLORS = {
    MachineMode.OFFLINE: "grey",
    MachineMode.STALE: "orange",
    MachineMode.E_STOP: "red",
    MachineMode.FAULT: "red",
    MachineMode.RUNNING: "green",
    MachineMode.IDLE: "blue",
}


class MachineStateMonitor:
    """Sits between polling loop and UI. Diffs tags, derives mode, logs only changes."""

    def __init__(self) -> None:
        self.mode: MachineMode = MachineMode.OFFLINE
        self.prev_tags: dict[str, Any] = {}
        self.last_change: datetime | None = None
        self.change_log: deque[tuple[datetime, str]] = deque(maxlen=50)
        self._initialized: bool = False

    def update(self, tags: dict[str, Any], stale: bool) -> bool:
        """Feed new tags. Returns True if anything changed."""
        # Derive mode
        if stale:
            new_mode = MachineMode.STALE
        elif tags.get("e_stop") or tags.get("e_stop_active"):
            new_mode = MachineMode.E_STOP
        elif tags.get("fault_alarm") or tags.get("fault_active"):
            new_mode = MachineMode.FAULT
        elif tags.get("motor_running"):
            new_mode = MachineMode.RUNNING
        else:
            new_mode = MachineMode.IDLE

        changed = False

        # Mode transition
        if new_mode != self.mode:
            msg = f"Machine: {self.mode.value} → {new_mode.value}"
            logger.info(msg)
            self.change_log.appendleft((datetime.now(), msg))
            self.mode = new_mode
            changed = True

        # Tag-level diff (skip on first poll — just record initial state)
        if not self._initialized:
            self.prev_tags = dict(tags)
            self._initialized = True
            logger.info("Initial state: %s | %d tags", new_mode.value, len(tags))
            changed = True
        else:
            for k, v in tags.items():
                old = self.prev_tags.get(k)
                if old != v:
                    msg = f"{k}: {old} → {v}"
                    logger.info("[CHANGE] %s", msg)
                    self.change_log.appendleft((datetime.now(), msg))
                    changed = True
            self.prev_tags = dict(tags)

        if changed:
            self.last_change = datetime.now()

        return changed


# ═══════════════════════════════════════════════════════════════════════
#  Jarvis Bridge PLC Client — proxies Modbus via PLC Laptop shell API
# ═══════════════════════════════════════════════════════════════════════
class JarvisBridgePLCClient:
    """Reads/writes Micro820 Modbus registers via the Jarvis Node shell API.

    Instead of direct Modbus TCP (which requires the app to be on the PLC
    subnet), this client sends Python one-liners to the Jarvis Node on the
    PLC Laptop, which has direct Ethernet access to the PLC.
    """

    # Python script template run on the PLC Laptop via shell API
    _READ_SCRIPT = (
        "import json; from pymodbus.client import ModbusTcpClient; "
        "c=ModbusTcpClient(host='{host}',port={port},timeout=5); c.connect(); "
        "r=c.read_holding_registers(address=100,count=6); "
        "regs=r.registers if r and not r.isError() else []; "
        "c2=c.read_coils(address=0,count=7); "
        "coils=c2.bits[:7] if c2 and not c2.isError() else []; "
        "c.close(); "
        "print(json.dumps({{'registers':regs,'coils':coils}}))"
    )

    _WRITE_REG_SCRIPT = (
        "from pymodbus.client import ModbusTcpClient; "
        "c=ModbusTcpClient(host='{host}',port={port},timeout=5); c.connect(); "
        "r=c.write_register(address={addr},value={val}); c.close(); "
        "print('OK' if r and not r.isError() else 'FAIL')"
    )

    _WRITE_COIL_SCRIPT = (
        "from pymodbus.client import ModbusTcpClient; "
        "c=ModbusTcpClient(host='{host}',port={port},timeout=5); c.connect(); "
        "r=c.write_coil(address={addr},value={val}); c.close(); "
        "print('OK' if r and not r.isError() else 'FAIL')"
    )

    def __init__(
        self,
        bridge_url: str = DEFAULT_BRIDGE_URL,
        plc_host: str = "192.168.1.100",
        plc_port: int = 502,
    ) -> None:
        self.bridge_url = bridge_url.rstrip("/")
        self.host = plc_host  # matches ModbusPLCClient.host for badge display
        self.plc_host = plc_host
        self.plc_port = plc_port
        self._connected = False

    def _shell(self, command: str, timeout: int = 10) -> dict:
        """Execute a shell command on the PLC Laptop via Jarvis Node."""
        payload = json.dumps({"command": command, "timeout": timeout}).encode()
        req = urllib.request.Request(
            f"{self.bridge_url}/shell",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
            return json.loads(resp.read())

    def connect(self) -> bool:
        """Test connectivity: ping Jarvis Node, then test Modbus connect."""
        try:
            # Health check on Jarvis Node
            req = urllib.request.Request(f"{self.bridge_url}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                health = json.loads(resp.read())
            if health.get("status") != "online":
                logger.warning("Jarvis Node not online: %s", health)
                return False

            # Test Modbus connectivity through the bridge
            result = self._shell(
                f"python -c \"from pymodbus.client import ModbusTcpClient; "
                f"c=ModbusTcpClient(host='{self.plc_host}',port={self.plc_port},timeout=5); "
                f"print('OK' if c.connect() else 'FAIL'); c.close()\"",
                timeout=10,
            )
            ok = result.get("stdout", "").strip() == "OK"
            self._connected = ok
            if ok:
                logger.info(
                    "Bridge connected: %s → %s:%d",
                    self.bridge_url, self.plc_host, self.plc_port,
                )
            else:
                logger.warning("Bridge Modbus test failed: %s", result)
            return ok
        except Exception as exc:
            logger.error("Bridge connect error: %s", exc)
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def read_tags(self) -> dict[str, Any]:
        """Read all Micro820 registers and coils via the bridge."""
        if not self._connected:
            raise ConnectionError("Bridge not connected")

        script = self._READ_SCRIPT.format(host=self.plc_host, port=self.plc_port)
        result = self._shell(f'python -c "{script}"', timeout=10)

        if result.get("returncode") != 0:
            stderr = result.get("stderr", "")
            logger.warning("Bridge read failed: %s", stderr[:200])
            raise ConnectionError(f"Bridge read error: {stderr[:100]}")

        raw = json.loads(result["stdout"].strip())
        regs = raw.get("registers", [])
        coils = raw.get("coils", [])

        data: dict[str, Any] = {}
        reg_names = list(DEFAULT_REGISTERS.keys())
        for i, name in enumerate(reg_names):
            if i < len(regs):
                val = regs[i]
                data[name] = val / SCALE_FACTORS[name] if name in SCALE_FACTORS else val

        coil_names = list(DEFAULT_COILS.keys())
        for i, name in enumerate(coil_names):
            if i < len(coils):
                data[name] = bool(coils[i])

        return data

    def write_tag(self, name: str, value: Any) -> bool:
        """Write a tag value via the bridge."""
        if not self._connected:
            raise ConnectionError("Bridge not connected")

        if name in DEFAULT_REGISTERS:
            addr = DEFAULT_REGISTERS[name]
            if name in SCALE_FACTORS:
                raw = int(float(value) * SCALE_FACTORS[name])
            else:
                raw = int(value)
            script = self._WRITE_REG_SCRIPT.format(
                host=self.plc_host, port=self.plc_port, addr=addr, val=raw,
            )
        elif name in DEFAULT_COILS:
            addr = DEFAULT_COILS[name]
            script = self._WRITE_COIL_SCRIPT.format(
                host=self.plc_host, port=self.plc_port, addr=addr,
                val="True" if value else "False",
            )
        else:
            raise ValueError(f"Unknown tag: {name}")

        result = self._shell(f'python -c "{script}"', timeout=10)
        return result.get("stdout", "").strip() == "OK"

# ═══════════════════════════════════════════════════════════════════════
#  Matrix API Client — same data source as the Discord bot
# ═══════════════════════════════════════════════════════════════════════
class MatrixAPIClient:
    """Fetches PLC tags from the Matrix API (same source as Discord bot)."""

    def __init__(self, base_url: str = MATRIX_API_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.host = base_url  # for badge display

    async def fetch_tags(self) -> dict[str, Any] | None:
        """Fetch the latest PLC tag snapshot. Returns dict or None on failure."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(f"{self.base_url}/api/tags", params={"limit": 1})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                    if isinstance(data, dict) and data:
                        return data
        except Exception:
            logger.debug("Matrix API unreachable at %s", self.base_url)
        return None

    async def check_health(self) -> bool:
        """Return True if the Matrix API /api/health endpoint responds 200."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as http:
                resp = await http.get(f"{self.base_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False


# Tags worth charting by default
DEFAULT_CHART_TAGS = ["motor_speed", "temperature", "motor_current", "pressure"]

HISTORY_MAX = 300  # ~10 min at 2 s poll
MAX_CONSECUTIVE_FAILS = 3  # retries before marking PLC disconnected


# ═══════════════════════════════════════════════════════════════════════
#  Shared state
# ═══════════════════════════════════════════════════════════════════════
class PLCState:
    """Connection state, latest tag snapshots, and ring-buffer history."""

    def __init__(self) -> None:
        self.micro820: ModbusPLCClient | JarvisBridgePLCClient | None = None
        self.s7: S7Client | None = None
        self.connected_micro820: bool = False
        self.connected_s7: bool = False
        self.micro820_tags: dict[str, Any] = {}
        self.s7_tags: dict[str, Any] = {}
        self.history: deque[tuple[datetime, dict[str, Any]]] = deque(maxlen=HISTORY_MAX)
        self.poll_interval: float = 2.0  # seconds
        self.last_poll: datetime | None = None
        self._micro820_fail_count: int = 0
        self._s7_fail_count: int = 0
        self._micro820_poll_count: int = 0
        self._s7_poll_count: int = 0
        # Matrix API (fast path — same source as Discord bot)
        self.matrix_client: MatrixAPIClient | None = None
        self.connected_matrix: bool = False
        self.stale: bool = False
        self._matrix_fail_count: int = 0
        self._matrix_poll_count: int = 0
        # Change-driven state monitor
        self.monitor: MachineStateMonitor = MachineStateMonitor()


state = PLCState()


# ═══════════════════════════════════════════════════════════════════════
#  PLC helpers
# ═══════════════════════════════════════════════════════════════════════
async def _polling_loop() -> None:
    """Single background task — polls all connected PLCs, regardless of browser tabs."""
    while True:
        snapshot: dict[str, Any] = {}
        micro820_handled = False

        # ── Auto-reconnect if no data source connected ──
        if not state.connected_matrix and not state.connected_micro820:
            if state._matrix_fail_count == 0 or state._matrix_fail_count % 5 == 0:
                ok = await connect_matrix(MATRIX_API_URL)
                if ok:
                    logger.info("Auto-reconnected to Matrix API")

        # ── Matrix API fast path (same data as Discord bot) ──
        if state.matrix_client and state.connected_matrix:
            tags = await state.matrix_client.fetch_tags()
            if tags is not None:
                # Strip metadata keys, keep only PLC tag values
                skip = {"id", "timestamp", "node_id", "snapshot_id"}
                clean = {k: v for k, v in tags.items() if k not in skip}
                state._matrix_fail_count = 0
                state._matrix_poll_count += 1
                micro820_handled = True
                # Stale detection (same logic as Discord bot)
                ts_raw = tags.get("timestamp")
                if ts_raw:
                    try:
                        if isinstance(ts_raw, str):
                            ts_raw = ts_raw.replace("Z", "+00:00")
                            snap_time = _dt.datetime.fromisoformat(ts_raw)
                        else:
                            snap_time = _dt.datetime.fromtimestamp(ts_raw, tz=_dt.timezone.utc)
                        if snap_time.tzinfo is None:
                            snap_time = snap_time.replace(tzinfo=_dt.timezone.utc)
                        age = (_dt.datetime.now(tz=_dt.timezone.utc) - snap_time).total_seconds()
                        state.stale = age > STALE_THRESHOLD_S
                    except (ValueError, TypeError, OSError):
                        state.stale = True
                else:
                    state.stale = True
                # Feed monitor — logs only on change
                state.monitor.update(clean, state.stale)
                state.micro820_tags = clean
                snapshot.update(clean)
            else:
                state._matrix_fail_count += 1
                logger.warning(
                    "Matrix API read failed (%d/%d)",
                    state._matrix_fail_count, MAX_CONSECUTIVE_FAILS,
                )
                state.stale = True
                if state._matrix_fail_count >= MAX_CONSECUTIVE_FAILS:
                    logger.warning("Matrix API: %d consecutive failures — will retry in 10s",
                                   state._matrix_fail_count)
                    # Don't permanently disconnect — try reconnecting
                    if state._matrix_fail_count % 5 == 0:  # every 5 failures (~10s)
                        logger.info("Matrix API: attempting reconnect to %s", MATRIX_API_URL)
                        ok = await connect_matrix(MATRIX_API_URL)
                        if ok:
                            logger.info("Matrix API: reconnected!")
                            state._matrix_fail_count = 0

        # ── Bridge / direct Modbus fallback ──
        if not micro820_handled and state.micro820 and state.connected_micro820:
            try:
                tags = await run.io_bound(state.micro820.read_tags)
                state._micro820_fail_count = 0
                state._micro820_poll_count += 1
                state.stale = False
                state.monitor.update(tags, state.stale)
                state.micro820_tags = tags
                snapshot.update(tags)
            except Exception:
                state._micro820_fail_count += 1
                logger.warning(
                    "Micro820 read failed (%d/%d)",
                    state._micro820_fail_count, MAX_CONSECUTIVE_FAILS,
                )
                if state._micro820_fail_count >= MAX_CONSECUTIVE_FAILS:
                    logger.error("Micro820 disconnected after %d failures", MAX_CONSECUTIVE_FAILS)
                    state.connected_micro820 = False

        if state.s7 and state.connected_s7:
            try:
                tags = await run.io_bound(state.s7.read_tags)
                state.s7_tags = tags
                snapshot.update(tags)
                state._s7_fail_count = 0
                state._s7_poll_count += 1
            except Exception:
                state._s7_fail_count += 1
                logger.warning(
                    "S7 read failed (%d/%d)",
                    state._s7_fail_count, MAX_CONSECUTIVE_FAILS,
                )
                if state._s7_fail_count >= MAX_CONSECUTIVE_FAILS:
                    logger.error("S7 disconnected after %d failures", MAX_CONSECUTIVE_FAILS)
                    state.connected_s7 = False

        if snapshot:
            state.history.append((datetime.now(), snapshot))
        state.last_poll = datetime.now()
        await asyncio.sleep(state.poll_interval)


async def _start_polling() -> None:
    # Auto-connect to Matrix API on startup (fast path)
    ok = await connect_matrix(MATRIX_API_URL)
    if ok:
        logger.info("Auto-connected to Matrix API at %s", MATRIX_API_URL)
    else:
        logger.warning("Matrix API not available at startup — connect manually via Connections tab")
    asyncio.create_task(_polling_loop())


app.on_startup(_start_polling)


def connect_micro820(ip: str, port: int, bridge_url: str = "") -> bool:
    """Connect to Micro820 — direct Modbus or via Jarvis bridge."""
    if bridge_url:
        state.micro820 = JarvisBridgePLCClient(
            bridge_url=bridge_url, plc_host=ip, plc_port=port,
        )
    else:
        state.micro820 = ModbusPLCClient(host=ip, port=port)
    state.connected_micro820 = state.micro820.connect()
    state._micro820_fail_count = 0
    return state.connected_micro820


def disconnect_micro820() -> None:
    if state.micro820:
        state.micro820.disconnect()
    state.connected_micro820 = False


async def connect_matrix(url: str) -> bool:
    """Connect to the Matrix API (same data source as Discord bot)."""
    client = MatrixAPIClient(base_url=url)
    ok = await client.check_health()
    if ok:
        state.matrix_client = client
        state.connected_matrix = True
        state._matrix_fail_count = 0
        state.stale = False
        logger.info("Matrix API connected: %s", url)
    else:
        logger.warning("Matrix API health check failed: %s", url)
    return ok


def disconnect_matrix() -> None:
    state.matrix_client = None
    state.connected_matrix = False
    state.stale = False


def connect_s7(ip: str, rack: int, slot: int) -> bool:
    state.s7 = S7Client(host=ip, rack=rack, slot=slot)
    state.connected_s7 = state.s7.connect()
    state._s7_fail_count = 0
    return state.connected_s7


def disconnect_s7() -> None:
    if state.s7:
        state.s7.disconnect()
    state.connected_s7 = False


def writable_tags() -> list[str]:
    """Return tag names that are safe to write."""
    tags: list[str] = []
    if state.connected_micro820:
        tags += [t for t in list(DEFAULT_REGISTERS) + list(DEFAULT_COILS) if t not in READ_ONLY_TAGS]
    if state.connected_s7:
        tags += [t[4] for t in S7_DEFAULT_TAGS if t[4] not in READ_ONLY_TAGS]
    return tags


def all_tag_names() -> list[str]:
    """All known tag names across connected PLCs."""
    tags: list[str] = []
    if state.connected_micro820 or state.connected_matrix:
        tags += list(DEFAULT_REGISTERS) + list(DEFAULT_COILS)
        # Include any Matrix-only tags not in the predefined lists
        for k in state.micro820_tags:
            if k not in tags:
                tags.append(k)
    if state.connected_s7:
        tags += [t[4] for t in S7_DEFAULT_TAGS]
    return tags


def _tag_type(name: str) -> str:
    if name in DEFAULT_COILS:
        return "bool"
    if name in DEFAULT_REGISTERS:
        return "int/float"
    for _, _, _, dtype, tname in S7_DEFAULT_TAGS:
        if tname == name:
            return dtype
    return "—"


def _tag_plc(name: str) -> str:
    if name in DEFAULT_REGISTERS or name in DEFAULT_COILS:
        return "Micro820"
    for *_, tname in S7_DEFAULT_TAGS:
        if tname == name:
            return "S7-1200"
    # Matrix API may include tags not in the static defs
    if state.connected_matrix and name in state.micro820_tags:
        return "Micro820"
    return "—"


# ═══════════════════════════════════════════════════════════════════════
#  UI
# ═══════════════════════════════════════════════════════════════════════
@ui.page("/")
def main_page():
    # ── dark theme + styling ──
    ui.dark_mode(True)
    ui.add_head_html("""
    <style>
        .alert-row { background-color: rgba(220, 38, 38, 0.25) !important; }
    </style>
    """)

    # ── header ──
    with ui.header().classes("items-center justify-between q-px-md"):
        ui.label("FactoryLM PLC Reader").classes("text-h5 text-weight-bold")
        with ui.row().classes("items-center gap-2"):
            mode_badge = ui.badge("OFFLINE", color="grey").props("outline")
            source_badge = ui.badge("No source", color="grey").props("outline")
            s7_badge = ui.badge("S7-1200 Not configured", color="grey").props("outline")

    # ── tabs ──
    with ui.tabs().classes("w-full") as tabs:
        live_tab = ui.tab("Live Tags")
        charts_tab = ui.tab("Trends")
        write_tab = ui.tab("Write")
        config_tab = ui.tab("Connections")

    with ui.tab_panels(tabs, value=live_tab).classes("w-full flex-grow"):

        # ═════════════════════════════════════════════════════════════
        #  Tab 1 — Live Tags
        # ═════════════════════════════════════════════════════════════
        with ui.tab_panel(live_tab):
            ui.label("Live Tag Values").classes("text-h6 q-mb-sm")
            stale_banner = ui.label("").classes("text-caption text-orange q-mb-xs")
            stale_banner.visible = False
            tag_table = ui.table(
                columns=[
                    {"name": "plc", "label": "PLC", "field": "plc", "align": "left"},
                    {"name": "tag", "label": "Tag Name", "field": "tag", "align": "left", "sortable": True},
                    {"name": "value", "label": "Value", "field": "value", "align": "right"},
                    {"name": "type", "label": "Type", "field": "type", "align": "center"},
                ],
                rows=[],
                row_key="tag",
            ).classes("w-full").props("dense flat bordered")

            poll_status = ui.label("No PLC connected").classes("text-caption text-grey q-mt-sm")

            # Slot to color-code alarm rows
            tag_table.add_slot(
                "body-cell-value",
                r"""
                <q-td :props="props"
                       :class="(props.row.tag === 'fault_alarm' || props.row.tag === 'e_stop')
                               && props.row.value === 'True' ? 'text-red text-weight-bold' : ''">
                    {{ props.row.value }}
                </q-td>
                """,
            )

            # ── Recent Changes panel ──
            ui.label("Recent Changes").classes("text-subtitle2 q-mt-md")
            change_log_container = ui.column().classes("w-full")

            # ── Test Cycle button ──
            ui.separator().classes("q-mt-md")
            test_status = ui.label("").classes("text-caption q-mt-xs")

            async def run_test_cycle():
                """Write a motor start/stop cycle through the bridge."""
                bridge = JarvisBridgePLCClient()
                test_status.text = "Connecting to bridge..."
                try:
                    ok = await run.io_bound(bridge.connect)
                except Exception as exc:
                    test_status.text = f"Bridge connect failed: {exc}"
                    return
                if not ok:
                    test_status.text = "Bridge connect failed — is Jarvis Node running?"
                    return

                try:
                    test_status.text = "Starting motor (speed=150)..."
                    await run.io_bound(bridge.write_tag, "motor_running", True)
                    await run.io_bound(bridge.write_tag, "motor_speed", 150)
                    await asyncio.sleep(3)

                    test_status.text = "Ramping to speed=200..."
                    await run.io_bound(bridge.write_tag, "motor_speed", 200)
                    await asyncio.sleep(3)

                    test_status.text = "Stopping motor..."
                    await run.io_bound(bridge.write_tag, "motor_running", False)
                    await run.io_bound(bridge.write_tag, "motor_speed", 0)
                    test_status.text = "Test cycle complete."
                except Exception as exc:
                    test_status.text = f"Test cycle error: {exc}"

            ui.button("Test Cycle", on_click=run_test_cycle, icon="play_circle").props(
                "color=deep-purple outline"
            ).tooltip("Write motor start/stop sequence to PLC via bridge")

        # ═════════════════════════════════════════════════════════════
        #  Tab 2 — Trend Charts
        # ═════════════════════════════════════════════════════════════
        with ui.tab_panel(charts_tab):
            ui.label("Tag Trends").classes("text-h6 q-mb-sm")
            selected_tags: dict[str, bool] = {t: True for t in DEFAULT_CHART_TAGS}

            with ui.row().classes("items-center gap-4 q-mb-md"):
                for tag in DEFAULT_CHART_TAGS:
                    ui.checkbox(tag, value=True, on_change=lambda e, t=tag: _toggle_chart_tag(t, e.value))
                extra_select = ui.select(
                    label="Add tag…",
                    options=[],
                    on_change=lambda e: _add_chart_tag(e.value),
                ).classes("w-40")

            chart = ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"show": True},
                "xAxis": {"type": "category", "data": []},
                "yAxis": {"type": "value"},
                "series": [],
                "animation": False,
                "grid": {"left": 60, "right": 30, "bottom": 40, "top": 40},
            }).classes("w-full h-80")

            def _toggle_chart_tag(tag: str, on: bool):
                selected_tags[tag] = on

            def _add_chart_tag(tag: str | None):
                if tag and tag not in selected_tags:
                    selected_tags[tag] = True

        # ═════════════════════════════════════════════════════════════
        #  Tab 3 — Write Tags
        # ═════════════════════════════════════════════════════════════
        with ui.tab_panel(write_tab):
            ui.label("Write Tag Value").classes("text-h6 q-mb-sm")
            write_select = ui.select(label="Tag", options=[], value=None).classes("w-64")
            write_input = ui.input(label="Value").classes("w-64")
            write_result = ui.label("").classes("q-mt-sm")

            async def do_write():
                tag = write_select.value
                val = write_input.value
                if not tag or val is None or val == "":
                    ui.notify("Select a tag and enter a value", type="warning")
                    return

                with ui.dialog() as dlg, ui.card():
                    ui.label(f'Write "{val}" to {tag}?').classes("text-subtitle1")
                    with ui.row():
                        ui.button("Confirm", on_click=lambda: dlg.submit(True)).props("color=positive")
                        ui.button("Cancel", on_click=lambda: dlg.submit(False)).props("flat")
                confirmed = await dlg
                if not confirmed:
                    return

                success = False
                try:
                    if state.connected_micro820 and state.micro820:
                        if tag in DEFAULT_REGISTERS or tag in DEFAULT_COILS:
                            success = state.micro820.write_tag(tag, val)
                    if not success and state.connected_s7 and state.s7:
                        success = state.s7.write_tag(tag, val)
                except Exception as exc:
                    ui.notify(f"Write failed: {exc}", type="negative")
                    write_result.text = f"Error: {exc}"
                    return

                if success:
                    ui.notify(f"{tag} ← {val}  OK", type="positive")
                    write_result.text = f"Wrote {val} to {tag}"
                else:
                    ui.notify("Write returned failure", type="negative")
                    write_result.text = "Write failed"

            ui.button("Write", on_click=do_write, icon="edit").props("color=primary")

        # ═════════════════════════════════════════════════════════════
        #  Tab 4 — Connection Manager
        # ═════════════════════════════════════════════════════════════
        with ui.tab_panel(config_tab):
            ui.label("Connection Manager").classes("text-h6 q-mb-sm")

            # ── Matrix API (fast path — same source as Discord bot) ──
            with ui.card().classes("w-full q-mb-md"):
                ui.label("Matrix API (Recommended)").classes("text-subtitle1 text-weight-bold")
                ui.label(
                    "Same data source as the Discord bot. "
                    "Reads from the collector cache — ~100ms vs 5-15s."
                ).classes("text-caption text-grey q-mb-xs")
                with ui.row().classes("items-end gap-4"):
                    mx_url = ui.input("Matrix API URL", value=MATRIX_API_URL).classes("w-80")
                    mx_status = ui.badge("Offline", color="grey")

                with ui.row().classes("q-mt-sm gap-2"):
                    async def on_matrix_connect():
                        url = mx_url.value.strip()
                        if not url:
                            ui.notify("Enter a Matrix API URL", type="warning")
                            return
                        mx_status.set_text("Connecting...")
                        mx_status.props("color=orange")
                        ok = await connect_matrix(url)
                        if ok:
                            mx_status.set_text("Connected")
                            mx_status.props("color=green")
                            ui.notify(f"Matrix API connected at {url}", type="positive")
                        else:
                            mx_status.set_text("Failed")
                            mx_status.props("color=red")
                            ui.notify("Matrix API health check failed", type="negative")

                    def on_matrix_disconnect():
                        disconnect_matrix()
                        mx_status.set_text("Offline")
                        mx_status.props("color=grey")
                        ui.notify("Matrix API disconnected")

                    ui.button("Connect", on_click=on_matrix_connect, icon="power").props("color=positive")
                    ui.button("Disconnect", on_click=on_matrix_disconnect, icon="power_off").props("flat color=negative")

            # ── Micro820 ──
            with ui.card().classes("w-full q-mb-md"):
                ui.label("Micro820 (Modbus TCP)").classes("text-subtitle1 text-weight-bold")
                with ui.row().classes("items-end gap-4"):
                    m_ip = ui.input("IP Address", value="192.168.1.100").classes("w-48")
                    m_port = ui.number("Port", value=502, min=1, max=65535, format="%d").classes("w-24")
                    m_status = ui.badge("Offline", color="red")

                # ── Bridge mode (route Modbus through PLC Laptop) ──
                m_bridge = ui.checkbox(
                    "Via PLC Laptop Bridge (Jarvis Node)",
                    value=True,
                ).classes("q-mt-sm")
                m_bridge_url = ui.input(
                    "Bridge URL", value=DEFAULT_BRIDGE_URL,
                ).classes("w-80")
                ui.label(
                    "Enable when this machine cannot reach the PLC directly. "
                    "The PLC Laptop forwards Modbus over Tailscale."
                ).classes("text-caption text-grey")

                with ui.row().classes("q-mt-sm gap-2"):
                    async def on_micro_connect():
                        ip = m_ip.value
                        port = int(m_port.value)
                        bridge = m_bridge_url.value.strip() if m_bridge.value else ""
                        mode = " (bridge)" if bridge else " (direct)"
                        m_status.set_text("Connecting...")
                        m_status.props("color=orange")
                        try:
                            ok = await run.io_bound(connect_micro820, ip, port, bridge)
                        except Exception as exc:
                            logger.error("Micro820 connect error: %s", exc)
                            ok = False
                        if ok:
                            m_status.set_text(f"Connected{mode}")
                            m_status.props("color=green")
                            ui.notify(f"Micro820 connected at {ip}{mode}", type="positive")
                        else:
                            m_status.set_text("Failed")
                            m_status.props("color=red")
                            ui.notify(f"Micro820 connection failed{mode}", type="negative")

                    def on_micro_disconnect():
                        disconnect_micro820()
                        m_status.set_text("Offline")
                        m_status.props("color=red")
                        ui.notify("Micro820 disconnected")

                    ui.button("Connect", on_click=on_micro_connect, icon="power").props("color=positive")
                    ui.button("Disconnect", on_click=on_micro_disconnect, icon="power_off").props("flat color=negative")

            # ── S7-1200 ──
            with ui.card().classes("w-full q-mb-md"):
                ui.label("S7-1200 (snap7)").classes("text-subtitle1 text-weight-bold")
                with ui.row().classes("items-end gap-4"):
                    s_ip = ui.input("IP Address", value="").props('placeholder="e.g. 192.168.0.1"').classes("w-48")
                    s_rack = ui.number("Rack", value=0, min=0, max=7, format="%d").classes("w-20")
                    s_slot = ui.number("Slot", value=1, min=0, max=31, format="%d").classes("w-20")
                    s_status = ui.badge("Not configured", color="grey")

                with ui.row().classes("q-mt-sm gap-2"):
                    async def on_s7_connect():
                        if not s_ip.value:
                            ui.notify("Enter an IP address", type="warning")
                            return
                        ip = s_ip.value
                        rack = int(s_rack.value)
                        slot = int(s_slot.value)
                        s_status.set_text("Connecting...")
                        s_status.props("color=orange")
                        try:
                            ok = await run.io_bound(connect_s7, ip, rack, slot)
                        except Exception as exc:
                            logger.error("S7 connect error: %s", exc)
                            ok = False
                        if ok:
                            s_status.set_text("Connected")
                            s_status.props("color=green")
                            ui.notify(f"S7-1200 connected at {ip}", type="positive")
                        else:
                            s_status.set_text("Failed")
                            s_status.props("color=red")
                            ui.notify("S7-1200 connection failed", type="negative")

                    def on_s7_disconnect():
                        disconnect_s7()
                        s_status.set_text("Offline")
                        s_status.props("color=red")
                        ui.notify("S7-1200 disconnected")

                    ui.button("Connect", on_click=on_s7_connect, icon="power").props("color=positive")
                    ui.button("Disconnect", on_click=on_s7_disconnect, icon="power_off").props("flat color=negative")

            # ── Settings ──
            with ui.card().classes("w-full"):
                ui.label("Settings").classes("text-subtitle1 text-weight-bold")
                poll_slider = ui.slider(min=1, max=10, value=2, step=0.5).classes("w-64")
                poll_label = ui.label(f"Poll interval: {state.poll_interval:.1f}s")

                def on_poll_change(e):
                    state.poll_interval = e.value
                    poll_label.text = f"Poll interval: {e.value:.1f}s"
                    timer.interval = e.value

                poll_slider.on("update:model-value", on_poll_change)

    # ═════════════════════════════════════════════════════════════════
    #  Periodic refresh
    # ═════════════════════════════════════════════════════════════════
    def tick():  # sync — no await, no I/O
        try:
            _refresh_tag_table()
            _refresh_chart()
            _refresh_badges()
            _refresh_write_options()
            _refresh_extra_select()
        except Exception:
            logger.exception("tick() error")

    def _refresh_tag_table():
        rows = []
        merged = {}
        if state.connected_micro820 or state.connected_matrix:
            merged.update(state.micro820_tags)
        if state.connected_s7:
            merged.update(state.s7_tags)

        for name, value in sorted(merged.items()):
            rows.append({
                "plc": _tag_plc(name),
                "tag": name,
                "value": str(value),
                "type": _tag_type(name),
            })
        tag_table.rows = rows
        tag_table.update()

        # Stale detection banner
        if state.connected_matrix and state.stale:
            stale_banner.text = "STALE — PLC data may be outdated (>{0}s old)".format(STALE_THRESHOLD_S)
            stale_banner.visible = True
        else:
            stale_banner.visible = False

        any_connected = state.connected_micro820 or state.connected_s7 or state.connected_matrix
        # Status line — mode + last change age
        age_str = ""
        if state.monitor.last_change:
            age = (datetime.now() - state.monitor.last_change).total_seconds()
            if age < 60:
                age_str = f"{int(age)}s ago"
            else:
                age_str = f"{int(age // 60)}m ago"

        source = "Matrix API" if state.connected_matrix else "Modbus" if state.connected_micro820 else ""
        if any_connected:
            poll_status.text = f"Mode: {state.monitor.mode.value} | Last change: {age_str or 'never'} | via {source}"
        else:
            poll_status.text = "No PLC connected"

        # Populate change log panel
        change_log_container.clear()
        with change_log_container:
            if not state.monitor.change_log:
                ui.label("No changes yet").classes("text-caption text-grey")
            else:
                for ts, msg in list(state.monitor.change_log)[:10]:
                    ui.label(f"{ts.strftime('%H:%M:%S')}  {msg}").classes("text-caption font-mono")

    def _refresh_chart():
        active = [t for t, on in selected_tags.items() if on]
        if not active or not state.history:
            return

        times = [ts.strftime("%H:%M:%S") for ts, _ in state.history]
        series = []
        for tag in active:
            data = []
            for _, snap in state.history:
                v = snap.get(tag)
                if isinstance(v, bool):
                    v = int(v)
                data.append(v if v is not None else None)
            series.append({"name": tag, "type": "line", "data": data, "smooth": True, "symbol": "none"})

        chart.options["xAxis"]["data"] = times
        chart.options["series"] = series
        chart.update()

    def _refresh_badges():
        # ── Mode badge (color-coded machine state) ──
        mode = state.monitor.mode
        mode_color = MACHINE_MODE_COLORS.get(mode, "grey")
        mode_badge.set_text(mode.value)
        mode_badge.props(f"color={mode_color}")

        # ── Source badge ──
        if state.connected_matrix:
            if state.stale:
                source_badge.set_text("Matrix API (stale)")
                source_badge.props("color=orange")
                mx_status.set_text("Connected (stale)")
                mx_status.props("color=orange")
            else:
                source_badge.set_text("Matrix API")
                source_badge.props("color=green")
                mx_status.set_text("Connected")
                mx_status.props("color=green")
        elif state.connected_micro820:
            is_bridge = isinstance(state.micro820, JarvisBridgePLCClient)
            label = "Modbus (bridge)" if is_bridge else "Modbus (direct)"
            source_badge.set_text(label)
            source_badge.props("color=green")
            m_status.set_text(f"Connected{' (bridge)' if is_bridge else ''}")
            m_status.props("color=green")
        else:
            source_badge.set_text("No source")
            source_badge.props("color=grey")
            m_status.set_text("Offline")
            m_status.props("color=red")

        # ── S7 badge ──
        if state.connected_s7:
            ip = state.s7.host if state.s7 else "?"
            s7_badge.set_text(f"S7-1200 Connected ({ip})")
            s7_badge.props("color=green")
            s_status.set_text("Connected")
            s_status.props("color=green")
        else:
            if s_ip.value:
                s7_badge.set_text("S7-1200 Offline")
                s7_badge.props("color=red")
            else:
                s7_badge.set_text("S7-1200 Not configured")
                s7_badge.props("color=grey")

    def _refresh_write_options():
        opts = writable_tags()
        if write_select.options != opts:
            write_select.options = opts
            write_select.update()

    def _refresh_extra_select():
        all_t = all_tag_names()
        extras = [t for t in all_t if t not in DEFAULT_CHART_TAGS]
        if extra_select.options != extras:
            extra_select.options = extras
            extra_select.update()

    timer = ui.timer(interval=state.poll_interval, callback=tick)


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ui.run(title="FactoryLM PLC Reader", port=8080, reload=False)
