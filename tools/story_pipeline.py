#!/usr/bin/env python3
"""
Story Pipeline — Video-to-Story Montage
========================================
Turn extracted frames into a narrated montage video by:
1. Describing frames via Grok Vision (OpenRouter)
2. Generating a documentary-style narrative
3. Building a montage plan (scene selection + timing)
4. Assembling montage.mp4 via ffmpeg

Usage:
    python tools/story_pipeline.py --frames-dir output/video_pipeline/<stem>/frames --output ./output/story_test
    python tools/story_pipeline.py --video recording.mp4 --fps 2 --output ./output/story_test
    python tools/story_pipeline.py --frames-dir ... --skip-describe --output ./output/story_test
    python tools/story_pipeline.py --frames-dir ... --skip-montage --output ./output/story_test

Requires OPENROUTER_API_KEY env var (use Doppler or export manually).
"""

import argparse
import base64
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Fix Windows console encoding (from video_pipeline.py)
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
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

VISION_MODEL = "google/gemini-2.5-flash"
TEXT_MODEL = "google/gemini-2.5-flash"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ffmpeg(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run an ffmpeg command, capturing output."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def check_prerequisites() -> str:
    """Verify ffmpeg, openai SDK, and API key. Returns API key or raises."""
    # ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found on PATH")

    # openai SDK
    if not OPENAI_AVAILABLE:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    # API key
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not set. Use: doppler run -p factorylm -c dev -- python tools/story_pipeline.py ..."
        )
    return api_key


def _get_client(api_key: str) -> "OpenAI":
    """Create OpenRouter-backed OpenAI client."""
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


def _encode_image_base64(image_path: str) -> str:
    """Read an image file and return its base64-encoded string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ---------------------------------------------------------------------------
# Stage 1: Describe frames via Grok Vision
# ---------------------------------------------------------------------------

def describe_frames(
    frames_dir: str,
    output_path: str,
    sample_rate: int = 5,
    api_key: str = "",
) -> str:
    """
    Send sampled frames to Grok Vision for descriptions.

    Args:
        frames_dir: Directory containing frame_NNNN.png files
        output_path: Where to write descriptions.json
        sample_rate: Describe every Nth frame (default: 5)
        api_key: OpenRouter API key

    Returns:
        Path to descriptions.json
    """
    fdir = Path(frames_dir)
    frames = sorted(fdir.glob("frame_*.png"))
    if not frames:
        raise FileNotFoundError(f"No frame_*.png files in {frames_dir}")

    sampled = frames[::sample_rate]
    logger.info("Describing %d/%d frames (sample_rate=%d)", len(sampled), len(frames), sample_rate)

    client = _get_client(api_key)
    descriptions = []

    for i, frame_path in enumerate(sampled):
        logger.info("  [%d/%d] %s", i + 1, len(sampled), frame_path.name)

        img_b64 = _encode_image_base64(str(frame_path))

        try:
            response = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe this factory/industrial frame. Note: equipment visible, "
                                "HMI screens, text on screen, any anomalies or status indicators. "
                                "Respond with JSON: {\"description\": \"...\", \"extracted_text\": \"...\", "
                                "\"tags\": [...], \"is_industrial\": true/false, \"is_screen_recording\": true/false}"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                    ],
                }],
                max_tokens=500,
                temperature=0.3,
            )

            raw_text = response.choices[0].message.content.strip()

            # Try to parse JSON from the response
            try:
                # Handle markdown code fences
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:]
                    raw_text = raw_text.strip()
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed = {
                    "description": raw_text,
                    "extracted_text": "",
                    "tags": [],
                    "is_industrial": True,
                    "is_screen_recording": False,
                }

            entry = {
                "frame": frame_path.name,
                "frame_path": str(frame_path.resolve()),
                **parsed,
            }
            descriptions.append(entry)

        except Exception as e:
            logger.warning("  Failed on %s: %s", frame_path.name, e)
            descriptions.append({
                "frame": frame_path.name,
                "frame_path": str(frame_path.resolve()),
                "description": f"[ERROR] {e}",
                "extracted_text": "",
                "tags": [],
                "is_industrial": True,
                "is_screen_recording": False,
            })

        # Rate limiting — 2s between calls
        if i < len(sampled) - 1:
            time.sleep(2)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, indent=2)

    logger.info("Wrote %d descriptions -> %s", len(descriptions), out)
    return str(out)


# ---------------------------------------------------------------------------
# Stage 2: Generate narrative from descriptions
# ---------------------------------------------------------------------------

def generate_narrative(
    descriptions_path: str,
    output_path: str,
    api_key: str = "",
) -> str:
    """
    Generate a documentary-style narrative from frame descriptions.

    Returns:
        Path to story_narrative.md
    """
    with open(descriptions_path, "r", encoding="utf-8") as f:
        descriptions = json.load(f)

    # Build a summary of what we see
    desc_text = "\n".join(
        f"- Frame {d['frame']}: {d.get('description', 'N/A')}"
        for d in descriptions
    )

    client = _get_client(api_key)

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a documentary narrator for industrial automation content. "
                    "Write in a professional, compelling style suitable for a GitHub demo video."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Write a short documentary-style narrative for a factory automation demo video. "
                    "Use these frame descriptions as source material. Keep it under 500 words. "
                    "Industrial, professional tone.\n\n"
                    f"Frame Descriptions:\n{desc_text}"
                ),
            },
        ],
        max_tokens=1000,
        temperature=0.7,
    )

    narrative = response.choices[0].message.content.strip()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(narrative)

    logger.info("Wrote narrative (%d chars) -> %s", len(narrative), out)
    return str(out)


# ---------------------------------------------------------------------------
# Stage 3: Build montage plan
# ---------------------------------------------------------------------------

def build_montage_plan(
    descriptions_path: str,
    narrative_path: str,
    output_path: str,
    api_key: str = "",
) -> str:
    """
    Create a montage plan selecting the best frames for a 60-90s video.

    Returns:
        Path to montage_plan.json
    """
    with open(descriptions_path, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    with open(narrative_path, "r", encoding="utf-8") as f:
        narrative = f.read()

    desc_text = json.dumps(descriptions, indent=2)

    client = _get_client(api_key)

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a video editor planning a montage from factory floor stills.",
            },
            {
                "role": "user",
                "content": (
                    "Create a montage plan selecting the best frames for a 60-90 second video. "
                    "Output ONLY valid JSON — an array of scene entries:\n"
                    '[{"frame_file": "frame_0001.png", "start_time": 0, "duration": 4, "caption": "..."}]\n\n'
                    "Rules:\n"
                    "- Select 15-20 frames that tell the best visual story\n"
                    "- Each scene should last 3-5 seconds\n"
                    "- Captions should be short (under 10 words)\n"
                    "- Total duration should be 60-90 seconds\n"
                    "- Order scenes for visual flow\n\n"
                    f"Narrative:\n{narrative}\n\n"
                    f"Available frames:\n{desc_text}"
                ),
            },
        ],
        max_tokens=2000,
        temperature=0.5,
    )

    raw = response.choices[0].message.content.strip()

    # Parse JSON from response
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        scenes = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse montage plan JSON, wrapping raw response")
        scenes = [{"frame_file": d["frame"], "start_time": i * 4, "duration": 4, "caption": ""}
                   for i, d in enumerate(descriptions[:20])]

    # Validate: ensure frame files exist in descriptions
    valid_frames = {d["frame"] for d in descriptions}
    validated_scenes = []
    t = 0.0
    for scene in scenes:
        ff = scene.get("frame_file", "")
        if ff in valid_frames:
            scene["start_time"] = t
            dur = scene.get("duration", 4)
            scene["duration"] = max(2, min(dur, 8))  # clamp 2-8s
            t += scene["duration"]
            validated_scenes.append(scene)

    if not validated_scenes:
        logger.warning("No valid scenes after validation, using all described frames")
        for i, d in enumerate(descriptions[:20]):
            validated_scenes.append({
                "frame_file": d["frame"],
                "start_time": i * 4,
                "duration": 4,
                "caption": "",
            })

    plan = {
        "total_duration": sum(s["duration"] for s in validated_scenes),
        "scene_count": len(validated_scenes),
        "scenes": validated_scenes,
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    logger.info("Wrote montage plan (%d scenes, %.0fs) -> %s",
                plan["scene_count"], plan["total_duration"], out)
    return str(out)


# ---------------------------------------------------------------------------
# Stage 4: Assemble montage via ffmpeg
# ---------------------------------------------------------------------------

def assemble_montage(
    montage_plan_path: str,
    frames_dir: str,
    output_path: str,
) -> str:
    """
    Assemble montage.mp4 from the montage plan using ffmpeg.

    Each frame becomes a still-image clip with optional caption overlay,
    then all clips are concatenated.

    Returns:
        Path to montage.mp4
    """
    with open(montage_plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    scenes = plan["scenes"]
    if not scenes:
        raise ValueError("Montage plan has no scenes")

    fdir = Path(frames_dir)
    out_dir = Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Create temp dir for intermediate clips
    tmp_dir = out_dir / "_montage_tmp"
    tmp_dir.mkdir(exist_ok=True)

    clip_files = []

    for i, scene in enumerate(scenes):
        frame_file = fdir / scene["frame_file"]
        if not frame_file.exists():
            logger.warning("Frame not found, skipping: %s", frame_file)
            continue

        duration = scene.get("duration", 4)
        caption = scene.get("caption", "")
        clip_path = str(tmp_dir / f"scene_{i:03d}.mp4")

        # Build ffmpeg command: still image -> video clip
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(frame_file),
            "-t", str(duration),
            "-r", "24",
            "-pix_fmt", "yuv420p",
        ]

        # Add caption overlay if present
        if caption:
            # Escape special characters for drawtext
            safe_caption = caption.replace("'", "\\'").replace(":", "\\:")
            cmd.extend([
                "-vf", (
                    f"drawtext=text='{safe_caption}'"
                    ":fontsize=24:fontcolor=white:borderw=2:bordercolor=black"
                    ":x=(w-text_w)/2:y=h-50"
                ),
            ])

        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            clip_path,
        ])

        result = _run_ffmpeg(cmd, timeout=60)
        if result.returncode != 0:
            logger.warning("Failed to create clip %d: %s", i, result.stderr[:200])
            continue

        clip_files.append(clip_path)

    if not clip_files:
        raise RuntimeError("No clips were created — cannot assemble montage")

    # Write concat list (short_builder.py pattern)
    concat_file = str(tmp_dir / "concat_list.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for cf in clip_files:
            safe_path = Path(cf).resolve().as_posix()
            f.write(f"file '{safe_path}'\n")

    # Concatenate all clips
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path,
    ]

    logger.info("Assembling %d clips -> %s", len(clip_files), output_path)
    result = _run_ffmpeg(cmd, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr[:300]}")

    size_mb = Path(output_path).stat().st_size / 1e6
    logger.info("Montage complete: %s (%.1f MB)", output_path, size_mb)

    # Cleanup temp clips
    for cf in clip_files:
        try:
            os.unlink(cf)
        except OSError:
            pass
    try:
        os.unlink(concat_file)
        tmp_dir.rmdir()
    except OSError:
        pass

    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Story Pipeline: frames -> descriptions -> narrative -> montage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python tools/story_pipeline.py --frames-dir output/video_pipeline/recording/frames\n'
            '  python tools/story_pipeline.py --video recording.mp4 --fps 2\n'
            '  python tools/story_pipeline.py --frames-dir ... --skip-describe\n'
            '  python tools/story_pipeline.py --frames-dir ... --skip-montage\n'
        ),
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", help="Path to video file or YouTube URL (runs video_pipeline first)")
    source.add_argument("--frames-dir", help="Path to pre-extracted frames directory")

    parser.add_argument("--fps", type=float, default=2, help="FPS for extraction when using --video (default: 2)")
    parser.add_argument("--output", "-o", default="./output/story_pipeline", help="Output directory")
    parser.add_argument("--sample-rate", type=int, default=5, help="Describe every Nth frame (default: 5)")
    parser.add_argument("--skip-describe", action="store_true", help="Reuse existing descriptions.json")
    parser.add_argument("--skip-montage", action="store_true", help="Stop after narrative (no video assembly)")

    args = parser.parse_args()

    api_key = check_prerequisites()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve frames directory
    if args.video:
        # Run video_pipeline to extract frames first
        logger.info("Extracting frames from %s ...", args.video)
        # Import sibling module
        sys.path.insert(0, str(Path(__file__).parent))
        from video_pipeline import extract_frames, check_ffmpeg
        check_ffmpeg()
        result = extract_frames(args.video, fps=args.fps)
        frames_dir = result["output_dir"]
        logger.info("Extracted %d frames -> %s", result["count"], frames_dir)
    else:
        frames_dir = args.frames_dir
        if not Path(frames_dir).is_dir():
            logger.error("Frames directory not found: %s", frames_dir)
            sys.exit(1)

    # Stage 1: Describe
    desc_path = str(out_dir / "descriptions.json")
    if args.skip_describe:
        if not Path(desc_path).exists():
            logger.error("--skip-describe but %s not found", desc_path)
            sys.exit(1)
        logger.info("Skipping describe (using cached %s)", desc_path)
    else:
        desc_path = describe_frames(frames_dir, desc_path, sample_rate=args.sample_rate, api_key=api_key)

    # Stage 2: Narrative
    narrative_path = str(out_dir / "story_narrative.md")
    narrative_path = generate_narrative(desc_path, narrative_path, api_key=api_key)

    # Stage 3: Montage plan
    plan_path = str(out_dir / "montage_plan.json")
    plan_path = build_montage_plan(desc_path, narrative_path, plan_path, api_key=api_key)

    if args.skip_montage:
        logger.info("Skipping montage assembly (--skip-montage)")
    else:
        # Stage 4: Assemble
        montage_path = str(out_dir / "montage.mp4")
        assemble_montage(plan_path, frames_dir, montage_path)

    # Summary
    print(f"\n{'='*50}")
    print(f"  Story Pipeline Complete")
    print(f"{'='*50}")
    print(f"  Frames:      {frames_dir}")
    print(f"  Descriptions: {desc_path}")
    print(f"  Narrative:    {narrative_path}")
    print(f"  Plan:         {plan_path}")
    if not args.skip_montage:
        print(f"  Montage:      {out_dir / 'montage.mp4'}")
    print()


if __name__ == "__main__":
    main()
