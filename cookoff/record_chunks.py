#!/usr/bin/env python3
"""
Factory I/O Chunk Recorder — Video + PLC Snapshots for Cosmos R2
================================================================
Records 15-second MP4 video chunks of Factory I/O at 4 FPS with
synchronized Modbus PLC tag snapshots. Produces paired files
(MP4 + JSON) that the diagnosis engine can consume directly.

Usage:
    python cookoff/record_chunks.py --label sorting --chunks 2
    python cookoff/record_chunks.py --label test --duration 10 --chunks 5
    python cookoff/record_chunks.py  # runs continuously until Ctrl+C

Requires: mss, cv2, numpy, pymodbus (all installed)
"""

import argparse
import datetime
import json
import signal
import sys
import time
from pathlib import Path

import cv2
import mss
import numpy as np
from pymodbus.client import ModbusTcpClient

REPO_ROOT = Path(__file__).parent.parent
CLIPS_DIR = REPO_ROOT / "cookoff" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# Matches modbus_server.py I/O map
SENSOR_NAMES = [
    "high_sensor", "low_sensor", "pallet_sensor", "loaded",
    "at_left_entry", "at_left_exit", "at_right_entry", "at_right_exit",
    "start_button", "reset_button", "stop_button", "e_stop",
    "auto_mode", "fio_running",
]

ACTUATOR_NAMES = [
    "conveyor_entry", "load", "unload", "transfer_left", "transfer_right",
    "conveyor_left", "conveyor_right", "start_light", "reset_light", "stop_light",
]

_stop = False


def _handle_sigint(sig, frame):
    global _stop
    _stop = True


def snapshot_plc(host: str, port: int) -> dict | None:
    """Read all Modbus tags from the running server. Returns None on failure."""
    client = ModbusTcpClient(host, port=port, timeout=2)
    if not client.connect():
        return None
    try:
        tags = {}
        # Sensors: FC1 (coils) addr 0-13 — FIO writes here
        result = client.read_coils(address=0, count=len(SENSOR_NAMES))
        if not result.isError():
            for i, name in enumerate(SENSOR_NAMES):
                tags[name] = bool(result.bits[i])
        # Actuators: FC2 (discrete inputs) addr 0-9 — FIO reads here
        result = client.read_discrete_inputs(address=0, count=len(ACTUATOR_NAMES))
        if not result.isError():
            for i, name in enumerate(ACTUATOR_NAMES):
                tags[name] = bool(result.bits[i])
        tags["_ts"] = datetime.datetime.now().isoformat()
        return tags
    finally:
        client.close()


def record_chunk(
    chunk_num: int,
    label: str,
    duration: float,
    fps: int,
    monitor_index: int,
    plc_host: str,
    plc_port: int,
) -> tuple[Path, Path] | None:
    """Record one video chunk with PLC snapshots. Returns (mp4_path, json_path)."""
    global _stop
    tag = f"chunk_{chunk_num:03d}_{label}"
    mp4_path = CLIPS_DIR / f"{tag}.mp4"
    json_path = CLIPS_DIR / f"{tag}.json"
    total_frames = int(duration * fps)
    frame_interval = 1.0 / fps

    # PLC snapshot at start
    plc_start = snapshot_plc(plc_host, plc_port)
    ts_start = datetime.datetime.now().isoformat()

    print(f"  Recording {tag} ({duration}s, {total_frames} frames)...")

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        # Grab one frame to get dimensions
        sample = np.array(sct.grab(monitor))
        h, w = sample.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(mp4_path), fourcc, fps, (w, h))

        for i in range(total_frames):
            if _stop:
                break
            t0 = time.perf_counter()
            frame = np.array(sct.grab(monitor))
            # mss gives BGRA, cv2 wants BGR
            writer.write(frame[:, :, :3])
            elapsed = time.perf_counter() - t0
            sleep = frame_interval - elapsed
            if sleep > 0:
                time.sleep(sleep)

        actual_frames = min(i + 1, total_frames) if not _stop else i
        writer.release()

    # PLC snapshot at end
    plc_end = snapshot_plc(plc_host, plc_port)
    ts_end = datetime.datetime.now().isoformat()

    # Compute changes
    changes = []
    if plc_start and plc_end:
        for key in plc_start:
            if key.startswith("_"):
                continue
            if plc_start[key] != plc_end.get(key):
                changes.append(f"{key}: {plc_start[key]}->{plc_end.get(key)}")

    # Strip internal fields for output
    def clean(d):
        if d is None:
            return None
        return {k: v for k, v in d.items() if not k.startswith("_")}

    meta = {
        "chunk": chunk_num,
        "label": label,
        "ts_start": ts_start,
        "ts_end": ts_end,
        "video_file": mp4_path.name,
        "plc_start": clean(plc_start),
        "plc_end": clean(plc_end),
        "plc_changes": changes,
        "duration_s": duration,
        "frames": actual_frames,
        "fps": fps,
    }
    json_path.write_text(json.dumps(meta, indent=2))

    size_mb = mp4_path.stat().st_size / (1024 * 1024)
    print(f"  Saved: {mp4_path.name} ({size_mb:.1f} MB) + {json_path.name}")
    if changes:
        print(f"  PLC changes: {', '.join(changes)}")
    elif plc_start is None:
        print(f"  PLC: not connected (video-only)")
    else:
        print(f"  PLC: no changes during chunk")

    return mp4_path, json_path


def main():
    parser = argparse.ArgumentParser(description="Record Factory I/O chunks for Cosmos R2")
    parser.add_argument("--label", default="sorting", help="Label for chunk files")
    parser.add_argument("--duration", type=float, default=15.0, help="Seconds per chunk")
    parser.add_argument("--fps", type=int, default=4, help="Frames per second")
    parser.add_argument("--chunks", type=int, default=0, help="Number of chunks (0=infinite)")
    parser.add_argument("--monitor", type=int, default=1, help="Monitor index (1=primary)")
    parser.add_argument("--host", default="127.0.0.1", help="Modbus server host")
    parser.add_argument("--port", type=int, default=5020, help="Modbus server port")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_sigint)

    max_chunks = args.chunks if args.chunks > 0 else float("inf")
    print(f"Factory I/O Chunk Recorder")
    print(f"{'='*50}")
    print(f"Label: {args.label} | Duration: {args.duration}s | FPS: {args.fps}")
    print(f"Modbus: {args.host}:{args.port}")
    print(f"Chunks: {'infinite (Ctrl+C to stop)' if args.chunks == 0 else args.chunks}")
    print(f"Output: {CLIPS_DIR}")
    print(f"{'='*50}")

    # Test PLC connection
    test = snapshot_plc(args.host, args.port)
    if test:
        active = [k for k, v in test.items() if not k.startswith("_") and v]
        print(f"PLC connected — active tags: {active or 'none'}")
    else:
        print(f"PLC not reachable at {args.host}:{args.port} — recording video only")
    print()

    chunk_num = 0
    recorded = []
    while chunk_num < max_chunks and not _stop:
        chunk_num += 1
        result = record_chunk(
            chunk_num, args.label, args.duration, args.fps,
            args.monitor, args.host, args.port,
        )
        if result:
            recorded.append(result)

    print(f"\n{'='*50}")
    print(f"Recorded {len(recorded)} chunks")

    if recorded:
        mp4, js = recorded[0]
        print(f"\nRun diagnosis on first chunk:")
        print(f"  python cookoff/diagnosis_engine.py --video {mp4} --plc-json {js}")


if __name__ == "__main__":
    main()
