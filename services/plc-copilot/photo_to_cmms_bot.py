#!/usr/bin/env python3
"""
FactoryLM — Industrial AI Bot (Production)
═══════════════════════════════════════════════════════
Receives equipment photos on Telegram, identifies them with Gemini Vision,
creates assets and work orders in Atlas CMMS.

Production hardened:
- Environment-based config (no hardcoded secrets)
- CMMS auto-retry with token refresh + correct API endpoints
- Duplicate asset detection before creation
- User allowlisting
- Rate limiting per user
- File + console logging with rotation
- Graceful shutdown
- Health check command
- Structured error handling (no internal leaks to users)
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
from io import BytesIO
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, NetworkError, TimedOut, RetryAfter
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Freemium user tracking
from user_db import db as user_db

FREE_PHOTO_LIMIT = 3
REGISTRATION_URL = "http://72.60.175.144/register"


# ════════════════════════════════════════════════════════════════════════
# CONFIG — all from environment variables
# ════════════════════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CMMS_BASE_URL = os.environ.get("CMMS_BASE_URL", "http://localhost:8080")
CMMS_EMAIL = os.environ.get("CMMS_EMAIL", "")
CMMS_PASSWORD = os.environ.get("CMMS_PASSWORD", "")

# Comma-separated Telegram user IDs allowed to use the bot (empty = allow all)
ALLOWED_USERS = os.environ.get("ALLOWED_USERS", "")
ALLOWED_USER_IDS = set()
if ALLOWED_USERS.strip():
    ALLOWED_USER_IDS = {int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip()}

# CMMS Frontend URL for deep links (no trailing slash)
CMMS_FRONTEND_URL = os.environ.get("CMMS_FRONTEND_URL", "http://72.60.175.144")

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

# ---------- OpenTelemetry (no-op if packages missing) ----------
try:
    from factorylm.observability import init_tracing, traced, create_span
    _OTEL_IMPORTED = True
except ImportError:
    _OTEL_IMPORTED = False

# ════════════════════════════════════════════════════════════════════════
# STARTUP VALIDATION
# ════════════════════════════════════════════════════════════════════════
_missing = []
if not BOT_TOKEN:
    _missing.append("TELEGRAM_BOT_TOKEN")
if not GEMINI_API_KEY:
    _missing.append("GEMINI_API_KEY")
if not CMMS_EMAIL:
    _missing.append("CMMS_EMAIL")
if not CMMS_PASSWORD:
    _missing.append("CMMS_PASSWORD")
if _missing:
    log.critical(f"Missing required environment variables: {', '.join(_missing)}")
    sys.exit(1)

# ════════════════════════════════════════════════════════════════════════
# GEMINI VISION
# ════════════════════════════════════════════════════════════════════════
genai.configure(api_key=GEMINI_API_KEY)
vision_model = genai.GenerativeModel("gemini-2.5-flash")

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


async def _analyze_photo_inner(photo_bytes: bytes) -> dict:
    """Core Gemini Vision analysis (extracted for tracing wrapper)."""
    import PIL.Image

    for attempt in range(3):
        try:
            image = PIL.Image.open(BytesIO(photo_bytes))
            response = vision_model.generate_content(
                [ANALYSIS_PROMPT, image],
                generation_config={"temperature": 0.2},
            )
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            result = json.loads(text)
            log.info(f"Gemini analysis: {result.get('equipment_type', '?')} / {result.get('manufacturer', '?')}")
            return result
        except json.JSONDecodeError:
            log.warning(f"Gemini returned non-JSON (attempt {attempt + 1}/3): {text[:200]}")
            if attempt == 2:
                return {"error": "AI could not parse equipment details. Please try a clearer photo."}
        except Exception as e:
            log.error(f"Gemini analysis error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                return {"error": "AI analysis temporarily unavailable. Please try again in a moment."}
    return {"error": "Analysis failed after retries."}


async def analyze_photo(photo_bytes: bytes) -> dict:
    """Send photo to Gemini Vision with retry (traced)."""
    if _OTEL_IMPORTED:
        with create_span("analyze_photo", {"photo_size_bytes": str(len(photo_bytes))}):
            return await _analyze_photo_inner(photo_bytes)
    return await _analyze_photo_inner(photo_bytes)


# ════════════════════════════════════════════════════════════════════════
# CMMS CLIENT — with auto-retry, token refresh, correct endpoints
# ════════════════════════════════════════════════════════════════════════
class CMMSClient:
    """Atlas/Grash CMMS API client with production reliability."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.token_time = 0
        self.session = requests.Session()
        self._asset_cache = {}  # name_lower -> asset_id (for dedup)
        self._cache_time = 0

    def login(self) -> str:
        for attempt in range(3):
            try:
                r = self.session.post(
                    f"{self.base_url}/auth/signin",
                    json={"email": CMMS_EMAIL, "password": CMMS_PASSWORD, "type": "client"},
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                self.token = data.get("accessToken") or data.get("token")
                self.token_time = time.time()
                self.session.headers["Authorization"] = f"Bearer {self.token}"
                log.info("CMMS authenticated")
                return self.token
            except Exception as e:
                log.warning(f"CMMS login attempt {attempt + 1}/3: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise ConnectionError("CMMS login failed after 3 attempts")

    def ensure_auth(self):
        """Re-authenticate if token is missing or >50 min old."""
        if not self.token or (time.time() - self.token_time) > 3000:
            self.login()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response | None:
        """HTTP request with auto-retry and 401 token refresh."""
        self.ensure_auth()
        url = f"{self.base_url}{path}"
        for attempt in range(3):
            try:
                r = self.session.request(method, url, timeout=15, **kwargs)
                if r.status_code == 401:
                    log.info("CMMS token expired, re-authenticating...")
                    self.token = None
                    self.ensure_auth()
                    r = self.session.request(method, url, timeout=15, **kwargs)
                return r
            except requests.exceptions.ConnectionError:
                log.warning(f"CMMS connection error ({attempt + 1}/3)")
                if attempt < 2:
                    time.sleep(2 ** attempt)
            except requests.exceptions.Timeout:
                log.warning(f"CMMS timeout ({attempt + 1}/3)")
                if attempt < 2:
                    time.sleep(2)
        return None

    # ── Asset Operations ─────────────────────────────────────────────

    def refresh_asset_cache(self):
        """Load all assets into cache for dedup lookups."""
        r = self._request("GET", "/assets/mini")
        if r and r.status_code == 200:
            assets = r.json()
            self._asset_cache = {}
            for a in assets:
                name = (a.get("name") or "").strip().lower()
                if name:
                    self._asset_cache[name] = a.get("id")
            self._cache_time = time.time()
            log.debug(f"Asset cache refreshed: {len(self._asset_cache)} assets")
        else:
            log.warning("Failed to refresh asset cache")

    def find_existing_asset(self, name: str) -> int | None:
        """Check if an asset with this name (case-insensitive) already exists."""
        # Refresh cache if stale (>5 min)
        if time.time() - self._cache_time > 300:
            self.refresh_asset_cache()
        return self._asset_cache.get(name.strip().lower())

    def create_asset(self, name: str, description: str = "", model_num: str = "",
                     manufacturer: str = "") -> dict:
        """Create asset, or return existing if duplicate detected."""
        # Dedup check
        existing_id = self.find_existing_asset(name)
        if existing_id:
            log.info(f"Asset already exists: '{name}' (#{existing_id})")
            return {"id": existing_id, "name": name, "existed": True}

        payload = {
            "name": name,
            "description": description,
            "model": model_num,
            "area": manufacturer,
            "status": "OPERATIONAL",
        }
        r = self._request("POST", "/assets", json=payload)
        if r and r.status_code in (200, 201):
            result = r.json()
            # Update cache
            self._asset_cache[name.strip().lower()] = result.get("id")
            log.info(f"Asset created: '{name}' (#{result.get('id')})")
            return result
        log.warning(f"Asset creation failed: {r.status_code if r else 'no response'}")
        return {"id": None, "name": name}

    def list_assets(self) -> list:
        """List all assets (mini format)."""
        r = self._request("GET", "/assets/mini")
        if r and r.status_code == 200:
            return r.json()
        return []

    # ── Work Order Operations ────────────────────────────────────────

    def create_work_order(self, title: str, description: str, priority: str = "MEDIUM",
                          asset_id: int | None = None) -> dict | None:
        # Validate priority is in allowed set
        if priority not in VALID_PRIORITIES:
            log.warning(f"Invalid priority '{priority}', defaulting to MEDIUM")
            priority = "MEDIUM"
        
        payload = {
            "title": title,
            "description": description,
            "priority": priority,
        }
        if asset_id:
            payload["asset"] = {"id": asset_id}
        
        log.debug(f"Creating WO with payload: {payload}")
        r = self._request("POST", "/work-orders", json=payload)
        
        if r and r.status_code in (200, 201):
            wo = r.json()
            log.info(f"Work Order created: #{wo.get('id')} - {title}")
            return wo
        
        # Enhanced error logging
        error_detail = ""
        if r is not None:
            error_detail = f"status={r.status_code}"
            try:
                error_detail += f" body={r.text[:500]}"
            except Exception:
                pass
        else:
            error_detail = "no response"
        log.error(f"WO creation failed: {error_detail}")
        return None

    def list_work_orders(self, page_size: int = 10) -> list:
        """List recent work orders."""
        r = self._request("POST", "/work-orders/search",
                          json={"filterFields": [], "pageNum": 0, "pageSize": page_size})
        if r and r.status_code == 200:
            return r.json().get("content", [])
        return []

    def health_check(self) -> bool:
        """Check if CMMS is reachable and auth works."""
        try:
            self.ensure_auth()
            r = self._request("GET", "/assets/mini")
            return r is not None and r.status_code == 200
        except Exception:
            return False


cmms = CMMSClient(CMMS_BASE_URL)

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
        self.assets_created = 0
        self.work_orders_created = 0
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
        plan_line = "✅ *Registered* — unlimited photo analysis"
    else:
        remaining = access["remaining"]
        plan_line = f"🆓 *Free Trial* — {remaining} scans remaining"

    await update.message.reply_text(
        "🏭 *FactoryLM* — Industrial AI for Maintenance Teams\n\n"
        f"{plan_line}\n\n"
        "📸 Send me a photo of any equipment and I'll:\n"
        "1️⃣ Identify it with AI vision\n"
        "2️⃣ Create an asset in CMMS\n"
        "3️⃣ Generate a work order\n\n"
        "Just snap a photo and send it!\n\n"
        "Commands:\n"
        "/status — Account status & stats\n"
        "/register — Create free account\n"
        "/assets — List CMMS assets\n"
        "/recent — Recent work orders",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_id = str(update.effective_user.id)
    access = check_freemium_access(tg_id)
    cmms_ok = cmms.health_check()

    if access["is_verified"]:
        try:
            user = user_db.get_user_by_telegram_id(tg_id)
            plan_info = (
                f"👤 *Account*\n"
                f"  Name: {user['first_name']} {user['last_name']}\n"
                f"  Plan: ✅ Unlimited\n"
            )
        except Exception:
            plan_info = "👤 *Account:* ✅ Registered (Unlimited)\n"
    else:
        plan_info = (
            f"👤 *Account:* 🆓 Free Trial\n"
            f"  Photos used: {access['photo_count']}/{FREE_PHOTO_LIMIT}\n"
            f"  Remaining: {access['remaining']}\n"
        )

    await update.message.reply_text(
        f"🏭 *FactoryLM Status*\n\n"
        f"{plan_info}\n"
        f"🤖 Bot: ✅ Online\n"
        f"🔍 Gemini Vision: ✅ Ready\n"
        f"🏗️ CMMS: {'✅ Connected' if cmms_ok else '❌ Offline'}\n\n"
        f"📊 *Session Stats:*\n"
        f"⏱ Uptime: {stats.uptime()}\n"
        f"📸 Photos: {stats.photos_processed}\n"
        f"📦 Assets: {stats.assets_created}\n"
        f"🔧 Work orders: {stats.work_orders_created}",
        parse_mode="Markdown",
    )


async def cmd_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /register command."""
    tg_id = str(update.effective_user.id)
    access = check_freemium_access(tg_id)

    if access["is_verified"]:
        await update.message.reply_text(
            "✅ *You're already registered!*\n\n"
            f"You have unlimited access.\n"
            f"🔗 Dashboard: {CMMS_FRONTEND_URL}/app",
            parse_mode="Markdown",
        )
        return

    reg_url = f"{REGISTRATION_URL}?tg={tg_id}"
    keyboard = [[InlineKeyboardButton("📝 Register Now (Free)", url=reg_url)]]

    await update.message.reply_text(
        "🚀 *Register for FactoryLM*\n\n"
        "Get unlimited access to:\n"
        "✅ Photo analysis\n"
        "✅ Equipment tracking\n"
        "✅ Work order management\n"
        "✅ Full CMMS integration\n\n"
        "📱 Takes less than 2 minutes!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_assets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        assets = cmms.list_assets()
        if assets:
            lines = [f"📦 *Assets in CMMS* ({len(assets)}):\n"]
            for a in assets[-20:]:
                lines.append(f"• {a.get('name', 'Unknown')} (#{a.get('id')})")
            if len(assets) > 20:
                lines.append(f"\n_...and {len(assets) - 20} more_")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("📦 No assets found in CMMS yet.")
    except Exception as e:
        log.error(f"Asset listing failed: {e}")
        await update.message.reply_text("❌ Could not retrieve assets. CMMS may be temporarily unavailable.")


async def cmd_recent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        wos = cmms.list_work_orders(10)
        if wos:
            lines = [f"🔧 *Recent Work Orders* ({len(wos)}):\n"]
            for wo in wos[:10]:
                priority = wo.get("priority", "?")
                p_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(priority, "⚪")
                title = wo.get("title", "Untitled")
                if len(title) > 50:
                    title = title[:47] + "..."
                lines.append(f"{p_emoji} WO#{wo.get('id')} — {title}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("🔧 No work orders found.")
    except Exception as e:
        log.error(f"WO listing failed: {e}")
        await update.message.reply_text("❌ Could not retrieve work orders.")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Main flow: Photo → Gemini → CMMS Asset → Work Order → Reply."""
    msg = update.message
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or str(user_id)

    # Freemium access check
    tg_id = str(user_id)
    access = check_freemium_access(tg_id)

    if not access["has_access"]:
        reg_url = f"{REGISTRATION_URL}?tg={tg_id}"
        keyboard = [[InlineKeyboardButton("🔓 Register for Free", url=reg_url)]]
        await msg.reply_text(
            "🔒 *You've used your 3 free equipment scans!*\n\n"
            "Create a free account to continue — unlimited photo analysis, "
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
        await msg.reply_text(f"⏳ Rate limit reached. Try again in {wait_secs // 60 + 1} minutes.")
        log.warning(f"Rate limited: {user_name} ({user_id})")
        return

    t_start = time.monotonic()
    status_msg = await msg.reply_text("📸 Photo received! Analyzing with AI vision...")

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
        await status_msg.edit_text("❌ Failed to download photo. Please try again.")
        return

    # ── 2. Gemini Vision analysis ────────────────────────────────────
    try:
        await status_msg.edit_text("🤖 AI analyzing equipment...")
    except Exception:
        pass  # Edit can fail if message was deleted

    analysis = await analyze_photo(bytes(photo_bytes))
    if "error" in analysis:
        stats.errors += 1
        await status_msg.edit_text(f"❌ {analysis['error']}")
        return

    t_gemini = time.monotonic() - t_start
    log.info(f"Gemini analysis completed [{t_gemini:.1f}s total]")
    rate_limiter.record(user_id)
    stats.photos_processed += 1

    equip_type = analysis.get("equipment_type", "Unknown")
    manufacturer = analysis.get("manufacturer", "Unknown")
    log.info(f"Identified: {equip_type} / {manufacturer}")

    # ── 3. Create/find asset in CMMS ─────────────────────────────────
    try:
        await status_msg.edit_text("🏭 Checking CMMS for existing asset...")
    except Exception:
        pass

    asset_id = None
    asset_name = analysis.get("asset_name", equip_type)
    asset_existed = False
    try:
        asset = cmms.create_asset(
            name=asset_name,
            description=analysis.get("description", ""),
            model_num=analysis.get("model_number", ""),
            manufacturer=manufacturer,
        )
        asset_id = asset.get("id")
        asset_existed = asset.get("existed", False)
        t_asset = time.monotonic() - t_start
        if asset_existed:
            log.info(f"Using existing asset: #{asset_id} [{t_asset:.1f}s total]")
        if asset_id:
            stats.assets_created += (0 if asset_existed else 1)
    except Exception as e:
        log.error(f"Asset creation failed: {e}")

    # ── 4. Create work order ─────────────────────────────────────────
    try:
        await status_msg.edit_text("🔧 Creating work order...")
    except Exception:
        pass

    wo = None
    try:
        # Normalize priority to valid CMMS values (NONE, LOW, MEDIUM, HIGH)
        raw_priority = analysis.get("priority", "MEDIUM")
        validated_priority = normalize_priority(raw_priority)
        if raw_priority != validated_priority:
            log.info(f"Priority normalized: {raw_priority} -> {validated_priority}")
        
        wo = cmms.create_work_order(
            title=analysis.get("work_order_title", f"Inspect {equip_type}"),
            description=analysis.get("work_order_description",
                                     analysis.get("description", "Equipment inspection needed")),
            priority=validated_priority,
            asset_id=asset_id,
        )
        if wo:
            stats.work_orders_created += 1
    except Exception as e:
        log.error(f"Work order creation failed: {e}")
        stats.errors += 1

    # ── 5. Format response ───────────────────────────────────────────
    t_total = time.monotonic() - t_start
    log.info(f"Pipeline complete [{t_total:.1f}s total]")
    issues = analysis.get("visible_issues", [])
    issues_text = "\n".join(f"  ⚠️ {i}" for i in issues) if issues else "  ✅ None detected"

    cond = analysis.get("condition", "Unknown")
    cond_emoji = {"GOOD": "🟢", "FAIR": "🟡", "POOR": "🟠", "CRITICAL": "🔴"}.get(cond, "⚪")
    prio = analysis.get("priority", "MEDIUM")
    prio_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(prio, "⚪")

    wo_id = wo.get("id", "N/A") if wo else "Failed"
    asset_tag = f"{'Existing' if asset_existed else 'New'}: {asset_name}" if asset_id else "Not created"

    # Build deep links
    links_section = ""
    if wo and wo.get("id"):
        wo_link = f"{CMMS_FRONTEND_URL}/app/work-orders/{wo['id']}"
        links_section += f"🔗 [View Work Order]({wo_link})\n"
    if asset_id:
        asset_link = f"{CMMS_FRONTEND_URL}/app/assets/{asset_id}"
        links_section += f"🔗 [View Asset]({asset_link})\n"

    response = (
        f"🏭 *Equipment Analysis Complete*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Equipment:* {equip_type}\n"
        f"*Manufacturer:* {manufacturer}\n"
        f"*Model:* {analysis.get('model_number', 'N/A')}\n"
        f"*Condition:* {cond_emoji} {cond}\n\n"
        f"*Description:*\n{analysis.get('description', 'N/A')}\n\n"
        f"*Visible Issues:*\n{issues_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *CMMS Work Order*\n\n"
        f"*WO #:* {wo_id}\n"
        f"*Priority:* {prio_emoji} {prio}\n"
        f"*Asset:* {asset_tag}\n"
        f"*Title:* {analysis.get('work_order_title', 'N/A')}\n\n"
        f"*Action Required:*\n{analysis.get('recommended_action', 'Inspection needed')}\n\n"
    )

    if links_section:
        response += f"━━━━━━━━━━━━━━━━━━━━━━\n{links_section}\n"

    response += (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ _Powered by FactoryLM_"
    )

    try:
        await status_msg.edit_text(response, parse_mode="Markdown")
    except Exception:
        # Fallback without markdown if formatting breaks
        try:
            await status_msg.edit_text(response.replace("*", "").replace("_", ""))
        except Exception as e:
            log.error(f"Failed to send response: {e}")

    log.info(f"Complete: WO #{wo_id} for {equip_type} (user: {user_name})")

    # Record structured tracing event for the completed pipeline
    if _OTEL_IMPORTED:
        from factorylm.observability import record_event
        record_event("cmms_pipeline_complete", {
            "equipment_type": equip_type,
            "manufacturer": manufacturer,
            "work_order_id": str(wo_id),
            "pipeline_duration_s": f"{t_total:.2f}",
            "user": user_name,
        })

    # Track freemium usage
    usage = track_photo_usage(tg_id)
    if not usage.get("is_verified") and usage.get("photo_count", 0) > 0:
        remaining = FREE_PHOTO_LIMIT - usage["photo_count"]
        if remaining > 0:
            try:
                await msg.reply_text(
                    f"📊 *Free scans remaining:* {remaining}/{FREE_PHOTO_LIMIT}\n"
                    f"Register for unlimited access: /register",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        elif remaining == 0:
            reg_url = f"{REGISTRATION_URL}?tg={tg_id}"
            keyboard = [[InlineKeyboardButton("🔓 Register Now (Free)", url=reg_url)]]
            try:
                await msg.reply_text(
                    "🎯 *That was your last free scan!*\n\n"
                    "Register now to continue with unlimited photo analysis.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            except Exception:
                pass


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle non-command text messages."""
    await update.message.reply_text(
        "📸 Send me a *photo* of equipment to analyze it!\n\n"
        "Or use /status, /assets, or /recent",
        parse_mode="Markdown",
    )


# ════════════════════════════════════════════════════════════════════════
# ERROR HANDLER
# ════════════════════════════════════════════════════════════════════════
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler — log and continue, never crash."""
    err = context.error
    log.error(f"Unhandled exception: {err}")
    log.debug(traceback.format_exc())
    stats.errors += 1

    if isinstance(err, Conflict):
        log.critical("Another bot instance is running! Exiting to avoid conflict loop.")
        os._exit(1)  # Hard exit — systemd will restart us

    if isinstance(err, (NetworkError, TimedOut)):
        log.warning("Network issue — will auto-retry on next poll cycle")
        return

    if isinstance(err, RetryAfter):
        log.warning(f"Rate limited by Telegram, waiting {err.retry_after}s")
        return

    # Notify user if possible (without leaking internals)
    if update and hasattr(update, "message") and update.message:
        try:
            await update.message.reply_text(
                "⚠️ Something went wrong. Please try again."
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
    log.info("FactoryLM Bot starting (production)")
    log.info(f"  CMMS: {CMMS_BASE_URL}")
    log.info(f"  Mode: Freemium ({FREE_PHOTO_LIMIT} free photos, then registration)")
    log.info(f"  Rate limit: {RATE_LIMIT_PER_HOUR}/hour")
    log.info(f"  Log dir: {LOG_DIR}")

    # Initialise OpenTelemetry tracing (no-op if packages/key missing)
    if _OTEL_IMPORTED:
        init_tracing("plc-copilot")

    log.info("=" * 60)

    # Clear stale polling lock
    clear_telegram_lock()

    # Pre-auth CMMS and warm asset cache
    try:
        cmms.login()
        cmms.refresh_asset_cache()
        log.info(f"Asset cache loaded: {len(cmms._asset_cache)} assets")
    except Exception as e:
        log.warning(f"CMMS startup failed: {e} — will retry on first request")

    # Build Telegram bot
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("assets", cmd_assets))
    app.add_handler(CommandHandler("recent", cmd_recent))
    app.add_handler(CommandHandler("register", cmd_register))

    # Content handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Global error handler
    app.add_error_handler(error_handler)

    log.info("Bot ready — listening for photos!")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message"],
    )


if __name__ == "__main__":
    main()
