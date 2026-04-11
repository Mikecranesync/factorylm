#!/usr/bin/env python3
"""
Analytics Reporter — YouTube Performance + Self-Improving Calendar
==================================================================
Pulls weekly YouTube Analytics, ranks series by completion rate,
and generates the next week's content calendar weighted toward
what's actually working.

Run every Sunday midnight via Cowork scheduled task on ALPHA.
Posts report to Telegram #content-analytics.

Usage:
    python tools/analytics_reporter.py report --days 7
    python tools/analytics_reporter.py next-calendar --days 7 --output output/next_week.json
    python tools/analytics_reporter.py full-run   # report + calendar + Telegram post

Secrets required (Doppler: factorylm/prd):
  YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, YOUTUBE_CHANNEL_ID
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (for #content-analytics channel)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("analytics-reporter")

# Series keys — must match thumbnail_generator.py and youtube_uploader.py
SERIES_KEYS = [
    "before_it_breaks",
    "price_shock",
    "inside_machine",
    "live_diagnosis",
    "tech_stories",
    "off_the_grid",
]

# Topic backlog per series — pick next uncovered topic
TOPIC_BACKLOG: dict[str, list[dict]] = {
    "before_it_breaks": [
        {"title": "VFD Fault E005: What It Means & How AI Fixes It", "hook": "E005 alarm audio"},
        {"title": "Motor Overheating? AI Spots It 6 Hours Early", "hook": "Thermal reading climbing"},
        {"title": "How We Stopped a $40K Downtime Event With $30", "hook": "Dollar bill visual"},
        {"title": "Bearing Fault: The Register Doesn't Lie", "hook": "Vibration value spiking"},
        {"title": "E-Stop Nuisance Trip Root Cause", "hook": "E-stop activation sound"},
        {"title": "PLC Fault Code 101: What It Actually Means", "hook": "Fault code on screen"},
        {"title": "Lubrication Interval AI: Over-Greasing Kills Bearings", "hook": "Bearing cutaway"},
    ],
    "price_shock": [
        {"title": "They Quoted $500K. We Charge $30.", "hook": "Competitor price screenshot"},
        {"title": "Augury Needs 6 Months to Deploy. We Need 6 Minutes.", "hook": "Timer visual"},
        {"title": "Fiix CMMS License vs $30/Device", "hook": "License cost graphic"},
        {"title": "Hiring a Second Tech: $60K/yr vs $600/mo", "hook": "Salary vs subscription"},
        {"title": "$260K/hr Downtime vs $30/Device Insurance", "hook": "Dollar counter"},
    ],
    "inside_machine": [
        {"title": "Your PLC Already Knows the Answer", "hook": "Ladder rung closeup"},
        {"title": "25,000 Maintenance Answers. In Your Factory. Offline.", "hook": "KB counter"},
        {"title": "What Modbus Registers Actually Tell You", "hook": "Register values scrolling"},
        {"title": "How Edge Inference Works (No GPU Required)", "hook": "Edge board closeup"},
        {"title": "Predictive vs Preventive: The Real Difference", "hook": "Failure curve graphic"},
    ],
    "live_diagnosis": [
        {"title": "Live: AI Diagnoses Conveyor Jam in 1.8 Seconds", "hook": "Uncut screen recording"},
        {"title": "Technician Sends Photo. AI Sends Fix. (Real Telegram)", "hook": "Notification sound"},
        {"title": "Multi-Fault: Two Alarms. AI Prioritizes.", "hook": "Two alarm sounds"},
        {"title": "Night Shift: AI Handles Fault at 2AM With No Tech", "hook": "Dark factory floor"},
        {"title": "MIRA Reads a Nameplate. Gets the Part Number.", "hook": "Photo flash"},
    ],
    "tech_stories": [
        {"title": "The 3AM Call That Made Me Build This", "hook": "Phone ringing at 3AM"},
        {"title": "15 Years of 3AM Calls. Then I Built the Fix.", "hook": "Face-cam tired engineer"},
        {"title": "Why I Quit to Build FactoryLM", "hook": "Face-cam direct address"},
        {"title": "When the PLC Talked Back", "hook": "PLC screen lighting up"},
        {"title": "Building AI Alone for 18 Months", "hook": "Lone developer at desk"},
    ],
    "off_the_grid": [
        {"title": "AI Diagnosis With Zero Internet", "hook": "Ethernet cable unplugged"},
        {"title": "Factory Firewall Compliance Walkthrough", "hook": "Network diagram"},
        {"title": "Data Never Leaves the Floor", "hook": "Server rack closeup"},
        {"title": "Works During an Internet Outage: 3-Day Test", "hook": "Modem unplugged"},
        {"title": "OSHA Data Sovereignty: What It Actually Requires", "hook": "Compliance checklist"},
    ],
}


def _next_schedule_slots(count: int = 3) -> list[str]:
    """Return the next N Mon/Wed/Fri 9AM EST slots from today."""
    from datetime import timezone
    est_offset = timedelta(hours=-4)  # EDT; -5 for EST winter
    now = datetime.now() + est_offset  # approximate EST

    slots = []
    candidate = now.replace(hour=9, minute=0, second=0, microsecond=0)
    candidate += timedelta(days=1)  # start from tomorrow

    while len(slots) < count:
        if candidate.weekday() in (0, 2, 4):  # Mon, Wed, Fri
            slots.append(
                candidate.strftime("%Y-%m-%dT09:00:00-04:00")
            )
        candidate += timedelta(days=1)

    return slots


def generate_next_week_calendar(
    analytics_report: dict,
    series_weights: dict | None = None,
    covered_topics: list[str] | None = None,
) -> list[dict]:
    """
    Generate next week's Mon/Wed/Fri content schedule.

    Algorithm:
    1. Rank all series by avg_view_percentage (completion rate) from analytics
    2. Top 2 series get 2 slots next week; remaining 1 slot goes to lowest-ranked series
       (ensures all series stay active, not just optimizing top performers)
    3. Within each series, pick the next uncovered topic from TOPIC_BACKLOG
    4. Return [{day, series, title, hook, source, schedule_time}, ...]

    Args:
        analytics_report: Output of youtube_uploader.get_channel_analytics()
        series_weights: Optional override weights per series (0.0–1.0)
        covered_topics: List of already-published video titles to skip

    Returns:
        List of 3 calendar entries (Mon, Wed, Fri)
    """
    covered_topics = covered_topics or []
    slots = _next_schedule_slots(3)
    days = ["Monday", "Wednesday", "Friday"]

    # Build series rankings from analytics
    series_performance: dict[str, float] = {s: 0.5 for s in SERIES_KEYS}  # default 50%

    if analytics_report.get("videos"):
        # Map video titles back to series (best effort — titles contain series keywords)
        for video in analytics_report["videos"]:
            title = video.get("video", "").lower()
            completion = float(video.get("averageViewPercentage", 50)) / 100
            for series in SERIES_KEYS:
                label_words = series.replace("_", " ").split()
                if any(w in title for w in label_words):
                    # Weighted average (new data weighs more)
                    series_performance[series] = (series_performance[series] + completion) / 2

    # Apply manual overrides
    if series_weights:
        for series, weight in series_weights.items():
            if series in series_performance:
                series_performance[series] = weight

    # Rank series by completion rate
    ranked = sorted(series_performance.items(), key=lambda x: x[1], reverse=True)
    logger.info("Series ranking (completion rate):")
    for series, rate in ranked:
        logger.info("  %s: %.1f%%", series, rate * 100)

    # Slot allocation: top 2 get 2 slots, bottom 1 gets 1 slot
    # (3 videos total for Mon/Wed/Fri)
    selected_series = [ranked[0][0], ranked[1][0], ranked[-1][0]]

    calendar = []
    for i, (day, slot_time, series) in enumerate(zip(days, slots, selected_series)):
        # Find next uncovered topic for this series
        topic = None
        for candidate in TOPIC_BACKLOG.get(series, []):
            if candidate["title"] not in covered_topics:
                topic = candidate
                break

        if not topic:
            # All topics covered — cycle back to first
            backlog = TOPIC_BACKLOG.get(series, [])
            topic = backlog[0] if backlog else {"title": f"FactoryLM {series}", "hook": ""}

        calendar.append({
            "day": day,
            "series": series,
            "title": topic["title"],
            "hook": topic["hook"],
            "schedule_time": slot_time,
            "completion_rate": f"{series_performance[series]:.1%}",
        })
        logger.info("  %s → %s: %s", day, series, topic["title"])

    return calendar


def generate_report(analytics_data: dict) -> str:
    """
    Generate a human-readable markdown report from analytics data.
    Suitable for posting to Telegram #content-analytics.
    """
    if not analytics_data:
        return "No analytics data available."

    lines = [
        f"## FactoryLM Content Analytics — Past {analytics_data.get('period_days', 7)} Days",
        f"**Period:** {analytics_data.get('start_date')} → {analytics_data.get('end_date')}",
        "",
        "### Top Videos by Views",
    ]

    videos = analytics_data.get("videos", [])
    if not videos:
        lines.append("No video data found.")
    else:
        for i, v in enumerate(videos[:10], 1):
            views = int(v.get("views", 0))
            avg_pct = float(v.get("averageViewPercentage", 0))
            avg_dur = int(v.get("averageViewDuration", 0))
            video_id = v.get("video", "")
            lines.append(
                f"{i}. `{video_id}` — "
                f"**{views:,} views** | "
                f"{avg_pct:.1f}% completion | "
                f"{avg_dur}s avg watch"
            )

    if videos:
        total_views = sum(int(v.get("views", 0)) for v in videos)
        avg_completion = sum(float(v.get("averageViewPercentage", 0)) for v in videos) / len(videos)
        lines += [
            "",
            f"**Total views:** {total_views:,}",
            f"**Avg completion:** {avg_completion:.1f}%",
        ]

    return "\n".join(lines)


def post_to_telegram(message: str) -> bool:
    """Post a message to Telegram #content-analytics channel."""
    import urllib.request
    import urllib.parse

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping Telegram post")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                logger.info("Posted to Telegram")
                return True
            logger.warning("Telegram API error: %s", result)
            return False
    except Exception as e:
        logger.error("Telegram post failed: %s", e)
        return False


def run_weekly(output_dir: Path | None = None) -> None:
    """
    Full weekly run: pull analytics → generate report → generate next calendar → post to Telegram.
    Called by ALPHA Cowork task every Sunday midnight.
    """
    # Import here to avoid circular deps at module level
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        from youtube_uploader import get_channel_analytics
    except ImportError:
        logger.error("youtube_uploader.py not found in tools/ directory")
        return

    logger.info("=== Weekly Analytics Run ===")

    analytics = get_channel_analytics(days=7)
    report_md = generate_report(analytics)
    calendar = generate_next_week_calendar(analytics)

    print("\n" + report_md)
    print("\n### Next Week Calendar")
    for entry in calendar:
        print(f"  {entry['day']:10s} [{entry['series']}] {entry['title']}")

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        (output_dir / f"analytics_{date_str}.json").write_text(
            json.dumps(analytics, indent=2)
        )
        (output_dir / f"calendar_{date_str}.json").write_text(
            json.dumps(calendar, indent=2)
        )
        (output_dir / f"report_{date_str}.md").write_text(report_md)
        logger.info("Reports written to %s", output_dir)

    # Post to Telegram
    calendar_lines = "\n".join(
        f"  {e['day']}: [{e['series']}] {e['title']}"
        for e in calendar
    )
    telegram_msg = (
        report_md + "\n\n"
        "### Next Week Schedule\n"
        + calendar_lines
    )
    post_to_telegram(telegram_msg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube analytics reporter + self-improving content calendar"
    )
    sub = parser.add_subparsers(dest="command")

    # Full weekly run
    full = sub.add_parser("full-run", help="Pull analytics + generate calendar + post to Telegram")
    full.add_argument("--output-dir", help="Directory to write JSON/MD reports")

    # Report only
    rep = sub.add_parser("report", help="Pull and display analytics report")
    rep.add_argument("--days", type=int, default=7, help="Lookback days")
    rep.add_argument("--output", help="Optional output JSON path")

    # Calendar only
    cal = sub.add_parser("next-calendar", help="Generate next week's content calendar")
    cal.add_argument("--days", type=int, default=7, help="Analytics lookback for ranking")
    cal.add_argument("--output", help="Optional output JSON path")
    cal.add_argument("--covered", help="JSON file listing already-published titles")

    args = parser.parse_args()

    if args.command == "full-run":
        run_weekly(Path(args.output_dir) if args.output_dir else None)

    elif args.command == "report":
        sys.path.insert(0, str(Path(__file__).parent))
        from youtube_uploader import get_channel_analytics
        data = get_channel_analytics(args.days)
        report = generate_report(data)
        print(report)
        if args.output:
            Path(args.output).write_text(json.dumps(data, indent=2))
            logger.info("Written to %s", args.output)

    elif args.command == "next-calendar":
        sys.path.insert(0, str(Path(__file__).parent))
        from youtube_uploader import get_channel_analytics
        analytics = get_channel_analytics(args.days)
        covered = []
        if args.covered:
            covered = json.loads(Path(args.covered).read_text())
        calendar = generate_next_week_calendar(analytics, covered_topics=covered)
        print(json.dumps(calendar, indent=2))
        if args.output:
            Path(args.output).write_text(json.dumps(calendar, indent=2))
            logger.info("Written to %s", args.output)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
