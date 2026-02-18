"""IEC 60617 symbol library for wiring diagrams.

Each symbol is a function that returns SVG element strings positioned at (cx, cy).
Symbols use outline-only style (fill: none) per IEC convention.
Connection stubs extend from the symbol body for wire routing.
"""

from __future__ import annotations

from openclaw.diagram.style import (
    COLOR_BLACK,
    COLOR_PE,
    CONNECTION_DOT,
    MOTOR_RADIUS,
    STROKE_DETAIL,
    STROKE_PRIMARY,
    SYMBOL_HEIGHT,
    SYMBOL_WIDTH,
    TERMINAL_RADIUS,
)


def _line(x1: float, y1: float, x2: float, y2: float, sw: float = STROKE_PRIMARY) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{COLOR_BLACK}" stroke-width="{sw}" stroke-linecap="round"/>'
    )


def _rect(x: float, y: float, w: float, h: float, sw: float = STROKE_PRIMARY) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{sw}"/>'
    )


def _circle(cx: float, cy: float, r: float, fill: str = "none", sw: float = STROKE_PRIMARY) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" '
        f'fill="{fill}" stroke="{COLOR_BLACK}" stroke-width="{sw}"/>'
    )


def _text(x: float, y: float, txt: str, size: float = 9, anchor: str = "middle") -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" '
        f'font-family="Arial, sans-serif" text-anchor="{anchor}" '
        f'dominant-baseline="central" fill="{COLOR_BLACK}">{txt}</text>'
    )


def _terminal_dot(x: float, y: float) -> str:
    """Small unfilled circle marking a terminal connection point."""
    return _circle(x, y, TERMINAL_RADIUS, fill="none", sw=STROKE_DETAIL)


def _connection_dot(x: float, y: float) -> str:
    """Filled black circle at a wire T-junction."""
    return _circle(x, y, CONNECTION_DOT, fill=COLOR_BLACK, sw=0)


# ---------------------------------------------------------------------------
# Component symbols
# ---------------------------------------------------------------------------

def motor_3ph(cx: float, cy: float, tag: str = "M1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Three-phase motor: circle with 'M' + 3~ inside, U/V/W terminals top, PE bottom.

    Returns (svg_string, terminal_positions_dict).
    """
    r = MOTOR_RADIUS
    parts = [
        _circle(cx, cy, r),
        _text(cx, cy - 5, "M", size=16),
        _text(cx, cy + 12, "3~", size=10),
        # Tag label
        _text(cx + r + 15, cy, tag, size=13, anchor="start"),
    ]

    # Terminal stubs: U1, V1, W1 on top; PE on bottom
    spacing = 20
    terminals = {
        "U1": (cx - spacing, cy - r),
        "V1": (cx, cy - r),
        "W1": (cx + spacing, cy - r),
        "PE": (cx, cy + r),
    }

    # Stub lines extending upward from motor
    for name, (tx, ty) in terminals.items():
        stub_y = ty - 20 if ty < cy else ty + 20
        parts.append(_line(tx, ty, tx, stub_y))
        parts.append(_terminal_dot(tx, stub_y))

    # PE has special color indicator
    pe_x, pe_y = terminals["PE"]
    parts.append(
        f'<line x1="{pe_x}" y1="{pe_y}" x2="{pe_x}" y2="{pe_y + 20}" '
        f'stroke="{COLOR_PE}" stroke-width="{STROKE_PRIMARY}" stroke-linecap="round"/>'
    )

    # Update terminal positions to stub endpoints (where wires connect)
    wire_terminals = {
        "U1": (cx - spacing, cy - r - 20),
        "V1": (cx, cy - r - 20),
        "W1": (cx + spacing, cy - r - 20),
        "PE": (cx, cy + r + 20),
    }

    return "\n".join(parts), wire_terminals


def motor_1ph(cx: float, cy: float, tag: str = "M1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Single-phase motor: circle with 'M' + 1~ inside, L/N terminals."""
    r = MOTOR_RADIUS
    parts = [
        _circle(cx, cy, r),
        _text(cx, cy - 5, "M", size=16),
        _text(cx, cy + 12, "1~", size=10),
        _text(cx + r + 15, cy, tag, size=13, anchor="start"),
    ]

    terminals = {
        "L": (cx - 15, cy - r - 20),
        "N": (cx + 15, cy - r - 20),
    }
    for name, (tx, ty) in terminals.items():
        parts.append(_line(tx, ty, tx, cy - r))
        parts.append(_terminal_dot(tx, ty))

    return "\n".join(parts), terminals


def contactor_3pole(cx: float, cy: float, tag: str = "K1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Three-pole contactor: rectangle with NO contact symbols inside.

    Terminals: 1,3,5 (top/line) and 2,4,6 (bottom/load) + A1,A2 (coil).
    """
    w, h = SYMBOL_WIDTH, SYMBOL_HEIGHT
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        _text(cx, cy, tag, size=13),
    ]

    spacing = 20
    # Power terminals: 1/2, 3/4, 5/6 (three poles)
    terminals = {}
    for i, (num_top, num_bot) in enumerate([(1, 2), (3, 4), (5, 6)]):
        tx = cx - spacing + i * spacing
        # Top terminals (line side)
        parts.append(_line(tx, y0, tx, y0 - 20))
        parts.append(_terminal_dot(tx, y0 - 20))
        terminals[str(num_top)] = (tx, y0 - 20)
        # Bottom terminals (load side)
        parts.append(_line(tx, y0 + h, tx, y0 + h + 20))
        parts.append(_terminal_dot(tx, y0 + h + 20))
        terminals[str(num_bot)] = (tx, y0 + h + 20)

        # NO contact symbol inside (diagonal arm)
        contact_y = y0 + 10
        parts.append(_line(tx - 5, contact_y + 20, tx + 5, contact_y, sw=STROKE_DETAIL))

    # Coil terminals A1 (right top) and A2 (right bottom)
    coil_x = x0 + w + 20
    terminals["A1"] = (coil_x, y0)
    terminals["A2"] = (coil_x, y0 + h)
    parts.append(_line(x0 + w, y0 + 10, coil_x, y0))
    parts.append(_line(x0 + w, y0 + h - 10, coil_x, y0 + h))
    parts.append(_terminal_dot(coil_x, y0))
    parts.append(_terminal_dot(coil_x, y0 + h))

    # Aux contacts 13/14 (NO) — small side stubs
    aux_x = x0 - 20
    terminals["13"] = (aux_x, y0 + 15)
    terminals["14"] = (aux_x, y0 + h - 15)
    parts.append(_line(x0, y0 + 15, aux_x, y0 + 15))
    parts.append(_line(x0, y0 + h - 15, aux_x, y0 + h - 15))
    parts.append(_terminal_dot(aux_x, y0 + 15))
    parts.append(_terminal_dot(aux_x, y0 + h - 15))

    return "\n".join(parts), terminals


def contactor_coil(cx: float, cy: float, tag: str = "K1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Contactor coil (for control circuit): rectangle with two horizontal leads."""
    w, h = 40, 30
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        _text(cx, cy, tag, size=11),
        # Terminal stubs left (A1) and right (A2)
        _line(x0 - 20, cy, x0, cy),
        _line(x0 + w, cy, x0 + w + 20, cy),
        _terminal_dot(x0 - 20, cy),
        _terminal_dot(x0 + w + 20, cy),
    ]
    terminals = {
        "A1": (x0 - 20, cy),
        "A2": (x0 + w + 20, cy),
    }
    return "\n".join(parts), terminals


def overload_relay(cx: float, cy: float, tag: str = "F1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Thermal overload relay: rectangle with OL zigzag + heater elements.

    Terminals: 1,3,5 (top) / 2,4,6 (bottom) + 95/96 (NC aux) + 97/98 (NO aux).
    """
    w, h = SYMBOL_WIDTH, SYMBOL_HEIGHT
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        _text(cx, cy - 8, tag, size=11),
        _text(cx, cy + 10, "OL", size=9),
    ]

    # Zigzag heater elements (3 phases)
    spacing = 20
    for i in range(3):
        zx = cx - spacing + i * spacing
        # Simple zigzag
        zy = cy + 2
        pts = f"{zx-4},{zy-6} {zx+4},{zy-2} {zx-4},{zy+2} {zx+4},{zy+6}"
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{COLOR_BLACK}" '
            f'stroke-width="{STROKE_DETAIL}"/>'
        )

    # Power terminals: 1/2, 3/4, 5/6
    terminals = {}
    for i, (num_top, num_bot) in enumerate([(1, 2), (3, 4), (5, 6)]):
        tx = cx - spacing + i * spacing
        parts.append(_line(tx, y0, tx, y0 - 20))
        parts.append(_terminal_dot(tx, y0 - 20))
        terminals[str(num_top)] = (tx, y0 - 20)
        parts.append(_line(tx, y0 + h, tx, y0 + h + 20))
        parts.append(_terminal_dot(tx, y0 + h + 20))
        terminals[str(num_bot)] = (tx, y0 + h + 20)

    # Aux contacts 95/96 (NC) and 97/98 (NO)
    aux_x = x0 - 20
    terminals["95"] = (aux_x, y0 + 15)
    terminals["96"] = (aux_x, y0 + h - 15)
    parts.append(_line(x0, y0 + 15, aux_x, y0 + 15))
    parts.append(_line(x0, y0 + h - 15, aux_x, y0 + h - 15))
    parts.append(_terminal_dot(aux_x, y0 + 15))
    parts.append(_terminal_dot(aux_x, y0 + h - 15))

    return "\n".join(parts), terminals


def circuit_breaker(cx: float, cy: float, tag: str = "Q1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Circuit breaker: rectangle with X-pattern inside.

    Terminals: 1,3,5 (top) / 2,4,6 (bottom) for 3-pole.
    """
    w, h = SYMBOL_WIDTH, 50
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        _text(cx, cy, tag, size=13),
    ]

    # X-pattern inside each pole
    spacing = 20
    terminals = {}
    for i, (num_top, num_bot) in enumerate([(1, 2), (3, 4), (5, 6)]):
        tx = cx - spacing + i * spacing
        # X marks
        parts.append(_line(tx - 4, y0 + 10, tx + 4, y0 + h - 10, sw=STROKE_DETAIL))
        parts.append(_line(tx + 4, y0 + 10, tx - 4, y0 + h - 10, sw=STROKE_DETAIL))
        # Terminal stubs
        parts.append(_line(tx, y0, tx, y0 - 20))
        parts.append(_terminal_dot(tx, y0 - 20))
        terminals[str(num_top)] = (tx, y0 - 20)
        parts.append(_line(tx, y0 + h, tx, y0 + h + 20))
        parts.append(_terminal_dot(tx, y0 + h + 20))
        terminals[str(num_bot)] = (tx, y0 + h + 20)

    return "\n".join(parts), terminals


def fuse(cx: float, cy: float, tag: str = "F1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Fuse: small rectangle with line through center."""
    w, h = 30, 15
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        _line(x0, cy, x0 + w, cy, sw=STROKE_DETAIL),
        _text(cx, cy - h / 2 - 8, tag, size=9),
        # Vertical stubs
        _line(cx, y0, cx, y0 - 20),
        _line(cx, y0 + h, cx, y0 + h + 20),
        _terminal_dot(cx, y0 - 20),
        _terminal_dot(cx, y0 + h + 20),
    ]
    terminals = {
        "1": (cx, y0 - 20),
        "2": (cx, y0 + h + 20),
    }
    return "\n".join(parts), terminals


def pushbutton_no(cx: float, cy: float, tag: str = "S1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Normally-open pushbutton: diagonal arm NOT touching right terminal."""
    parts = [
        # Left terminal
        _line(cx - 25, cy, cx - 10, cy),
        _terminal_dot(cx - 25, cy),
        # Right terminal (gap — NO)
        _line(cx + 10, cy, cx + 25, cy),
        _terminal_dot(cx + 25, cy),
        # Diagonal arm (rising, not touching right)
        _line(cx - 10, cy, cx + 8, cy - 12),
        # Push actuator (vertical line with arrow)
        _line(cx, cy - 18, cx, cy - 12, sw=STROKE_DETAIL),
        _line(cx - 4, cy - 18, cx + 4, cy - 18, sw=STROKE_DETAIL),
        # Tag
        _text(cx, cy - 25, tag, size=9),
    ]
    terminals = {
        "3": (cx - 25, cy),
        "4": (cx + 25, cy),
    }
    return "\n".join(parts), terminals


def pushbutton_nc(cx: float, cy: float, tag: str = "S0") -> tuple[str, dict[str, tuple[float, float]]]:
    """Normally-closed pushbutton: arm crosses vertical bar (touching)."""
    parts = [
        # Left terminal
        _line(cx - 25, cy, cx - 10, cy),
        _terminal_dot(cx - 25, cy),
        # Right terminal
        _line(cx + 10, cy, cx + 25, cy),
        _terminal_dot(cx + 25, cy),
        # Diagonal arm (crossing)
        _line(cx - 10, cy, cx + 10, cy - 10),
        # Vertical bar (NC indicator)
        _line(cx + 6, cy - 12, cx + 6, cy + 2, sw=STROKE_DETAIL),
        # Push actuator
        _line(cx, cy - 20, cx, cy - 14, sw=STROKE_DETAIL),
        _line(cx - 4, cy - 20, cx + 4, cy - 20, sw=STROKE_DETAIL),
        # Tag
        _text(cx, cy - 28, tag, size=9),
    ]
    terminals = {
        "1": (cx - 25, cy),
        "2": (cx + 25, cy),
    }
    return "\n".join(parts), terminals


def emergency_stop(cx: float, cy: float, tag: str = "S0") -> tuple[str, dict[str, tuple[float, float]]]:
    """Emergency stop: mushroom button NC contact (IEC 60617)."""
    parts = [
        # NC contact
        _line(cx - 25, cy, cx - 10, cy),
        _terminal_dot(cx - 25, cy),
        _line(cx + 10, cy, cx + 25, cy),
        _terminal_dot(cx + 25, cy),
        _line(cx - 10, cy, cx + 10, cy - 10),
        _line(cx + 6, cy - 12, cx + 6, cy + 2, sw=STROKE_DETAIL),
        # Mushroom cap (arc)
        f'<path d="M{cx - 12},{cy - 22} A 12 8 0 0 1 {cx + 12},{cy - 22}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
        _line(cx, cy - 22, cx, cy - 14, sw=STROKE_DETAIL),
        # Red circle indicator
        f'<circle cx="{cx}" cy="{cy - 28}" r="6" fill="#CC0000" stroke="{COLOR_BLACK}" stroke-width="{STROKE_DETAIL}"/>',
        _text(cx, cy + 15, tag, size=9),
    ]
    terminals = {
        "1": (cx - 25, cy),
        "2": (cx + 25, cy),
    }
    return "\n".join(parts), terminals


def terminal_block(cx: float, cy: float, tag: str = "X1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Terminal block: small unfilled circle with stubs top and bottom."""
    parts = [
        _circle(cx, cy, 5, fill="none"),
        _line(cx, cy - 5, cx, cy - 20),
        _line(cx, cy + 5, cx, cy + 20),
        _terminal_dot(cx, cy - 20),
        _terminal_dot(cx, cy + 20),
        _text(cx + 10, cy, tag, size=8, anchor="start"),
    ]
    terminals = {
        "1": (cx, cy - 20),
        "2": (cx, cy + 20),
    }
    return "\n".join(parts), terminals


def plc_io_card(cx: float, cy: float, tag: str = "PLC", pins: list[dict] | None = None) -> tuple[str, dict[str, tuple[float, float]]]:
    """PLC I/O card: tall rectangle with labeled pins on left and right sides.

    pins: list of {"name": "DI0", "side": "left", "label": "E-Stop"}
    """
    if not pins:
        pins = [
            {"name": "DI0", "side": "left"},
            {"name": "DI1", "side": "left"},
            {"name": "DI2", "side": "left"},
            {"name": "DI3", "side": "left"},
            {"name": "DO0", "side": "right"},
            {"name": "DO1", "side": "right"},
            {"name": "COM", "side": "right"},
            {"name": "24V", "side": "right"},
        ]

    left_pins = [p for p in pins if p.get("side") == "left"]
    right_pins = [p for p in pins if p.get("side") == "right"]
    max_pins = max(len(left_pins), len(right_pins), 1)
    pin_spacing = 25

    w = 100
    h = max(max_pins * pin_spacing + 30, 80)
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        _text(cx, y0 + 15, tag, size=13),
    ]

    terminals = {}

    # Left-side pins
    for i, pin in enumerate(left_pins):
        py = y0 + 30 + i * pin_spacing
        parts.append(_line(x0 - 20, py, x0, py))
        parts.append(_terminal_dot(x0 - 20, py))
        parts.append(_text(x0 + 8, py, pin["name"], size=8, anchor="start"))
        terminals[pin["name"]] = (x0 - 20, py)

    # Right-side pins
    for i, pin in enumerate(right_pins):
        py = y0 + 30 + i * pin_spacing
        parts.append(_line(x0 + w, py, x0 + w + 20, py))
        parts.append(_terminal_dot(x0 + w + 20, py))
        parts.append(_text(x0 + w - 8, py, pin["name"], size=8, anchor="end"))
        terminals[pin["name"]] = (x0 + w + 20, py)

    return "\n".join(parts), terminals


def vfd(cx: float, cy: float, tag: str = "U1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Variable Frequency Drive: large rectangle with labeled terminals."""
    w, h = 120, 100
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        _text(cx, cy - 15, tag, size=13),
        _text(cx, cy + 5, "VFD", size=11),
    ]

    # Power input terminals (top): R/S/T (or L1/L2/L3)
    spacing = 25
    terminals = {}
    for i, name in enumerate(["R", "S", "T"]):
        tx = cx - spacing + i * spacing
        parts.append(_line(tx, y0, tx, y0 - 20))
        parts.append(_terminal_dot(tx, y0 - 20))
        terminals[name] = (tx, y0 - 20)

    # Motor output terminals (bottom): U/V/W
    for i, name in enumerate(["U", "V", "W"]):
        tx = cx - spacing + i * spacing
        parts.append(_line(tx, y0 + h, tx, y0 + h + 20))
        parts.append(_terminal_dot(tx, y0 + h + 20))
        terminals[name] = (tx, y0 + h + 20)

    # Control terminals (right side): FWD, REV, VI, ACM, FA
    ctrl_names = ["FWD", "REV", "VI", "ACM", "FA"]
    for i, name in enumerate(ctrl_names):
        py = y0 + 15 + i * 18
        parts.append(_line(x0 + w, py, x0 + w + 20, py))
        parts.append(_terminal_dot(x0 + w + 20, py))
        parts.append(_text(x0 + w - 5, py, name, size=7, anchor="end"))
        terminals[name] = (x0 + w + 20, py)

    # PE terminal (bottom center)
    parts.append(_line(cx, y0 + h, cx, y0 + h + 20))
    terminals["PE"] = (cx, y0 + h + 20)

    return "\n".join(parts), terminals


def relay_coil(cx: float, cy: float, tag: str = "K1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Relay coil (for control circuits): rectangle with leads left/right."""
    return contactor_coil(cx, cy, tag)


def relay_contact_no(cx: float, cy: float, tag: str = "K1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Relay NO contact: diagonal arm with small arc at pivot (electromagnetic)."""
    parts = [
        _line(cx - 20, cy, cx - 8, cy),
        _terminal_dot(cx - 20, cy),
        _line(cx + 8, cy, cx + 20, cy),
        _terminal_dot(cx + 20, cy),
        # Diagonal arm (NO — not touching)
        _line(cx - 8, cy, cx + 6, cy - 10),
        # Arc at pivot (electromagnetic indicator)
        f'<path d="M{cx - 10},{cy + 2} A 3 3 0 0 1 {cx - 4},{cy + 2}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_DETAIL}"/>',
        _text(cx, cy - 18, tag, size=8),
    ]
    terminals = {
        "13": (cx - 20, cy),
        "14": (cx + 20, cy),
    }
    return "\n".join(parts), terminals


def relay_contact_nc(cx: float, cy: float, tag: str = "K1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Relay NC contact: arm crosses bar with arc at pivot."""
    parts = [
        _line(cx - 20, cy, cx - 8, cy),
        _terminal_dot(cx - 20, cy),
        _line(cx + 8, cy, cx + 20, cy),
        _terminal_dot(cx + 20, cy),
        # Arm (NC — crossing)
        _line(cx - 8, cy, cx + 8, cy - 10),
        # Vertical bar
        _line(cx + 4, cy - 12, cx + 4, cy + 2, sw=STROKE_DETAIL),
        # Arc at pivot
        f'<path d="M{cx - 10},{cy + 2} A 3 3 0 0 1 {cx - 4},{cy + 2}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_DETAIL}"/>',
        _text(cx, cy - 18, tag, size=8),
    ]
    terminals = {
        "21": (cx - 20, cy),
        "22": (cx + 20, cy),
    }
    return "\n".join(parts), terminals


def indicator_light(cx: float, cy: float, tag: str = "H1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Indicator light: circle with X inside."""
    r = 12
    parts = [
        _circle(cx, cy, r),
        _line(cx - 7, cy - 7, cx + 7, cy + 7, sw=STROKE_DETAIL),
        _line(cx + 7, cy - 7, cx - 7, cy + 7, sw=STROKE_DETAIL),
        _text(cx + r + 8, cy, tag, size=9, anchor="start"),
        _line(cx - r, cy, cx - r - 15, cy),
        _line(cx + r, cy, cx + r + 15, cy),
        _terminal_dot(cx - r - 15, cy),
        _terminal_dot(cx + r + 15, cy),
    ]
    terminals = {
        "1": (cx - r - 15, cy),
        "2": (cx + r + 15, cy),
    }
    return "\n".join(parts), terminals


def proximity_sensor(cx: float, cy: float, tag: str = "B1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Proximity sensor (IEC): rectangle with sensing face + 3-wire output."""
    w, h = 50, 30
    x0 = cx - w / 2
    y0 = cy - h / 2

    parts = [
        _rect(x0, y0, w, h),
        # Sensing face (left side — two curved lines)
        f'<path d="M{x0 + 3},{y0 + 5} Q{x0 - 5},{cy} {x0 + 3},{y0 + h - 5}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_DETAIL}"/>',
        _text(cx + 5, cy, tag, size=9),
        # 3 output wires (right side): +V, signal, 0V
        _line(x0 + w, y0 + 8, x0 + w + 20, y0 + 8),
        _line(x0 + w, cy, x0 + w + 20, cy),
        _line(x0 + w, y0 + h - 8, x0 + w + 20, y0 + h - 8),
        _terminal_dot(x0 + w + 20, y0 + 8),
        _terminal_dot(x0 + w + 20, cy),
        _terminal_dot(x0 + w + 20, y0 + h - 8),
    ]
    terminals = {
        "BN": (x0 + w + 20, y0 + 8),      # +V (brown)
        "BK": (x0 + w + 20, cy),            # signal (black)
        "BU": (x0 + w + 20, y0 + h - 8),   # 0V (blue)
    }
    return "\n".join(parts), terminals


def transformer(cx: float, cy: float, tag: str = "T1") -> tuple[str, dict[str, tuple[float, float]]]:
    """Transformer: two coil symbols side by side."""
    parts = [
        # Primary coil (left arcs)
        f'<path d="M{cx - 10},{cy - 25} A 8 8 0 0 1 {cx - 10},{cy - 10}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
        f'<path d="M{cx - 10},{cy - 10} A 8 8 0 0 1 {cx - 10},{cy + 5}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
        f'<path d="M{cx - 10},{cy + 5} A 8 8 0 0 1 {cx - 10},{cy + 20}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
        # Secondary coil (right arcs)
        f'<path d="M{cx + 10},{cy - 25} A 8 8 0 0 0 {cx + 10},{cy - 10}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
        f'<path d="M{cx + 10},{cy - 10} A 8 8 0 0 0 {cx + 10},{cy + 5}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
        f'<path d="M{cx + 10},{cy + 5} A 8 8 0 0 0 {cx + 10},{cy + 20}" '
        f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
        # Core lines
        _line(cx - 2, cy - 28, cx - 2, cy + 23, sw=STROKE_DETAIL),
        _line(cx + 2, cy - 28, cx + 2, cy + 23, sw=STROKE_DETAIL),
        # Tag
        _text(cx + 25, cy, tag, size=11, anchor="start"),
    ]

    terminals = {
        "1": (cx - 10, cy - 30),  # Primary top
        "2": (cx - 10, cy + 25),  # Primary bottom
        "3": (cx + 10, cy - 30),  # Secondary top
        "4": (cx + 10, cy + 25),  # Secondary bottom
    }
    for _, (tx, ty) in terminals.items():
        parts.append(_line(tx, ty, tx, ty + (-5 if ty < cy else 5)))
        parts.append(_terminal_dot(tx, ty))

    return "\n".join(parts), terminals


# ---------------------------------------------------------------------------
# Symbol registry — maps component type strings to drawing functions
# ---------------------------------------------------------------------------

SYMBOL_REGISTRY: dict[str, callable] = {
    "motor_3ph": motor_3ph,
    "motor_1ph": motor_1ph,
    "contactor_3pole": contactor_3pole,
    "contactor_coil": contactor_coil,
    "overload_relay": overload_relay,
    "circuit_breaker": circuit_breaker,
    "fuse": fuse,
    "pushbutton_no": pushbutton_no,
    "pushbutton_nc": pushbutton_nc,
    "emergency_stop": emergency_stop,
    "terminal_block": terminal_block,
    "plc_input_card": plc_io_card,
    "plc_output_card": plc_io_card,
    "vfd": vfd,
    "relay_coil": relay_coil,
    "relay_contact_no": relay_contact_no,
    "relay_contact_nc": relay_contact_nc,
    "indicator_light": indicator_light,
    "proximity_sensor": proximity_sensor,
    "transformer": transformer,
}
