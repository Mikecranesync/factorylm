"""
Cosmos Video Analyzer — analyzes video clips via Cosmos Reason 2.

Polls Matrix API for clips with status='pending_analysis', analyzes each,
stores results, and marks highlights.

Usage:
    python video/cosmos_analyzer.py
    python video/cosmos_analyzer.py --matrix-url http://localhost:8000 --interval 10
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import httpx

from cosmos.client import CosmosClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

INTERESTING_THRESHOLD = int(os.getenv("VIDEO_INTERESTING_THRESHOLD", "60"))


def run_analyzer(
    matrix_url: str = "http://localhost:8000",
    interval: float = 10.0,
    threshold: int = INTERESTING_THRESHOLD,
) -> None:
    """Poll for pending clips and analyze them."""
    client = CosmosClient()
    logger.info(
        "Video analyzer started — matrix=%s interval=%.0fs threshold=%d",
        matrix_url, interval, threshold,
    )

    while True:
        try:
            resp = httpx.get(
                f"{matrix_url}/api/video/clips",
                params={"status": "pending_analysis", "limit": 10},
                timeout=10,
            )
            resp.raise_for_status()
            clips = resp.json()

            for clip in clips:
                clip_id = clip["id"]
                clip_file = clip.get("chunk_file", "")
                logger.info("Analyzing clip #%d: %s", clip_id, Path(clip_file).name if clip_file else "unknown")

                # Run Cosmos video analysis
                analysis = client.analyze_video(
                    video_path=clip_file,
                    context=f"Factory floor camera, clip from {clip.get('start_time', 0):.1f}s to {clip.get('end_time', 0):.1f}s",
                )

                # Determine if this is a highlight
                score = analysis.get("interesting_score", 0)
                new_status = "highlight" if score >= threshold else "analyzed"

                # Post analysis to Matrix
                post_resp = httpx.post(
                    f"{matrix_url}/api/video/analyses",
                    json={
                        "clip_id": clip_id,
                        "caption": analysis.get("caption", ""),
                        "key_events_json": analysis.get("key_events", []),
                        "interesting_score": score,
                        "cosmos_model": analysis.get("cosmos_model", "nvidia/cosmos-reason2"),
                    },
                    timeout=10,
                )
                post_resp.raise_for_status()

                # Update clip status
                httpx.patch(
                    f"{matrix_url}/api/video/clips/{clip_id}",
                    json={"status": new_status},
                    timeout=10,
                )

                logger.info(
                    "  %s clip #%d — score=%d caption=%s",
                    "★ HIGHLIGHT" if new_status == "highlight" else "✓ Analyzed",
                    clip_id, score, analysis.get("caption", "")[:60],
                )

        except httpx.ConnectError:
            logger.warning("Cannot reach Matrix API at %s", matrix_url)
        except Exception:
            logger.exception("Analyzer error")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Cosmos Video Analyzer")
    parser.add_argument("--matrix-url", default=os.getenv("MATRIX_URL", "http://localhost:8000"))
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--threshold", type=int, default=INTERESTING_THRESHOLD)
    args = parser.parse_args()

    try:
        run_analyzer(matrix_url=args.matrix_url, interval=args.interval, threshold=args.threshold)
    except KeyboardInterrupt:
        logger.info("Analyzer stopped.")


if __name__ == "__main__":
    main()
