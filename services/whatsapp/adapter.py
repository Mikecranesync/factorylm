"""WhatsApp adapter — thin bridge from Twilio WhatsApp to FactoryLM pipeline.

Inbound:  POST /whatsapp/webhook (Twilio form data) → FactoryLMInput → pipeline.process()
Outbound: FactoryLMResponse → TwiML XML response

Uses Twilio WhatsApp Sandbox (free, no business approval needed for testing).
Join sandbox: send "join <sandbox-word>" to +1 415 523 8886 on WhatsApp.

Usage:
    uvicorn services.whatsapp.main:app --port 8200
    # or: make whatsapp
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx

# Ensure monorepo root is importable
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.pipeline import FactoryLMInput, FactoryLMResponse, process

logger = logging.getLogger("factorylm.whatsapp")

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
MEDIA_INBOX = Path.home() / ".openclaw" / "media-inbox" / "whatsapp"


def validate_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Validate X-Twilio-Signature header to prevent spoofed webhooks."""
    if not TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return True

    # Build the data string per Twilio spec
    data = url
    for key in sorted(params.keys()):
        data += key + params[key]

    expected = hmac.new(
        TWILIO_AUTH_TOKEN.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    import base64
    expected_b64 = base64.b64encode(expected).decode("utf-8")
    return hmac.compare_digest(expected_b64, signature)


def parse_twilio_whatsapp(form: dict) -> tuple[FactoryLMInput, dict]:
    """Normalize Twilio WhatsApp webhook form data → FactoryLMInput.

    Twilio form fields:
        Body: message text
        From: whatsapp:+1234567890
        To: whatsapp:+14155238886
        NumMedia: "0" or "1"
        MediaUrl0: URL to media file
        MediaContentType0: "image/jpeg", "video/mp4", etc.
        ProfileName: sender's WhatsApp display name
        MessageSid: unique message ID
    """
    text = form.get("Body", "").strip()
    sender = form.get("From", "").replace("whatsapp:", "")
    profile_name = form.get("ProfileName", "")
    message_sid = form.get("MessageSid", "")
    num_media = int(form.get("NumMedia", "0"))

    media_url = form.get("MediaUrl0") if num_media > 0 else None
    media_type_raw = form.get("MediaContentType0", "")

    # Map MIME type to pipeline media type
    media_type = None
    if media_type_raw.startswith("image/"):
        media_type = "photo"
    elif media_type_raw.startswith("video/"):
        media_type = "video"

    inp = FactoryLMInput(
        text=text if not media_url else None,
        caption=text if media_url else None,
        user_id=sender,
        channel="whatsapp",
    )

    meta = {
        "sender": sender,
        "profile_name": profile_name,
        "message_sid": message_sid,
        "media_url": media_url,
        "media_type": media_type,
        "media_content_type": media_type_raw,
    }

    return inp, meta


async def download_twilio_media(url: str, media_type: str) -> Optional[str]:
    """Download media from Twilio and save to local inbox."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = TWILIO_AUTH_TOKEN

    if not account_sid or not auth_token:
        logger.warning("Twilio credentials not set — cannot download media")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, auth=(account_sid, auth_token))
            resp.raise_for_status()

            from datetime import datetime
            date_folder = MEDIA_INBOX / datetime.now().strftime("%Y-%m-%d")
            date_folder.mkdir(parents=True, exist_ok=True)

            ext = ".jpg" if media_type == "photo" else ".mp4"
            filename = f"{datetime.now().strftime('%H%M%S')}_{os.urandom(4).hex()}{ext}"
            file_path = date_folder / filename
            file_path.write_bytes(resp.content)

            logger.info("Downloaded WhatsApp media: %s (%.1f KB)", file_path, len(resp.content) / 1024)
            return str(file_path)
    except Exception as e:
        logger.error("Failed to download Twilio media: %s", e)
        return None


async def handle_webhook(form: dict) -> str:
    """Process an inbound WhatsApp message and return TwiML response."""
    inp, meta = parse_twilio_whatsapp(form)

    logger.info(
        "WhatsApp from %s (%s): %s",
        meta["sender"],
        meta["profile_name"],
        (inp.text or inp.caption or "media")[:80],
    )

    # Handle media if present
    if meta["media_url"] and meta["media_type"]:
        media_path = await download_twilio_media(meta["media_url"], meta["media_type"])
        if media_path:
            inp.media_path = media_path
            inp.media_type = meta["media_type"]

    # Route through unified pipeline
    resp = await process(inp)

    logger.info(
        "[%s] WhatsApp reply to %s (%ss, %s)",
        resp.trace_id or "?",
        meta["sender"],
        resp.elapsed_s,
        resp.provider or "?",
    )

    # Build TwiML response
    return build_twiml(resp.text)


def build_twiml(body: str) -> str:
    """Build a Twilio MessagingResponse XML string."""
    # Escape XML special characters
    safe_body = (
        body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{safe_body}</Message>"
        "</Response>"
    )
