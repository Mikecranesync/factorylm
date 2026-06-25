# FactoryLM Hub and Conveyor Lab: Issues and Documentation Gaps

## FactoryLM Hub Issues

### 1. Dashboard Placeholder
- **Location:** `factorylm/apps/dashboard/`
- **Problem:** Only a stub (`NOT_IMPLEMENTED.md`) – no real UI for monitoring Stardust Racers coaster or the `conv_simple` conveyor cell.
- **Impact:** No central "one‑glass" view of open faults, dispatch intervals, or conveyor status.
- **Fix:** Build out the dashboard with real‑time UNS tiles for Stardust block zones and conveyor‑cell panel (PLC tags, VFD status, sensor data). Include assignable fault list with aging timers.

### 2. Lint / React‑Hooks Violations in `mira-hub`
- **Location:** `MIRA/mira-hub/src/app/(hub)/...`
- **Specific warnings:**
  - `admin/users/page.tsx`: `useEffect` calls `setState` synchronously → cascading renders.
  - `alerts/page.tsx` and `assets/[id]/page.tsx`: Hooks (`useTranslations`, `useState`) called conditionally → breaks Rules of Hooks.
- **Impact:** Unnecessary re‑runs, possible UI stalls, noisy console.
- **Fix:** 
  1. Move state updates out of effect bodies (call state inside the async function).
  2. Ensure every hook call lives at the top level of the component.
  3. Run `bun run lint` and add a lint step to CI.

### 3. Missing / Noisy Environment Variables (Docker Compose)
- **Observed warnings:** `TELEGRAM_BOT_TOKEN`, `SLACK_*`, `REDDIT_*`, `APIFY_API_KEY`, `NEON_DATABASE_URL`, `ANTHROPIC_API_KEY`, etc., default to empty strings.
- **Impact:** Clutters logs, may cause silent failures for integrations.
- **Fix:** 
  - Populate required secrets via Doppler (`factorylm/prd`) for services that need them.
  - For optional dev‑only integrations, either provide harmless defaults or guard initialization with `if (!process.env.VAR) return;`.
  - Document mandatory vars for a minimal dev run.

### 4. Unified Namespace (UNS) Model Gaps
- **Stardust Racers (coaster):**
  - Zones (Launch 1/2, Station Load/Unload) are "empty shells" – no live telemetry mapped.
  - Missing UNS topics for: proximity‑sensor health per block, LSM launch‑ready flags, magnetic‑brake status, dispatch‑interval timers, ride‑stop fault latching.
- **Conveyor Cell (`conv_simple`):**
  - Basic asset model present, but live data from Micro820 PLC (motor‑run command, fault codes, Modbus‑TCP comm status) and GS10 VFD (speed, current, accel/decel) not flowing into the UNS.
  - Sort‑by‑height sensor not modeled.
- **Impact:** Cannot answer historical fault questions or view real‑time conveyor speed from UNS; tribal knowledge siloed.
- **Fix:**
  - Work with controls lead (Reggie) to enumerate exact Modbus tags / IEC‑61131 addresses for each Stardust block and conveyor device.
  - Add corresponding asset definitions in the UNS (e.g., `uns://factory/Stardust/Launch1/Prox/Health`).
  - Ensure `diagnosis` or `plc-modbus` service publishes those tags to the UNS (MQTT/Kafka) on change or at suitable intervals.
  - Have a junior tech (Marcus) build a simple UNS‑viewer widget for the conveyor cell as a learning task.

### 5. CI/CD / Pre‑commit Gaps
- The lint errors above indicate no automated gate keeping bad patterns out of `mira-hub`.
- **Fix:**
  - Add a `lint` step to the project’s CI (GitHub Actions or similar) that runs `bun run lint` and fails on warnings/errors.
  - Consider a pre‑commit hook (`husky` + `lint‑staged`) for instant feedback before pushing.

## Conveyor Lab Documentation Audit

**Location:** `factorylm/apps/conveyor-lab/`  
**Current files:** 
- `README.md`
- `backend/` (source)
- `frontend/` (source)

### Missing / Recommended Documentation Files

| Expected Doc | Why It’s Useful / Typical Content | Status |
|--------------|-----------------------------------|--------|
| `CONTRIBUTING.md` | Guidelines for contributors (setup, coding style, PR process, testing). | Missing |
| `CODE_OF_CONDUCT.md` | Project conduct expectations (often a pointer to a shared repo‑wide file). | Missing |
| `CONTRIBUTORS` / `AUTHORS` | List of people who have contributed (optional but nice for recognition). | Missing |
| `DEVELOPMENT.md` or `DEVELOPMENT_GUIDE.md` | Detailed dev setup, linting, testing, building, debugging steps beyond the quick start. | Missing |
| `ARCHITECTURE.md` | High‑level diagram & description of the HMI/backend/frontend stack, data flow (Modbus ↔ WebSocket ↔ UI). | Missing |
| `DESIGN.md` | UI/UX rationale (ISA‑101 compliance, color scheme, layout choices). | Missing |
| `API.md` (or `API_REFERENCE.md`) | Auto‑generated or hand‑written reference for the REST (`/api/*`) and WebSocket (`/ws/telemetry`) endpoints, payloads, error codes. | Missing |
| `TROUBLESHOOTING.md` / `FAQ.md` | Common issues (Factory I/O not detected, Modbus timeout, voice‑recognition permission problems) and their fixes. | Missing |
| `CHANGELOG.md` | Chronological list of notable changes per version (helps users/admin track upgrades). | Missing |
| `LICENSE` | Full license text (MIT is mentioned in README but a standalone file is standard). | Missing |
| `SECURITY.md` | Instructions for reporting security vulnerabilities (optional but good practice). | Missing |
| `SUPPORT.md` | Where to get help (e.g., Discord, mailing list, issue tracker). | Missing |
| `ROADMAP.md` | Planned features or improvements (useful for contributors). | Missing |
| `STYLE.md` or `CODE_STYLE.md` | Coding conventions (TypeScript/JS, ESLint/Prettier rules) if not fully covered by tooling config. | Missing |
| `DATA_FLOW.md` or `MODBUS_MAP.md` | Detailed mapping of Modbus registers/coils to the HMI gauges & controls (currently only in README tables). | Missing (could be a subsection of `ARCHITECTURE.md`) |

### Quick Wins for Documentation

1. **Create a `CONTRIBUTING.md`** – point to the existing README for the quick start, then add:
   - Prerequisites (Node.js, Bun/npm, Factory I/O)
   - How to run lint (`bun run lint`) and tests (`bun run test`)
   - Pull‑request checklist (lint passes, tests pass, updated docs if needed)
   - Coding style (refer to existing ESLint/Prettier config)

2. **Add a minimal `CODE_OF_CONDUCT.md`** – can simply reference the Contributor Covenant v2.1 (or the project‑wide file if one exists).

3. **Copy the MIT license text into a `LICENSE` file** (the repo likely already has one at the root; you can symlink or duplicate it here for clarity).

4. **Extract the Modbus register table** from the README into a dedicated `MODBUS_MAP.md` (or keep it in `ARCHITECTURE.md`) and add a simple diagram of the data flow (Factory I/O ↔ Modbus TCP Client ↔ WebSocket Server ↔ Browser).

5. **Draft a `TROUBLESHOOTING.md`** using the existing “Troubleshooting” section from the README as a starting point, then expand with any additional gotchas you’ve seen while testing.

6. **Consider a `CHANGELOG.md`** – even if the project is still pre‑1.0, logging notable changes (e.g., “added PTT voice control”, “switched to Vite”, “added ISA‑101 theme”) helps contributors and users.

### Next Steps for the Team

- **Assign an owner** (e.g., Marcus – a good “growth” task) to create the missing docs.
- **Review** the newly added files in a quick PR; ensure they link back to the README where appropriate.
- **Link** the new docs from the README’s “See also” or “Further reading” section so newcomers discover them easily.

---

**Bottom line:** The biggest blockers right now are the missing dashboard and the UNS gaps – without those you’re still fighting fires blind‑sided. Fix the lint and env‑var noise to keep the dev base clean, then get the UNS populated and the dashboard lit up. Once you’ve got real‑time block‑zone and conveyor data in one place, you’ll spend less time chasing ghosts and more time keeping the line moving.