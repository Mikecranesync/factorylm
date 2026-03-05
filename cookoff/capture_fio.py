#!/usr/bin/env python3
"""
Factory I/O Screen Capture for Cosmos Cookoff
==============================================
Records Factory I/O window as MP4 clips at 4 FPS (matches Cosmos R2 training).

Usage:
    python cookoff/capture_fio.py record --duration 15 --label normal
    python cookoff/capture_fio.py record --duration 30 --label box_jam
    python cookoff/capture_fio.py screenshot --label snapshot_01
    python cookoff/capture_fio.py auto --scenarios normal,jam,stop --duration 20

Outputs to cookoff/clips/ as labeled MP4/PNG files.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import mss
import mss.tools

# Add repo root to path for imports
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

CLIPS_DIR = REPO_ROOT / "cookoff" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FPS = 4
FRAME_INTERVAL = 1.0 / TARGET_FPS


def capture_screenshot(label: str = "screenshot", monitor_index: int = 1) -> Path:
    """Capture a single screenshot and save as PNG."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{timestamp}.png"
    output_path = CLIPS_DIR / filename

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)

    output_path.write_bytes(png_bytes)
    print(f"Screenshot saved: {output_path} ({screenshot.width}x{screenshot.height})")
    return output_path


def record_clip(
    duration: float = 15.0,
    label: str = "clip",
    monitor_index: int = 1,
    fps: int = TARGET_FPS,
) -> Path:
    """Record Factory I/O window as MP4 clip.

    Captures frames as PNGs then assembles with ffmpeg.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_name = f"{label}_{timestamp}"
    output_mp4 = CLIPS_DIR / f"{output_name}.mp4"
    frames_dir = CLIPS_DIR / f".frames_{output_name}"
    frames_dir.mkdir(exist_ok=True)

    frame_interval = 1.0 / fps
    total_frames = int(duration * fps)

    print(f"Recording: {duration}s at {fps} FPS ({total_frames} frames)")
    print(f"Output: {output_mp4}")

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]

        for i in range(total_frames):
            t_start = time.perf_counter()

            screenshot = sct.grab(monitor)
            frame_path = frames_dir / f"frame_{i:05d}.png"
            png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
            frame_path.write_bytes(png_bytes)

            # Print progress every second
            if i % fps == 0:
                elapsed = i / fps
                print(f"  {elapsed:.0f}s / {duration:.0f}s ({i}/{total_frames} frames)")

            # Maintain target FPS
            elapsed = time.perf_counter() - t_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    print(f"Capture complete. Encoding MP4...")

    # Assemble frames into MP4 with ffmpeg
    import subprocess

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        output_mp4,
    ]

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}")
        # Fallback: keep frames, no MP4
        print(f"Frames saved in: {frames_dir}")
        return frames_dir
    else:
        # Clean up frames
        import shutil
        shutil.rmtree(frames_dir)
        file_size = output_mp4.stat().st_size / (1024 * 1024)
        print(f"MP4 saved: {output_mp4} ({file_size:.1f} MB)")
        return output_mp4


def record_scenarios(scenarios: list[str], duration: float = 20.0):
    """Record multiple labeled scenarios with pause between each."""
    for i, scenario in enumerate(scenarios):
        print(f"\n{'='*60}")
        print(f"Scenario {i+1}/{len(scenarios)}: {scenario}")
        print(f"{'='*60}")
        print(f"Set up the '{scenario}' scenario in Factory I/O, then press Enter...")
        input()
        record_clip(duration=duration, label=scenario)
        print(f"Done with '{scenario}'.")


def main():
    parser = argparse.ArgumentParser(description="Factory I/O screen capture for Cosmos Cookoff")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Screenshot command
    ss = subparsers.add_parser("screenshot", help="Take a single screenshot")
    ss.add_argument("--label", default="screenshot", help="Label for the file")
    ss.add_argument("--monitor", type=int, default=1, help="Monitor index (1=primary)")

    # Record command
    rec = subparsers.add_parser("record", help="Record a video clip")
    rec.add_argument("--duration", type=float, default=15.0, help="Duration in seconds")
    rec.add_argument("--label", default="clip", help="Label for the file")
    rec.add_argument("--fps", type=int, default=TARGET_FPS, help="Frames per second")
    rec.add_argument("--monitor", type=int, default=1, help="Monitor index (1=primary)")

    # Auto command (multiple scenarios)
    auto = subparsers.add_parser("auto", help="Record multiple scenarios")
    auto.add_argument("--scenarios", default="normal,box_jam,conveyor_stop",
                       help="Comma-separated scenario labels")
    auto.add_argument("--duration", type=float, default=20.0, help="Duration per scenario")

    args = parser.parse_args()

    if args.command == "screenshot":
        capture_screenshot(label=args.label, monitor_index=args.monitor)
    elif args.command == "record":
        record_clip(duration=args.duration, label=args.label, fps=args.fps, monitor_index=args.monitor)
    elif args.command == "auto":
        scenarios = [s.strip() for s in args.scenarios.split(",")]
        record_scenarios(scenarios, duration=args.duration)


if __name__ == "__main__":
    main()
