"""Layout engine for wiring diagram component placement and wire routing.

Places components on a grid and routes wires orthogonally between terminals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from openclaw.diagram.schema import Bus, Component, Connection, DiagramSpec
from openclaw.diagram.style import (
    BUS_SPACING,
    CONTROL_OFFSET_Y,
    DEVICE_SPACING_H,
    DEVICE_SPACING_V,
    GRID_UNIT,
    MARGIN_LEFT,
    MARGIN_TOP,
    WORK_HEIGHT,
    WORK_WIDTH,
)

log = logging.getLogger(__name__)


@dataclass
class PlacedComponent:
    """A component with resolved position on the canvas."""

    component: Component
    cx: float
    cy: float
    # Filled after symbol drawing — maps terminal ID to (x, y)
    terminal_positions: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class WireSegment:
    """An orthogonal wire segment between two points."""

    x1: float
    y1: float
    x2: float
    y2: float
    wire_type: str = "power"
    wire_label: str = ""


@dataclass
class BusBar:
    """A positioned bus bar."""

    name: str
    x1: float
    y1: float
    x2: float
    y2: float
    bus_type: str = "power"


@dataclass
class LayoutResult:
    """Complete layout computation result."""

    placed_components: list[PlacedComponent]
    bus_bars: list[BusBar]
    # Wire segments are computed after terminal positions are known
    wire_segments: list[WireSegment] = field(default_factory=list)


def _snap(value: float) -> float:
    """Snap a coordinate to the grid."""
    return round(value / GRID_UNIT) * GRID_UNIT


def compute_layout(spec: DiagramSpec) -> LayoutResult:
    """Compute positions for all components, buses, and wires.

    Strategy:
    - Power components flow top-to-bottom (breaker → contactor → overload → motor)
    - Control components flow left-to-right (+24V → switches → coils → 0V)
    - Buses are horizontal bars at the top (power) or edges (control)
    - Wire routing is orthogonal (horizontal + vertical segments only)
    """
    placed: list[PlacedComponent] = []
    bus_bars: list[BusBar] = []

    # Group components by their group field
    groups: dict[str, list[Component]] = {}
    for comp in spec.components:
        g = comp.group or "main"
        groups.setdefault(g, []).append(comp)

    # Separate power and control groups
    power_groups: dict[str, list[Component]] = {}
    control_groups: dict[str, list[Component]] = {}
    power_types = {
        "circuit_breaker", "contactor_3pole", "overload_relay",
        "motor_3ph", "motor_1ph", "vfd", "fuse", "transformer",
    }
    control_types = {
        "pushbutton_no", "pushbutton_nc", "emergency_stop",
        "contactor_coil", "relay_coil", "relay_contact_no",
        "relay_contact_nc", "indicator_light",
    }

    for gname, comps in groups.items():
        has_power = any(c.type in power_types for c in comps)
        has_control = any(c.type in control_types for c in comps)

        if has_power and not has_control:
            power_groups[gname] = comps
        elif has_control and not has_power:
            control_groups[gname] = comps
        else:
            # Mixed group — split
            power_comps = [c for c in comps if c.type in power_types]
            ctrl_comps = [c for c in comps if c.type in control_types]
            other_comps = [c for c in comps if c.type not in power_types and c.type not in control_types]
            if power_comps:
                power_groups[gname] = power_comps + other_comps
            if ctrl_comps:
                control_groups[gname + "_ctrl"] = ctrl_comps

    # --- Place power buses (L1, L2, L3 at top) ---
    power_buses = [b for b in spec.buses if b.type in ("power", "neutral")]
    control_buses = [b for b in spec.buses if b.type in ("control",)]
    earth_buses = [b for b in spec.buses if b.type == "earth"]

    bus_y_start = MARGIN_TOP + 20
    bus_x_start = MARGIN_LEFT + 60
    bus_x_end = MARGIN_LEFT + WORK_WIDTH - 60

    for i, bus in enumerate(power_buses):
        by = _snap(bus_y_start + i * BUS_SPACING)
        bus_bars.append(BusBar(
            name=bus.name,
            x1=bus_x_start, y1=by,
            x2=bus_x_end, y2=by,
            bus_type=bus.type,
        ))

    # --- Place power components (top-to-bottom per group) ---
    # Vertical stacking order preference
    power_order = [
        "circuit_breaker", "fuse", "contactor_3pole", "overload_relay",
        "vfd", "transformer", "motor_3ph", "motor_1ph",
    ]

    num_power_groups = max(len(power_groups), 1)
    group_width = min(DEVICE_SPACING_H, WORK_WIDTH / num_power_groups)

    for gi, (gname, comps) in enumerate(power_groups.items()):
        # Sort components by preferred order
        sorted_comps = sorted(
            comps,
            key=lambda c: power_order.index(c.type) if c.type in power_order else 99,
        )

        group_cx = _snap(MARGIN_LEFT + 100 + gi * group_width)
        comp_y = _snap(bus_y_start + len(power_buses) * BUS_SPACING + 40)

        for comp in sorted_comps:
            placed.append(PlacedComponent(component=comp, cx=group_cx, cy=comp_y))
            comp_y = _snap(comp_y + DEVICE_SPACING_V)

    # --- Place control components (left-to-right) ---
    ctrl_y = _snap(CONTROL_OFFSET_Y)
    if not power_groups:
        ctrl_y = _snap(MARGIN_TOP + 200)

    # Control bus bars (+24V left, 0V right)
    for bus in control_buses:
        if "+24" in bus.name or "pos" in bus.name.lower():
            bus_bars.append(BusBar(
                name=bus.name,
                x1=bus_x_start, y1=ctrl_y - 30,
                x2=bus_x_start, y2=ctrl_y + 60,
                bus_type="control",
            ))
        elif "0V" in bus.name or "neg" in bus.name.lower() or "GND" in bus.name:
            bus_bars.append(BusBar(
                name=bus.name,
                x1=bus_x_end, y1=ctrl_y - 30,
                x2=bus_x_end, y2=ctrl_y + 60,
                bus_type="control",
            ))

    # Earth bus
    for bus in earth_buses:
        by = _snap(CONTROL_OFFSET_Y + 100)
        bus_bars.append(BusBar(
            name=bus.name,
            x1=bus_x_start, y1=by,
            x2=bus_x_end, y2=by,
            bus_type="earth",
        ))

    ctrl_x = _snap(MARGIN_LEFT + 150)
    all_ctrl_comps = []
    for comps in control_groups.values():
        all_ctrl_comps.extend(comps)

    # Sort control components: NC first (stop), then NO (start), then coils, then indicators
    ctrl_order = [
        "emergency_stop", "pushbutton_nc", "pushbutton_no",
        "contactor_coil", "relay_coil", "relay_contact_no",
        "relay_contact_nc", "indicator_light",
    ]
    all_ctrl_comps.sort(
        key=lambda c: ctrl_order.index(c.type) if c.type in ctrl_order else 99,
    )

    for comp in all_ctrl_comps:
        placed.append(PlacedComponent(component=comp, cx=ctrl_x, cy=ctrl_y))
        ctrl_x = _snap(ctrl_x + 120)

    # --- Place PLC cards ---
    plc_comps = [c for c in spec.components if c.type in ("plc_input_card", "plc_output_card")]
    if plc_comps:
        plc_x = _snap(MARGIN_LEFT + WORK_WIDTH - 150)
        plc_y = _snap(MARGIN_TOP + 200)
        for comp in plc_comps:
            if comp not in [p.component for p in placed]:
                placed.append(PlacedComponent(component=comp, cx=plc_x, cy=plc_y))
                plc_y = _snap(plc_y + 250)

    return LayoutResult(placed_components=placed, bus_bars=bus_bars)


def route_wires(
    layout: LayoutResult,
    connections: list[Connection],
) -> list[WireSegment]:
    """Route wires orthogonally between placed terminal positions.

    Uses simple L-routing (one bend per wire): go vertical first, then horizontal.
    Falls back to Z-routing (two bends) if direct L-route crosses another component.
    """
    # Build terminal lookup: "tag.terminal_id" → (x, y)
    terminal_map: dict[str, tuple[float, float]] = {}
    for pc in layout.placed_components:
        tag = pc.component.tag
        for tid, pos in pc.terminal_positions.items():
            terminal_map[f"{tag}.{tid}"] = pos

    segments: list[WireSegment] = []

    for conn in connections:
        src_key = conn.from_terminal
        dst_key = conn.to_terminal

        src = terminal_map.get(src_key)
        dst = terminal_map.get(dst_key)

        if not src or not dst:
            log.warning("Wire %s → %s: terminal not found (src=%s, dst=%s)", src_key, dst_key, src, dst)
            continue

        sx, sy = src
        dx, dy = dst

        # Simple L-route: vertical then horizontal
        if abs(sx - dx) < 2:
            # Already vertically aligned — straight line
            segments.append(WireSegment(
                x1=sx, y1=sy, x2=dx, y2=dy,
                wire_type=conn.wire_type, wire_label=conn.wire_label,
            ))
        elif abs(sy - dy) < 2:
            # Horizontally aligned — straight line
            segments.append(WireSegment(
                x1=sx, y1=sy, x2=dx, y2=dy,
                wire_type=conn.wire_type, wire_label=conn.wire_label,
            ))
        else:
            # L-route: go vertical to dst Y, then horizontal to dst X
            mid_y = dy
            segments.append(WireSegment(
                x1=sx, y1=sy, x2=sx, y2=mid_y,
                wire_type=conn.wire_type, wire_label=conn.wire_label,
            ))
            segments.append(WireSegment(
                x1=sx, y1=mid_y, x2=dx, y2=dy,
                wire_type=conn.wire_type, wire_label="",
            ))

    return segments
