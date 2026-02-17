"""Telegram photo handler for wiring reconstruction + KB enrichment.

Handles incoming photos in the Gus bot:
1. Immediate ack
2. Download photo bytes
3. Classify intent from caption + conversation state
4. ALWAYS run KB enrichment (background)
5. IF active wiring project → also run reconstruction (background)
6. Send follow-up messages with results

Per-chat project state is stored in a JSON file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# State file for per-chat wiring projects
STATE_FILE = os.getenv(
    "OPENCLAW_STATE_FILE",
    "/tmp/openclaw_telegram_state.json",
)


# ---------------------------------------------------------------------------
# Per-chat state management
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    """Load per-chat state from JSON file."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    """Save per-chat state to JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_active_project(chat_id: int) -> Optional[str]:
    """Get the active wiring project ID for a chat, if any."""
    state = _load_state()
    chat_state = state.get(str(chat_id), {})
    return chat_state.get("project_id")


def set_active_project(chat_id: int, project_id: str) -> None:
    """Set the active wiring project for a chat."""
    state = _load_state()
    state[str(chat_id)] = {
        "project_id": project_id,
        "started_at": datetime.now().isoformat(),
    }
    _save_state(state)


def clear_active_project(chat_id: int) -> None:
    """Clear the active wiring project for a chat."""
    state = _load_state()
    state.pop(str(chat_id), None)
    _save_state(state)


# ---------------------------------------------------------------------------
# Photo download
# ---------------------------------------------------------------------------

async def _download_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Download the highest-resolution photo from a Telegram message.

    Returns the path to a temporary file.
    """
    photo = update.message.photo[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()

    # Save to temp file
    suffix = ".jpg"
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        prefix="openclaw_photo_",
    )
    tmp.write(image_bytes)
    tmp.close()

    log.info("Downloaded photo %s (%d bytes) -> %s",
             photo.file_id, len(image_bytes), tmp.name)
    return tmp.name


# ---------------------------------------------------------------------------
# Background enrichment task
# ---------------------------------------------------------------------------

async def _run_enrichment(
    photo_path: str,
    photo_id: str,
    tags: Optional[str],
    chat_id: int,
    bot,
) -> None:
    """Run KB enrichment in the background and send results."""
    try:
        from openclaw.wiring.kb_enrichment import enrich_from_photo

        # Run the sync pipeline in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: enrich_from_photo(photo_path, tags=tags, photo_id=photo_id),
        )

        # Send the result
        await bot.send_message(chat_id=chat_id, text=result.summary)

    except Exception as e:
        log.error("Enrichment pipeline failed: %s", e)
        await bot.send_message(
            chat_id=chat_id,
            text=f"Couldn't process that component photo: {str(e)[:100]}",
        )


# ---------------------------------------------------------------------------
# Background reconstruction task
# ---------------------------------------------------------------------------

async def _run_reconstruction(
    photo_path: str,
    project_id: str,
    focus_tag: Optional[str],
    chat_id: int,
    bot,
) -> None:
    """Run wiring reconstruction in the background and send results."""
    try:
        from openclaw.wiring.pipeline import process_photo, render_diagram
        from openclaw.wiring.store import load_project, save_project

        project = load_project(project_id)
        if not project:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Wiring project {project_id} not found.",
            )
            return

        # Run the sync pipeline in a thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: process_photo(project, photo_path, focus_tag=focus_tag),
        )

        # Save updated project
        save_project(result.project)

        # Send text summary
        lines = [f"Reconstruction update ({result.completeness:.0f}% complete):"]
        lines.append(result.summary)

        if result.next_question:
            lines.append(f"\nNext question: {result.next_question}")

        await bot.send_message(chat_id=chat_id, text="\n".join(lines))

        # If diagram ready, render and send PNG
        if result.diagram_ready:
            try:
                png_path = tempfile.mktemp(suffix=".png", prefix="openclaw_diagram_")
                await loop.run_in_executor(
                    None,
                    lambda: render_diagram(result.project, png_path, hires=True),
                )
                with open(png_path, "rb") as f:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=f,
                        caption=f"Wiring diagram — {result.project.panel_name} ({result.completeness:.0f}%)",
                    )
                os.unlink(png_path)
            except Exception as e:
                log.error("Diagram render failed: %s", e)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Diagram render failed: {str(e)[:100]}. Use 'wd build-diagram' on CLI.",
                )

    except Exception as e:
        log.error("Reconstruction pipeline failed: %s", e)
        await bot.send_message(
            chat_id=chat_id,
            text=f"Reconstruction error: {str(e)[:100]}",
        )


# ---------------------------------------------------------------------------
# Main photo handler (registered in factorylm_bot.py)
# ---------------------------------------------------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle an incoming photo message.

    Flow:
    1. Ack immediately
    2. Download photo
    3. Classify intent
    4. Always run KB enrichment (background)
    5. If active project, also run reconstruction (background)
    """
    chat_id = update.effective_chat.id
    caption = update.message.caption or ""
    photo_id = update.message.photo[-1].file_id if update.message.photo else ""

    # Immediate ack
    await update.message.reply_text("Got it, parsing now...")

    # Download the photo
    try:
        photo_path = await _download_photo(update, context)
    except Exception as e:
        log.error("Photo download failed: %s", e)
        await update.message.reply_text(f"Couldn't download that photo: {str(e)[:80]}")
        return

    # Classify intent
    try:
        from openclaw.messages.intent import classify_intent, classify_photo_intent

        project_id = get_active_project(chat_id)
        has_active = project_id is not None

        intents = classify_photo_intent(caption, has_active_project=has_active)
        log.info("Photo intents for chat %d: %s (caption: %s)",
                 chat_id, [str(i) for i in intents], caption[:50])
    except ImportError:
        log.warning("Intent classifier not available, defaulting to enrichment only")
        intents = []
        project_id = None

    # Extract tags hint from caption (e.g., "K1", "F1 close-up")
    tags = None
    if caption:
        import re
        tag_match = re.search(r'\b([QKFSMHUTBX]\d+)\b', caption.upper())
        if tag_match:
            tags = tag_match.group(1)

    # Always run KB enrichment (background)
    asyncio.create_task(
        _run_enrichment(photo_path, photo_id, tags, chat_id, context.bot)
    )

    # Check if we should also run reconstruction
    from openclaw.types import Intent

    should_reconstruct = False
    if project_id:
        should_reconstruct = True
    elif Intent.WIRING_RECONSTRUCT in intents:
        # No active project but caption indicates reconstruction
        # Create a new project
        try:
            from openclaw.wiring.models import WiringProject
            from openclaw.wiring.store import save_project, set_active_project as store_set_active

            project = WiringProject(panel_name=caption or "Telegram Panel")
            save_project(project)
            store_set_active(project.project_id)
            set_active_project(chat_id, project.project_id)
            project_id = project.project_id

            await update.message.reply_text(
                f"Starting new wiring reconstruction project: {project.project_id[:8]}..."
            )
            should_reconstruct = True
        except Exception as e:
            log.error("Failed to create wiring project: %s", e)

    if should_reconstruct and project_id:
        asyncio.create_task(
            _run_reconstruction(photo_path, project_id, tags, chat_id, context.bot)
        )


# ---------------------------------------------------------------------------
# Text handler for wiring project answers
# ---------------------------------------------------------------------------

async def handle_wiring_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Handle a text message as a wiring project answer.

    Returns True if the message was handled (active project + answer processed),
    False if there's no active project (let the normal handler take it).
    """
    chat_id = update.effective_chat.id
    project_id = get_active_project(chat_id)

    if not project_id:
        return False

    text = update.message.text or ""
    if not text:
        return False

    # Check for project control commands
    text_lower = text.lower().strip()
    if text_lower in ("done", "finish", "complete", "exit project"):
        clear_active_project(chat_id)
        await update.message.reply_text(
            "Wiring project closed. Send a new panel photo to start another."
        )
        return True

    if text_lower in ("status", "progress"):
        try:
            from openclaw.wiring.store import load_project

            project = load_project(project_id)
            if project:
                await update.message.reply_text(
                    f"Project: {project.panel_name}\n"
                    f"Components: {len(project.components)}\n"
                    f"Connections: {len(project.connections)}\n"
                    f"Completeness: {project.completeness():.0f}%\n"
                    f"Photos: {len(project.photos)}"
                )
            return True
        except Exception:
            pass

    # Process as a pipeline answer
    try:
        from openclaw.wiring.pipeline import process_answer
        from openclaw.wiring.store import load_project, save_project

        project = load_project(project_id)
        if not project:
            clear_active_project(chat_id)
            return False

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: process_answer(project, text),
        )
        save_project(result.project)

        lines = [result.summary]
        if result.next_question:
            lines.append(f"\nNext: {result.next_question}")
        if result.diagram_ready:
            lines.append("\nDiagram ready! Send 'done' to finish or another photo to continue.")

        await update.message.reply_text("\n".join(lines))
        return True

    except Exception as e:
        log.error("Answer processing failed: %s", e)
        return False
