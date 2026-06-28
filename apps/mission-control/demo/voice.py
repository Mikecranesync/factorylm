"""
Mission Control Demo — Voice Generator

Reads a script.md, extracts narration text per segment,
generates per-segment audio files, and concatenates into full_narration.mp3.

Usage:
    # Full walkthrough (legacy):
    TTS_PROVIDER=macos python demo/voice.py

    # Single tab promo:
    TTS_PROVIDER=macos python demo/voice.py --tab 01_chat_relay

Env vars:
    TTS_PROVIDER          elevenlabs | openai | macos  (default: macos)
    ELEVENLABS_API_KEY    required for elevenlabs
    OPENAI_API_KEY        required for openai
    ELEVENLABS_VOICE_ID   optional (default: Rachel)
"""

import argparse
import os
import re
import sys
import subprocess
import json
from pathlib import Path

DEMO_DIR = Path(__file__).parent
SCRIPT_PATH = DEMO_DIR / "script.md"
AUDIO_DIR = DEMO_DIR / "audio"
TIMECODES_PATH = DEMO_DIR / "timecodes.json"

AUDIO_DIR.mkdir(exist_ok=True)

PROVIDER = os.environ.get("TTS_PROVIDER", "macos").lower()


# ---------------------------------------------------------------------------
# Script parser
# ---------------------------------------------------------------------------

def parse_segments(path):
    """Return list of {t, narration} dicts from script.md."""
    segments = []
    pattern = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\]\s+\[[^\]]+\]\s+(.+)$')
    for line in path.read_text().splitlines():
        m = pattern.match(line)
        if not m:
            continue
        ts, narration = m.group(1), m.group(2).strip()
        if narration == "END" or "[END]" in line:
            continue
        h, mn, s = map(int, ts.split(":"))
        t = h * 3600 + mn * 60 + s
        segments.append({"ts": ts, "t": t, "narration": narration})
    return segments


# ---------------------------------------------------------------------------
# TTS backends
# ---------------------------------------------------------------------------

def generate_elevenlabs(text, out_path):
    try:
        import requests
    except ImportError:
        sys.exit("Install requests: pip install requests")

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("Set ELEVENLABS_API_KEY env var")

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    resp = requests.post(
        url,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=30,
    )
    resp.raise_for_status()

    # ElevenLabs returns mp3 directly
    out_path.with_suffix(".mp3").write_bytes(resp.content)
    return out_path.with_suffix(".mp3")


def generate_openai(text, out_path):
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("Install openai: pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Set OPENAI_API_KEY env var")

    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice="onyx",
        input=text,
    )
    mp3_path = out_path.with_suffix(".mp3")
    response.stream_to_file(str(mp3_path))
    return mp3_path


def generate_macos(text, out_path):
    """Use macOS say command — no API key required."""
    aiff_path = out_path.with_suffix(".aiff")
    mp3_path = out_path.with_suffix(".mp3")

    subprocess.run(
        ["say", "-v", "Samantha", "-r", "165", "-o", str(aiff_path), text],
        check=True,
    )

    # Convert aiff → mp3 via ffmpeg
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(aiff_path), "-q:a", "2", str(mp3_path)],
        check=True,
        capture_output=True,
    )
    aiff_path.unlink(missing_ok=True)
    return mp3_path


GENERATORS = {
    "elevenlabs": generate_elevenlabs,
    "openai": generate_openai,
    "macos": generate_macos,
}


# ---------------------------------------------------------------------------
# Concatenation
# ---------------------------------------------------------------------------

def concatenate_segments(mp3_paths, out_path):
    """Use ffmpeg concat demuxer to join segments in order."""
    list_path = AUDIO_DIR / "concat_list.txt"
    list_path.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in mp3_paths)
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(out_path),
        ],
        check=True,
    )
    list_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Mission Control Voice Generator")
    parser.add_argument("--tab", help="Tab slug (e.g. 01_chat_relay). Omit for full walkthrough script.")
    args = parser.parse_args()

    if args.tab:
        script_path = DEMO_DIR / "tabs" / args.tab / "script.md"
        audio_dir = DEMO_DIR / "tabs" / args.tab / "audio"
    else:
        script_path = SCRIPT_PATH
        audio_dir = AUDIO_DIR

    audio_dir.mkdir(parents=True, exist_ok=True)

    if not script_path.exists():
        sys.exit(f"Script not found: {script_path}")

    if PROVIDER not in GENERATORS:
        sys.exit(f"Unknown TTS_PROVIDER '{PROVIDER}'. Choose: {', '.join(GENERATORS)}")

    generate = GENERATORS[PROVIDER]
    segments = parse_segments(script_path)

    label = args.tab or "full walkthrough"
    print(f"\nMission Control Demo — Voice Generator")
    print(f"Provider : {PROVIDER}")
    print(f"Tab      : {label}")
    print(f"Segments : {len(segments)}")
    print(f"Output   : {audio_dir}/\n")

    mp3_paths = []

    for i, seg in enumerate(segments):
        num = str(i + 1).zfill(3)
        stem = audio_dir / f"segment_{num}"
        mp3_path = stem.with_suffix(".mp3")

        if mp3_path.exists():
            print(f"  [{num}] SKIP (exists): {mp3_path.name}")
            mp3_paths.append(mp3_path)
            continue

        print(f"  [{num}] {seg['ts']} — {seg['narration'][:60]}…")
        try:
            result = generate(seg["narration"], stem)
            mp3_paths.append(result)
        except Exception as e:
            print(f"    ERROR: {e}")
            sys.exit(1)

    print(f"\nConcatenating {len(mp3_paths)} segments…")
    full_path = audio_dir / "full_narration.mp3"
    concatenate_segments(mp3_paths, full_path)

    next_cmd = (f"bash demo/sync_tab.sh {args.tab}" if args.tab else "bash demo/sync.sh")
    print(f"Done → {full_path}")
    print(f"\nNext step: {next_cmd}")


if __name__ == "__main__":
    main()
