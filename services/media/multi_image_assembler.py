#!/usr/bin/env python3
"""
Multi-Image Video Assembler
===========================
Creates YouTube Shorts (9:16 vertical) from multiple images with:
- Ken Burns zoom effect per image
- Crossfade transitions between images
- Audio track overlay
- Auto-calculated timing based on audio duration

Fixes the issue where only ONE image was used instead of all provided images.
"""

import os
import sys
import json
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file in seconds using ffprobe."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            audio_path
        ], capture_output=True, text=True)

        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}")
        return 60.0  # Default to 60 seconds


def validate_images(images: List[str]) -> List[Path]:
    """Validate and return list of existing image paths."""
    valid = []
    for img in images:
        p = Path(img)
        if p.exists() and p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            valid.append(p)
        else:
            logger.warning(f"Invalid or missing image: {img}")
    return valid


def assemble_multi_image_video(
    images: List[str],
    audio_path: str,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    transition_duration: float = 0.5,
    zoom_amount: float = 0.1
) -> Dict[str, Any]:
    """
    Assemble multiple images into a vertical video with Ken Burns effect.

    Args:
        images: List of image file paths (3-10 recommended)
        audio_path: Path to audio file (MP3, WAV)
        output_path: Output video path (MP4)
        width: Output width (default 1080 for Shorts)
        height: Output height (default 1920 for Shorts)
        transition_duration: Seconds for crossfade between images
        zoom_amount: Ken Burns zoom factor (0.1 = 10% zoom)

    Returns:
        dict with success status, output path, and metadata
    """
    result = {
        "success": False,
        "output_path": None,
        "error": None,
        "metadata": {}
    }

    # Validate inputs
    valid_images = validate_images(images)
    if len(valid_images) < 2:
        result["error"] = f"Need at least 2 valid images, got {len(valid_images)}"
        return result

    if not Path(audio_path).exists():
        result["error"] = f"Audio file not found: {audio_path}"
        return result

    # Calculate timing
    audio_duration = get_audio_duration(audio_path)
    num_images = len(valid_images)

    # Account for transitions overlapping
    # Total = (per_image * n) - (transition * (n-1))
    # Solve for per_image: per_image = (total + transition * (n-1)) / n
    per_image_duration = (audio_duration + transition_duration * (num_images - 1)) / num_images
    fps = 30

    logger.info(f"Assembling {num_images} images over {audio_duration:.1f}s audio")
    logger.info(f"Per image: {per_image_duration:.2f}s, transition: {transition_duration}s")

    result["metadata"] = {
        "image_count": num_images,
        "audio_duration": audio_duration,
        "per_image_duration": per_image_duration,
        "output_resolution": f"{width}x{height}"
    }

    # Build FFmpeg command
    # Strategy: Use zoompan for each image, then xfade to chain them

    inputs = []
    filter_parts = []

    # Input streams for each image (looped for duration)
    for i, img in enumerate(valid_images):
        inputs.extend(["-loop", "1", "-t", str(per_image_duration), "-i", str(img)])

    # Add audio input
    audio_index = len(valid_images)
    inputs.extend(["-i", audio_path])

    # Build filter_complex
    # Step 1: Scale and apply zoompan to each image
    zoompan_outputs = []
    for i in range(num_images):
        # Zoompan: slow zoom from 100% to 100%+zoom_amount over duration
        # z='1+0.0003*on' zooms in slowly
        # s= output size
        # d= frames
        frames = int(per_image_duration * fps)
        zoom_rate = zoom_amount / frames

        # Scale image larger first so zoompan has room to crop
        scale_factor = 1.2  # 20% larger than output
        scaled_w = int(width * scale_factor)
        scaled_h = int(height * scale_factor)

        filter_parts.append(
            f"[{i}:v]scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase,"
            f"crop={scaled_w}:{scaled_h},"
            f"zoompan=z='1+{zoom_rate:.6f}*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={fps}[v{i}]"
        )
        zoompan_outputs.append(f"[v{i}]")

    # Step 2: Chain xfade transitions
    if num_images == 2:
        # Simple case: one transition
        offset = per_image_duration - transition_duration
        filter_parts.append(
            f"{zoompan_outputs[0]}{zoompan_outputs[1]}"
            f"xfade=transition=fade:duration={transition_duration}:offset={offset}[vout]"
        )
    else:
        # Chain multiple transitions
        current_output = zoompan_outputs[0]
        cumulative_offset = per_image_duration - transition_duration

        for i in range(1, num_images):
            next_input = zoompan_outputs[i]
            out_label = f"[vx{i}]" if i < num_images - 1 else "[vout]"

            filter_parts.append(
                f"{current_output}{next_input}"
                f"xfade=transition=fade:duration={transition_duration}:offset={cumulative_offset}{out_label}"
            )

            current_output = out_label
            cumulative_offset += per_image_duration - transition_duration

    # Combine all filters
    filter_complex = ";".join(filter_parts)

    # Build full command
    cmd = ["ffmpeg", "-y"]
    cmd.extend(inputs)
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", f"{audio_index}:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ])

    logger.info(f"Running FFmpeg with {len(valid_images)} images...")
    logger.debug(f"Filter complex: {filter_complex[:200]}...")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 min timeout
        )

        if proc.returncode == 0:
            output_file = Path(output_path)
            result["success"] = True
            result["output_path"] = str(output_file)
            result["metadata"]["file_size_mb"] = output_file.stat().st_size / (1024 * 1024)
            logger.info(f"Video created: {output_path} ({result['metadata']['file_size_mb']:.2f} MB)")
        else:
            result["error"] = proc.stderr[-1000:] if proc.stderr else "Unknown FFmpeg error"
            logger.error(f"FFmpeg failed: {result['error']}")

    except subprocess.TimeoutExpired:
        result["error"] = "FFmpeg timeout (10 min)"
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Assembly failed: {e}")

    return result


def assemble_shorts_video(
    images: List[str],
    audio_path: str,
    output_path: str
) -> Dict[str, Any]:
    """
    Convenience function for YouTube Shorts (1080x1920, 9:16).

    This is the main entry point for the Antfarm workflow.
    """
    return assemble_multi_image_video(
        images=images,
        audio_path=audio_path,
        output_path=output_path,
        width=1080,
        height=1920,
        transition_duration=0.5,
        zoom_amount=0.08  # 8% zoom over duration
    )


# CLI interface
if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.INFO
    )

    if len(sys.argv) < 4:
        print("Usage: python multi_image_assembler.py <output.mp4> <audio.mp3> <img1.jpg> <img2.jpg> ...")
        print("\nExample:")
        print("  python multi_image_assembler.py short.mp4 voice.mp3 plc1.jpg plc2.jpg plc3.jpg")
        sys.exit(1)

    output = sys.argv[1]
    audio = sys.argv[2]
    images = sys.argv[3:]

    print(f"Images: {images}")
    print(f"Audio: {audio}")
    print(f"Output: {output}")

    result = assemble_shorts_video(images, audio, output)

    if result["success"]:
        print(f"\n✅ Success! Video saved to: {result['output_path']}")
        print(f"   Size: {result['metadata'].get('file_size_mb', 0):.2f} MB")
    else:
        print(f"\n❌ Failed: {result['error']}")
        sys.exit(1)
