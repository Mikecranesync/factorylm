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
import concurrent.futures
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import time
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
# Batch processing
# ---------------------------------------------------------------------------

_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}


def _process_single_video(
    video_path: str,
    output_dir: str,
    fps: float,
    frames_only: bool,
    scene_threshold: float,
    index: int,
    total: int,
) -> dict:
    """Process one video file. Returns a result dict (ok or error)."""
    name = Path(video_path).name
    logger.info("[%d/%d] Processing %s ...", index, total, name)

    # Skip zero-byte files
    if Path(video_path).stat().st_size == 0:
        return {"file": name, "status": "error", "error": "zero-byte file"}

    try:
        duration = get_video_duration(video_path)
        if duration <= 0:
            return {"file": name, "status": "error", "error": "cannot determine duration (corrupt?)"}

        frames_result = None
        clips_result = None

        frames_dir = str(Path(output_dir) / "frames")
        frames_result = extract_frames(video_path, fps=fps, output_dir=frames_dir)

        if not frames_only:
            clips_dir = str(Path(output_dir) / "clips")
            clips_result = make_presentation_clips(
                video_path,
                output_dir=clips_dir,
                scene_threshold=scene_threshold,
            )

        manifest_path = write_manifest(
            source_path=video_path,
            duration=duration,
            frames_result=frames_result,
            clips_result=clips_result,
            output_dir=output_dir,
        )

        frame_count = frames_result["count"] if frames_result else 0
        result = {
            "file": name,
            "status": "ok",
            "duration": round(duration, 2),
            "frames": frame_count,
            "manifest": manifest_path,
        }
        if clips_result:
            result["clips"] = clips_result["count"]

        logger.info("[%d/%d] Done %s — %d frames", index, total, name, frame_count)
        return result

    except Exception as exc:
        logger.error("[%d/%d] Failed %s: %s", index, total, name, exc)
        return {"file": name, "status": "error", "error": str(exc)}


def batch_process(
    input_dir: str,
    output_dir: str | None = None,
    fps: float = 0.5,
    max_workers: int = 3,
    frames_only: bool = True,
    scene_threshold: float = 0.3,
) -> list[dict]:
    """
    Process all video files in a directory using ThreadPoolExecutor.

    Returns list of per-video result dicts.
    """
    check_ffmpeg()

    src = Path(input_dir)
    if not src.is_dir():
        logger.error("Not a directory: %s", input_dir)
        sys.exit(1)

    # Collect video files
    videos = sorted(
        f for f in src.iterdir()
        if f.is_file() and f.suffix.lower() in _VIDEO_EXTENSIONS
    )

    if not videos:
        logger.error("No video files found in %s", input_dir)
        sys.exit(1)

    base_output = output_dir or "output/video_pipeline"
    total = len(videos)
    logger.info("Found %d video files in %s (workers=%d, fps=%g)", total, input_dir, max_workers, fps)

    results: list[dict] = [None] * total  # type: ignore[list-item]
    t0 = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx: dict[concurrent.futures.Future, int] = {}
        for idx, vpath in enumerate(videos):
            vid_output = str(Path(base_output) / vpath.stem)
            fut = pool.submit(
                _process_single_video,
                str(vpath),
                vid_output,
                fps,
                frames_only,
                scene_threshold,
                idx + 1,
                total,
            )
            future_to_idx[fut] = idx

        for fut in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception as exc:
                results[idx] = {
                    "file": videos[idx].name,
                    "status": "error",
                    "error": str(exc),
                }

    elapsed = time.monotonic() - t0
    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = total - ok_count
    total_frames = sum(r.get("frames", 0) for r in results)

    # Write batch manifest
    batch_manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "input_dir": str(src.resolve()),
        "settings": {
            "fps": fps,
            "max_workers": max_workers,
            "frames_only": frames_only,
        },
        "total_videos": total,
        "processed": ok_count,
        "skipped": err_count,
        "total_frames": total_frames,
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }

    manifest_dir = Path(base_output)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = str(manifest_dir / "batch_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(batch_manifest, f, indent=2)

    # Summary
    print(f"\n{'='*50}")
    print(f"  Batch Processing Complete")
    print(f"{'='*50}")
    print(f"  Videos:   {ok_count}/{total} processed ({err_count} errors)")
    print(f"  Frames:   {total_frames} total")
    print(f"  Time:     {elapsed:.1f}s")
    print(f"  Manifest: {manifest_path}")
    if err_count:
        print(f"  Errors:")
        for r in results:
            if r["status"] == "error":
                print(f"    - {r['file']}: {r['error']}")
    print()

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_single(args: argparse.Namespace) -> None:
    """Handle the 'run' subcommand (single video processing)."""
    # Determine if source is a URL
    is_url = args.source.startswith(("http://", "https://"))

    if is_url:
        dl_dir = args.output or "output/video_pipeline/_downloads"
        video_path = download_video(args.source, dl_dir)
    else:
        video_path = args.source
        if not Path(video_path).exists():
            logger.error("File not found: %s", video_path)
            sys.exit(1)

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


def _run_batch(args: argparse.Namespace) -> None:
    """Handle the 'batch' subcommand."""
    batch_process(
        input_dir=args.directory,
        output_dir=args.output,
        fps=args.fps,
        max_workers=args.workers,
        frames_only=args.frames_only,
        scene_threshold=args.scene_threshold,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Video-to-Frames Pipeline: extract frames and clips from video files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- 'run' subcommand (single file) ---
    run_parser = subparsers.add_parser(
        "run",
        help="Process a single video file or YouTube URL",
        epilog=(
            "Examples:\n"
            "  python tools/video_pipeline.py run video.mp4\n"
            "  python tools/video_pipeline.py run video.mp4 --frames-only --fps 1\n"
            '  python tools/video_pipeline.py run "https://youtube.com/watch?v=..." -o out/yt\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument("source", help="Path to a video file or a YouTube URL")
    run_parser.add_argument("--fps", type=float, default=2, help="Frames per second (default: 2)")
    run_parser.add_argument("--output", "-o", help="Base output directory")
    run_parser.add_argument("--frames-only", action="store_true", help="Only extract frames")
    run_parser.add_argument("--clips-only", action="store_true", help="Only extract clips")
    run_parser.add_argument("--scene-threshold", type=float, default=0.3,
                            help="Scene detection threshold 0-1 (default: 0.3)")

    # --- 'batch' subcommand ---
    batch_parser = subparsers.add_parser(
        "batch",
        help="Process all videos in a directory in parallel",
        epilog=(
            "Examples:\n"
            '  python tools/video_pipeline.py batch "C:/Users/hharp/Videos" --fps 0.5\n'
            '  python tools/video_pipeline.py batch ./videos --workers 4 --fps 1\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    batch_parser.add_argument("directory", help="Directory containing video files")
    batch_parser.add_argument("--fps", type=float, default=0.5, help="Frames per second (default: 0.5)")
    batch_parser.add_argument("--output", "-o", help="Base output directory (default: output/video_pipeline)")
    batch_parser.add_argument("--workers", type=int, default=3, help="Concurrent workers (default: 3)")
    batch_parser.add_argument("--frames-only", action="store_true", default=True,
                              help="Only extract frames, skip clips (default: true)")
    batch_parser.add_argument("--with-clips", action="store_true",
                              help="Also extract scene-based clips")
    batch_parser.add_argument("--scene-threshold", type=float, default=0.3,
                              help="Scene detection threshold 0-1 (default: 0.3)")

    # Backward compat: bare `python video_pipeline.py <source>` with no subcommand
    # Insert 'run' before the first arg if it doesn't match a subcommand
    if len(sys.argv) > 1 and sys.argv[1] not in ("run", "batch", "-h", "--help"):
        sys.argv.insert(1, "run")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "run":
        _run_single(args)
    elif args.command == "batch":
        if args.with_clips:
            args.frames_only = False
        _run_batch(args)


if __name__ == "__main__":
    main()
