#!/usr/bin/env python3
"""
Video-to-Frames Pipeline Tool
==============================
Extract frames and scene-based clips from any video file (or YouTube URL),
producing a manifest.json for downstream agent consumption.

Usage:
    python tools/video_pipeline.py video.mp4
    python tools/video_pipeline.py video.mp4 --frames-only --fps 1
    python tools/video_pipeline.py video.mp4 --clips-only --scene-threshold 0.4
    python tools/video_pipeline.py "https://youtube.com/watch?v=..." --output output/yt
"""

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding (from kb_query.py)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Null device varies by platform
_NULL_DEV = "NUL" if sys.platform == "win32" else "/dev/null"


# ---------------------------------------------------------------------------
# Internal helpers (mirrors ingester.py subprocess pattern)
# ---------------------------------------------------------------------------

def _run_ffmpeg(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Run an ffmpeg command, capturing output."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _run_ffprobe(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run an ffprobe command, capturing output."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

def check_ffmpeg() -> None:
    """Verify ffmpeg is available on PATH. Raises RuntimeError if missing."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, timeout=10,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install from https://ffmpeg.org/download.html"
        )


def check_yt_dlp() -> bool:
    """Check if yt-dlp is available. Returns bool, does not raise."""
    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds via ffprobe (quality_validator.py pattern)."""
    try:
        result = _run_ffprobe([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ])
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        return 0.0


def download_video(url: str, output_dir: str) -> str:
    """Download a YouTube video via yt-dlp. Returns path to downloaded file."""
    if not check_yt_dlp():
        raise RuntimeError(
            "yt-dlp not found. Install with: pip install yt-dlp"
        )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Use sys.executable -m yt_dlp (from kb_query.py pattern)
    output_template = str(out_dir / "%(title)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--print", "after_move:filepath",
        "--no-playlist",
        url,
    ]

    logger.info("Downloading: %s", url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()[:300]}")

    # Last non-empty line of stdout is the final filepath
    downloaded = result.stdout.strip().splitlines()[-1]
    logger.info("Downloaded: %s", downloaded)
    return downloaded


def extract_frames(
    video_path: str,
    fps: float = 2,
    output_dir: str | None = None,
) -> dict:
    """
    Extract frames as PNGs at the given FPS rate.

    Returns dict with keys: count, fps, output_dir, files.
    """
    check_ffmpeg()
    vp = Path(video_path)
    if output_dir is None:
        output_dir = str(Path("output/video_pipeline") / vp.stem / "frames")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    pattern = str(out / "frame_%04d.png")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(vp),
        "-vf", f"fps={fps}",
        pattern,
    ]

    logger.info("Extracting frames at %g fps -> %s", fps, out)
    result = _run_ffmpeg(cmd, timeout=600)
    if result.returncode != 0:
        logger.warning("ffmpeg stderr: %s", result.stderr[:300])

    frames = sorted(out.glob("frame_*.png"))
    logger.info("Extracted %d frames", len(frames))

    return {
        "count": len(frames),
        "fps": fps,
        "output_dir": str(out.resolve()),
        "files": [str(f.resolve()) for f in frames],
    }


def _detect_scene_timestamps(
    video_path: str,
    threshold: float = 0.3,
) -> list[float]:
    """
    Detect scene-change timestamps using ffmpeg select filter.

    Parses pts_time from showinfo output on stderr.
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", _NULL_DEV,
    ]

    logger.info("Detecting scenes (threshold=%.2f)...", threshold)
    result = _run_ffmpeg(cmd, timeout=600)

    # Parse pts_time from showinfo lines in stderr
    timestamps: list[float] = []
    for match in re.finditer(r"pts_time:\s*([\d.]+)", result.stderr):
        ts = float(match.group(1))
        # Deduplicate very close cuts (< 1s apart)
        if not timestamps or ts - timestamps[-1] >= 1.0:
            timestamps.append(ts)

    logger.info("Found %d scene changes", len(timestamps))
    return timestamps


def _extract_clip(
    video_path: str,
    start: float,
    duration: float,
    output_path: str,
) -> bool:
    """Extract a single clip. Uses -c copy with re-encode fallback (ingester.py pattern)."""
    # Fast path: stream copy
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        return True
    except subprocess.CalledProcessError:
        pass

    # Fallback: re-encode (same as ingester.py)
    cmd_reencode = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac",
        output_path,
    ]
    try:
        subprocess.run(cmd_reencode, capture_output=True, timeout=300, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to extract clip at t=%.1f: %s", start, str(e)[:200])
        return False


def make_presentation_clips(
    video_path: str,
    output_dir: str | None = None,
    scene_threshold: float = 0.3,
) -> dict:
    """
    Split video into clips by scene detection.

    Falls back to 30-second fixed intervals if < 2 scene cuts detected.

    Returns dict with keys: count, method, output_dir, items.
    """
    check_ffmpeg()
    vp = Path(video_path)
    if output_dir is None:
        output_dir = str(Path("output/video_pipeline") / vp.stem / "clips")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total_duration = get_video_duration(video_path)
    if total_duration <= 0:
        logger.warning("Cannot determine video duration for %s", video_path)
        return {"count": 0, "method": "error", "output_dir": str(out.resolve()), "items": []}

    # Detect scene boundaries
    timestamps = _detect_scene_timestamps(video_path, threshold=scene_threshold)

    # Decide method
    if len(timestamps) >= 2:
        method = "scene_detection"
        # Build segment boundaries: [0, ts1, ts2, ..., total_duration]
        boundaries = [0.0] + timestamps + [total_duration]
    else:
        method = "fixed_interval"
        logger.info("< 2 scene cuts detected, falling back to 30s intervals")
        interval = 30.0
        boundaries = []
        t = 0.0
        while t < total_duration:
            boundaries.append(t)
            t += interval
        boundaries.append(total_duration)

    # Extract clips
    items: list[dict] = []
    for idx in range(len(boundaries) - 1):
        seg_start = boundaries[idx]
        seg_end = boundaries[idx + 1]
        seg_duration = seg_end - seg_start

        if seg_duration < 1.0:  # Skip tiny segments
            continue

        clip_name = f"clip_{idx:03d}_t{int(seg_start):05d}.mp4"
        clip_path = str(out / clip_name)

        if _extract_clip(video_path, seg_start, seg_duration, clip_path):
            items.append({
                "index": idx,
                "path": str(Path(clip_path).resolve()),
                "start": round(seg_start, 2),
                "end": round(seg_end, 2),
                "duration": round(seg_duration, 2),
            })
            logger.info("  Clip %d: %.1f-%.1fs (%s)", idx, seg_start, seg_end, clip_name)

    logger.info("Created %d clips via %s", len(items), method)

    return {
        "count": len(items),
        "method": method,
        "output_dir": str(out.resolve()),
        "items": items,
    }


def write_manifest(
    source_path: str,
    duration: float,
    frames_result: dict | None,
    clips_result: dict | None,
    output_dir: str,
) -> str:
    """Write manifest.json summarising the pipeline output. Returns manifest path."""
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": {
            "path": str(Path(source_path).resolve()),
            "filename": Path(source_path).name,
            "duration_seconds": round(duration, 2),
        },
    }

    if frames_result is not None:
        manifest["frames"] = frames_result

    if clips_result is not None:
        manifest["clips"] = clips_result

    manifest_path = str(Path(output_dir) / "manifest.json")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Wrote manifest: %s", manifest_path)
    return manifest_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract frames and scene-based clips from a video file or YouTube URL.",
        epilog=(
            "Examples:\n"
            "  python tools/video_pipeline.py video.mp4\n"
            "  python tools/video_pipeline.py video.mp4 --frames-only --fps 1\n"
            "  python tools/video_pipeline.py video.mp4 --clips-only --scene-threshold 0.4\n"
            '  python tools/video_pipeline.py "https://youtube.com/watch?v=..." --output out/yt\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", help="Path to a video file or a YouTube URL")
    parser.add_argument("--fps", type=float, default=2, help="Frames per second for extraction (default: 2)")
    parser.add_argument("--output", "-o", help="Base output directory (default: output/video_pipeline/<stem>)")
    parser.add_argument("--frames-only", action="store_true", help="Only extract frames, skip clips")
    parser.add_argument("--clips-only", action="store_true", help="Only extract clips, skip frames")
    parser.add_argument("--scene-threshold", type=float, default=0.3,
                        help="Scene detection threshold 0-1 (default: 0.3, lower = more cuts)")

    args = parser.parse_args()

    # Determine if source is a URL
    is_url = args.source.startswith(("http://", "https://"))

    if is_url:
        # Download first
        dl_dir = args.output or "output/video_pipeline/_downloads"
        video_path = download_video(args.source, dl_dir)
    else:
        video_path = args.source
        if not Path(video_path).exists():
            logger.error("File not found: %s", video_path)
            sys.exit(1)

    # Resolve output directory
    stem = Path(video_path).stem
    base_output = args.output or str(Path("output/video_pipeline") / stem)

    duration = get_video_duration(video_path)
    if duration <= 0:
        logger.error("Cannot determine video duration for %s", video_path)
        sys.exit(1)

    logger.info("Source: %s (%.1fs)", Path(video_path).name, duration)

    frames_result = None
    clips_result = None

    if not args.clips_only:
        frames_dir = str(Path(base_output) / "frames")
        frames_result = extract_frames(video_path, fps=args.fps, output_dir=frames_dir)

    if not args.frames_only:
        clips_dir = str(Path(base_output) / "clips")
        clips_result = make_presentation_clips(
            video_path,
            output_dir=clips_dir,
            scene_threshold=args.scene_threshold,
        )

    manifest_path = write_manifest(
        source_path=video_path,
        duration=duration,
        frames_result=frames_result,
        clips_result=clips_result,
        output_dir=base_output,
    )

    # Summary
    print(f"\n{'='*50}")
    print(f"  Video Pipeline Complete")
    print(f"{'='*50}")
    print(f"  Source:   {Path(video_path).name} ({duration:.1f}s)")
    if frames_result:
        print(f"  Frames:   {frames_result['count']} @ {frames_result['fps']} fps")
    if clips_result:
        print(f"  Clips:    {clips_result['count']} ({clips_result['method']})")
    print(f"  Manifest: {manifest_path}")
    print()


if __name__ == "__main__":
    main()
