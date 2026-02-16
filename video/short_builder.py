"""
Short Builder — assemble highlight clips into demo videos.

Uses ffmpeg to concatenate clips and optionally add text overlays.

Usage:
    python video/short_builder.py --clips 1,5,12 --output demo.mp4
    python video/short_builder.py --clips 1,5,12 --output demo.mp4 --title "Jam Diagnosis Demo"
    python video/short_builder.py --auto --top 5 --output best_of.mp4
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def get_clip_files(matrix_url: str, clip_ids: list[int]) -> list[str]:
    """Fetch file paths for given clip IDs from Matrix API."""
    files = []
    for cid in clip_ids:
        try:
            resp = httpx.get(f"{matrix_url}/api/video/clips/{cid}", timeout=10)
            resp.raise_for_status()
            clip = resp.json()
            chunk_file = clip.get("chunk_file", "")
            if chunk_file and Path(chunk_file).exists():
                files.append(chunk_file)
            else:
                logger.warning("Clip #%d file not found: %s", cid, chunk_file)
        except Exception as e:
            logger.warning("Failed to fetch clip #%d: %s", cid, e)
    return files


def concatenate_clips(
    clip_files: list[str],
    output_path: str,
    title: str | None = None,
) -> bool:
    """Concatenate video clips using ffmpeg concat demuxer."""
    if not clip_files:
        logger.error("No clips to concatenate")
        return False

    # Create concat file list
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for cf in clip_files:
            # ffmpeg concat needs forward slashes and escaped quotes
            safe_path = Path(cf).resolve().as_posix()
            f.write(f"file '{safe_path}'\n")
        concat_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
        ]

        if title:
            # Add title overlay using drawtext filter
            cmd.extend([
                "-vf", (
                    f"drawtext=text='{title}'"
                    ":fontsize=28:fontcolor=white:borderw=2:bordercolor=black"
                    ":x=(w-text_w)/2:y=h-60"
                    ":enable='between(t,0,3)'"
                ),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac",
            ])
        else:
            cmd.extend(["-c", "copy"])

        cmd.append(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        logger.info("Building video: %d clips → %s", len(clip_files), output_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error("ffmpeg error: %s", result.stderr[-500:] if result.stderr else "unknown")
            return False

        size_mb = Path(output_path).stat().st_size / 1e6
        logger.info("✓ Output: %s (%.1f MB)", output_path, size_mb)
        return True
    finally:
        os.unlink(concat_file)


def main():
    parser = argparse.ArgumentParser(description="Short Builder")
    parser.add_argument("--clips", type=str, help="Comma-separated clip IDs or file paths")
    parser.add_argument("--output", type=str, required=True, help="Output video path")
    parser.add_argument("--title", type=str, default=None, help="Title overlay text")
    parser.add_argument("--matrix-url", default=os.getenv("MATRIX_URL", "http://localhost:8000"))
    parser.add_argument("--auto", action="store_true", help="Auto-select top highlights")
    parser.add_argument("--top", type=int, default=5, help="Number of highlights for --auto")
    args = parser.parse_args()

    if args.auto:
        # Auto-select from highlights
        from video.highlight_selector import select_highlights
        highlights = select_highlights(matrix_url=args.matrix_url, top=args.top)
        clip_files = [h["file"] for h in highlights if Path(h["file"]).exists()]
        if not clip_files:
            logger.error("No highlight clips found with existing files")
            return
    elif args.clips:
        parts = [p.strip() for p in args.clips.split(",")]
        # Check if they're IDs or file paths
        if all(p.isdigit() for p in parts):
            clip_files = get_clip_files(args.matrix_url, [int(p) for p in parts])
        else:
            clip_files = [p for p in parts if Path(p).exists()]
    else:
        parser.error("Either --clips or --auto is required")
        return

    success = concatenate_clips(clip_files, args.output, title=args.title)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
