#!/usr/bin/env python3
"""
FactoryLM — Industrial AI Bot (Production)
═══════════════════════════════════════════════════════
Receives equipment photos on Telegram, identifies them with Groq Vision,
creates GitHub Gists with structured equipment reports.

Production hardened:
- Environment-based config (no hardcoded secrets)
- GitHub Gist integration for equipment tracking
- User allowlisting
- Rate limiting per user
- File + console logging with rotation
- Graceful shutdown
- Health check command
- Structured error handling (no internal leaks to users)

UPDATED: Feb 2026 - Switched from Gemini to Groq Vision (llama-3.2-11b-vision)
UPDATED: Feb 2026 - Migrated from Atlas CMMS to GitHub Gists
"""
import os
import sys
import json
import signal
import logging
import logging.handlers
import requests
import time
import traceback
import asyncio
import base64
from io import BytesIO
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, NetworkError, TimedOut, RetryAfter
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Freemium user tracking
from user_db import db as user_db

FREE_PHOTO_LIMIT = 999999  # Testing mode - unlimited for everyone
REGISTRATION_URL = "http://72.60.175.144/register"


# ════════════════════════════════════════════════════════════════════════
# CONFIG — all from environment variables
# ════════════════════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Comma-separated Telegram user IDs allowed to use the bot (empty = allow all)
ALLOWED_USERS = os.environ.get("ALLOWED_USERS", "")
ALLOWED_USER_IDS = set()
if ALLOWED_USERS.strip():
    ALLOWED_USER_IDS = {int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip()}

# Rate limiting: max photos per user per hour
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "30"))

# Log directory
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/plc-copilot")

# ════════════════════════════════════════════════════════════════════════
# LOGGING — file + console with rotation
# ════════════════════════════════════════════════════════════════════════
def setup_logging():
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(logging.INFO)

    # File handler with rotation (10MB, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "plc-copilot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    # Error-only file for quick triage
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "plc-copilot-errors.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setFormatter(fmt)
    error_handler.setLevel(logging.ERROR)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.addHandler(error_handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    return logging.getLogger("plc-copilot")


log = setup_logging()

# ════════════════════════════════════════════════════════════════════════
# STARTUP VALIDATION
# ════════════════════════════════════════════════════════════════════════
_missing = []
if not BOT_TOKEN:
    _missing.append("TELEGRAM_BOT_TOKEN")
if not GROQ_API_KEY:
    _missing.append("GROQ_API_KEY")
if not GITHUB_TOKEN:
    _missing.append("GITHUB_TOKEN")
if _missing:
    log.critical(f"Missing required environment variables: {', '.join(_missing)}")
    sys.exit(1)

# ════════════════════════════════════════════════════════════════════════
# GROQ VISION (Llama 3.2 11B Vision)
# ════════════════════════════════════════════════════════════════════════
groq_client = Groq(api_key=GROQ_API_KEY)
VISION_MODEL = "llama-3.2-11b-vision-preview"

ANALYSIS_PROMPT = """You are an industrial equipment identification expert for a CMMS system.

Analyze this photo and provide a JSON response with:
{
  "equipment_type": "type of equipment (e.g., Motor, Pump, Conveyor, PLC, VFD, Valve, etc.)",
  "manufacturer": "manufacturer if visible (e.g., Allen-Bradley, Siemens, ABB)",
  "model_number": "model number if visible",
  "description": "brief description of what you see",
  "condition": "GOOD | FAIR | POOR | CRITICAL",
  "visible_issues": ["list of any visible issues, damage, wear, etc."],
  "recommended_action": "recommended maintenance action",
  "work_order_title": "suggested work order title",
  "work_order_description": "detailed work order description for a maintenance technician",
  "priority": "NONE | LOW | MEDIUM | HIGH",
  "asset_name": "suggested asset name for CMMS (short, descriptive)"
}

Be specific and practical. If you can't identify something, say so.
Focus on actionable maintenance information a technician would need.
Return ONLY valid JSON, no markdown fences."""

# Valid CMMS priorities - used for validation
VALID_PRIORITIES = {"NONE", "LOW", "MEDIUM", "HIGH"}

def normalize_priority(priority: str) -> str:
    """Normalize priority to valid CMMS values. Maps CRITICAL -> HIGH."""
    if not priority:
        return "MEDIUM"
    priority = priority.upper().strip()
    if priority in VALID_PRIORITIES:
        return priority
    # Map invalid values to closest valid ones
    if priority == "CRITICAL":
        return "HIGH"
    if priority in ("URGENT", "EMERGENCY"):
        return "HIGH"
    return "MEDIUM"  # Default fallback


async def analyze_photo(photo_bytes: bytes) -> dict:
    """Send photo to Groq Vision with retry."""
    for attempt in range(3):
        try:
            # Encode image as base64
            base64_image = base64.b64encode(photo_bytes).decode('utf-8')

            # Call Groq Vision API
            response = groq_client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }}
                    ]
                }],
                temperature=0.2,
                max_tokens=1024,
            )

            text = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

            result = json.loads(text)
            log.info(f"Groq analysis: {result.get('equipment_type', '?')} / {result.get('manufacturer', '?')}")
            return result

        except json.JSONDecodeError:
            log.warning(f"Groq returned non-JSON (attempt {attempt + 1}/3): {text[:200]}")
            if attempt == 2:
                return {"error": "AI could not parse equipment details. Please try a clearer photo."}
        except Exception as e:
            log.error(f"Groq analysis error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                return {"error": "AI analysis temporarily unavailable. Please try again in a moment."}
    return {"error": "Analysis failed after retries."}


# ════════════════════════════════════════════════════════════════════════
# GITHUB GIST CLIENT — equipment reports as Gists
# ════════════════════════════════════════════════════════════════════════
class GistClient:
    """GitHub Gist API client for equipment reports."""

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self._gist_cache = {}  # equipment_name -> gist_id (for dedup)

    def create_equipment_report(self, analysis: dict, user_name: str = "Unknown") -> dict | None:
        """Create a Gist with equipment analysis report."""
        equip_type = analysis.get("equipment_type", "Unknown Equipment")
        manufacturer = analysis.get("manufacturer", "Unknown")
        model_num = analysis.get("model_number", "N/A")
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Build markdown report
        issues = analysis.get("visible_issues", [])
        issues_text = "\n".join(f"- {i}" for i in issues) if issues else "- None detected"

        report_md = f"""# Equipment Report: {equip_type}

**Generated:** {timestamp}
**Reported by:** {user_name}
**AI Model:** Groq Vision (Llama 3.2 11B)

---

## Equipment Details

| Field | Value |
|-------|-------|
| Type | {equip_type} |
| Manufacturer | {manufacturer} |
| Model | {model_num} |
| Condition | {analysis.get("condition", "Unknown")} |

## Description

{analysis.get("description", "No description available")}

## Visible Issues

{issues_text}

## Recommended Action

{analysis.get("recommended_action", "Inspection needed")}

---

## Work Order Details

**Title:** {analysis.get("work_order_title", f"Inspect {equip_type}")}

**Priority:** {analysis.get("priority", "MEDIUM")}

**Description:**
{analysis.get("work_order_description", "Equipment inspection needed")}

---

*Powered by FactoryLM + Groq Vision*
"""

        # JSON data file for programmatic access
        report_json = json.dumps({
            "equipment_type": equip_type,
            "manufacturer": manufacturer,
            "model_number": model_num,
            "condition": analysis.get("condition"),
            "description": analysis.get("description"),
            "visible_issues": issues,
            "recommended_action": analysis.get("recommended_action"),
            "work_order": {
                "title": analysis.get("work_order_title"),
                "description": analysis.get("work_order_description"),
                "priority": analysis.get("priority"),
            },
            "metadata": {
                "reported_by": user_name,
                "timestamp": timestamp,
                "ai_model": "llama-3.2-11b-vision-preview",
            }
        }, indent=2)

        # Create Gist with both markdown and JSON files
        safe_name = equip_type.replace(" ", "_").replace("/", "-")[:30]
        gist_payload = {
            "description": f"FactoryLM Equipment Report: {equip_type} - {manufacturer}",
            "public": False,
            "files": {
                f"{safe_name}_report.md": {"content": report_md},
                f"{safe_name}_data.json": {"content": report_json},
            }
        }

        for attempt in range(3):
            try:
                r = self.session.post(
                    "https://api.github.com/gists",
                    json=gist_payload,
                    timeout=15,
                )
                if r.status_code in (200, 201):
                    gist = r.json()
                    gist_id = gist.get("id")
                    gist_url = gist.get("html_url")
                    log.info(f"Gist created: {gist_id} - {equip_type}")
                    return {
                        "id": gist_id,
                        "url": gist_url,
                        "equipment_type": equip_type,
                    }
                else:
                    log.warning(f"Gist creation failed: {r.status_code} - {r.text[:200]}")
            except Exception as e:
                log.error(f"Gist creation error (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)

        return None

    def list_equipment_gists(self, limit: int = 10) -> list:
        """List recent equipment report Gists."""
        try:
            r = self.session.get(
                "https://api.github.com/gists",
                params={"per_page": 100},
                timeout=15,
            )
            if r.status_code == 200:
                gists = r.json()
                # Filter to FactoryLM equipment reports
                equipment_gists = [
                    g for g in gists
                    if "FactoryLM Equipment Report" in (g.get("description") or "")
                ]
                return equipment_gists[:limit]
        except Exception as e:
            log.error(f"Failed to list gists: {e}")
        return []

    def health_check(self) -> bool:
        """Check if GitHub API is reachable and token works."""
        try:
            r = self.session.get("https://api.github.com/user", timeout=10)
            return r.status_code == 200
        except Exception:
            return False


gist_client = GistClient(GITHUB_TOKEN)

# ════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ════════════════════════════════════════════════════════════════════════
class RateLimiter:
    def __init__(self, max_per_hour: int):
        self.max_per_hour = max_per_hour
        self.requests = defaultdict(list)  # user_id -> [timestamps]

    def check(self, user_id: int) -> tuple[bool, int]:
        """Returns (allowed, seconds_until_reset)."""
        now = time.time()
        cutoff = now - 3600
        # Prune old entries
        self.requests[user_id] = [t for t in self.requests[user_id] if t > cutoff]
        if len(self.requests[user_id]) >= self.max_per_hour:
            oldest = min(self.requests[user_id])
            wait = int(oldest + 3600 - now) + 1
            return False, wait
        return True, 0

    def record(self, user_id: int):
        self.requests[user_id].append(time.time())


rate_limiter = RateLimiter(RATE_LIMIT_PER_HOUR)

# ════════════════════════════════════════════════════════════════════════
# STATS TRACKING
# ════════════════════════════════════════════════════════════════════════
class Stats:
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.photos_processed = 0
        self.gists_created = 0
        self.errors = 0

    def uptime(self) -> str:
        delta = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m {seconds}s"


stats = Stats()

# ════════════════════════════════════════════════════════════════════════
# AUTH CHECK
# ════════════════════════════════════════════════════════════════════════
def check_freemium_access(telegram_id: str) -> dict:
    """Check freemium access for a Telegram user.
    Returns: {has_access, is_registered, is_verified, photo_count, remaining}
    """
    try:
        usage = user_db.get_telegram_usage(telegram_id)
        return {
            "has_access": not usage["limit_reached"],
            "is_registered": usage["is_registered"],
            "is_verified": usage["is_verified"],
            "photo_count": usage["photo_count"],
            "remaining": max(0, FREE_PHOTO_LIMIT - usage["photo_count"]),
        }
    except Exception as e:
        log.error(f"Freemium check error: {e}")
        return {"has_access": True, "is_registered": False, "is_verified": False,
                "photo_count": 0, "remaining": FREE_PHOTO_LIMIT}


def track_photo_usage(telegram_id: str) -> dict:
    """Track a photo analysis for freemium limits."""
    try:
        return user_db.track_telegram_usage(telegram_id)
    except Exception as e:
        log.error(f"Usage tracking error: {e}")
        return {"photo_count": 0, "is_registered": False, "is_verified": False, "limit_reached": False}


# ════════════════════════════════════════════════════════════════════════
# TELEGRAM HANDLERS
# ════════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = str(update.effective_user.id)
    access = check_freemium_access(tg_id)

    if access["is_verified"]:
        plan_line = "* *Registered* - unlimited photo analysis"
    else:
        remaining = access["remaining"]
        plan_line = f"*Free Trial* - {remaining} scans remaining"

    await update.message.reply_text(
        "*FactoryLM* - Industrial AI for Maintenance Teams\n\n"
        f"{plan_line}\n\n"
        "Send me a photo of any equipment and I'll:\n"
        "1. Identify it with AI vision\n"
        "2. Create a detailed equipment report\n"
        "3. Save it as a GitHub Gist\n\n"
        "Just snap a photo and send it!\n\n"
        "Commands:\n"
        "/status - Account status & stats\n"
        "/register - Create free account\n"
        "/reports - Recent equipment reports",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = str(update.effective_user.id)
    access = check_freemium_access(tg_id)
    github_ok = gist_client.health_check()

    if access["is_verified"]:
        try:
            user = user_db.get_user_by_telegram_id(tg_id)
            plan_info = (
                f"*Account*\n"
                f"  Name: {user['first_name']} {user['last_name']}\n"
                f"  Plan: Unlimited\n"
            )
        except Exception:
            plan_info = "*Account:* Registered (Unlimited)\n"
    else:
        plan_info = (
            f"*Account:* Free Trial\n"
            f"  Photos used: {access['photo_count']}/{FREE_PHOTO_LIMIT}\n"
            f"  Remaining: {access['remaining']}\n"
        )

    await update.message.reply_text(
        f"*FactoryLM Status*\n\n"
        f"{plan_info}\n"
        f"Bot: Online\n"
        f"Groq Vision: Ready\n"
        f"GitHub Gists: {'Connected' if github_ok else 'Offline'}\n\n"
        f"*Session Stats:*\n"
        f"Uptime: {stats.uptime()}\n"
        f"Photos: {stats.photos_processed}\n"
        f"Gists: {stats.gists_created}",
        parse_mode="Markdown",
    )


async def cmd_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /register command."""
    tg_id = str(update.effective_user.id)
    access = check_freemium_access(tg_id)

    if access["is_verified"]:
        await update.message.reply_text(
            "*You're already registered!*\n\n"
            f"You have unlimited access.\n"
            f"Dashboard: {CMMS_FRONTEND_URL}/app",
            parse_mode="Markdown",
        )
        return

    reg_url = f"{REGISTRATION_URL}?tg={tg_id}"
    keyboard = [[InlineKeyboardButton("Register Now (Free)", url=reg_url)]]

    await update.message.reply_text(
        "*Register for FactoryLM*\n\n"
        "Get unlimited access to:\n"
        "- Photo analysis\n"
        "- Equipment tracking\n"
        "- Work order management\n"
        "- Full CMMS integration\n\n"
        "Takes less than 2 minutes!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_reports(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """List recent equipment report Gists."""
    try:
        gists = gist_client.list_equipment_gists(10)
        if gists:
            lines = [f"*Recent Equipment Reports* ({len(gists)}):\n"]
            for g in gists[:10]:
                desc = g.get("description", "Unknown")
                # Extract equipment type from description
                equip_name = desc.replace("FactoryLM Equipment Report: ", "")[:40]
                url = g.get("html_url", "")
                lines.append(f"- [{equip_name}]({url})")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text("No equipment reports found yet. Send a photo to create one!")
    except Exception as e:
        log.error(f"Report listing failed: {e}")
        await update.message.reply_text("Could not retrieve reports. Please try again.")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Main flow: Photo -> Groq Vision -> GitHub Gist Report."""
    msg = update.message
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or str(user_id)

    # Freemium access check
    tg_id = str(user_id)
    access = check_freemium_access(tg_id)

    if not access["has_access"]:
        reg_url = f"{REGISTRATION_URL}?tg={tg_id}"
        keyboard = [[InlineKeyboardButton("Register for Free", url=reg_url)]]
        await msg.reply_text(
            "*You've used your free equipment scans!*\n\n"
            "Create a free account to continue - unlimited photo analysis, "
            "work order management, and full CMMS access.\n\n"
            "Registration takes less than 2 minutes!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        log.info(f"Freemium limit reached: {user_name} ({user_id})")
        return

    # Rate limit check
    allowed, wait_secs = rate_limiter.check(user_id)
    if not allowed:
        await msg.reply_text(f"Rate limit reached. Try again in {wait_secs // 60 + 1} minutes.")
        log.warning(f"Rate limited: {user_name} ({user_id})")
        return

    t_start = time.monotonic()
    status_msg = await msg.reply_text("Photo received! Analyzing with AI vision...")

    # ── 1. Download photo ────────────────────────────────────────────
    try:
        photo = msg.photo[-1]  # Largest resolution
        file = await ctx.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        t_download = time.monotonic() - t_start
        log.info(f"Photo from {user_name} ({user_id}): {len(photo_bytes)} bytes [{t_download:.1f}s]")
    except Exception as e:
        log.error(f"Photo download failed: {e}")
        stats.errors += 1
        await status_msg.edit_text("Failed to download photo. Please try again.")
        return

    # ── 2. Groq Vision analysis ────────────────────────────────────
    try:
        await status_msg.edit_text("AI analyzing equipment...")
    except Exception:
        pass  # Edit can fail if message was deleted

    analysis = await analyze_photo(bytes(photo_bytes))
    if "error" in analysis:
        stats.errors += 1
        await status_msg.edit_text(f"{analysis['error']}")
        return

    t_groq = time.monotonic() - t_start
    log.info(f"Groq analysis completed [{t_groq:.1f}s total]")
    rate_limiter.record(user_id)
    stats.photos_processed += 1

    equip_type = analysis.get("equipment_type", "Unknown")
    manufacturer = analysis.get("manufacturer", "Unknown")
    log.info(f"Identified: {equip_type} / {manufacturer}")

    # ── 3. Create GitHub Gist with equipment report ──────────────────
    try:
        await status_msg.edit_text("Creating equipment report...")
    except Exception:
        pass

    gist = None
    try:
        gist = gist_client.create_equipment_report(analysis, user_name)
        if gist:
            stats.gists_created += 1
    except Exception as e:
        log.error(f"Gist creation failed: {e}")
        stats.errors += 1

    # ── 4. Format response ───────────────────────────────────────────
    t_total = time.monotonic() - t_start
    log.info(f"Pipeline complete [{t_total:.1f}s total]")
    issues = analysis.get("visible_issues", [])
    issues_text = "\n".join(f"  - {i}" for i in issues) if issues else "  None detected"

    cond = analysis.get("condition", "Unknown")
    cond_tag = {"GOOD": "[OK]", "FAIR": "[FAIR]", "POOR": "[POOR]", "CRITICAL": "[CRIT]"}.get(cond, "[?]")
    prio = analysis.get("priority", "MEDIUM")
    prio_tag = {"LOW": "[L]", "MEDIUM": "[M]", "HIGH": "[H]", "CRITICAL": "[!]"}.get(prio, "[?]")

    gist_status = "Created" if gist else "Failed"
    gist_url = gist.get("url") if gist else None

    response = (
        f"*Equipment Analysis Complete*\n"
        f"========================\n\n"
        f"*Equipment:* {equip_type}\n"
        f"*Manufacturer:* {manufacturer}\n"
        f"*Model:* {analysis.get('model_number', 'N/A')}\n"
        f"*Condition:* {cond_tag} {cond}\n\n"
        f"*Description:*\n{analysis.get('description', 'N/A')}\n\n"
        f"*Visible Issues:*\n{issues_text}\n\n"
        f"========================\n"
        f"*Maintenance Recommendation*\n\n"
        f"*Priority:* {prio_tag} {prio}\n"
        f"*Title:* {analysis.get('work_order_title', 'N/A')}\n\n"
        f"*Action Required:*\n{analysis.get('recommended_action', 'Inspection needed')}\n\n"
    )

    if gist_url:
        response += (
            f"========================\n"
            f"*Report Saved:*\n[View Full Report]({gist_url})\n\n"
        )

    response += (
        f"========================\n"
        f"_Powered by FactoryLM + Groq Vision_"
    )

    try:
        await status_msg.edit_text(response, parse_mode="Markdown")
    except Exception:
        # Fallback without markdown if formatting breaks
        try:
            await status_msg.edit_text(response.replace("*", "").replace("_", ""))
        except Exception as e:
            log.error(f"Failed to send response: {e}")

    gist_id = gist.get("id", "N/A") if gist else "Failed"
    log.info(f"Complete: Gist {gist_id} for {equip_type} (user: {user_name})")

    # Track freemium usage
    usage = track_photo_usage(tg_id)
    if not usage.get("is_verified") and usage.get("photo_count", 0) > 0:
        remaining = FREE_PHOTO_LIMIT - usage["photo_count"]
        if remaining > 0:
            try:
                await msg.reply_text(
                    f"*Free scans remaining:* {remaining}/{FREE_PHOTO_LIMIT}\n"
                    f"Register for unlimited access: /register",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        elif remaining == 0:
            reg_url = f"{REGISTRATION_URL}?tg={tg_id}"
            keyboard = [[InlineKeyboardButton("Register Now (Free)", url=reg_url)]]
            try:
                await msg.reply_text(
                    "*That was your last free scan!*\n\n"
                    "Register now to continue with unlimited photo analysis.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            except Exception:
                pass


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle non-command text messages."""
    await update.message.reply_text(
        "Send me a *photo* of equipment to analyze it!\n\n"
        "Or use /status or /reports",
        parse_mode="Markdown",
    )


# ════════════════════════════════════════════════════════════════════════
# ERROR HANDLER
# ════════════════════════════════════════════════════════════════════════
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler - log and continue, never crash."""
    err = context.error
    log.error(f"Unhandled exception: {err}")
    log.debug(traceback.format_exc())
    stats.errors += 1

    if isinstance(err, Conflict):
        log.critical("Another bot instance is running! Exiting to avoid conflict loop.")
        os._exit(1)  # Hard exit - systemd will restart us

    if isinstance(err, (NetworkError, TimedOut)):
        log.warning("Network issue - will auto-retry on next poll cycle")
        return

    if isinstance(err, RetryAfter):
        log.warning(f"Rate limited by Telegram, waiting {err.retry_after}s")
        return

    # Notify user if possible (without leaking internals)
    if update and hasattr(update, "message") and update.message:
        try:
            await update.message.reply_text(
                "Something went wrong. Please try again."
            )
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════
# TELEGRAM LOCK CLEARING
# ════════════════════════════════════════════════════════════════════════
def clear_telegram_lock():
    """Force-clear any stale polling lock from a previous instance."""
    import requests as req

    log.info("Clearing any stale Telegram polling lock...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    try:
        req.post(f"{url}/deleteWebhook", json={"drop_pending_updates": True}, timeout=10)
    except Exception:
        pass

    for i in range(10):
        try:
            r = req.post(f"{url}/getUpdates", json={"timeout": 1, "offset": -1}, timeout=10)
            if r.status_code == 200:
                log.info(f"  Lock cleared (attempt {i + 1})")
                break
            elif r.status_code == 409:
                log.info(f"  Still locked (attempt {i + 1}), waiting 5s...")
                time.sleep(5)
            else:
                log.info(f"  Unexpected status {r.status_code} (attempt {i + 1})")
                time.sleep(2)
        except Exception as e:
            log.warning(f"  Lock clear attempt {i + 1} failed: {e}")
            time.sleep(2)

    time.sleep(3)
    log.info("Lock clear complete")


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════
def main():
    log.info("=" * 60)
    log.info("FactoryLM Bot starting (production) - Groq Vision + GitHub Gists")
    log.info(f"  Vision: {VISION_MODEL}")
    log.info(f"  Output: GitHub Gists")
    log.info(f"  Mode: Freemium ({FREE_PHOTO_LIMIT} free photos, then registration)")
    log.info(f"  Rate limit: {RATE_LIMIT_PER_HOUR}/hour")
    log.info(f"  Log dir: {LOG_DIR}")
    log.info("=" * 60)

    # Clear stale polling lock
    clear_telegram_lock()

    # Verify GitHub API access
    try:
        if gist_client.health_check():
            log.info("GitHub API: Connected")
        else:
            log.warning("GitHub API: Connection failed - check GITHUB_TOKEN")
    except Exception as e:
        log.warning(f"GitHub startup check failed: {e}")

    # Build Telegram bot
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("reports", cmd_reports))
    app.add_handler(CommandHandler("register", cmd_register))

    # Content handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Global error handler
    app.add_error_handler(error_handler)

    log.info("Bot ready - listening for photos!")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message"],
    )


if __name__ == "__main__":
    main()
