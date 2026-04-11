#!/usr/bin/env python3
"""
YouTube Uploader — YouTube Data API v3 Wrapper
===============================================
Uploads Shorts with scheduling, thumbnails, and series playlist management.

Quota guard is mandatory: YouTube Data API v3 = 10,000 units/day.
One upload = 1,600 units → max ~6 uploads/day.
Every upload call checks remaining quota first and raises QuotaExceededError
with a reschedule suggestion rather than silently failing.

Secrets required (Doppler: factorylm/prd):
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN
  YOUTUBE_CHANNEL_ID

Usage:
    python tools/youtube_uploader.py upload \\
        --video output/shorts/vfd_e005.mp4 \\
        --title "VFD Fault E005: What It Means & How AI Fixes It" \\
        --series before_it_breaks \\
        --schedule "2026-04-14T09:00:00-04:00" \\
        --thumbnail output/thumbnails/vfd_e005.png

    python tools/youtube_uploader.py quota
    python tools/youtube_uploader.py analytics --days 28
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("youtube-uploader")

# YouTube Data API constants
YOUTUBE_UPLOAD_QUOTA_COST = 1600  # units per upload
YOUTUBE_DAILY_QUOTA = 10_000      # units/day default
YOUTUBE_CATEGORY_SCIENCE_TECH = "28"
YOUTUBE_SHORTS_TAGS = [
    "industrialAI", "PLC", "maintenance", "manufacturing", "Industry40",
    "factoryautomation", "predictivemaintenance", "AllenBradley", "VFD",
    "factoryLM",
]

SERIES_DESCRIPTIONS: dict[str, str] = {
    "before_it_breaks": "AI catches industrial equipment faults before they cause downtime. Real hardware. Real results.",
    "price_shock": "Enterprise predictive maintenance costs $500K. FactoryLM costs $30/device. Same result. 1/16th the price.",
    "inside_machine": "How FactoryLM reads PLC registers and Modbus data to diagnose faults in real time.",
    "live_diagnosis": "Uncut demos: real fault, real Telegram message, real AI diagnosis. No staging.",
    "tech_stories": "The founder's journey — 15 years of 3AM calls and the AI that finally fixes them.",
    "off_the_grid": "FactoryLM works air-gapped, behind factory firewalls, with zero cloud dependency.",
}


class QuotaExceededError(Exception):
    """Raised when YouTube API quota is exhausted."""

    def __init__(self, used: int, daily_limit: int, next_slot: str):
        self.used = used
        self.daily_limit = daily_limit
        self.next_slot = next_slot
        super().__init__(
            f"YouTube quota exhausted: {used}/{daily_limit} units used today. "
            f"Next available upload slot: {next_slot}"
        )


def _build_youtube_client():
    """Build authenticated YouTube Data API v3 client."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        logger.error(
            "Google API client not installed. Run:\n"
            "  pip install google-api-python-client google-auth-oauthlib"
        )
        sys.exit(1)

    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        missing = [k for k, v in {
            "YOUTUBE_CLIENT_ID": client_id,
            "YOUTUBE_CLIENT_SECRET": client_secret,
            "YOUTUBE_REFRESH_TOKEN": refresh_token,
        }.items() if not v]
        raise EnvironmentError(
            f"Missing Doppler secrets: {missing}. "
            "Run with: doppler run -p factorylm -c prd -- python tools/youtube_uploader.py ..."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds)


def check_quota_remaining() -> int:
    """
    Estimate remaining daily quota by checking today's upload count.

    YouTube does not expose quota directly via API. We approximate by
    counting uploads made today from the channel and subtracting their cost.

    Returns estimated remaining units (conservative estimate).
    """
    youtube = _build_youtube_client()
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID", "")
    if not channel_id:
        logger.warning("YOUTUBE_CHANNEL_ID not set — assuming full quota available")
        return YOUTUBE_DAILY_QUOTA

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    try:
        response = youtube.search().list(
            part="id",
            channelId=channel_id,
            publishedAfter=today_start,
            type="video",
            maxResults=50,
        ).execute()

        uploads_today = len(response.get("items", []))
        # search.list costs 100 units; each upload costs 1600
        estimated_used = 100 + (uploads_today * YOUTUBE_UPLOAD_QUOTA_COST)
        remaining = max(0, YOUTUBE_DAILY_QUOTA - estimated_used)
        logger.info(
            "Quota estimate: %d uploads today → ~%d units used → ~%d remaining",
            uploads_today, estimated_used, remaining,
        )
        return remaining
    except Exception as e:
        logger.warning("Could not check quota: %s — assuming %d units available", e, YOUTUBE_DAILY_QUOTA)
        return YOUTUBE_DAILY_QUOTA


def _next_available_slot() -> str:
    """Return the next Mon/Wed/Fri 9AM EST slot after now."""
    est = timezone(timedelta(hours=-4))  # EDT; adjust to -5 for EST winter
    now = datetime.now(est)

    slot_days = {0: "Mon", 2: "Wed", 4: "Fri"}  # weekday numbers
    slot_hour = 9

    # Try the next 7 days
    for delta in range(1, 8):
        candidate = now + timedelta(days=delta)
        if candidate.weekday() in slot_days:
            slot = candidate.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
            return slot.isoformat()

    # Fallback: tomorrow same time
    return (now + timedelta(days=1)).replace(hour=slot_hour, minute=0, second=0, microsecond=0).isoformat()


def _get_or_create_playlist(youtube, series: str) -> str:
    """Get the YouTube playlist ID for a series, creating it if it doesn't exist."""
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID", "")
    title = SERIES_DESCRIPTIONS.get(series, "FactoryLM")
    series_label = series.replace("_", " ").title()
    playlist_title = f"FactoryLM — {series_label}"

    # Search for existing playlist
    response = youtube.playlists().list(
        part="id,snippet",
        channelId=channel_id,
        maxResults=50,
    ).execute()

    for item in response.get("items", []):
        if item["snippet"]["title"] == playlist_title:
            return item["id"]

    # Create new playlist
    body = {
        "snippet": {
            "title": playlist_title,
            "description": SERIES_DESCRIPTIONS.get(series, ""),
        },
        "status": {"privacyStatus": "public"},
    }
    created = youtube.playlists().insert(part="snippet,status", body=body).execute()
    playlist_id = created["id"]
    logger.info("Created playlist '%s': %s", playlist_title, playlist_id)
    return playlist_id


def upload_short(
    video_path: Path | str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    schedule_time: str | None = None,
    thumbnail_path: Path | str | None = None,
    series: str | None = None,
    made_for_kids: bool = False,
) -> dict:
    """
    Upload a Short to YouTube with full metadata.

    Args:
        video_path: Path to the MP4 file
        title: Video title
        description: Video description (auto-generated if empty)
        tags: List of tags (merged with YOUTUBE_SHORTS_TAGS)
        schedule_time: ISO 8601 publish time (e.g. "2026-04-14T09:00:00-04:00")
                      If None, publishes immediately as public.
        thumbnail_path: Path to 1280×720 PNG thumbnail
        series: Series key for playlist assignment
        made_for_kids: YouTube "made for kids" flag

    Returns:
        dict with video_id, video_url, status, scheduled_time

    Raises:
        QuotaExceededError: If daily quota is insufficient
        FileNotFoundError: If video or thumbnail not found
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Quota guard — must be first
    remaining = check_quota_remaining()
    if remaining < YOUTUBE_UPLOAD_QUOTA_COST:
        next_slot = _next_available_slot()
        raise QuotaExceededError(
            used=YOUTUBE_DAILY_QUOTA - remaining,
            daily_limit=YOUTUBE_DAILY_QUOTA,
            next_slot=next_slot,
        )

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        logger.error("google-api-python-client not installed")
        sys.exit(1)

    youtube = _build_youtube_client()

    # Build description
    if not description:
        series_desc = SERIES_DESCRIPTIONS.get(series or "", "")
        description = (
            f"{series_desc}\n\n"
            "FactoryLM — AI that lives inside your PLC.\n"
            "$30/device. Not $500K.\n\n"
            "Free demo: https://factorylm.com\n"
            "Book a call: https://calendly.com/mike-cranesync/30min\n\n"
            + " ".join(f"#{t}" for t in YOUTUBE_SHORTS_TAGS)
        )

    # Merge tags
    all_tags = list(set((tags or []) + YOUTUBE_SHORTS_TAGS))

    # Privacy status and scheduling
    if schedule_time:
        privacy_status = "private"  # YouTube requires private for scheduled
        publish_at = schedule_time
    else:
        privacy_status = "public"
        publish_at = None

    body: dict = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": all_tags,
            "categoryId": YOUTUBE_CATEGORY_SCIENCE_TECH,
        },
        "status": {
            "privacyStatus": privacy_status,
            "madeForKids": made_for_kids,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)

    logger.info("Uploading: %s", video_path.name)
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    # Resumable upload with progress
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            logger.info("Upload progress: %d%%", pct)

    video_id = response["id"]
    video_url = f"https://www.youtube.com/shorts/{video_id}"
    logger.info("Uploaded: %s → %s", video_path.name, video_url)

    # Set thumbnail
    if thumbnail_path:
        thumbnail_path = Path(thumbnail_path)
        if thumbnail_path.exists():
            try:
                from googleapiclient.http import MediaFileUpload as MFU
                thumb_media = MFU(str(thumbnail_path), mimetype="image/png")
                youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
                logger.info("Thumbnail set: %s", thumbnail_path.name)
            except Exception as e:
                logger.warning("Failed to set thumbnail: %s", e)
        else:
            logger.warning("Thumbnail not found: %s", thumbnail_path)

    # Add to series playlist
    if series:
        try:
            playlist_id = _get_or_create_playlist(youtube, series)
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
            logger.info("Added to playlist: %s", series)
        except Exception as e:
            logger.warning("Failed to add to playlist: %s", e)

    return {
        "video_id": video_id,
        "video_url": video_url,
        "status": privacy_status,
        "scheduled_time": publish_at,
        "title": title,
    }


def create_series_playlist(series_name: str) -> str:
    """Create (or retrieve) a YouTube playlist for the given series. Returns playlist ID."""
    youtube = _build_youtube_client()
    return _get_or_create_playlist(youtube, series_name)


def get_channel_analytics(days: int = 28) -> dict:
    """
    Pull channel analytics for the past N days.

    Returns dict with per-video stats: views, avg_view_duration, ctr.
    Uses YouTube Analytics API (separate from Data API — same OAuth creds).
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
    except ImportError:
        logger.error("google-api-python-client not installed")
        return {}

    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID", "")

    if not all([client_id, client_secret, refresh_token, channel_id]):
        logger.error("Missing credentials for analytics — check Doppler factorylm/prd")
        return {}

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )

    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        response = analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,averageViewDuration,averageViewPercentage,annotationClickThroughRate",
            dimensions="video",
            sort="-views",
            maxResults=25,
        ).execute()

        headers = [h["name"] for h in response.get("columnHeaders", [])]
        rows = response.get("rows", [])
        results = []
        for row in rows:
            results.append(dict(zip(headers, row)))

        return {
            "period_days": days,
            "start_date": start_date,
            "end_date": end_date,
            "videos": results,
        }
    except Exception as e:
        logger.error("Analytics query failed: %s", e)
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube uploader for FactoryLM Shorts")
    sub = parser.add_subparsers(dest="command")

    # Upload
    up = sub.add_parser("upload", help="Upload a Short")
    up.add_argument("--video", required=True, help="Path to MP4")
    up.add_argument("--title", required=True, help="Video title")
    up.add_argument("--series", choices=list(SERIES_DESCRIPTIONS), help="Content series")
    up.add_argument("--schedule", help="ISO 8601 publish time (e.g. 2026-04-14T09:00:00-04:00)")
    up.add_argument("--thumbnail", help="Path to 1280×720 PNG thumbnail")
    up.add_argument("--description", default="", help="Video description (auto-generated if empty)")

    # Quota check
    sub.add_parser("quota", help="Check remaining daily quota")

    # Analytics
    an = sub.add_parser("analytics", help="Pull channel analytics")
    an.add_argument("--days", type=int, default=28, help="Lookback window in days")
    an.add_argument("--output", help="Optional output JSON path")

    # Create playlist
    pl = sub.add_parser("create-playlist", help="Create a series playlist")
    pl.add_argument("--series", required=True, choices=list(SERIES_DESCRIPTIONS))

    args = parser.parse_args()

    if args.command == "upload":
        try:
            result = upload_short(
                video_path=args.video,
                title=args.title,
                series=args.series,
                schedule_time=args.schedule,
                thumbnail_path=args.thumbnail,
                description=args.description,
            )
            print(json.dumps(result, indent=2))
        except QuotaExceededError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    elif args.command == "quota":
        remaining = check_quota_remaining()
        max_uploads = remaining // YOUTUBE_UPLOAD_QUOTA_COST
        print(f"Estimated remaining quota: {remaining} units (~{max_uploads} uploads)")

    elif args.command == "analytics":
        data = get_channel_analytics(args.days)
        if args.output:
            Path(args.output).write_text(json.dumps(data, indent=2))
            print(f"Written to {args.output}")
        else:
            print(json.dumps(data, indent=2))

    elif args.command == "create-playlist":
        playlist_id = create_series_playlist(args.series)
        print(f"Playlist ID: {playlist_id}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
