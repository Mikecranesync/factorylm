"""
Video Ingester — watches for new recordings and chunks them with ffmpeg.

Monitors a directory for new video files, splits them into 10-30 second
clips, stores metadata in Matrix DB, and queues clips for Cosmos analysis.

Usage:
    python video/ingester.py
    python video/ingester.py --input recordings/raw --chunk-duration 15
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        return 0.0


def chunk_video(
    video_path: Path,
    output_dir: Path,
    chunk_duration: int = 15,
) -> list[dict]:
    """Split a video into chunks using ffmpeg. Returns list of chunk metadata."""
    duration = get_video_duration(video_path)
    if duration <= 0:
        logger.warning("Cannot determine duration for %s", video_path)
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    video_id = f"{video_path.stem}_{uuid.uuid4().hex[:8]}"
    chunks = []
    start = 0.0

    while start < duration:
        end = min(start + chunk_duration, duration)
        if end - start < 3:  # Skip tiny tail chunks
            break

        chunk_name = f"{video_id}_t{int(start):04d}.mp4"
        chunk_path = output_dir / chunk_name

        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
            "-t", str(chunk_duration),
            "-c", "copy",  # Fast: no re-encoding
            "-avoid_negative_ts", "make_zero",
            str(chunk_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        except subprocess.CalledProcessError as e:
            # Fallback: re-encode if copy fails (e.g., keyframe alignment)
            cmd_reencode = [
                "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
                "-t", str(chunk_duration),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac",
                str(chunk_path),
            ]
            try:
                subprocess.run(cmd_reencode, capture_output=True, timeout=300, check=True)
            except subprocess.CalledProcessError:
                logger.error("Failed to chunk %s at t=%.1f", video_path, start)
                start = end
                continue

        chunks.append({
            "video_id": video_id,
            "source_file": str(video_path),
            "chunk_file": str(chunk_path),
            "start_time": round(start, 2),
            "end_time": round(end, 2),
            "duration": round(end - start, 2),
        })
        logger.info("  Chunk: %s (%.1f-%.1fs)", chunk_name, start, end)
        start = end

    return chunks


def register_clip(matrix_url: str, clip: dict) -> int | None:
    """POST clip metadata to Matrix API. Returns clip ID."""
    try:
        resp = httpx.post(
            f"{matrix_url}/api/video/clips",
            json={
                "video_id": clip["video_id"],
                "source_file": clip["source_file"],
                "chunk_file": clip["chunk_file"],
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "source_camera": "default",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("clip_id")
    except Exception as e:
        logger.warning("Failed to register clip: %s", e)
        return None


def run_ingester(
    input_dir: str = "recordings/raw",
    chunks_dir: str = "recordings/chunks",
    chunk_duration: int = 15,
    matrix_url: str = "http://localhost:8000",
    poll_interval: float = 5.0,
) -> None:
    """Watch input_dir for new videos, chunk them, and register with Matrix."""
    input_path = Path(input_dir)
    chunks_path = Path(chunks_dir)
    input_path.mkdir(parents=True, exist_ok=True)
    chunks_path.mkdir(parents=True, exist_ok=True)

    processed: set[str] = set()

    logger.info(
        "Video ingester started — watching %s, chunk_duration=%ds, posting to %s",
        input_path, chunk_duration, matrix_url,
    )

    while True:
        for f in input_path.iterdir():
            if f.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if str(f) in processed:
                continue
            # Wait for file to finish writing (check size stability)
            size1 = f.stat().st_size
            time.sleep(1)
            if f.exists() and f.stat().st_size == size1 and size1 > 0:
                logger.info("New video: %s (%.1f MB)", f.name, size1 / 1e6)
                chunks = chunk_video(f, chunks_path, chunk_duration)
                for c in chunks:
                    clip_id = register_clip(matrix_url, c)
                    if clip_id:
                        logger.info("  Registered clip #%d", clip_id)
                processed.add(str(f))
                logger.info("  Chunked into %d clips", len(chunks))

        time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Video Ingester")
    parser.add_argument("--input", default=os.getenv("VIDEO_INPUT_DIR", "recordings/raw"))
    parser.add_argument("--output", default=os.getenv("VIDEO_CHUNKS_DIR", "recordings/chunks"))
    parser.add_argument("--chunk-duration", type=int, default=15)
    parser.add_argument("--matrix-url", default=os.getenv("MATRIX_URL", "http://localhost:8000"))
    parser.add_argument("--poll", type=float, default=5.0)
    args = parser.parse_args()

    try:
        run_ingester(
            input_dir=args.input, chunks_dir=args.output,
            chunk_duration=args.chunk_duration,
            matrix_url=args.matrix_url, poll_interval=args.poll,
        )
    except KeyboardInterrupt:
        logger.info("Ingester stopped.")


if __name__ == "__main__":
    main()
