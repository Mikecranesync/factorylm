"""
Highlight Selector — find the best video clips for demos and docs.

Usage:
    python video/highlight_selector.py --top 5
    python video/highlight_selector.py --date 2026-02-13 --event jam --top 10
    python video/highlight_selector.py --min-score 80
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import httpx

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def select_highlights(
    matrix_url: str = "http://localhost:8000",
    top: int = 10,
    date: str | None = None,
    event: str | None = None,
    min_score: int = 0,
) -> list[dict]:
    """Query Matrix API for highlight clips, filtered and ranked."""
    resp = httpx.get(
        f"{matrix_url}/api/video/clips",
        params={"status": "highlight", "limit": 100},
        timeout=10,
    )
    resp.raise_for_status()
    clips = resp.json()

    # Fetch analyses for each clip
    results = []
    for clip in clips:
        try:
            a_resp = httpx.get(
                f"{matrix_url}/api/video/analyses",
                params={"clip_id": clip["id"]},
                timeout=10,
            )
            a_resp.raise_for_status()
            analyses = a_resp.json()
            analysis = analyses[0] if analyses else {}
        except Exception:
            analysis = {}

        score = analysis.get("interesting_score", 0)
        caption = analysis.get("caption", "")

        # Apply filters
        if score < min_score:
            continue
        if date and not clip.get("timestamp", "").startswith(date):
            continue
        if event and event.lower() not in caption.lower():
            continue

        results.append({
            "clip_id": clip["id"],
            "file": clip.get("chunk_file", ""),
            "score": score,
            "caption": caption,
            "start_time": clip.get("start_time", 0),
            "end_time": clip.get("end_time", 0),
            "timestamp": clip.get("timestamp", ""),
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top]


def main():
    parser = argparse.ArgumentParser(description="Highlight Selector")
    parser.add_argument("--matrix-url", default=os.getenv("MATRIX_URL", "http://localhost:8000"))
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--date", type=str, default=None, help="Filter by date (YYYY-MM-DD)")
    parser.add_argument("--event", type=str, default=None, help="Filter by keyword in caption")
    parser.add_argument("--min-score", type=int, default=0, help="Minimum interesting score")
    args = parser.parse_args()

    try:
        results = select_highlights(
            matrix_url=args.matrix_url, top=args.top,
            date=args.date, event=args.event, min_score=args.min_score,
        )
    except httpx.ConnectError:
        logger.error("Cannot reach Matrix API at %s", args.matrix_url)
        return

    if not results:
        logger.info("No highlights found matching criteria.")
        return

    logger.info("Top %d highlights:\n", len(results))
    logger.info("%-6s %-5s %-50s %s", "Clip#", "Score", "Caption", "File")
    logger.info("-" * 120)
    for r in results:
        logger.info(
            "%-6d %-5d %-50s %s",
            r["clip_id"], r["score"], r["caption"][:50], r["file"],
        )

    # Also output as JSON for piping
    print("\n" + json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
