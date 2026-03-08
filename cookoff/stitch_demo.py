#!/usr/bin/env python3
"""Stitch Factory I/O clips into a 2-3 minute Cosmos Cookoff demo video."""

import cv2
import numpy as np
from pathlib import Path

REPO = Path(__file__).parent.parent
OUT = REPO / "cookoff" / "clips" / "cosmos_cookoff_demo.mp4"
W, H, FPS = 1920, 1080, 30


def make_title(text: str, subtitle: str = "", duration_s: float = 3.0) -> list[np.ndarray]:
    """Generate title card frames (white text on dark background)."""
    frames = []
    for _ in range(int(duration_s * FPS)):
        img = np.zeros((H, W, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)  # dark gray

        # Main title
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.8
        thick = 3
        (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
        x = (W - tw) // 2
        y = (H - th) // 2 if not subtitle else (H // 2 - 40)
        cv2.putText(img, text, (x, y), font, scale, (255, 255, 255), thick, cv2.LINE_AA)

        # Subtitle
        if subtitle:
            scale2 = 1.0
            (sw, sh), _ = cv2.getTextSize(subtitle, font, scale2, 2)
            cv2.putText(img, subtitle, ((W - sw) // 2, y + th + 40),
                        font, scale2, (100, 200, 255), 2, cv2.LINE_AA)

        frames.append(img)
    return frames


def load_video(path: str | Path, target_fps: int = FPS) -> list[np.ndarray]:
    """Load video frames, resize to target resolution, adjust to target FPS."""
    cap = cv2.VideoCapture(str(path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 4
    ratio = target_fps / src_fps  # e.g. 30/4 = 7.5 means repeat each frame ~7x

    frames = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        resized = cv2.resize(frame, (W, H))
        # Duplicate frames to match target FPS
        count = int((idx + 1) * ratio) - int(idx * ratio)
        frames.extend([resized] * count)
        idx += 1
    cap.release()
    return frames


def main():
    WK = REPO / ".claude" / "worktrees" / "feat-open-brain" / "cookoff" / "clips"

    sections = []

    # 1. Title
    sections.append(("title", make_title(
        "FactoryLM Vision",
        "Cosmos R2 Factory Diagnostics Demo", 4.0)))

    # 2. Factory I/O overview
    sections.append(("title", make_title(
        "Factory I/O Sorting Simulation",
        "Conveyor belt with height-based sorting logic", 2.5)))

    conv = REPO / "demos" / "conveyor_beginnings.mp4"
    if conv.exists():
        sections.append(("video", load_video(conv)))

    # 3. Live PLC + capture
    sections.append(("title", make_title(
        "Live PLC Data Capture",
        "Modbus TCP sensors + actuators synchronized with video", 2.5)))

    # Pick a spread of clips showing different states
    clip_picks = [
        WK / "iter1_normal_20260305_104021.mp4",
        WK / "iter1_normal_20260305_104341.mp4",
        WK / "iter1_normal_20260305_104648.mp4",
        WK / "session_20260305_112437" / "chunk_000.mp4",
        WK / "session_20260305_112437" / "chunk_001.mp4",
        WK / "session_20260305_112437" / "chunk_002.mp4",
    ]
    for c in clip_picks:
        if c.exists():
            sections.append(("video", load_video(c)))

    # 4. Diagnosis
    sections.append(("title", make_title(
        "Cosmos Reason2 Diagnosis",
        "Video + PLC tags -> R2 multimodal reasoning -> fault report", 2.5)))

    diag_picks = [
        WK / "diag_000_20260305_115633.mp4",
        WK / "diag_000_20260305_121725.mp4",
        WK / "r00_c00_20260305_123803.mp4",
        WK / "r00_c01_20260305_123824.mp4",
        WK / "r01_c00_20260305_123950.mp4",
        WK / "r01_c01_20260305_124019.mp4",
        WK / "r02_c00_20260305_125747.mp4",
        WK / "r02_c01_20260305_125804.mp4",
    ]
    for c in diag_picks:
        if c.exists():
            sections.append(("video", load_video(c)))

    # 5. End card
    sections.append(("title", make_title(
        "FactoryLM",
        "Text your factory. AI tells you what's wrong.", 4.0)))

    # Write output
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(OUT), fourcc, FPS, (W, H))

    total = 0
    for label, frames in sections:
        print(f"  {label:6s} +{len(frames)/FPS:.1f}s ({len(frames)} frames)")
        total += len(frames)
        for f in frames:
            writer.write(f)

    writer.release()
    dur = total / FPS
    sz = OUT.stat().st_size / (1024 * 1024)
    print(f"\nOutput: {OUT}")
    print(f"Duration: {dur:.1f}s ({dur/60:.1f} min) | Size: {sz:.1f} MB")


if __name__ == "__main__":
    main()
