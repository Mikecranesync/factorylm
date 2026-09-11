# FactoryLM UI Design Policy

**Status:** Canonical UI policy  
**Applies to:** FactoryLM + MIRA user-facing web/mobile UI  
**Last updated:** 2026-09-10  
**Owner:** Product/UX direction is set by Mike; agents implement and verify it.  

> **North star:** FactoryLM should feel like **quiet industrial software with a ChatGPT-class interaction model** — content-first, restrained, consistent, fast, and obvious. It must not look like a generic AI-generated SaaS template.

This file is repo-owned policy. Figma may later become the visual editing and approval surface, but **Figma is not the source of truth for the design system**. The durable design rules, tokens, components, states, and acceptance evidence live in the repository.

---

## 1. Why this exists

FactoryLM/MIRA has accumulated working UI faster than it has accumulated visual discipline. That creates the familiar “AI slop” failure mode: individually plausible screens with inconsistent spacing, arbitrary cards, one-off controls, decorative gradients, oversized radii, duplicate patterns, and styles invented screen-by-screen by different agents.

The fix is not “make each screen prettier.” The fix is to establish one small visual language and require all UI work to use it.

**System rule:**

> Fix the system, not the screenshot.

Examples:

- Ugly button → fix the canonical `Button` primitive.
- Ugly sidebar → fix the canonical `Sidebar` primitive/pattern.
- Ugly spacing → fix the spacing/layout tokens.
- Ugly machine header → fix the shared machine-context component.
- Ugly empty state → establish one canonical empty-state pattern.

Prefer one systemic correction that improves many screens over local CSS patches on each screen.

---

## 2. Current evidence baseline — 2026-09-10

The current Pixel UI catalog is the baseline evidence set for the unified shell.

**Current state:**

- Live dogfood build: **#3746** unified shell.
- Catalog: **12 unique screens + classic Workorders**.
- Bravo pack: `/Users/bravonode/mira-dogfood/ui-catalog-2026-09-10/` plus ZIP.
- Durable note: https://github.com/Mikecranesync/MIRA/pull/3746#issuecomment-5627490178
- Shell restored to `flm.chatui.v1=unified`.
- #3746 remains draft/behind.
- No merge, deploy, OTA, or Pixel-ready claim is authorized by this document.

### Immediate evidence work

Complete **A + light B**, not C:

**A — short wiki/docs page from the Bravo catalog**

Document the unified shell so IR/reviewers do not guess what currently exists. Cover at least:

- Ask vs Work
- sidebar/navigation
- scan/nameplate sheet
- sensor sheet
- no-machine/general Ask state
- classic Workorders continuity

**Light B — selected #3746 frames only**

Attach representative evidence frames for:

- Empty Ask
- Work
- Sidebar
- Scan/nameplate
- Sensor
- Classic Workorders

Do **not** attach Camera-open evidence until a human proves `+ → Camera` on this exact build.

### Open acceptance items

- **Camera human proof:** OPEN until a person taps `+ → Camera` on #3746 and verifies the expected camera behavior.
- **VFD general Ask:** OPEN until `What is a VFD?` passes with **no machine selected**.
- **12-screen regression walk:** required on each serious candidate before a Pixel-ready claim.

Do not hide these gaps by parking the UI lane. Keep them visible as acceptance work while structural/design-system work continues.

---

## 3. Design authority order

When sources disagree, use this order:

1. Explicit product/UX decisions from the product owner.
2. This canonical repo design policy.
3. Canonical shared components and design tokens.
4. Accepted Pixel/device evidence.
5. Existing unified-shell behavior.
6. Agent aesthetic judgment.

**Agent preference is last.**

If two higher-authority sources materially disagree, stop and report the conflict instead of improvising a third interpretation.

---

## 4. Design direction: “Quiet industrial software”

FactoryLM gets its industrial identity from the **work and evidence**, not decorative chrome.

Industrial identity should come from:

- machines and equipment names
- asset metadata
- manuals and documentation
- citations and source passages
- nameplate photos
- faults and diagnostic history
- work orders and maintenance history
- sensor readings
- real machine/work context

It should **not** come from fake futuristic styling, dashboard decoration, glowing controls, hazard-striping-as-decoration, or generic “AI” visuals.

The application shell should be neutral and restrained enough that the machine, evidence, and technician workflow are what users notice.

Useful shorthand:

> **ChatGPT interaction restraint + industrial service software information density.**

Not:

> **AI SaaS startup dashboard.**

---

## 5. AI-slop denylist

Do not introduce the following without a documented, intentional product/design reason:

- purple/blue “AI” gradients
- glowing backgrounds
- decorative blobs/orbs
- glassmorphism
- excessive backdrop blur
- gradient borders
- arbitrary shadows
- giant rounded cards everywhere
- cards nested inside cards
- unnecessary pill-shaped containers
- meaningless colored status chips
- sparkle/magic/AI icons used decoratively
- oversized SaaS marketing headings inside the application
- unnecessary animation
- decorative illustrations on operational screens
- unrelated visual treatments invented separately for each screen
- arbitrary new colors
- arbitrary new radii
- arbitrary new spacing values
- one-off buttons
- one-off form controls
- duplicate navigation patterns
- decorative dashboard tiles where plain information hierarchy would work
- excessive badges for normal states
- fake “technical” ornamentation with no operational meaning

**“Looks cool” is not sufficient justification.**

This denylist is a guard against unintentional default aesthetics, not a ban on every listed technique forever. Exceptions must be deliberate, reusable, and justified by user need.

---

## 6. Visual vocabulary must stay small

Normalize FactoryLM around a deliberately small vocabulary.

Prefer:

- one primary type family
- a small typography scale
- a small spacing scale
- a restrained radius scale
- one icon family
- a small set of button variants
- a small set of input/composer variants
- a few meaningful surface levels
- semantic colors only where meaning requires them
- predictable content widths and gutters
- consistent divider/border behavior

Feature PRs must not quietly expand this vocabulary.

If a new token or component is genuinely required, add it to the shared system rather than leaving it local to one screen.

---

## 7. Canonical design-system inventory

Before broad aesthetic work, identify the canonical implementation location(s) for each of the following:

- typography
- spacing
- colors
- borders
- corner radii
- elevations/shadows
- icon set
- buttons
- inputs
- composer
- sidebar/navigation
- sheets/dialogs
- message/content layout
- citations
- machine/asset context
- status presentation
- empty states
- loading states
- error states
- Work/Ask transitions

Do **not** create another parallel UI package, theme, shell, component library, or styling system if an existing canonical location can be extended.

For each category record:

- canonical path
- current owner/package
- duplicate implementations
- consumers
- whether consolidation is safe now
- whether a compatibility layer is temporarily required

---

## 8. Canonical component inventory

Map the accepted screens to the primitives that produce them.

Use this model:

```text
SCREEN
  → SHELL
  → NAVIGATION
  → COMPONENTS
  → STATES
  → TOKENS
```

The purpose is to expose places where two screens perform the same function with different markup, components, or styling.

When duplicates are found, prefer consolidating the underlying pattern over polishing both implementations.

Examples of likely canonical families:

- AppShell
- Sidebar
- Project/Thread list item
- Header / context bar
- MachineContext
- Message/Answer content
- Citation/Source affordance
- Composer
- Attachment action
- Sheet/Dialog
- EmptyState
- ErrorState
- LoadingState
- WorkOrder surface/bridge

Names above are conceptual; do not rename working code merely to match this document.

---

## 9. Ask and Work are one product

Ask and Work are modes of the same FactoryLM product.

Do not make them look like separate applications.

Differences should come primarily from:

- information architecture
- available actions
- machine/work context
- content and workflow

They should still share the same:

- typography
- spacing rhythm
- navigation grammar
- interaction primitives
- icon family
- button/input language
- surface treatment

---

## 10. No-machine Ask is first-class

Machine context must enrich a conversation, not become a prerequisite for useful general questions.

Adding a machine may reveal useful context, but should not transform the UI into a dashboard full of cards, badges, colors, and panels.

The no-machine state is a first-class product state.

Therefore:

> `What is a VFD?` with no machine selected is an important acceptance case, not an edge case.

---

## 11. Separate structure from style

Agents may continue improving structural/behavioral UX while visual cleanup is underway, including:

- information architecture
- Projects and thread organization
- navigation/back behavior
- history persistence
- machine scope
- attachments
- citations
- accessibility
- responsive behavior
- keyboard/safe-area behavior
- loading/error/empty states

But those changes must use established visual primitives. Structural work is not permission to invent a new aesthetic locally.

---

## 12. The 12-screen catalog is a regression fixture

The Pixel catalog is not a one-time screenshot dump. Treat it as a fixed acceptance walk.

Create/maintain a simple manifest for the canonical states. Each state should record:

- state/screen name
- expected route/context
- exact build/head
- required visible elements
- important interaction(s)
- acceptance status
- evidence reference

Every serious Pixel candidate should repeat the same walk before anyone claims Pixel-ready.

Do not rely on memory when deciding whether the UI drifted.

When a new canonical user-visible state is added, decide deliberately whether it belongs in this manifest.

---

## 13. UI PR evidence contract

Meaningful presentation changes should include evidence sufficient for another reviewer to understand exactly what changed.

Include:

- exact branch/head/build
- affected canonical screens
- before evidence
- after evidence
- intentional design-system change, if any
- neighboring-state regression result
- known unverified interactions

**“No obvious regression” is not evidence. Show it.**

Do not label an interaction as proven merely because its button is visible in a screenshot.

Example: Camera-open remains unproven until someone actually taps `+ → Camera` on the tested build.

---

## 14. Pre-Figma implementation phases

Figma is optional. Work can and should become disciplined before Figma is connected.

### Phase 0 — preserve current evidence

- Complete the catalog wiki/docs page.
- Attach selected frames to #3746.
- Preserve the exact build/head association.
- Keep VFD and Camera acceptance items visible.

### Phase 1 — inventory before styling

- Locate current tokens/styles/primitives.
- Locate duplicate component systems.
- Locate one-off styling hotspots.
- Identify which package/shell is canonical under the unified-UI cutover.
- Produce a short KEEP / CONSOLIDATE / RETIRE / DEFER map.

Do not broadly restyle during this inventory.

### Phase 2 — token normalization

Converge arbitrary visual values toward canonical tokens for:

- spacing
- type
- radii
- borders
- surfaces
- semantic color
- shadows/elevation

Prefer mechanical/systemic cleanup over aesthetic invention.

### Phase 3 — primitive consolidation

Consolidate the highest-leverage shared primitives first, such as:

- button
- input/composer
- sidebar/navigation row
- sheet/dialog
- empty/loading/error states
- message content
- machine context

Prove each change across all known consumers.

### Phase 4 — screen cleanup

Apply the canonical system to the 12-screen set.

For each screen ask:

1. Is hierarchy obvious?
2. Is anything decorative without purpose?
3. Is information duplicated?
4. Is this using canonical primitives?
5. Are spacing/type/radius values canonical?
6. Does this still feel like the same application as neighboring states?

### Phase 5 — device acceptance

- run the full 12-screen walk
- prove navigation/back behavior
- prove scrolling and keyboard behavior where relevant
- prove Camera human tap
- prove VFD no-machine Ask
- record exact head/build

Only then is a Pixel-ready claim eligible for review.

---

## 15. Figma’s future role

When Figma is connected, do **not** independently rebuild a second design system inside Figma.

The intended mapping is:

```text
Repo design policy  ↔  Figma design guidance
Repo tokens         ↔  Figma variables
Repo components     ↔  Figma components
12 Pixel states     ↔  Figma frames
Approved Figma      ↔  implementation target
Implemented UI      ↔  device/browser evidence
```

Figma becomes the visual editor and approval surface for the same system already defined in code/docs.

A useful future loop is:

```text
Current UI/device evidence
        ↓
Figma reference + editable proposed frames
        ↓
Human visual approval
        ↓
Implementation using canonical repo primitives
        ↓
Capture/compare implemented UI
        ↓
Pixel/device acceptance
```

If Figma disappears, the FactoryLM design system must still remain understandable and enforceable from the repository.

---

## 16. Open-source/reference stack

These are reference tools/patterns, not automatic dependencies.

### assistant-ui

Use as a reference/implementation layer for ChatGPT-class interaction behavior where already adopted: message rendering, composer behavior, streaming, scrolling, attachments, accessibility, and conversation primitives.

**Policy:** behavior infrastructure does not dictate FactoryLM’s visual identity.

### shadcn/ui

Use as a component-pattern/reference source where appropriate, not as a license to ship untouched defaults everywhere.

**Policy:** default shadcn styling can itself become generic AI-looking output. Components must resolve through FactoryLM’s restrained tokens and product needs.

### TweakCN

May be used as a visual exploration/tuning aid for shadcn-style tokens/themes.

**Policy:** exported values are proposals until they are normalized into the canonical repo token system.

### avoid-ai-design / equivalent audits

May be used as a heuristic audit for common AI-generated visual tells.

**Policy:** automated “anti-slop” tools are reviewers, not design authorities.

### Figma

Future visual authoring/approval surface. Optional to continue current cleanup.

**Dependency rule:** no project is adopted merely because it appears in this section. All normal repo license, security, dependency, and governance requirements still apply. MIRA’s license constraints remain authoritative.

---

## 17. Agent working rules

When assigned UI work:

1. Read root `AGENTS.md` and this file first.
2. Read the current unified-UI cutover/architecture guidance for the repo.
3. Identify the canonical component/token path before editing.
4. Inspect known consumers of the primitive being changed.
5. Prefer the smallest systemic fix.
6. Run relevant tests/guards.
7. Capture before/after evidence for meaningful presentation changes.
8. Run or report the relevant catalog states.
9. Keep unproven interactions explicitly OPEN.
10. Do not merge/deploy/OTA unless separately authorized.

Do not hand-sculpt an individual screen unless the design genuinely cannot be represented by an existing/shared pattern. If a new pattern is required, make it canonical and document why.

---

## 18. Stop conditions

Stop and report rather than improvising when:

- two canonical sources disagree
- a change requires creating a second component system
- a new design direction is being introduced
- a feature requires bypassing the shared shell
- fixing one screen would knowingly make another canonical state inconsistent
- the correct canonical component/token owner cannot be identified
- a lifecycle/governance guard requires an exception not already authorized
- Pixel/device evidence would be claimed without actually performing the interaction

Do not paper over structural disagreement with CSS.

---

## 19. Required implementation report

For a design-policy implementation pass, report:

```text
A / wiki evidence: PASS/FAIL
#3746 selected evidence: PASS/FAIL
Canonical design-system location: <path>
Design policy: docs/ux/FACTORYLM_UI_DESIGN_POLICY.md
Token source: <path>
Component inventory: <path>
12-screen manifest: <path>
Duplicate/competing UI systems found: <list>
AI-slop violations identified: <count + categories>
Systemic cleanup candidates: <ordered list>
Changes implemented: <summary>
Tests/guards: <results>
VFD general Ask: PASS/FAIL/OPEN
Camera human-tap proof: PASS/OPEN
12-screen regression walk: PASS/FAIL/NOT RUN
Exact head/build: <sha/build>
Remaining blockers: <list>
Merge/deploy/OTA performed: NO unless separately authorized
```

---

## 20. Definition of done for the design-system cleanup

The cleanup is not done because one screenshot looks good.

It is done when:

- canonical tokens/primitives are identifiable
- duplicate visual systems have a disposition
- the 12-screen set uses a consistent vocabulary
- new arbitrary values/components are no longer appearing casually
- Ask and Work read as one product
- no-machine Ask is healthy
- UI PRs carry visual evidence
- regressions are checked against the same fixed screen inventory
- human/device-only interactions remain honestly distinguished from screenshot evidence
- Figma can be added later without changing who owns the design rules

The enduring goal is simple:

> **FactoryLM should look intentionally designed even when no designer or Figma session is present, because the design discipline is encoded in the product itself.**
