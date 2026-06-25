# Conveyor Lab Design Notes

The UI should feel like an industrial HMI, not a marketing page.

## Principles

- Status must be readable at a glance.
- Controls must make current state, requested state, and fault state distinct.
- Use compact panels for repeated operational data.
- Keep colors meaningful and consistent.
- Avoid decorative animation that could be confused with machine state.

## HMI Color Semantics

| Meaning | Preferred Treatment |
|---------|---------------------|
| Running or healthy | Green status lamp |
| Warning or degraded | Amber status lamp |
| Fault or unsafe | Red status lamp |
| Stopped or idle | Neutral gray |
| Manual action | Button with clear icon and label |

## Mobile Constraints

The Telegram Mini App surface is narrow. Primary controls should stay reachable without horizontal scroll, and telemetry should collapse into scan-friendly rows instead of dense tables.
