"""
CLI for Factory Opportunities service.

Commands:
- opps refresh         : Fetch from all sources, update database
- opps sync-calendar   : Push opportunities to Google Calendar
- opps track-progress  : Calculate RAG status, send Telegram digest
- opps list-upcoming   : Show upcoming opportunities
- opps add             : Manually add an opportunity
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from .adapters import ALL_ADAPTERS
from .calendar_sync import CalendarSync
from .models import Opportunity, OpportunityType, OpportunityStatus, RAGStatus
from .storage import OpportunitiesStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_refresh(args) -> int:
    """Refresh opportunities from all sources."""
    storage = OpportunitiesStorage(args.db)

    total_new = 0
    total_updated = 0

    for AdapterClass in ALL_ADAPTERS:
        adapter_name = AdapterClass.name
        logger.info(f"Fetching from {adapter_name}...")

        try:
            with AdapterClass() as adapter:
                opportunities = adapter.fetch()

            for opp in opportunities:
                existing = storage.get_by_name(opp.name)
                if existing:
                    # Update existing
                    opp.id = existing.id
                    opp.google_event_ids = existing.google_event_ids
                    opp.progress_percent = existing.progress_percent
                    opp.materials_checklist = existing.materials_checklist or opp.materials_checklist
                    storage.update(opp)
                    total_updated += 1
                else:
                    storage.create(opp)
                    total_new += 1

            logger.info(f"  Found {len(opportunities)} opportunities from {adapter_name}")

        except Exception as e:
            logger.error(f"  Failed to fetch from {adapter_name}: {e}")

    # Update RAG statuses
    storage.update_all_rag_statuses()

    # Mark expired opportunities
    expired = storage.mark_expired()

    logger.info(f"\nRefresh complete:")
    logger.info(f"  New: {total_new}")
    logger.info(f"  Updated: {total_updated}")
    logger.info(f"  Marked expired: {expired}")

    return 0


def cmd_sync_calendar(args) -> int:
    """Sync opportunities to Google Calendar."""
    storage = OpportunitiesStorage(args.db)

    try:
        calendar = CalendarSync()
    except Exception as e:
        logger.error(f"Failed to initialize Google Calendar: {e}")
        return 1

    # Get opportunities to sync
    if args.all:
        opportunities = storage.list_all()
    else:
        opportunities = storage.list_upcoming(days=90)

    logger.info(f"Syncing {len(opportunities)} opportunities to Google Calendar...")

    stats = calendar.sync_all(opportunities, storage)

    logger.info(f"\nSync complete:")
    logger.info(f"  Events created: {stats['created']}")
    logger.info(f"  Skipped (already synced): {stats['skipped']}")
    logger.info(f"  Errors: {stats['errors']}")

    return 0 if stats['errors'] == 0 else 1


def cmd_track_progress(args) -> int:
    """Track progress and send Telegram digest."""
    storage = OpportunitiesStorage(args.db)

    # Update all RAG statuses
    updated = storage.update_all_rag_statuses()
    logger.info(f"Updated RAG status for {updated} opportunities")

    # Get active opportunities grouped by RAG status
    active = storage.list_active()

    red = [o for o in active if o.rag_status == RAGStatus.RED]
    yellow = [o for o in active if o.rag_status == RAGStatus.YELLOW]
    green = [o for o in active if o.rag_status == RAGStatus.GREEN]
    grey = [o for o in active if o.rag_status == RAGStatus.GREY]

    # Build digest
    lines = [
        f"OPPORTUNITIES DIGEST - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 50,
        "",
    ]

    if red:
        lines.append("RED - BEHIND (action needed!)")
        lines.append("-" * 30)
        for opp in red:
            days = opp.days_until_deadline()
            days_str = f"{days} days" if days is not None else "no deadline"
            lines.append(f"  {opp.name}")
            lines.append(f"    Progress: {opp.progress_percent}% | {days_str}")
            lines.append(f"    URL: {opp.url}")
        lines.append("")

    if yellow:
        lines.append("YELLOW - AT RISK")
        lines.append("-" * 30)
        for opp in yellow:
            days = opp.days_until_deadline()
            days_str = f"{days} days" if days is not None else "no deadline"
            lines.append(f"  {opp.name}")
            lines.append(f"    Progress: {opp.progress_percent}% | {days_str}")
        lines.append("")

    if green:
        lines.append("GREEN - ON TRACK")
        lines.append("-" * 30)
        for opp in green:
            days = opp.days_until_deadline()
            days_str = f"{days} days" if days is not None else "no deadline"
            lines.append(f"  {opp.name} ({opp.progress_percent}%, {days_str})")
        lines.append("")

    if grey:
        lines.append(f"GREY - NO DEADLINE ({len(grey)} items)")
        lines.append("")

    # Summary
    lines.append("SUMMARY")
    lines.append("-" * 30)
    lines.append(f"  RED: {len(red)} | YELLOW: {len(yellow)} | GREEN: {len(green)} | GREY: {len(grey)}")
    lines.append(f"  Total active: {len(active)}")

    digest = "\n".join(lines)

    # Print to console
    print(digest)

    # Send to Telegram via Jarvis if configured
    if not args.no_telegram:
        send_telegram_digest(digest)

    return 0


def send_telegram_digest(digest: str) -> None:
    """Send digest to Telegram via Jarvis."""
    try:
        import httpx

        jarvis_url = os.environ.get("JARVIS_URL", "http://100.68.120.99:8765")

        # Try to send via Jarvis notification endpoint
        response = httpx.post(
            f"{jarvis_url}/notify",
            json={
                "message": f"```\n{digest}\n```",
                "channel": "opportunities",
            },
            timeout=30,
        )
        if response.status_code == 200:
            logger.info("Digest sent to Telegram via Jarvis")
        else:
            logger.warning(f"Jarvis returned {response.status_code}")

    except Exception as e:
        logger.warning(f"Could not send to Telegram: {e}")
        logger.info("To enable Telegram notifications, set JARVIS_URL")


def cmd_list_upcoming(args) -> int:
    """List upcoming opportunities."""
    storage = OpportunitiesStorage(args.db)

    opportunities = storage.list_upcoming(days=args.days)

    if not opportunities:
        print(f"No opportunities with deadlines in the next {args.days} days.")
        return 0

    print(f"\nUpcoming Opportunities (next {args.days} days):")
    print("=" * 70)

    for opp in opportunities:
        deadline = opp.get_primary_deadline()
        days = opp.days_until_deadline()

        rag_emoji = {
            RAGStatus.GREEN: "[G]",
            RAGStatus.YELLOW: "[Y]",
            RAGStatus.RED: "[R]",
            RAGStatus.GREY: "[-]",
        }.get(opp.rag_status, "[-]")

        deadline_str = deadline.strftime("%Y-%m-%d") if deadline else "N/A"
        days_str = f"({days}d)" if days is not None else ""

        print(f"\n{rag_emoji} {opp.name}")
        print(f"    Type: {opp.type.value if hasattr(opp.type, 'value') else opp.type}")
        print(f"    Deadline: {deadline_str} {days_str}")
        print(f"    Progress: {opp.progress_percent}%")
        print(f"    URL: {opp.url}")

    print("\n" + "=" * 70)
    print(f"Total: {len(opportunities)} opportunities")

    return 0


def cmd_add(args) -> int:
    """Manually add an opportunity."""
    storage = OpportunitiesStorage(args.db)

    opp = Opportunity(
        name=args.name,
        organizer=args.organizer or "",
        type=OpportunityType(args.type),
        url=args.url or "",
        source="manual",
        status=OpportunityStatus.DISCOVERED,
    )

    if args.deadline:
        try:
            deadline = datetime.strptime(args.deadline, "%Y-%m-%d")
            if args.type in ("conference", "workshop"):
                opp.cfp_deadline = deadline
            else:
                opp.application_deadline = deadline
        except ValueError:
            logger.error(f"Invalid date format: {args.deadline}. Use YYYY-MM-DD.")
            return 1

    if args.event_date:
        try:
            opp.event_start = datetime.strptime(args.event_date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {args.event_date}. Use YYYY-MM-DD.")
            return 1

    storage.create(opp)
    logger.info(f"Created opportunity: {opp.name} (ID: {opp.id})")

    return 0


def cmd_update_progress(args) -> int:
    """Update progress for an opportunity."""
    storage = OpportunitiesStorage(args.db)

    opp = storage.get_by_name(args.name) or storage.get(args.name)
    if not opp:
        logger.error(f"Opportunity not found: {args.name}")
        return 1

    if args.progress is not None:
        opp.progress_percent = max(0, min(100, args.progress))

    if args.material:
        for m in args.material:
            key, value = m.split("=")
            opp.materials_checklist[key] = value.lower() in ("true", "1", "yes")

    opp.update_rag_status()
    storage.update(opp)

    logger.info(f"Updated {opp.name}: {opp.progress_percent}% ({opp.rag_status.value})")

    return 0


def cmd_stats(args) -> int:
    """Show statistics."""
    storage = OpportunitiesStorage(args.db)

    stats = storage.count()

    print("\nOpportunities Statistics:")
    print("=" * 40)
    print(f"Total: {stats['total']}")
    print("\nBy Status:")
    for status, count in stats['by_status'].items():
        if count > 0:
            print(f"  {status}: {count}")
    print("\nBy RAG Status:")
    for rag, count in stats['by_rag'].items():
        emoji = {"green": "[G]", "yellow": "[Y]", "red": "[R]", "grey": "[-]"}.get(rag, "")
        if count > 0:
            print(f"  {emoji} {rag}: {count}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="opps",
        description="Factory Opportunities CLI - Track AI/ML/Robotics opportunities"
    )
    parser.add_argument(
        "--db",
        help="Path to SQLite database",
        default=os.environ.get(
            "OPPORTUNITIES_DB_PATH",
            os.path.expanduser("~/.factorylm/opportunities.db")
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # refresh
    refresh_parser = subparsers.add_parser("refresh", help="Fetch from all sources")

    # sync-calendar
    sync_parser = subparsers.add_parser("sync-calendar", help="Sync to Google Calendar")
    sync_parser.add_argument("--all", action="store_true", help="Sync all, not just upcoming")

    # track-progress
    track_parser = subparsers.add_parser("track-progress", help="Track progress and send digest")
    track_parser.add_argument("--no-telegram", action="store_true", help="Don't send to Telegram")

    # list-upcoming
    list_parser = subparsers.add_parser("list-upcoming", help="List upcoming opportunities")
    list_parser.add_argument("--days", type=int, default=30, help="Days to look ahead (default: 30)")

    # add
    add_parser = subparsers.add_parser("add", help="Add an opportunity manually")
    add_parser.add_argument("--name", required=True, help="Opportunity name")
    add_parser.add_argument("--type", required=True, choices=[t.value for t in OpportunityType])
    add_parser.add_argument("--url", help="URL")
    add_parser.add_argument("--organizer", help="Organizer name")
    add_parser.add_argument("--deadline", help="Deadline date (YYYY-MM-DD)")
    add_parser.add_argument("--event-date", help="Event date (YYYY-MM-DD)")

    # update-progress
    update_parser = subparsers.add_parser("update-progress", help="Update progress for an opportunity")
    update_parser.add_argument("name", help="Opportunity name or ID")
    update_parser.add_argument("--progress", type=int, help="Progress percentage (0-100)")
    update_parser.add_argument("--material", action="append", help="Material status: key=true/false")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show statistics")

    args = parser.parse_args()

    commands = {
        "refresh": cmd_refresh,
        "sync-calendar": cmd_sync_calendar,
        "track-progress": cmd_track_progress,
        "list-upcoming": cmd_list_upcoming,
        "add": cmd_add,
        "update-progress": cmd_update_progress,
        "stats": cmd_stats,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
