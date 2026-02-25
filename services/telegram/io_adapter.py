"""
Telegram I/O Adapter — standalone module for live PLC/VFD display and LLM diagnosis.

Usage:
    from services.telegram.io_adapter import PLCIOReader, register_io_handlers

    reader = PLCIOReader()
    register_io_handlers(app, reader, groq_api_key="...")
"""

import os
import logging
from functools import partial

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

PLC_API_URL = os.getenv("PLC_API_URL", "http://100.66.216.6:5000")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

FACTORY_KEYWORDS = [
    "factory", "plc", "motor", "conveyor", "fault", "alarm",
    "temperature", "pressure", "sensor", "machine", "diagnos",
]


class PLCIOReader:
    """Reads live PLC and VFD data from the Pi gateway API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or PLC_API_URL).rstrip("/")
        self._client = httpx.Client(timeout=10)

    def get_status(self) -> dict:
        """GET /api/plc/status — returns PLC connection status."""
        resp = self._client.get(f"{self.base_url}/api/plc/status")
        resp.raise_for_status()
        return resp.json()

    def reconnect(self, ip: str = "192.168.1.100") -> bool:
        """POST /api/plc/connect — attempt to reconnect to the PLC."""
        resp = self._client.post(
            f"{self.base_url}/api/plc/connect",
            json={"ip": ip},
            timeout=10,
        )
        return resp.status_code == 200

    def read_io(self) -> dict:
        """GET /api/plc/io — returns {coils, inputs, outputs, registers, timestamp}."""
        resp = self._client.get(f"{self.base_url}/api/plc/io")
        resp.raise_for_status()
        return resp.json()

    def read_vfd(self) -> dict | None:
        """GET /api/vfd/data — returns VFD summary dict or None if unavailable."""
        try:
            resp = self._client.get(f"{self.base_url}/api/vfd/data")
            if resp.status_code == 200:
                return resp.json().get("summary")
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_io(io_data: dict, vfd_data: dict | None = None) -> str:
    """Format raw PLC + VFD data into a human-readable Telegram message."""
    coils = io_data.get("coils", {})
    inputs = io_data.get("inputs", {})
    outputs = io_data.get("outputs", {})
    regs = io_data.get("registers", {})

    lines = ["Factory Status (Live PLC)", "=" * 30, ""]
    lines.append("PLC: CONNECTED (Micro 820)")
    lines.append("")

    # Machine state
    lines.append("Machine State:")
    lines.append(f"  Motor: {'RUNNING' if coils.get('motor_running') else 'STOPPED'}")
    lines.append(f"  Conveyor: {'RUNNING' if coils.get('conveyor_running') else 'STOPPED'}")
    lines.append(f"  E-Stop: {'ACTIVE' if coils.get('e_stop_active') else 'Clear'}")
    if coils.get("fault_alarm"):
        lines.append("  *** FAULT ALARM ACTIVE ***")
    lines.append("")

    # Analog readings
    lines.append("Readings:")
    lines.append(f"  Speed: {regs.get('motor_speed', 0)} RPM")
    lines.append(f"  Current: {regs.get('motor_current', 0)} A")
    lines.append(f"  Temp: {regs.get('temperature', 0)} C")
    lines.append(f"  Pressure: {regs.get('pressure', 0)} PSI")
    lines.append("")

    # Digital I/O summary
    active_in = [k for k, v in inputs.items() if v]
    active_out = [k for k, v in outputs.items() if v]
    lines.append(f"Digital Inputs: {', '.join(active_in) if active_in else 'All clear'}")
    lines.append(f"Digital Outputs: {', '.join(active_out) if active_out else 'All off'}")

    # Overall status
    if not coils.get("fault_alarm") and not coils.get("e_stop_active"):
        lines.append("")
        lines.append("PLC Status: All systems nominal.")
    else:
        lines.append("")
        lines.append("WARNING: Check fault conditions above.")

    # VFD section
    if vfd_data is not None:
        lines.append("")
        lines.append("--- VFD (GS10 Drive) ---")
        state = "RUNNING" if vfd_data.get("running") else "STOPPED"
        direction = vfd_data.get("direction", "FWD")
        lines.append(f"  State: {state} ({direction})")
        lines.append(f"  Frequency: {vfd_data.get('frequency_hz', 0)} Hz")
        lines.append(f"  Current: {vfd_data.get('current_a', 0)} A")
        lines.append(f"  RPM: {vfd_data.get('rpm', 0)}")
        lines.append(f"  Voltage: {vfd_data.get('voltage_v', 0)} V")
        lines.append(f"  Drive Temp: {vfd_data.get('temp_c', 0)} C")
        if vfd_data.get("fault"):
            lines.append(f"  *** VFD FAULT: {vfd_data.get('fault_desc', 'Unknown')} ***")
        elif vfd_data.get("ready"):
            lines.append("  VFD: Ready")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM Diagnosis
# ---------------------------------------------------------------------------

async def diagnose_factory(
    question: str,
    reader: PLCIOReader,
    groq_api_key: str = "",
) -> str:
    """Read live PLC+VFD data, send to Groq LLM with factory diagnosis prompt."""
    api_key = groq_api_key or GROQ_API_KEY

    # Gather PLC context
    plc_context = "PLC: OFFLINE"
    try:
        data = reader.read_io()
        vfd_text = "VFD: Not connected"
        vfd_data = reader.read_vfd()
        if vfd_data:
            vfd_text = (
                f"VFD (GS10 DURApulse Drive):\n"
                f"  Running: {vfd_data.get('running', False)}\n"
                f"  Direction: {vfd_data.get('direction', 'FWD')}\n"
                f"  Frequency: {vfd_data.get('frequency_hz', 0)} Hz\n"
                f"  Current: {vfd_data.get('current_a', 0)} A\n"
                f"  RPM: {vfd_data.get('rpm', 0)}\n"
                f"  Voltage: {vfd_data.get('voltage_v', 0)} V\n"
                f"  Drive Temp: {vfd_data.get('temp_c', 0)} C\n"
                f"  Fault: {vfd_data.get('fault', False)} - {vfd_data.get('fault_desc', 'None')}\n"
                f"  Ready: {vfd_data.get('ready', False)}"
            )

        plc_context = (
            f"Live PLC Data (Micro 820 via EtherNet/IP):\n"
            f"Coils: {data.get('coils', {})}\n"
            f"Digital Inputs: {data.get('inputs', {})}\n"
            f"Digital Outputs: {data.get('outputs', {})}\n"
            f"Registers: {data.get('registers', {})}\n"
            f"Timestamp: {data.get('timestamp', 'unknown')}\n"
            f"\n{vfd_text}"
        )
    except Exception as e:
        plc_context = f"PLC read error: {e}"

    if not api_key:
        return f"[No LLM configured]\n\n{plc_context}"

    prompt = (
        "You are an expert industrial maintenance AI for FactoryLM.\n"
        "You help factory technicians diagnose equipment issues from live PLC data.\n\n"
        f"{plc_context}\n\n"
        f"Technician asks: {question}\n\n"
        "Provide a concise, actionable diagnosis (under 150 words). Be direct and practical.\n"
        "If something looks abnormal, explain the likely cause and recommended action."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.3,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            return f"LLM error: {resp.status_code}\n\nRaw PLC data:\n{plc_context}"
    except Exception as e:
        return f"LLM unavailable: {e}\n\nRaw PLC data:\n{plc_context}"


# ---------------------------------------------------------------------------
# Telegram command handlers
# ---------------------------------------------------------------------------

async def cmd_io_live(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reader: PLCIOReader | None = None,
) -> None:
    """/io_live — display live PLC + VFD status."""
    reader = reader or PLCIOReader()

    # Try reconnect if needed
    try:
        status = reader.get_status()
        if not status.get("connected"):
            reader.reconnect()
    except Exception:
        pass

    try:
        io_data = reader.read_io()
        vfd_data = reader.read_vfd()
        text = format_io(io_data, vfd_data)
    except Exception as e:
        text = f"Factory Status (Live PLC)\n{'=' * 30}\n\nPLC: OFFLINE ({e})"

    await update.message.reply_text(text)


async def cmd_diagnose_live(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reader: PLCIOReader | None = None,
    groq_api_key: str = "",
) -> None:
    """/diagnose_live <question> — ask the LLM to diagnose from live PLC data."""
    reader = reader or PLCIOReader()
    question = " ".join(context.args) if context.args else "General health check"
    result = await diagnose_factory(question, reader, groq_api_key)
    await update.message.reply_text(result)


def is_factory_question(text: str) -> bool:
    """Return True if the message text matches factory-related keywords."""
    lower = text.lower()
    return any(kw in lower for kw in FACTORY_KEYWORDS)


def register_io_handlers(
    app: Application,
    reader: PLCIOReader | None = None,
    groq_api_key: str = "",
) -> None:
    """Register /io_live and /diagnose_live handlers on a Telegram Application."""
    reader = reader or PLCIOReader()

    app.add_handler(
        CommandHandler(
            "io_live",
            partial(cmd_io_live, reader=reader),
        )
    )
    app.add_handler(
        CommandHandler(
            "diagnose_live",
            partial(cmd_diagnose_live, reader=reader, groq_api_key=groq_api_key),
        )
    )
