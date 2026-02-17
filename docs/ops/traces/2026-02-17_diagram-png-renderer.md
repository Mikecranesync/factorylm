# Ops Trace: Spec-Driven PNG Wiring Diagram Generator

**Date:** 2026-02-17
**Branch:** `feat/diagram-png-renderer`
**VPS Commit:** `7f7109e`
**PR:** https://github.com/Mikecranesync/openclaw/pull/5

## What Changed

Replaced ASCII art diagram generation with a professional IEC 60617 rendering engine that produces PNG images sent via Telegram. Two parallel workstreams:

1. **Eaton Wiring Manual KB Load** — parsed 594-page PDF into 695 structured KB atoms (570 concept, 76 fault_code, 36 spec, 12 procedure, 1 checklist)
2. **Diagram Rendering Engine** — new `openclaw/diagram/` package: schema → layout → symbols → renderer → PNG

### Files Created (6 new, 2 modified)

| File | Change |
|------|--------|
| `openclaw/diagram/__init__.py` | Package init |
| `openclaw/diagram/schema.py` | Pydantic models: DiagramSpec, Component, Connection, Bus, Ratings, Terminal, LayoutHints |
| `openclaw/diagram/style.py` | IEC visual constants: 2-tier stroke weights, wire colors, font sizes, layout spacing |
| `openclaw/diagram/symbols.py` | 20 IEC 60617 symbol functions with terminal position tracking |
| `openclaw/diagram/layout.py` | Auto-placement: power devices top-to-bottom, control left-to-right; orthogonal wire routing |
| `openclaw/diagram/renderer.py` | WiringRenderer: SVG generation + CairoSVG PNG export + markdown summary |
| `openclaw/skills/builtin/diagram.py` | Replaced ASCII art with JSON spec generation via LLM json_mode + PNG rendering |
| `openclaw/gateway/telegram.py` | Added `_send_attachments()` for photo/document delivery from OutboundMessage |

### VPS Package Installs

- `cairosvg` 2.8.2 (SVG → PNG conversion)
- `svgwrite` 1.4.3 (SVG generation helper)
- `Pillow` 12.1.1 (image manipulation)
- System libraries (`libcairo2`, `libpango`) were already present

### KB Atom Load

- Source: `eaton-wiring-manual-pu08703001z-en-en-us.pdf` (594 pages, 12 chapters)
- Parser: `scripts/parse_eaton_manual.py` (local, PyMuPDF)
- Loader: `scripts/load_kb_atoms.py` (VPS, asyncpg)
- Added `fault_code`, `spec`, `checklist` to `knowledge_atoms_atom_type_check` constraint
- Total KB: 5,312 atoms (was 4,617; +695 Eaton atoms)

## Architecture

```
User: "/diagram DOL motor starter 11kW"
  │
  ▼
DiagramSkill.handle()
  1. Search KB → Eaton wiring references
  2. Build LLM prompt with spec schema + KB context
  3. LLM generates JSON DiagramSpec (json_mode=true)
  4. Parse into Pydantic DiagramSpec
  5. WiringRenderer:
     a. compute_layout() — auto-place components + buses
     b. draw symbols (20 IEC 60617 types) → record terminal positions
     c. route_wires() — orthogonal L-routing between terminals
     d. draw buses, connection dots, terminal labels, title block
     e. CairoSVG → PNG bytes
  6. Return OutboundMessage with PNG attachment + markdown summary
  │
  ▼
TelegramAdapter._send_attachments()
  → reply_photo(png_bytes)
  → reply_text(markdown_summary)
```

## Symbol Library (20 types)

| Symbol | IEC Convention |
|--------|---------------|
| motor_3ph | Circle with M + 3~, U/V/W + PE terminals |
| motor_1ph | Circle with M + 1~, L/N terminals |
| contactor_3pole | Rectangle with NO contacts, 1-6 power + A1/A2 coil + 13/14 aux |
| contactor_coil | Rectangle with horizontal leads (control circuit) |
| overload_relay | Rectangle with OL zigzag heaters, 1-6 power + 95/96 NC aux |
| circuit_breaker | Rectangle with X-pattern per pole, 1-6 terminals |
| fuse | Small rectangle with line through center |
| pushbutton_no | Diagonal arm NOT touching (gap = normally open) |
| pushbutton_nc | Diagonal arm crossing vertical bar (NC) |
| emergency_stop | Mushroom cap arc + NC contact + red indicator |
| terminal_block | Small unfilled circle with stubs |
| plc_input_card | Tall rectangle with labeled left/right pins |
| plc_output_card | Same as input card |
| vfd | Large rectangle with R/S/T input, U/V/W output, FWD/REV/VI/ACM/FA control |
| transformer | Dual coil arcs with core lines |
| indicator_light | Circle with X inside |
| proximity_sensor | Rectangle with sensing face + 3-wire output |
| relay_coil | Rectangle with leads (same as contactor_coil) |
| relay_contact_no | Diagonal arm with arc at pivot |
| relay_contact_nc | Arm crosses bar with arc at pivot |

## Verification

- Render test passed: 43KB PNG generated for DOL motor starter spec
- 11 skills registered in journalctl
- Health check: `curl localhost:8340/` shows all skills + providers
- Branch pushed: `origin/feat/diagram-png-renderer`
- PR: https://github.com/Mikecranesync/openclaw/pull/5
