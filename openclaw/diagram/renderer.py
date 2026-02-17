"""WiringRenderer — spec → SVG → PNG pipeline.

Takes a DiagramSpec (JSON from LLM) and produces a professional
IEC 60617 wiring diagram as SVG, then converts to PNG via CairoSVG.
"""

from __future__ import annotations

import io
import logging
from datetime import date

from openclaw.diagram.layout import (
    BusBar,
    LayoutResult,
    PlacedComponent,
    WireSegment,
    compute_layout,
    route_wires,
)
from openclaw.diagram.schema import DiagramSpec
from openclaw.diagram.style import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COLOR_BG,
    COLOR_BLACK,
    COLOR_GRAY,
    COLOR_LIGHT_GRAY,
    COLOR_PE,
    CONNECTION_DOT,
    FONT_DEVICE_TAG,
    FONT_FAMILY,
    FONT_NOTE,
    FONT_SUBTITLE,
    FONT_TERMINAL,
    FONT_TITLE,
    FONT_WIRE_LABEL,
    HIRES_SCALE,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    STROKE_BUS,
    STROKE_DETAIL,
    STROKE_PRIMARY,
    TITLE_BLOCK_HEIGHT,
    TITLE_BLOCK_WIDTH,
    WIRE_COLORS,
    WORK_WIDTH,
)
from openclaw.diagram.symbols import SYMBOL_REGISTRY

log = logging.getLogger(__name__)


class WiringRenderer:
    """Renders a DiagramSpec into SVG and PNG."""

    def __init__(self, spec: DiagramSpec):
        self.spec = spec
        self._svg_parts: list[str] = []

    def render_svg(self) -> str:
        """Generate complete SVG string from the spec."""
        self._svg_parts = []

        # 1. Compute layout
        layout = compute_layout(self.spec)

        # 2. Draw components (fills terminal_positions on each PlacedComponent)
        self._draw_components(layout)

        # 3. Route and draw wires
        wire_segments = route_wires(layout, self.spec.connections)
        layout.wire_segments = wire_segments

        # 4. Build SVG document
        svg_lines = [self._svg_header()]

        # Background
        svg_lines.append(
            f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{COLOR_BG}"/>'
        )

        # Grid (subtle)
        svg_lines.append(self._draw_grid())

        # Bus bars (under wires and components)
        for bus in layout.bus_bars:
            svg_lines.append(self._draw_bus(bus))

        # Wires
        for seg in layout.wire_segments:
            svg_lines.append(self._draw_wire(seg))

        # Connection dots at T-junctions
        svg_lines.extend(self._draw_connection_dots(layout.wire_segments))

        # Component symbols (on top of wires)
        svg_lines.extend(self._svg_parts)

        # Terminal labels
        for pc in layout.placed_components:
            svg_lines.append(self._draw_terminal_labels(pc))

        # Title block
        svg_lines.append(self._draw_title_block())

        # Notes
        svg_lines.append(self._draw_notes())

        # Legend
        svg_lines.append(self._draw_legend())

        # Close SVG
        svg_lines.append("</svg>")

        return "\n".join(svg_lines)

    def render_png(self, hires: bool = False) -> bytes:
        """Generate PNG bytes from the spec via CairoSVG."""
        try:
            import cairosvg
        except ImportError:
            raise RuntimeError(
                "cairosvg required for PNG output: pip install cairosvg"
            )

        svg_str = self.render_svg()
        scale = HIRES_SCALE if hires else 1
        png_bytes = cairosvg.svg2png(
            bytestring=svg_str.encode("utf-8"),
            output_width=CANVAS_WIDTH * scale,
            output_height=CANVAS_HEIGHT * scale,
            background_color=COLOR_BG,
        )
        return png_bytes

    def render_png_to_file(self, path: str, hires: bool = False) -> None:
        """Render PNG to a file path."""
        png_bytes = self.render_png(hires=hires)
        with open(path, "wb") as f:
            f.write(png_bytes)
        log.info("PNG written to %s (%d bytes)", path, len(png_bytes))

    # ------------------------------------------------------------------
    # SVG construction helpers
    # ------------------------------------------------------------------

    def _svg_header(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" '
            f'viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" '
            f'style="font-family: {FONT_FAMILY};">'
        )

    def _draw_grid(self) -> str:
        """Subtle background grid for alignment reference."""
        lines = ['<g opacity="0.1">']
        # Vertical grid lines every 100px
        for x in range(0, CANVAS_WIDTH + 1, 100):
            lines.append(
                f'<line x1="{x}" y1="0" x2="{x}" y2="{CANVAS_HEIGHT}" '
                f'stroke="{COLOR_LIGHT_GRAY}" stroke-width="0.5"/>'
            )
        # Horizontal grid lines every 100px
        for y in range(0, CANVAS_HEIGHT + 1, 100):
            lines.append(
                f'<line x1="0" y1="{y}" x2="{CANVAS_WIDTH}" y2="{y}" '
                f'stroke="{COLOR_LIGHT_GRAY}" stroke-width="0.5"/>'
            )
        lines.append("</g>")
        return "\n".join(lines)

    def _draw_components(self, layout: LayoutResult) -> None:
        """Draw each component symbol and record terminal positions."""
        for pc in layout.placed_components:
            comp = pc.component
            draw_fn = SYMBOL_REGISTRY.get(comp.type)
            if not draw_fn:
                log.warning("Unknown symbol type: %s for %s", comp.type, comp.tag)
                # Fallback: draw a labeled rectangle
                svg, terminals = self._fallback_symbol(pc.cx, pc.cy, comp.tag, comp.type)
            else:
                # Handle PLC cards with custom pins
                if comp.type in ("plc_input_card", "plc_output_card") and comp.terminals:
                    pins = [
                        {"name": t.id, "side": t.side, "label": t.label}
                        for t in comp.terminals
                    ]
                    svg, terminals = draw_fn(pc.cx, pc.cy, tag=comp.tag, pins=pins)
                else:
                    svg, terminals = draw_fn(pc.cx, pc.cy, tag=comp.tag)

            pc.terminal_positions = terminals
            self._svg_parts.append(f'<g id="comp-{comp.tag}">\n{svg}\n</g>')

    def _fallback_symbol(
        self, cx: float, cy: float, tag: str, comp_type: str
    ) -> tuple[str, dict[str, tuple[float, float]]]:
        """Draw a generic labeled box for unknown component types."""
        w, h = 80, 50
        x0, y0 = cx - w / 2, cy - h / 2
        parts = [
            f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" '
            f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}" '
            f'stroke-dasharray="4,2"/>',
            f'<text x="{cx}" y="{cy - 5}" font-size="{FONT_DEVICE_TAG}" '
            f'text-anchor="middle" fill="{COLOR_BLACK}">{tag}</text>',
            f'<text x="{cx}" y="{cy + 12}" font-size="8" '
            f'text-anchor="middle" fill="{COLOR_GRAY}">{comp_type}</text>',
        ]
        # Generic terminals top and bottom
        terminals = {
            "1": (cx, y0 - 20),
            "2": (cx, y0 + h + 20),
        }
        parts.append(
            f'<line x1="{cx}" y1="{y0}" x2="{cx}" y2="{y0 - 20}" '
            f'stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>'
        )
        parts.append(
            f'<line x1="{cx}" y1="{y0 + h}" x2="{cx}" y2="{y0 + h + 20}" '
            f'stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>'
        )
        return "\n".join(parts), terminals

    def _draw_bus(self, bus: BusBar) -> str:
        """Draw a bus bar with label."""
        color = WIRE_COLORS.get(bus.bus_type, COLOR_BLACK)
        if bus.name == "PE":
            color = COLOR_PE

        parts = [
            f'<line x1="{bus.x1}" y1="{bus.y1}" x2="{bus.x2}" y2="{bus.y2}" '
            f'stroke="{color}" stroke-width="{STROKE_BUS}" stroke-linecap="round"/>',
        ]

        # Bus label
        if bus.x1 == bus.x2:
            # Vertical bus
            lx, ly = bus.x1 - 15, (bus.y1 + bus.y2) / 2
            parts.append(
                f'<text x="{lx}" y="{ly}" font-size="{FONT_WIRE_LABEL}" '
                f'text-anchor="end" fill="{color}" font-weight="bold">{bus.name}</text>'
            )
        else:
            # Horizontal bus
            lx, ly = bus.x1 - 10, bus.y1
            parts.append(
                f'<text x="{lx}" y="{ly + 4}" font-size="{FONT_WIRE_LABEL}" '
                f'text-anchor="end" fill="{color}" font-weight="bold">{bus.name}</text>'
            )

        return "\n".join(parts)

    def _draw_wire(self, seg: WireSegment) -> str:
        """Draw a wire segment."""
        color = WIRE_COLORS.get(seg.wire_type, COLOR_BLACK)
        sw = STROKE_PRIMARY
        if seg.wire_type == "signal":
            sw = STROKE_DETAIL

        parts = [
            f'<line x1="{seg.x1}" y1="{seg.y1}" x2="{seg.x2}" y2="{seg.y2}" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>',
        ]

        # Wire label at midpoint
        if seg.wire_label:
            mx = (seg.x1 + seg.x2) / 2
            my = (seg.y1 + seg.y2) / 2
            # Offset label slightly from wire
            offset = 8 if seg.x1 == seg.x2 else -8  # right of vertical, above horizontal
            if seg.x1 == seg.x2:
                parts.append(
                    f'<text x="{mx + offset}" y="{my}" font-size="{FONT_WIRE_LABEL}" '
                    f'text-anchor="start" fill="{color}">{seg.wire_label}</text>'
                )
            else:
                parts.append(
                    f'<text x="{mx}" y="{my + offset}" font-size="{FONT_WIRE_LABEL}" '
                    f'text-anchor="middle" fill="{color}">{seg.wire_label}</text>'
                )

        return "\n".join(parts)

    def _draw_connection_dots(self, segments: list[WireSegment]) -> list[str]:
        """Find T-junctions (3+ wire endpoints at same point) and draw filled dots."""
        # Count endpoints at each coordinate
        point_count: dict[tuple[float, float], int] = {}
        for seg in segments:
            p1 = (round(seg.x1, 1), round(seg.y1, 1))
            p2 = (round(seg.x2, 1), round(seg.y2, 1))
            point_count[p1] = point_count.get(p1, 0) + 1
            point_count[p2] = point_count.get(p2, 0) + 1

        dots = []
        for (x, y), count in point_count.items():
            if count >= 3:
                dots.append(
                    f'<circle cx="{x}" cy="{y}" r="{CONNECTION_DOT}" '
                    f'fill="{COLOR_BLACK}" stroke="none"/>'
                )
        return dots

    def _draw_terminal_labels(self, pc: PlacedComponent) -> str:
        """Draw terminal number labels near each terminal point."""
        parts = []
        for tid, (tx, ty) in pc.terminal_positions.items():
            # Offset label slightly from terminal dot
            parts.append(
                f'<text x="{tx + 6}" y="{ty - 6}" font-size="{FONT_TERMINAL}" '
                f'fill="{COLOR_GRAY}" text-anchor="start">{tid}</text>'
            )
        return "\n".join(parts)

    def _draw_title_block(self) -> str:
        """Draw the title block in the bottom-right corner."""
        bx = CANVAS_WIDTH - TITLE_BLOCK_WIDTH - 20
        by = CANVAS_HEIGHT - TITLE_BLOCK_HEIGHT - 15
        bw = TITLE_BLOCK_WIDTH
        bh = TITLE_BLOCK_HEIGHT

        d = self.spec.date or date.today().isoformat()

        parts = [
            f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" '
            f'fill="none" stroke="{COLOR_BLACK}" stroke-width="{STROKE_PRIMARY}"/>',
            # Horizontal divider
            f'<line x1="{bx}" y1="{by + bh / 2}" x2="{bx + bw}" y2="{by + bh / 2}" '
            f'stroke="{COLOR_BLACK}" stroke-width="{STROKE_DETAIL}"/>',
            # Title
            f'<text x="{bx + 10}" y="{by + 20}" font-size="{FONT_TITLE}" '
            f'font-weight="bold" fill="{COLOR_BLACK}">{self.spec.title}</text>',
            # Drawing number + revision
            f'<text x="{bx + 10}" y="{by + bh / 2 + 18}" font-size="{FONT_SUBTITLE}" '
            f'fill="{COLOR_BLACK}">{self.spec.drawing_number} Rev {self.spec.revision} | '
            f'{self.spec.standard} | {d}</text>',
            # Author
            f'<text x="{bx + bw - 10}" y="{by + bh / 2 + 18}" font-size="{FONT_NOTE}" '
            f'text-anchor="end" fill="{COLOR_GRAY}">{self.spec.author}</text>',
        ]
        return "\n".join(parts)

    def _draw_notes(self) -> str:
        """Draw notes in the bottom-center area."""
        if not self.spec.notes:
            return ""

        nx = MARGIN_LEFT + 20
        ny = CANVAS_HEIGHT - MARGIN_BOTTOM + 20

        parts = [
            f'<text x="{nx}" y="{ny}" font-size="{FONT_NOTE}" '
            f'font-weight="bold" fill="{COLOR_BLACK}">Notes:</text>'
        ]
        for i, note in enumerate(self.spec.notes[:5]):
            parts.append(
                f'<text x="{nx}" y="{ny + 15 + i * 14}" font-size="{FONT_NOTE}" '
                f'fill="{COLOR_BLACK}">{i + 1}. {_escape_xml(note[:120])}</text>'
            )
        return "\n".join(parts)

    def _draw_legend(self) -> str:
        """Draw wire type legend."""
        lx = MARGIN_LEFT + 20
        ly = CANVAS_HEIGHT - 30

        # Collect wire types used
        wire_types_used = {c.wire_type for c in self.spec.connections}
        if not wire_types_used:
            return ""

        parts = []
        offset = 0
        for wt in sorted(wire_types_used):
            color = WIRE_COLORS.get(wt, COLOR_BLACK)
            x = lx + offset
            parts.append(
                f'<line x1="{x}" y1="{ly}" x2="{x + 20}" y2="{ly}" '
                f'stroke="{color}" stroke-width="{STROKE_PRIMARY}"/>'
            )
            parts.append(
                f'<text x="{x + 25}" y="{ly + 4}" font-size="8" '
                f'fill="{COLOR_BLACK}">{wt}</text>'
            )
            offset += 80

        return "\n".join(parts)


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_from_json(spec_json: dict) -> bytes:
    """Convenience: parse JSON dict into DiagramSpec and render PNG."""
    spec = DiagramSpec.model_validate(spec_json)
    renderer = WiringRenderer(spec)
    return renderer.render_png()


def render_markdown_summary(spec: DiagramSpec) -> str:
    """Generate the Telegram markdown summary for a diagram."""
    lines = [
        f"**{spec.title}**",
        f"Drawing: {spec.drawing_number} Rev {spec.revision}",
        "",
    ]

    if spec.components:
        lines.append("**Components:**")
        for comp in spec.components:
            ratings_str = ""
            if comp.ratings:
                r = comp.ratings
                parts = []
                if r.voltage:
                    parts.append(r.voltage)
                if r.current:
                    parts.append(r.current)
                if r.power:
                    parts.append(r.power)
                ratings_str = ", " + ", ".join(parts) if parts else ""
            label = comp.label or comp.type.replace("_", " ").title()
            lines.append(f"- {comp.tag}: {label}{ratings_str}")

    if spec.connections:
        lines.append("")
        lines.append("**Connections:**")
        lines.append("| From | To | Wire | Type |")
        lines.append("|------|----|------|------|")
        for conn in spec.connections[:15]:
            lines.append(
                f"| {conn.from_terminal} | {conn.to_terminal} | "
                f"{conn.wire_label} | {conn.wire_type} |"
            )
        if len(spec.connections) > 15:
            lines.append(f"| ... | +{len(spec.connections) - 15} more | | |")

    if spec.notes:
        lines.append("")
        lines.append("**Notes:**")
        for note in spec.notes:
            lines.append(f"- {note}")

    return "\n".join(lines)
