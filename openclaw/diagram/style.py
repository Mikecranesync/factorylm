"""Visual style constants for IEC 60617 wiring diagrams."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------
CANVAS_WIDTH = 1600   # px (landscape, Telegram-friendly)
CANVAS_HEIGHT = 1000  # px
HIRES_SCALE = 2       # multiply for high-res output (3200x2000)

# Internal coordinate space (mm-like, maps to pixels at export)
GRID_UNIT = 20        # px — base grid for snapping
MARGIN_TOP = 80       # px
MARGIN_BOTTOM = 120   # px (title block + legend)
MARGIN_LEFT = 40      # px
MARGIN_RIGHT = 40     # px

# Derived work area
WORK_WIDTH = CANVAS_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
WORK_HEIGHT = CANVAS_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# ---------------------------------------------------------------------------
# Line weights (two-tier per plan)
# ---------------------------------------------------------------------------
STROKE_PRIMARY = 2.0   # pt — symbol outlines + wires
STROKE_DETAIL = 0.5    # pt — internal symbol features, annotations
STROKE_BUS = 3.0       # pt — power bus bars

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
COLOR_BLACK = "#000000"
COLOR_WHITE = "#FFFFFF"
COLOR_PE = "#00AA00"       # protective earth (green)
COLOR_NEUTRAL = "#0088CC"  # neutral conductor (blue)
COLOR_CTRL_POS = "#CC0000" # +24V control (red)
COLOR_CTRL_NEG = "#0000CC" # 0V control (blue)
COLOR_GRAY = "#666666"     # annotations, status labels
COLOR_LIGHT_GRAY = "#CCCCCC"  # grid lines, separators
COLOR_BG = "#FFFFFF"

# Wire type to color mapping
WIRE_COLORS = {
    "power": COLOR_BLACK,
    "control": COLOR_CTRL_POS,
    "earth": COLOR_PE,
    "neutral": COLOR_NEUTRAL,
    "signal": COLOR_GRAY,
}

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONT_FAMILY = "Arial, Helvetica, Liberation Sans, sans-serif"
FONT_DEVICE_TAG = 13      # pt — device designations (Q1, K1, M1)
FONT_TERMINAL = 9         # pt — terminal numbers
FONT_WIRE_LABEL = 9       # pt — wire labels
FONT_TITLE = 14           # pt — title block
FONT_SUBTITLE = 11        # pt — title block subtitle
FONT_NOTE = 9             # pt — notes and legend

# ---------------------------------------------------------------------------
# Symbol dimensions
# ---------------------------------------------------------------------------
SYMBOL_WIDTH = 80    # px — default symbol bounding box width
SYMBOL_HEIGHT = 60   # px — default symbol bounding box height
MOTOR_RADIUS = 30    # px — motor circle radius
TERMINAL_RADIUS = 3  # px — terminal connection dot
CONNECTION_DOT = 4   # px — T-junction filled dot

# ---------------------------------------------------------------------------
# Layout spacing
# ---------------------------------------------------------------------------
DEVICE_SPACING_V = 120  # px — vertical spacing between stacked devices
DEVICE_SPACING_H = 200  # px — horizontal spacing between parallel groups
BUS_SPACING = 60        # px — spacing between power bus bars
CONTROL_OFFSET_Y = 600  # px — Y offset for control circuit section
SECTION_GAP = 40        # px — gap between power and control sections

# ---------------------------------------------------------------------------
# Title block
# ---------------------------------------------------------------------------
TITLE_BLOCK_HEIGHT = 60    # px
TITLE_BLOCK_WIDTH = 400    # px (right-aligned)
