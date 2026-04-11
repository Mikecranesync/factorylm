#!/usr/bin/env python3
"""
Shorts Pipeline — LinkedIn-First Vertical Video Producer
=========================================================
Takes an existing montage.mp4 + script and renders a platform-ready
vertical video with:
  - Smart crop to 9:16 (1080×1920)
  - Animated hook card (0–3s bold text overlay)
  - Whisper caption burn-in (mute-safe — 85% of social video watched muted)
  - Progress bar (YouTube Shorts UX convention)
  - Watermark: "factorylm.com" bottom-right
  - End card with CTA (final 15s)
  - Hard trim to 58–60s

LinkedIn is the source of truth. cross_post.py derives all other formats.

Usage:
    python tools/shorts_pipeline.py --input montage.mp4 --hook "VFD Fault E005: AI Fixes It" \\
        --output output/shorts/vfd_e005.mp4

Requires: ffmpeg in PATH, openai-whisper installed.
Secrets: none required for local render.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("shorts-pipeline")

# Output spec
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_DURATION_MIN = 58.0
TARGET_DURATION_MAX = 60.0
TARGET_LUFS = -14.0
WATERMARK_TEXT = "factorylm.com"
END_CARD_DURATION = 15  # seconds
HOOK_DURATION = 3  # seconds
PROGRESS_BAR_HEIGHT = 8  # pixels


def _ffprobe(path: Path) -> dict:
    """Return stream metadata for the first video stream."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_duration(path: Path) -> float:
    info = _ffprobe(path)
    return float(info["format"]["duration"])


def get_dimensions(path: Path) -> tuple[int, int]:
    info = _ffprobe(path)
    for stream in info["streams"]:
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])
    raise ValueError(f"No video stream in {path}")


def crop_to_vertical(input_path: Path, output_path: Path) -> Path:
    """
    Smart-crop 16:9 (or any ratio) to 9:16 (1080×1920).
    Centers the crop horizontally; uses full height if source is taller.
    """
    w, h = get_dimensions(input_path)
    target_aspect = TARGET_WIDTH / TARGET_HEIGHT  # 0.5625

    # Determine crop region in source dimensions
    source_aspect = w / h
    if source_aspect > target_aspect:
        # Source is wider — crop sides, use full height
        crop_h = h
        crop_w = int(h * target_aspect)
    else:
        # Source is taller — crop top/bottom, use full width
        crop_w = w
        crop_h = int(w / target_aspect)

    # Center the crop
    x_offset = (w - crop_w) // 2
    y_offset = (h - crop_h) // 2

    vf = (
        f"crop={crop_w}:{crop_h}:{x_offset}:{y_offset},"
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:flags=lanczos"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]
    logger.info("Cropping to vertical: %s → %s", input_path.name, output_path.name)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def trim_to_60s(input_path: Path, output_path: Path) -> Path:
    """Hard cap at TARGET_DURATION_MAX seconds. Warns if already shorter than TARGET_DURATION_MIN."""
    duration = get_duration(input_path)

    if duration < TARGET_DURATION_MIN:
        logger.warning(
            "Video is %.1fs — shorter than minimum %.1fs. "
            "Add filler or extend end card before publishing.",
            duration, TARGET_DURATION_MIN,
        )

    if duration <= TARGET_DURATION_MAX:
        # Already within spec — just copy
        cmd = ["ffmpeg", "-y", "-i", str(input_path), "-c", "copy", str(output_path)]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-t", str(TARGET_DURATION_MAX),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]

    logger.info("Trimming to 60s: %.1fs → max %.1fs", duration, TARGET_DURATION_MAX)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def normalize_audio(input_path: Path, output_path: Path) -> Path:
    """Normalize audio to -14 LUFS (broadcast standard for social video)."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11",
        "-c:v", "copy",
        str(output_path),
    ]
    logger.info("Normalizing audio to %s LUFS", TARGET_LUFS)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def add_hook_card(input_path: Path, output_path: Path, hook_text: str) -> Path:
    """
    Overlay bold text hook card for the first HOOK_DURATION seconds.
    Style: white text, 2px black outline, centered, 72pt Inter Bold equivalent.
    Fades out at second 3.
    """
    # Escape special ffmpeg drawtext characters
    safe_text = hook_text.replace("'", "\\'").replace(":", "\\:").replace("\\", "\\\\")

    # Split into two lines if text is long
    words = hook_text.split()
    if len(words) > 5:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        safe_text = line1.replace("'", "\\'") + "\\n" + line2.replace("'", "\\'")

    vf = (
        f"drawtext="
        f"text='{safe_text}':"
        f"fontsize=72:"
        f"fontcolor=white:"
        f"borderw=3:"
        f"bordercolor=black:"
        f"x=(w-text_w)/2:"
        f"y=(h/2-text_h/2):"
        f"enable='between(t,0,{HOOK_DURATION})':"
        f"alpha='if(lt(t,{HOOK_DURATION-0.5}),1,1-(t-{HOOK_DURATION-0.5})/0.5)'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output_path),
    ]
    logger.info("Adding hook card: '%s'", hook_text[:50])
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def add_progress_bar(input_path: Path, output_path: Path) -> Path:
    """
    Add a thin progress bar at the bottom of the frame.
    Standard YouTube Shorts UX convention — shows viewers how far through they are.
    """
    duration = get_duration(input_path)

    vf = (
        # Dark background strip
        f"drawbox=x=0:y=ih-{PROGRESS_BAR_HEIGHT}:w=iw:h={PROGRESS_BAR_HEIGHT}:"
        f"color=black@0.4:t=fill,"
        # Bright orange progress bar growing with time
        f"drawbox=x=0:y=ih-{PROGRESS_BAR_HEIGHT}:"
        f"w=iw*t/{duration}:h={PROGRESS_BAR_HEIGHT}:"
        f"color=#F97316@0.9:t=fill"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output_path),
    ]
    logger.info("Adding progress bar")
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def add_watermark(input_path: Path, output_path: Path, text: str = WATERMARK_TEXT) -> Path:
    """Add semi-transparent watermark text at bottom-right."""
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    vf = (
        f"drawtext="
        f"text='{safe_text}':"
        f"fontsize=32:"
        f"fontcolor=white@0.6:"
        f"borderw=1:"
        f"bordercolor=black@0.4:"
        f"x=w-text_w-20:"
        f"y=h-text_h-{PROGRESS_BAR_HEIGHT + 16}"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output_path),
    ]
    logger.info("Adding watermark: %s", text)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def add_end_card(
    input_path: Path,
    output_path: Path,
    cta_text: str = "Free Demo →",
    cta_url: str = "factorylm.com",
    duration: int = END_CARD_DURATION,
) -> Path:
    """
    Overlay CTA text on the final `duration` seconds.
    Semi-transparent dark background strip + bold CTA text.
    """
    total_duration = get_duration(input_path)
    start_t = total_duration - duration

    safe_cta = cta_text.replace("'", "\\'").replace(":", "\\:")
    safe_url = cta_url.replace("'", "\\'").replace(":", "\\:")

    vf = (
        # Dark strip behind CTA
        f"drawbox="
        f"x=0:y=ih*0.75:w=iw:h=ih*0.15:"
        f"color=black@0.75:t=fill:"
        f"enable='gte(t,{start_t})',"
        # CTA main text
        f"drawtext="
        f"text='{safe_cta}':"
        f"fontsize=56:"
        f"fontcolor=white:"
        f"borderw=2:bordercolor=black:"
        f"x=(w-text_w)/2:y=ih*0.78:"
        f"enable='gte(t,{start_t})',"
        # URL subtext
        f"drawtext="
        f"text='{safe_url}':"
        f"fontsize=40:"
        f"fontcolor=#F97316:"
        f"borderw=2:bordercolor=black:"
        f"x=(w-text_w)/2:y=ih*0.84:"
        f"enable='gte(t,{start_t})'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output_path),
    ]
    logger.info("Adding end card: '%s %s' at t=%.1fs", cta_text, cta_url, start_t)
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def transcribe(input_path: Path) -> str:
    """
    Transcribe audio using local openai-whisper.
    Returns SRT-format subtitle string.
    Falls back to empty string if whisper not installed.
    """
    try:
        import whisper  # type: ignore
    except ImportError:
        logger.warning("openai-whisper not installed — skipping caption burn-in. pip install openai-whisper")
        return ""

    logger.info("Transcribing audio with Whisper (base model)...")
    model = whisper.load_model("base")
    result = model.transcribe(str(input_path), verbose=False)

    # Build SRT format
    lines = []
    for i, seg in enumerate(result["segments"], 1):
        start = _seconds_to_srt_time(seg["start"])
        end = _seconds_to_srt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")

    return "\n".join(lines)


def _seconds_to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def add_captions(
    input_path: Path,
    output_path: Path,
    srt_content: str | None = None,
    style: str = "bold_industrial",
) -> Path:
    """
    Burn captions into video. Uses Whisper transcription if srt_content not provided.

    style='bold_industrial': white text, 2px black outline, 52pt, bottom-third.
    Caption burn-in is non-optional — 85% of social video is watched muted.
    """
    if not srt_content:
        srt_content = transcribe(input_path)

    if not srt_content:
        logger.warning("No captions generated — publishing without captions is not recommended")
        import shutil
        shutil.copy(input_path, output_path)
        return output_path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
        f.write(srt_content)
        srt_path = f.name

    if style == "bold_industrial":
        subtitle_style = (
            "FontName=Arial,FontSize=52,PrimaryColour=&Hffffff&,"
            "OutlineColour=&H000000&,Outline=2,Shadow=0,"
            "Alignment=2,MarginV=80"
        )
    else:
        subtitle_style = "FontSize=44"

    vf = f"subtitles={srt_path}:force_style='{subtitle_style}'"

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(output_path),
    ]
    logger.info("Burning in captions (style: %s)", style)
    subprocess.run(cmd, check=True, capture_output=True)

    os.unlink(srt_path)
    return output_path


def validate_output(output_path: Path) -> dict:
    """
    Run technical quality gates. Returns dict of pass/fail results.
    Mirrors REVIEW_CHECKLIST.md technical section.
    """
    results: dict[str, bool | str] = {}

    w, h = get_dimensions(output_path)
    results["resolution_ok"] = w == TARGET_WIDTH and h == TARGET_HEIGHT
    results["resolution"] = f"{w}×{h}"

    duration = get_duration(output_path)
    results["duration_ok"] = TARGET_DURATION_MIN <= duration <= TARGET_DURATION_MAX
    results["duration"] = f"{duration:.1f}s"

    all_pass = all(v for k, v in results.items() if k.endswith("_ok"))
    results["all_pass"] = all_pass

    return results


def render_short(
    input_mp4: Path | str,
    hook_text: str,
    output_path: Path | str,
    cta_text: str = "Free Demo →",
    cta_url: str = "factorylm.com",
    srt_content: str | None = None,
    skip_captions: bool = False,
) -> Path:
    """
    Full pipeline: input montage → platform-ready Short.

    Steps:
      1. Crop to 9:16
      2. Trim to 60s
      3. Normalize audio to -14 LUFS
      4. Add hook card (0–3s)
      5. Burn in captions (Whisper or provided SRT)
      6. Add progress bar
      7. Add watermark
      8. Add end card
      9. Validate output

    Returns path to final output file.
    Raises RuntimeError if technical validation fails.
    """
    input_mp4 = Path(input_mp4)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_mp4.exists():
        raise FileNotFoundError(f"Input not found: {input_mp4}")

    logger.info("=== Shorts Pipeline: %s ===", input_mp4.name)

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)

        # Step 1: Crop to vertical
        cropped = crop_to_vertical(input_mp4, t / "01_cropped.mp4")

        # Step 2: Trim to 60s
        trimmed = trim_to_60s(cropped, t / "02_trimmed.mp4")

        # Step 3: Normalize audio
        normalized = normalize_audio(trimmed, t / "03_normalized.mp4")

        # Step 4: Hook card
        hooked = add_hook_card(normalized, t / "04_hooked.mp4", hook_text)

        # Step 5: Captions (base render — before platform derivatives)
        if skip_captions:
            captioned = hooked
        else:
            captioned = add_captions(hooked, t / "05_captioned.mp4", srt_content)

        # Step 6: Progress bar
        progress = add_progress_bar(captioned, t / "06_progress.mp4")

        # Step 7: Watermark
        watermarked = add_watermark(progress, t / "07_watermarked.mp4")

        # Step 8: End card
        final_tmp = add_end_card(watermarked, t / "08_final.mp4", cta_text, cta_url)

        # Copy to final destination
        import shutil
        shutil.copy(final_tmp, output_path)

    # Step 9: Validate
    validation = validate_output(output_path)
    if not validation["all_pass"]:
        failed = {k: v for k, v in validation.items() if k.endswith("_ok") and not v}
        raise RuntimeError(
            f"Technical validation failed for {output_path.name}: {failed}\n"
            f"Full results: {validation}"
        )

    logger.info(
        "=== Done: %s | %s | %s ===",
        output_path.name,
        validation["resolution"],
        validation["duration"],
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a platform-ready Short from a montage MP4")
    parser.add_argument("--input", required=True, help="Input montage MP4")
    parser.add_argument("--hook", required=True, help="Hook text for 0–3s overlay")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    parser.add_argument("--cta-text", default="Free Demo →", help="End card CTA text")
    parser.add_argument("--cta-url", default="factorylm.com", help="End card CTA URL")
    parser.add_argument("--srt", help="Path to pre-existing SRT file (skips Whisper)")
    parser.add_argument("--skip-captions", action="store_true", help="Skip caption burn-in")
    args = parser.parse_args()

    srt_content = None
    if args.srt:
        srt_content = Path(args.srt).read_text()

    output = render_short(
        input_mp4=args.input,
        hook_text=args.hook,
        output_path=args.output,
        cta_text=args.cta_text,
        cta_url=args.cta_url,
        srt_content=srt_content,
        skip_captions=args.skip_captions,
    )
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
