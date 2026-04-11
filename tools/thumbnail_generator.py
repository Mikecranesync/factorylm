#!/usr/bin/env python3
"""
Thumbnail Generator — YouTube Series Thumbnails
================================================
Auto-generates 1280×720 YouTube thumbnails per series template using Pillow.

Each series has:
  - Signature background color
  - Bold hook text (max 5 words — readable at 100px mobile width)
  - Optional background image (factory/PLC photo) with overlay
  - "FactoryLM" logo bug at bottom-left

Usage:
    python tools/thumbnail_generator.py \\
        --series before_it_breaks \\
        --text "VFD Fault E005 Fixed" \\
        --output output/thumbnails/vfd_e005.png

    python tools/thumbnail_generator.py --batch docs/gtm/CONTENT_CALENDAR_4W.md \\
        --output-dir output/thumbnails/

Requires: Pillow  (pip install Pillow)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("thumbnail-generator")

# Output spec
THUMB_WIDTH = 1280
THUMB_HEIGHT = 720

# Series color palette — matches REVIEW_CHECKLIST.md
SERIES_COLORS: dict[str, dict] = {
    "before_it_breaks": {
        "bg": "#1A0A00",
        "accent": "#F97316",
        "label": "BEFORE IT BREAKS",
    },
    "price_shock": {
        "bg": "#001A08",
        "accent": "#22C55E",
        "label": "$500K vs $30",
    },
    "inside_machine": {
        "bg": "#00081A",
        "accent": "#3B82F6",
        "label": "INSIDE THE MACHINE",
    },
    "live_diagnosis": {
        "bg": "#1A0000",
        "accent": "#EF4444",
        "label": "LIVE DIAGNOSIS",
    },
    "tech_stories": {
        "bg": "#0D0014",
        "accent": "#8B5CF6",
        "label": "TECH STORIES",
    },
    "off_the_grid": {
        "bg": "#0A0A0A",
        "accent": "#9CA3AF",
        "label": "OFF THE GRID",
    },
}

LOGO_TEXT = "FactoryLM"
LOGO_SUBTEXT = "factorylm.com"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def _load_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        return Image, ImageDraw, ImageFont, ImageFilter
    except ImportError:
        logger.error("Pillow not installed. Run: pip install Pillow")
        sys.exit(1)


def _get_font(size: int, bold: bool = False):
    Image, ImageDraw, ImageFont, ImageFilter = _load_pillow()
    # Try system fonts in order of preference
    candidates = []
    if bold:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "arial.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "arial.ttf",
        ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue

    # Fallback to PIL default (no size control)
    logger.warning("No TrueType font found — using PIL default font (quality will be lower)")
    return ImageFont.load_default()


def generate_thumbnail(
    series: str,
    hook_text: str,
    output_path: Path | str,
    bg_image: Path | str | None = None,
) -> Path:
    """
    Generate a 1280×720 YouTube thumbnail for the given series.

    Args:
        series: Series key from SERIES_COLORS (e.g. "before_it_breaks")
        hook_text: Up to 5 words of bold hook text
        output_path: Output PNG path
        bg_image: Optional background photo (will be darkened with series overlay)

    Returns:
        Path to the generated PNG.
    """
    Image, ImageDraw, ImageFont, ImageFilter = _load_pillow()

    if series not in SERIES_COLORS:
        raise ValueError(f"Unknown series '{series}'. Valid: {list(SERIES_COLORS)}")

    config = SERIES_COLORS[series]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Word count guard
    words = hook_text.split()
    if len(words) > 5:
        logger.warning(
            "Hook text '%s' is %d words — max 5 for readable thumbnail. Truncating.",
            hook_text, len(words),
        )
        hook_text = " ".join(words[:5])

    # === Base image ===
    if bg_image and Path(bg_image).exists():
        img = Image.open(bg_image).convert("RGB")
        img = img.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)
        # Darken and tint with series color
        bg_rgb = _hex_to_rgb(config["bg"])
        overlay = Image.new("RGBA", (THUMB_WIDTH, THUMB_HEIGHT), (*bg_rgb, 180))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay).convert("RGB")
    else:
        bg_rgb = _hex_to_rgb(config["bg"])
        img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), bg_rgb)

    draw = ImageDraw.Draw(img)
    accent_rgb = _hex_to_rgb(config["accent"])

    # === Accent stripe (left edge) ===
    draw.rectangle([(0, 0), (12, THUMB_HEIGHT)], fill=accent_rgb)

    # === Series label (top-left, small caps style) ===
    label_font = _get_font(32, bold=True)
    label_text = config["label"]
    draw.text((32, 40), label_text, font=label_font, fill=accent_rgb)

    # === Hook text (large, center) ===
    hook_font = _get_font(96, bold=True)

    # Word-wrap if needed (max 2 lines)
    words = hook_text.split()
    if len(words) <= 3:
        lines = [hook_text]
    else:
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]

    # Measure total text block height
    line_height = 110
    total_text_height = len(lines) * line_height
    start_y = (THUMB_HEIGHT - total_text_height) // 2 - 20  # slightly above center

    for i, line in enumerate(lines):
        # Measure line width for centering
        try:
            bbox = draw.textbbox((0, 0), line, font=hook_font)
            text_w = bbox[2] - bbox[0]
        except AttributeError:
            # Older Pillow fallback
            text_w, _ = draw.textsize(line, font=hook_font)

        x = (THUMB_WIDTH - text_w) // 2
        y = start_y + i * line_height

        # Shadow / outline (draw at offsets)
        shadow_offset = 3
        for dx in [-shadow_offset, 0, shadow_offset]:
            for dy in [-shadow_offset, 0, shadow_offset]:
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), line, font=hook_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=hook_font, fill=(255, 255, 255))

    # === Accent underline below hook text ===
    underline_y = start_y + len(lines) * line_height + 8
    draw.rectangle(
        [(THUMB_WIDTH // 4, underline_y), (THUMB_WIDTH * 3 // 4, underline_y + 6)],
        fill=accent_rgb,
    )

    # === Logo bug (bottom-left) ===
    logo_font = _get_font(36, bold=True)
    sub_font = _get_font(24, bold=False)

    logo_x = 32
    logo_y = THUMB_HEIGHT - 90

    # Logo background pill
    try:
        logo_bbox = draw.textbbox((0, 0), LOGO_TEXT, font=logo_font)
        logo_w = logo_bbox[2] - logo_bbox[0]
    except AttributeError:
        logo_w, _ = draw.textsize(LOGO_TEXT, font=logo_font)

    draw.rectangle(
        [(logo_x - 8, logo_y - 4), (logo_x + logo_w + 8, logo_y + 46)],
        fill=(*accent_rgb, 200),  # type: ignore
    )
    draw.text((logo_x, logo_y), LOGO_TEXT, font=logo_font, fill=(255, 255, 255))
    draw.text((logo_x, logo_y + 38), LOGO_SUBTEXT, font=sub_font, fill=(255, 255, 255, 180))  # type: ignore

    # === Save ===
    img.save(str(output_path), "PNG", optimize=True)
    logger.info("Generated thumbnail: %s (%s)", output_path.name, series)
    return output_path


def batch_generate(
    calendar: list[dict],
    output_dir: Path | str,
) -> list[Path]:
    """
    Generate thumbnails for a batch of calendar entries.

    Each entry must have:
        series (str): series key
        title (str): episode title → used as hook text
        output_name (str, optional): filename stem

    Returns list of generated Paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for i, entry in enumerate(calendar):
        series = entry.get("series", "before_it_breaks")
        title = entry.get("title", "FactoryLM")
        stem = entry.get("output_name") or f"thumb_{i:02d}_{series}"
        out = output_dir / f"{stem}.png"

        try:
            path = generate_thumbnail(
                series=series,
                hook_text=title,
                output_path=out,
                bg_image=entry.get("bg_image"),
            )
            results.append(path)
        except Exception as e:
            logger.error("Failed to generate thumbnail for '%s': %s", title, e)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate YouTube thumbnails for FactoryLM content series")
    sub = parser.add_subparsers(dest="command")

    # Single thumbnail
    single = sub.add_parser("generate", help="Generate a single thumbnail")
    single.add_argument("--series", required=True, choices=list(SERIES_COLORS), help="Content series")
    single.add_argument("--text", required=True, help="Hook text (max 5 words)")
    single.add_argument("--output", required=True, help="Output PNG path")
    single.add_argument("--bg-image", help="Optional background photo")

    # Batch from JSON
    batch = sub.add_parser("batch", help="Batch generate from JSON calendar file")
    batch.add_argument("--calendar", required=True, help="JSON file with list of {series, title, output_name} entries")
    batch.add_argument("--output-dir", required=True, help="Output directory")

    # List series
    sub.add_parser("list-series", help="List available series")

    args = parser.parse_args()

    if args.command == "generate":
        path = generate_thumbnail(
            series=args.series,
            hook_text=args.text,
            output_path=args.output,
            bg_image=args.bg_image,
        )
        print(f"Generated: {path}")

    elif args.command == "batch":
        import json
        calendar = json.loads(Path(args.calendar).read_text())
        paths = batch_generate(calendar, args.output_dir)
        for p in paths:
            print(p)

    elif args.command == "list-series":
        for key, config in SERIES_COLORS.items():
            print(f"  {key:20s} — {config['label']} (accent: {config['accent']})")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
