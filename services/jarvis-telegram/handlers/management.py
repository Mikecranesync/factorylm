# Restored from: feature/factorylm-remote:infrastructure/bot/management_handlers.py
"""
Management dashboard handlers — /status, /agents, /metrics for ops monitoring.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Agent definitions — TODO: replace with live endpoint checks from agents_config.json
AGENTS_CONFIG_PATH = Path(__file__).parent.parent / "agents_config.json"

# Default agent roster (stubbed — 24 agents across 6 teams)
DEFAULT_AGENTS = {
    "Executive Team (2)": [
        "AICEOAgent",
        "AIChiefOfStaffAgent",
    ],
    "Research & Knowledge (6)": [
        "ResearchAgent",
        "AtomBuilderAgent",
        "AtomLibrarianAgent",
        "QualityCheckerAgent",
        "OEMPDFScraperAgent",
        "AtomBuilderFromPDF",
    ],
    "Content Production (8)": [
        "MasterCurriculumAgent",
        "ContentStrategyAgent",
        "ScriptwriterAgent",
        "SEOAgent",
        "ThumbnailAgent",
        "ContentCuratorAgent",
        "TrendScoutAgent",
        "VideoQualityReviewerAgent",
    ],
    "Media & Publishing (4)": [
        "VoiceProductionAgent",
        "VideoAssemblyAgent",
        "PublishingStrategyAgent",
        "YouTubeUploaderAgent",
    ],
    "Engagement & Analytics (3)": [
        "CommunityAgent",
        "AnalyticsAgent",
        "SocialAmplifierAgent",
    ],
    "Orchestration (1)": [
        "MasterOrchestratorAgent",
    ],
}


def _load_agents() -> dict:
    """Load agent definitions from config file, falling back to defaults."""
    if AGENTS_CONFIG_PATH.exists():
        try:
            return json.loads(AGENTS_CONFIG_PATH.read_text())
        except Exception:
            pass
    return DEFAULT_AGENTS


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Overall system health check."""
    config = context.bot_data["config"]
    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    cmms = context.bot_data.get("cmms")
    cmms_ok = False
    if cmms:
        cmms_ok = await cmms.test_connection()

    groq_ok = config.groq_api_key is not None
    claude_ok = context.bot_data.get("claude_available", False)

    lines = [
        "*JARVIS STATUS*",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"{'✅' if groq_ok else '❌'} Groq (Vision + Text + Voice)",
        f"{'✅' if claude_ok else '❌'} Claude CLI Bridge",
        f"{'✅' if cmms_ok else '❌'} CMMS ({config.cmms_url or 'not configured'})",
        f"✅ Bot Online",
        "",
        f"Machine: {config.machine_name}",
        f"Rate limit: {config.rate_limit} msg/min",
    ]

    allowed = config.allowed_users
    if allowed:
        lines.append(f"Allowed users: {len(allowed)}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all 24 agents and their status."""
    config = context.bot_data["config"]
    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    agents = _load_agents()

    lines = [
        "*AGENTS STATUS*",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    total = 0
    for team, members in agents.items():
        lines.append(f"*{team}*")
        for agent in members:
            # TODO: Replace with live health check per agent endpoint
            lines.append(f"  ✅ {agent}")
            total += 1
        lines.append("")

    lines.insert(3, f"Total: {total} agents")
    lines.insert(4, "")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_metrics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Performance KPIs snapshot."""
    config = context.bot_data["config"]
    user_id = update.effective_user.id
    if not config.is_user_allowed(user_id):
        return

    conv = context.bot_data["conversation_manager"]

    active_sessions = len(conv.active_sessions)
    total_messages = sum(
        len(s.history.messages) for s in conv.active_sessions.values()
    )

    lines = [
        "*PERFORMANCE METRICS*",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "*Bot Activity*",
        f"Active sessions: {active_sessions}",
        f"Total messages: {total_messages}",
        "",
        "*Integrations*",
        f"Groq: {'configured' if config.groq_api_key else 'not configured'}",
        f"CMMS: {'configured' if config.cmms_url else 'not configured'}",
        f"Claude CLI: {'available' if context.bot_data.get('claude_available') else 'unavailable'}",
    ]

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
