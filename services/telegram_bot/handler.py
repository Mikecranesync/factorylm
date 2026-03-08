"""
Conversational maintenance bot — Telegram handler.

Every message goes to Haiku with live PLC context. No menus, no workflows.
Technicians just talk.

Run: TELEGRAM_TOKEN=<token> python -m services.telegram_bot
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Add project root to path so we can import diagnosis, services, etc.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from diagnosis.conveyor_faults import detect_faults, format_diagnosis_for_technician
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("diagnosis module not available — fault detection disabled")
    detect_faults = lambda tags: []
    format_diagnosis_for_technician = lambda f: str(f)

from services.telegram_bot.prompts import build_system_prompt, HELP_TEXT
from services.telegram_bot.work_orders import WorkOrderStore
from core.src.factorylm.llm.client import async_diagnose

logger = logging.getLogger(__name__)

# --- Configuration ---
PLC_MODBUS_URL = os.getenv("PLC_MODBUS_URL", "http://127.0.0.1:8001")
MATRIX_API_URL = os.getenv("MATRIX_API_URL", "http://127.0.0.1:8000")
MAX_HISTORY = 10  # messages per user to keep in context


# --- Conversation History ---
@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


class ConversationManager:
    """Per-user message history. In-memory, resets on restart."""

    def __init__(self, max_messages: int = MAX_HISTORY):
        self._history: dict[str, List[Message]] = defaultdict(list)
        self._max = max_messages

    def add(self, user_id: str, role: str, content: str) -> None:
        history = self._history[user_id]
        history.append(Message(role=role, content=content))
        if len(history) > self._max:
            self._history[user_id] = history[-self._max:]

    def get(self, user_id: str) -> List[Message]:
        return self._history[user_id]

    def format_for_llm(self, user_id: str) -> List[dict]:
        return [{"role": m.role, "content": m.content} for m in self.get(user_id)]


# --- Singletons ---
conversations = ConversationManager()
work_orders = WorkOrderStore()
http_client = httpx.AsyncClient(timeout=15.0)


# --- PLC / Context Helpers ---
async def get_plc_state() -> tuple[str, dict]:
    """Fetch live PLC state. Returns (formatted_string, raw_tags_dict)."""
    try:
        r = await http_client.get(f"{PLC_MODBUS_URL}/api/plc/io")
        r.raise_for_status()
        io_data = r.json()

        # Build human-readable summary
        coils = io_data.get("coils", {})
        regs = io_data.get("registers", {})
        lines = []
        for name, val in sorted(coils.items()):
            lines.append(f"  {name}: {'ON' if val else 'OFF'}")
        for name, val in sorted(regs.items()):
            if "Current" in name:
                lines.append(f"  {name}: {val / 10:.1f} A")
            elif "Temp" in name:
                lines.append(f"  {name}: {val / 10:.1f} C")
            else:
                lines.append(f"  {name}: {val}")

        return "\n".join(lines) if lines else "  (no data)", io_data

    except Exception as e:
        logger.warning("PLC read failed: %s", e)
        return f"  PLC OFFLINE ({e})", {}


async def get_recent_incidents(limit: int = 5) -> str:
    """Fetch recent incidents from Matrix API."""
    try:
        r = await http_client.get(f"{MATRIX_API_URL}/api/incidents", params={"limit": limit})
        r.raise_for_status()
        incidents = r.json()
        if not incidents:
            return "  No recent incidents"
        lines = []
        for inc in incidents[:limit]:
            ts = inc.get("timestamp", "?")
            desc = inc.get("description", inc.get("fault_code", "unknown"))
            lines.append(f"  {ts}: {desc}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("Matrix API unavailable: %s", e)
        return "  Incident history unavailable"


async def ask_llm(system_prompt: str, messages: List[dict]) -> str:
    """Send conversation to LLM via LiteLLM Proxy. Fallbacks handled by proxy config."""
    result = await async_diagnose(system_prompt, messages)
    return result or "I'm having trouble reaching the AI service right now. Try again in a moment."


def extract_actions(response: str) -> tuple[str, Optional[str]]:
    """Extract [ACTION:*] tags from LLM response. Returns (clean_text, action)."""
    action_match = re.search(r"\[ACTION:(CREATE_WO|CLOSE_WO)\]", response)
    action = action_match.group(1) if action_match else None
    clean = re.sub(r"\s*\[ACTION:\w+\]\s*", "", response).strip()
    return clean, action


# --- Telegram Handlers ---
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle every text message — the core conversational loop."""
    user_id = f"tg_{update.effective_user.id}"
    text = update.message.text.strip()

    if not text:
        return

    # Record user message
    conversations.add(user_id, "user", text)

    # Gather live context
    plc_state, raw_tags = await get_plc_state()

    # Run rule-based fault detection on raw tags
    faults = []
    if raw_tags:
        flat_tags = {}
        for section in ("coils", "inputs", "outputs", "registers"):
            flat_tags.update(raw_tags.get(section, {}))
        faults = detect_faults(flat_tags)

    active_faults = "  No active faults"
    if faults:
        active_faults = "\n".join(
            f"  {format_diagnosis_for_technician(f)}" for f in faults
        )

    incidents = await get_recent_incidents()
    open_wo = work_orders.format_open_wo(user_id)

    # Build system prompt with full context
    system_prompt = build_system_prompt(
        plc_state=plc_state,
        active_faults=active_faults,
        recent_incidents=incidents,
        open_work_order=open_wo,
    )

    # Get conversation history + current message for LLM
    history = conversations.format_for_llm(user_id)

    # Call LLM
    raw_response = await ask_llm(system_prompt, history)

    # Extract actions
    clean_response, action = extract_actions(raw_response)

    # Execute side effects
    if action == "CREATE_WO":
        # Try to extract fault code from recent conversation
        fault_code = "GENERAL"
        for msg in reversed(conversations.get(user_id)):
            code_match = re.search(r"[EVMTCPSJA]\d{3}", msg.content, re.IGNORECASE)
            if code_match:
                fault_code = code_match.group(0).upper()
                break

        wo = work_orders.create(user_id, fault_code, text[:200])
        clean_response += f"\n\n{wo.wo_id} created. Assigned to you. Text me when it's resolved."

    elif action == "CLOSE_WO":
        wo = work_orders.get_open(user_id)
        if wo:
            # Use the user's message as root cause
            root_cause = text
            work_orders.close(wo.wo_id, root_cause)
            clean_response += f"\n\n{wo.wo_id} closed. Root cause logged: {root_cause}"

    # Record assistant response
    conversations.add(user_id, "assistant", clean_response)

    await update.message.reply_text(clean_response)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick cluster health check."""
    plc_state, raw_tags = await get_plc_state()
    plc_online = bool(raw_tags)

    flat_tags = {}
    if raw_tags:
        for section in ("coils", "inputs", "outputs", "registers"):
            flat_tags.update(raw_tags.get(section, {}))
    faults = detect_faults(flat_tags) if flat_tags else []

    fault_count = len([f for f in faults if f.severity.value != "info"])
    status_icon = "\u2705" if plc_online and fault_count == 0 else "\u26a0\ufe0f"

    msg = (
        f"{status_icon} PLC: {'online' if plc_online else 'OFFLINE'} | "
        f"Active faults: {fault_count} | "
        f"Open work orders: {len(work_orders._user_open)}"
    )
    await update.message.reply_text(msg)


async def cmd_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sales demo — inject E-stop, diagnose, clear."""
    user_id = f"tg_{update.effective_user.id}"

    await update.message.reply_text(
        "\u26a0\ufe0f Demo mode: Injecting E-Stop fault..."
    )

    # Inject fault via diagnosis service
    try:
        r = await http_client.post(
            f"{PLC_MODBUS_URL.rsplit(':', 1)[0]}:8200/fault-inject",
            json={"fault_type": "estop"},
        )
    except Exception as e:
        logger.warning("Fault injection failed: %s", e)

    # Let it settle
    import asyncio
    await asyncio.sleep(2)

    # Simulate technician reporting it
    conversations.add(user_id, "user", "E-stop just triggered, what happened?")

    plc_state, raw_tags = await get_plc_state()
    faults = []
    if raw_tags:
        flat_tags = {}
        for section in ("coils", "inputs", "outputs", "registers"):
            flat_tags.update(raw_tags.get(section, {}))
        faults = detect_faults(flat_tags)

    active_faults = "  No active faults"
    if faults:
        active_faults = "\n".join(
            f"  {format_diagnosis_for_technician(f)}" for f in faults
        )

    system_prompt = build_system_prompt(
        plc_state=plc_state,
        active_faults=active_faults,
        recent_incidents="  (demo mode)",
    )

    response = await ask_llm(
        system_prompt,
        [{"role": "user", "content": "E-stop just triggered, what happened?"}],
    )
    clean, _ = extract_actions(response)

    conversations.add(user_id, "assistant", clean)
    await update.message.reply_text(clean)

    # Clear after demo
    await asyncio.sleep(5)
    try:
        await http_client.post(
            f"{PLC_MODBUS_URL.rsplit(':', 1)[0]}:8200/fault-inject",
            json={"fault_type": "clear"},
        )
    except Exception:
        pass

    await update.message.reply_text("\u2705 Demo complete. Faults cleared.")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error: %s", context.error, exc_info=context.error)


def create_app(token: str) -> Application:
    """Build the Telegram application with all handlers."""
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("demo", cmd_demo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)

    return app
