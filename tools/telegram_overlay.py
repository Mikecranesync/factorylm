#!/usr/bin/env python3
"""
Telegram Overlay — Stamp conversation text onto video frames
=============================================================
Reads kb/telegram/conversations.jsonl, matches messages to video sessions
by timestamp, and overlays conversation snippets on the nearest frame.

Usage:
    python tools/telegram_overlay.py --all
    python tools/telegram_overlay.py --session "2026-02-04 11-48-31"
    python tools/telegram_overlay.py --dry-run
    python tools/telegram_overlay.py --all --rebuild-montage
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    logger.error("Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
CONVERSATIONS_PATH = REPO_ROOT / "kb" / "telegram" / "conversations.jsonl"
VIDEO_PIPELINE_DIR = REPO_ROOT / "output" / "video_pipeline"

# Timezone: UTC-05:00 (EST)
EST = timezone(timedelta(hours=-5))

# Health-update patterns to filter out
HEALTH_FILTERS = [
    "VPS Heartbeat",
    "VPS Jarvis STILL DOWN",
]


# ---------------------------------------------------------------------------
# Conversation loading
# ---------------------------------------------------------------------------

def load_conversations(path: Path) -> list[dict]:
    """Load conversations.jsonl, filtering out health updates."""
    entries = []
    skipped = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            resp = entry.get("assistant_response", "")
            if any(pattern in resp for pattern in HEALTH_FILTERS):
                skipped += 1
                continue
            entries.append(entry)
    logger.info("Loaded %d conversations (%d health updates filtered)", len(entries), skipped)
    return entries


def parse_timestamp(ts_str: str) -> datetime:
    """Parse '01.02.2026 00:00:49 UTC-05:00' into a timezone-aware datetime."""
    # Format: DD.MM.YYYY HH:MM:SS UTC-05:00
    # Strip the 'UTC' prefix from timezone to get standard offset
    m = re.match(
        r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2}):(\d{2})\s+UTC([+-]\d{2}:\d{2})",
        ts_str,
    )
    if not m:
        raise ValueError(f"Cannot parse timestamp: {ts_str}")
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour, minute, second = int(m.group(4)), int(m.group(5)), int(m.group(6))
    offset_str = m.group(7)
    offset_hours, offset_mins = int(offset_str[:3]), int(offset_str[0] + offset_str[4:])
    tz = timezone(timedelta(hours=offset_hours, minutes=offset_mins))
    return datetime(year, month, day, hour, minute, second, tzinfo=tz)


# ---------------------------------------------------------------------------
# Session matching
# ---------------------------------------------------------------------------

def parse_session_start(session_name: str) -> datetime:
    """Parse session folder name 'YYYY-MM-DD HH-MM-SS' as EST datetime."""
    dt = datetime.strptime(session_name, "%Y-%m-%d %H-%M-%S")
    return dt.replace(tzinfo=EST)


def get_session_duration(session_dir: Path) -> float:
    """Get session duration from manifest.json, or estimate from frame count."""
    manifest = session_dir / "manifest.json"
    if manifest.exists():
        with open(manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
        duration = data.get("source", {}).get("duration_seconds")
        if duration:
            return float(duration)
    # Fallback: count frames * 2 seconds each (0.5 fps)
    frames_dir = session_dir / "frames"
    if frames_dir.exists():
        frame_count = len(list(frames_dir.glob("frame_*.png")))
        return frame_count * 2.0
    return 0.0


def match_messages_to_sessions(
    conversations: list[dict],
    sessions: list[str],
) -> dict[str, list[dict]]:
    """Match each conversation to its video session by timestamp overlap.

    Returns {session_name: [list of matched messages with frame info]}.
    """
    # Build session windows
    session_windows = []
    for name in sessions:
        session_dir = VIDEO_PIPELINE_DIR / name
        start = parse_session_start(name)
        duration = get_session_duration(session_dir)
        end = start + timedelta(seconds=duration)
        session_windows.append((name, start, end, duration))

    matches: dict[str, list[dict]] = {}
    for entry in conversations:
        ts_str = entry.get("timestamp", "")
        try:
            msg_time = parse_timestamp(ts_str)
        except ValueError:
            continue

        for name, start, end, duration in session_windows:
            if start <= msg_time <= end:
                seconds_in = (msg_time - start).total_seconds()
                frame_num = int(seconds_in // 2) + 1
                # Clamp to valid range
                frames_dir = VIDEO_PIPELINE_DIR / name / "frames"
                max_frame = len(list(frames_dir.glob("frame_*.png")))
                frame_num = min(frame_num, max_frame)
                frame_num = max(frame_num, 1)

                match_info = {
                    "timestamp": ts_str,
                    "msg_time": msg_time.isoformat(),
                    "seconds_into_session": round(seconds_in, 1),
                    "frame_number": frame_num,
                    "frame_file": f"frame_{frame_num:04d}.png",
                    "user_name": entry.get("metadata", {}).get("user_name", "Mike"),
                    "user_message": entry.get("user_message", ""),
                    "assistant_response": entry.get("assistant_response", ""),
                }
                matches.setdefault(name, []).append(match_info)
                break  # Each message matches at most one session

    return matches


# ---------------------------------------------------------------------------
# Overlay rendering
# ---------------------------------------------------------------------------

def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a monospace font, falling back to default."""
    candidates = [
        "C:/Windows/Fonts/consola.ttf",   # Consolas (Windows)
        "C:/Windows/Fonts/cour.ttf",      # Courier New
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def truncate(text: str, max_chars: int = 80) -> str:
    """Truncate text to max_chars, adding ellipsis if needed."""
    # Collapse whitespace and newlines
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "\u2026"


def overlay_frame(
    src_path: Path,
    dst_path: Path,
    match: dict,
) -> None:
    """Draw conversation overlay on a frame and save to dst_path."""
    img = Image.open(src_path).convert("RGBA")
    width, height = img.size

    # Build overlay text lines
    user_name = match.get("user_name", "Mike")
    user_msg = truncate(match["user_message"], 90)
    assistant_msg = truncate(match["assistant_response"], 90)
    time_label = match["timestamp"].split(" UTC")[0]  # Just the date+time part

    lines = [
        f"\u23F0 {time_label}",
        f"\U0001F4AC {user_name}: {user_msg}",
        f"\U0001F916 Jarvis: {assistant_msg}",
    ]

    # Font sizing: scale to image width
    font_size = max(14, width // 60)
    font = _get_font(font_size)
    line_height = font_size + 6
    banner_height = line_height * len(lines) + 20
    banner_y = height - banner_height

    # Create semi-transparent banner
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(
        [(0, banner_y), (width, height)],
        fill=(0, 0, 0, 180),
    )

    # Draw text lines
    y = banner_y + 8
    for line in lines:
        draw.text((12, y), line, fill=(255, 255, 255, 240), font=font)
        y += line_height

    # Composite and save as RGB PNG
    result = Image.alpha_composite(img, overlay).convert("RGB")
    result.save(dst_path, "PNG")


# ---------------------------------------------------------------------------
# Montage rebuild
# ---------------------------------------------------------------------------

def _run_ffmpeg(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run an ffmpeg command, capturing output."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def rebuild_montage(session_dir: Path, session_name: str) -> None:
    """Rebuild montage.mp4 using overlaid frames (falling back to originals)."""
    overlay_dir = session_dir / "frames_overlay"
    frames_dir = session_dir / "frames"
    output_path = session_dir / "montage_overlay.mp4"

    if not overlay_dir.exists():
        logger.warning("No frames_overlay dir for %s, skipping montage", session_name)
        return

    # Build frame list: use overlay if available, else original
    frame_files = sorted(frames_dir.glob("frame_*.png"))
    if not frame_files:
        logger.warning("No frames found for %s", session_name)
        return

    # Create a temporary concat file listing all frames in order
    list_path = session_dir / "_overlay_framelist.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for frame_file in frame_files:
            overlay_file = overlay_dir / frame_file.name
            if overlay_file.exists():
                f.write(f"file '{overlay_file}'\n")
            else:
                f.write(f"file '{frame_file}'\n")
            f.write("duration 2\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_path),
        "-vf", "fps=0.5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast",
        str(output_path),
    ]

    logger.info("Building montage_overlay.mp4 for %s ...", session_name)
    result = _run_ffmpeg(cmd, timeout=600)
    if result.returncode == 0:
        logger.info("Montage saved: %s", output_path)
    else:
        logger.error("ffmpeg failed for %s: %s", session_name, result.stderr[-500:] if result.stderr else "")

    # Cleanup temp file
    list_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_session(
    session_name: str,
    session_matches: list[dict],
    dry_run: bool = False,
    do_montage: bool = False,
) -> None:
    """Process a single session: overlay messages onto frames."""
    session_dir = VIDEO_PIPELINE_DIR / session_name
    frames_dir = session_dir / "frames"
    overlay_dir = session_dir / "frames_overlay"

    logger.info(
        "Session %s: %d matching message(s)", session_name, len(session_matches)
    )

    if dry_run:
        for m in session_matches:
            logger.info(
                "  Frame %s @ %.1fs — %s: %s",
                m["frame_file"],
                m["seconds_into_session"],
                m["user_name"],
                truncate(m["user_message"], 60),
            )
        return

    # Create overlay dir
    overlay_dir.mkdir(exist_ok=True)

    # Save match manifest
    matches_path = session_dir / "telegram_matches.json"
    with open(matches_path, "w", encoding="utf-8") as f:
        json.dump(session_matches, f, indent=2, ensure_ascii=False)
    logger.info("  Wrote %s", matches_path.name)

    # Overlay each matched frame
    for m in session_matches:
        src = frames_dir / m["frame_file"]
        dst = overlay_dir / m["frame_file"]
        if not src.exists():
            logger.warning("  Frame not found: %s", src)
            continue
        overlay_frame(src, dst, m)
        logger.info(
            "  Overlaid %s (%.1fs in) — %s",
            m["frame_file"],
            m["seconds_into_session"],
            truncate(m["user_message"], 40),
        )

    logger.info("  %d overlaid frames in %s", len(session_matches), overlay_dir)

    if do_montage:
        rebuild_montage(session_dir, session_name)


def main():
    parser = argparse.ArgumentParser(description="Overlay Telegram conversations on video frames")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Process all sessions")
    group.add_argument("--session", type=str, help="Process a single session by name")
    parser.add_argument("--dry-run", action="store_true", help="Show matches without writing files")
    parser.add_argument("--rebuild-montage", action="store_true", help="Rebuild montage.mp4 with overlaid frames")
    args = parser.parse_args()

    if not CONVERSATIONS_PATH.exists():
        logger.error("Conversations file not found: %s", CONVERSATIONS_PATH)
        sys.exit(1)

    # Load conversations
    conversations = load_conversations(CONVERSATIONS_PATH)

    # Discover sessions
    if args.all:
        sessions = sorted(
            d.name
            for d in VIDEO_PIPELINE_DIR.iterdir()
            if d.is_dir() and (d / "frames").is_dir()
        )
    else:
        session_dir = VIDEO_PIPELINE_DIR / args.session
        if not session_dir.is_dir():
            logger.error("Session not found: %s", session_dir)
            sys.exit(1)
        sessions = [args.session]

    logger.info("Processing %d session(s)...", len(sessions))

    # Match messages to sessions
    all_matches = match_messages_to_sessions(conversations, sessions)

    total_matched = sum(len(v) for v in all_matches.values())
    sessions_with_matches = len(all_matches)
    logger.info(
        "Found %d message(s) across %d session(s)",
        total_matched,
        sessions_with_matches,
    )

    if total_matched == 0:
        logger.info("No matching messages found. Nothing to do.")
        return

    # Process each session that has matches
    for session_name in sessions:
        if session_name not in all_matches:
            continue
        process_session(
            session_name,
            all_matches[session_name],
            dry_run=args.dry_run,
            do_montage=args.rebuild_montage,
        )

    logger.info("Done. %d frames overlaid across %d sessions.", total_matched, sessions_with_matches)


if __name__ == "__main__":
    main()
