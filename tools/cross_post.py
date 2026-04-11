#!/usr/bin/env python3
"""
Cross Post — One Render, Five Platform Derivatives
===================================================
Takes the LinkedIn master video (output of shorts_pipeline.py) and
derives platform-specific versions for YouTube Shorts, TikTok,
Instagram Reels, and Twitter/X.

LinkedIn is the source of truth — shot once, formatted for each platform.
Total extra processing time: ~3 minutes automated.

Platform specs:
  LinkedIn    : 1–3 min, 9:16 or 16:9, captions burned in (already done by shorts_pipeline)
  YouTube Shorts: 60s cut, 1080×1920, progress bar + end card (already done by shorts_pipeline)
  TikTok      : 60s, same file, TikTok caption style override
  Instagram Reels: 60s, safe zone crop ±10%, bottom watermark area removed
  Twitter/X   : 1:1 crop, 45s cut, end card removed

Usage:
    python tools/cross_post.py --input output/shorts/vfd_e005.mp4 \\
        --transcript output/shorts/vfd_e005.srt \\
        --output-dir output/cross_post/vfd_e005/

Requires: ffmpeg in PATH
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cross-post")

# Platform output specs
PLATFORMS = {
    "youtube_shorts": {"w": 1080, "h": 1920, "max_s": 60, "desc": "YouTube Shorts"},
    "tiktok": {"w": 1080, "h": 1920, "max_s": 60, "desc": "TikTok"},
    "reels": {"w": 1080, "h": 1920, "max_s": 60, "desc": "Instagram Reels"},
    "linkedin": {"w": 1080, "h": 1920, "max_s": 180, "desc": "LinkedIn"},
    "twitter": {"w": 1080, "h": 1080, "max_s": 45, "desc": "Twitter/X"},
}


def _ffprobe_duration(path: Path) -> float:
    import json
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def _run_ffmpeg(cmd: list[str], label: str) -> None:
    logger.info("  %s...", label)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({label}):\n{result.stderr[-500:]}")


def derive_youtube_shorts(input_path: Path, output_path: Path) -> Path:
    """
    YouTube Shorts derivative from LinkedIn master.
    The LinkedIn master from shorts_pipeline.py is already 9:16 with captions,
    hook card, watermark, and end card. Just ensure 60s hard cap.
    """
    duration = _ffprobe_duration(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if duration <= 60.0:
        shutil.copy(input_path, output_path)
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-t", "60",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
        _run_ffmpeg(cmd, "Trim to 60s for YouTube Shorts")

    logger.info("YouTube Shorts: %s", output_path.name)
    return output_path


def derive_tiktok(input_path: Path, output_path: Path) -> Path:
    """
    TikTok derivative: same 9:16 file, ensure 60s max.
    TikTok captions use the same burn-in (already on master).
    Removes the progress bar area from bottom 8px if visible (cosmetic).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # TikTok: trim to 60s, keep all overlays (captions already burned in)
    duration = _ffprobe_duration(input_path)
    trim_arg = ["-t", "60"] if duration > 60 else []

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        *trim_arg,
        # Crop bottom 8px to remove progress bar (TikTok has its own)
        "-vf", "crop=in_w:in_h-8:0:0,scale=1080:1920:flags=lanczos",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "Derive TikTok version")
    logger.info("TikTok: %s", output_path.name)
    return output_path


def derive_reels(input_path: Path, output_path: Path) -> Path:
    """
    Instagram Reels derivative: 9:16, 60s max.
    Safe zone crop: Instagram UI covers bottom ~13% and top ~8%.
    Remove the factorylm.com watermark from the very bottom to avoid
    it being covered by Reels UI chrome.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = _ffprobe_duration(input_path)
    trim_arg = ["-t", "60"] if duration > 60 else []

    # Crop to remove bottom watermark zone (bottom 120px) and rescale
    # Instagram safe zone: content visible between ~8% top and ~87% bottom
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        *trim_arg,
        "-vf", "crop=in_w:in_h-120:0:0,scale=1080:1920:flags=lanczos,pad=1080:1920:0:0:black",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "Derive Instagram Reels version")
    logger.info("Instagram Reels: %s", output_path.name)
    return output_path


def derive_linkedin(input_path: Path, output_path: Path) -> Path:
    """
    LinkedIn native video derivative.
    LinkedIn supports up to 3 min; the master is already LinkedIn-optimised.
    Remove the YouTube Shorts progress bar and end card re-skin is not needed
    for LinkedIn — but captions must stay (LinkedIn auto-captions are unreliable).
    Just copy the master with the end card stripped if > 90s.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = _ffprobe_duration(input_path)

    if duration <= 180:
        shutil.copy(input_path, output_path)
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-t", "180",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
        _run_ffmpeg(cmd, "Trim to 3min for LinkedIn")

    logger.info("LinkedIn: %s", output_path.name)
    return output_path


def derive_twitter(input_path: Path, output_path: Path) -> Path:
    """
    Twitter/X derivative: 1:1 square crop, 45s max.
    Removes end card (no CTA needed — Twitter bio has the link).
    Crops center 1080×1080 from 1080×1920 source.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Center crop 1080×1080 from 1080×1920 (take middle of frame)
    # y offset = (1920-1080)/2 = 420
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-t", "45",
        "-vf", "crop=1080:1080:0:420,scale=1080:1080:flags=lanczos",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]
    _run_ffmpeg(cmd, "Derive Twitter/X version")
    logger.info("Twitter/X: %s", output_path.name)
    return output_path


def repurpose_short(
    short_path: Path | str,
    output_dir: Path | str,
    transcript: str | None = None,
) -> dict[str, Path]:
    """
    Derive all platform versions from a single LinkedIn master Short.

    Args:
        short_path: Path to LinkedIn master MP4 (output of shorts_pipeline.py)
        output_dir: Directory for platform derivatives
        transcript: Optional SRT transcript (not currently used for re-captioning,
                    but passed through for upstream tools that want it)

    Returns:
        dict mapping platform name → output Path
        e.g. {"youtube_shorts": Path(...), "tiktok": Path(...), ...}
    """
    short_path = Path(short_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not short_path.exists():
        raise FileNotFoundError(f"Master video not found: {short_path}")

    stem = short_path.stem
    logger.info("=== Cross-post: %s → 5 platforms ===", stem)

    results: dict[str, Path] = {}

    try:
        results["youtube_shorts"] = derive_youtube_shorts(
            short_path, output_dir / f"{stem}_youtube_shorts.mp4"
        )
    except Exception as e:
        logger.error("YouTube Shorts failed: %s", e)

    try:
        results["tiktok"] = derive_tiktok(
            short_path, output_dir / f"{stem}_tiktok.mp4"
        )
    except Exception as e:
        logger.error("TikTok failed: %s", e)

    try:
        results["reels"] = derive_reels(
            short_path, output_dir / f"{stem}_reels.mp4"
        )
    except Exception as e:
        logger.error("Reels failed: %s", e)

    try:
        results["linkedin"] = derive_linkedin(
            short_path, output_dir / f"{stem}_linkedin.mp4"
        )
    except Exception as e:
        logger.error("LinkedIn failed: %s", e)

    try:
        results["twitter"] = derive_twitter(
            short_path, output_dir / f"{stem}_twitter.mp4"
        )
    except Exception as e:
        logger.error("Twitter/X failed: %s", e)

    logger.info(
        "=== Done: %d/%d platforms ===",
        len(results), len(PLATFORMS),
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive 5 platform versions from a LinkedIn master Short"
    )
    parser.add_argument("--input", required=True, help="LinkedIn master MP4 path")
    parser.add_argument("--output-dir", required=True, help="Output directory for platform derivatives")
    parser.add_argument("--transcript", help="Optional SRT transcript path")
    parser.add_argument(
        "--platform",
        choices=list(PLATFORMS.keys()) + ["all"],
        default="all",
        help="Generate only this platform (default: all)",
    )
    args = parser.parse_args()

    short_path = Path(args.input)
    output_dir = Path(args.output_dir)
    transcript = Path(args.transcript).read_text() if args.transcript else None

    if args.platform == "all":
        results = repurpose_short(short_path, output_dir, transcript)
        for platform, path in results.items():
            print(f"  {PLATFORMS[platform]['desc']:20s}: {path}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = short_path.stem
        out = output_dir / f"{stem}_{args.platform}.mp4"
        fn = {
            "youtube_shorts": derive_youtube_shorts,
            "tiktok": derive_tiktok,
            "reels": derive_reels,
            "linkedin": derive_linkedin,
            "twitter": derive_twitter,
        }[args.platform]
        path = fn(short_path, out)
        print(f"{PLATFORMS[args.platform]['desc']}: {path}")


if __name__ == "__main__":
    main()
