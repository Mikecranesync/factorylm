#!/usr/bin/env python3
"""
Factory I/O Screen Capture for Cosmos Cookoff
==============================================
Records Factory I/O window as MP4 clips at 4 FPS (matches Cosmos R2 training).

Usage:
    python cookoff/capture_fio.py record --duration 15 --label normal
    python cookoff/capture_fio.py record --duration 30 --label box_jam
    python cookoff/capture_fio.py screenshot --label snapshot_01
    python cookoff/capture_fio.py session --chunk-duration 8
    python cookoff/capture_fio.py stop
    python cookoff/capture_fio.py auto --scenarios normal,jam,stop --duration 20

Outputs to cookoff/clips/ as labeled MP4/PNG files.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import mss
import mss.tools
import numpy as np
import pygetwindow as gw

# Add repo root to path for imports
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

CLIPS_DIR = REPO_ROOT / "cookoff" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FPS = 4
FRAME_INTERVAL = 1.0 / TARGET_FPS

STOP_FILE = CLIPS_DIR / ".stop_recording"


def focus_factoryio():
    """Bring the Factory I/O window to the foreground.

    Returns the window object, or None if the window is not found.
    """
    try:
        windows = gw.getWindowsWithTitle("Factory IO")
        if not windows:
            # Try alternate title with hyphen
            windows = gw.getWindowsWithTitle("Factory I/O")
        if not windows:
            print("WARNING: Factory I/O window not found -- capturing whatever is on screen")
            return None
        win = windows[0]
        if win.isMinimized:
            win.restore()
            time.sleep(0.3)
        win.activate()
        time.sleep(0.5)
        return win
    except Exception as e:
        print(f"WARNING: Could not focus Factory I/O window: {e}")
        return None


def capture_clip(
    duration_seconds: float = 8,
    fps: int = TARGET_FPS,
    label: str = "clip",
    monitor_index: int = 1,
) -> Path:
    """Record a short MP4 clip of Factory I/O for Cosmos R2.

    Uses OpenCV VideoWriter (mp4v codec) for direct frame-to-MP4 encoding
    without needing ffmpeg.
    """
    focus_factoryio()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = CLIPS_DIR / f"{label}_{timestamp}.mp4"

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        width, height = monitor["width"], monitor["height"]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        frame_count = int(duration_seconds * fps)
        interval = 1.0 / fps

        print(f"Recording: {duration_seconds}s at {fps} FPS ({frame_count} frames, {width}x{height})")

        for i in range(frame_count):
            t0 = time.perf_counter()
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            out.write(frame)

            if i % fps == 0:
                elapsed_s = i / fps
                print(f"  {elapsed_s:.0f}s / {duration_seconds:.0f}s ({i}/{frame_count} frames)")

            elapsed = time.perf_counter() - t0
            time.sleep(max(0, interval - elapsed))

        out.release()

    file_size = output_path.stat().st_size / (1024 * 1024)
    print(f"Clip saved: {output_path} ({duration_seconds}s @ {fps}fps, {file_size:.1f} MB)")
    return output_path


def record_session(
    fps: int = TARGET_FPS,
    label: str = "session",
    monitor_index: int = 1,
    chunk_duration: float = 8,
) -> list[Path]:
    """Record Factory IO as rolling 8s chunks until stop file appears.

    Each chunk is a complete MP4 -- crash-safe, no data loss.
    Stop by creating: cookoff/clips/.stop_recording
    """
    # Clean up any stale stop file
    STOP_FILE.unlink(missing_ok=True)

    focus_factoryio()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    session_dir = CLIPS_DIR / f"{label}_{timestamp}"
    session_dir.mkdir(parents=True, exist_ok=True)

    frames_per_chunk = int(chunk_duration * fps)
    interval = 1.0 / fps
    chunk_paths: list[Path] = []
    chunk_idx = 0

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        width, height = monitor["width"], monitor["height"]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        print(f"Recording session: {width}x{height} @ {fps} FPS, {chunk_duration}s chunks")
        print(f"Output: {session_dir}")
        print(f"To stop: create {STOP_FILE}\n")

        try:
            while not STOP_FILE.exists():
                # Start new chunk
                chunk_path = session_dir / f"chunk_{chunk_idx:03d}.mp4"
                out = cv2.VideoWriter(str(chunk_path), fourcc, fps, (width, height))

                for frame_i in range(frames_per_chunk):
                    t0 = time.perf_counter()
                    img = np.array(sct.grab(monitor))
                    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    out.write(frame)
                    elapsed = time.perf_counter() - t0
                    time.sleep(max(0, interval - elapsed))

                out.release()  # chunk is now a valid MP4
                chunk_paths.append(chunk_path)

                elapsed_total = (chunk_idx + 1) * chunk_duration
                size_mb = chunk_path.stat().st_size / (1024 * 1024)
                print(f"  Chunk {chunk_idx}: {elapsed_total:.0f}s ({size_mb:.1f} MB)")
                chunk_idx += 1

        except KeyboardInterrupt:
            pass

    # Clean up stop file
    STOP_FILE.unlink(missing_ok=True)

    total_s = len(chunk_paths) * chunk_duration
    print(f"\nSession complete: {len(chunk_paths)} chunks, {total_s:.0f}s total")
    print(f"Chunks in: {session_dir}")
    return chunk_paths


def stop_recording():
    """Signal a running record_session() to stop."""
    STOP_FILE.touch()
    print(f"Stop signal sent: {STOP_FILE}")


def chunk_session(video_path: Path, chunk_duration: float = 8, output_dir: Path | None = None) -> list[dict]:
    """Split an MP4 into fixed-length chunks using OpenCV (no ffmpeg needed).

    Returns list of chunk metadata dicts with keys:
        chunk_file, start_time, end_time, duration
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: Cannot open {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or TARGET_FPS
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_duration = total_frames / fps

    if output_dir is None:
        output_dir = CLIPS_DIR / "chunks"
    output_dir.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    frames_per_chunk = int(chunk_duration * fps)
    chunks = []
    chunk_idx = 0
    frame_num = 0

    print(f"Chunking {video_path.name}: {total_duration:.1f}s total, {chunk_duration}s per chunk, {fps} FPS")

    while True:
        start_time = chunk_idx * chunk_duration
        if start_time >= total_duration:
            break

        # Skip tiny tail chunks (< 3s)
        remaining = total_duration - start_time
        if remaining < 3:
            break

        chunk_path = output_dir / f"{video_path.stem}_chunk{chunk_idx:03d}.mp4"
        out = cv2.VideoWriter(str(chunk_path), fourcc, fps, (width, height))

        frames_written = 0
        for _ in range(frames_per_chunk):
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
            frames_written += 1
            frame_num += 1

        out.release()

        if frames_written > 0:
            end_time = start_time + (frames_written / fps)
            chunks.append({
                "chunk_file": str(chunk_path),
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "duration": round(frames_written / fps, 2),
            })
            print(f"  Chunk {chunk_idx+1}: {start_time:.0f}s-{end_time:.0f}s ({frames_written} frames)")

        chunk_idx += 1

    cap.release()
    print(f"Done: {len(chunks)} chunks created in {output_dir}")
    return chunks


def capture_screenshot(label: str = "screenshot", monitor_index: int = 1) -> Path:
    """Capture a single screenshot and save as PNG."""
    focus_factoryio()
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

    # Session command (rolling chunks until stop file)
    sess = subparsers.add_parser("session", help="Record rolling chunks until stop file")
    sess.add_argument("--label", default="session", help="Label for the session")
    sess.add_argument("--fps", type=int, default=TARGET_FPS, help="Frames per second")
    sess.add_argument("--monitor", type=int, default=1, help="Monitor index (1=primary)")
    sess.add_argument("--chunk-duration", type=float, default=8, help="Seconds per chunk")

    # Stop command
    subparsers.add_parser("stop", help="Signal a running session to stop")

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
    elif args.command == "session":
        record_session(fps=args.fps, label=args.label, monitor_index=args.monitor, chunk_duration=args.chunk_duration)
    elif args.command == "stop":
        stop_recording()
    elif args.command == "auto":
        scenarios = [s.strip() for s in args.scenarios.split(",")]
        record_scenarios(scenarios, duration=args.duration)


if __name__ == "__main__":
    main()
