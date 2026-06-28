/**
 * Mission Control — Per-Tab Promo Recorder
 *
 * Records a single tab's promo video from the live production site.
 * Reads demo/tabs/<slug>/script.md, drives the UI, outputs webm.
 *
 * Usage:
 *   node demo/record_tab.mjs <slug>
 *
 * Slugs:
 *   01_chat_relay   02_dashboard   03_terminal   04_worker_swarm
 *   05_ralph_loop   06_agents      07_tools       08_hub
 *
 * Prerequisites:
 *   1. node demo/login.mjs  →  demo/auth.json must exist
 *   2. Playwright chromium installed: npx playwright install chromium
 *
 * Env vars:
 *   HUB_URL   Base URL of the Hub (default: https://app.factorylm.com)
 */

import { chromium } from 'playwright'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const HUB_URL = process.env.HUB_URL || 'https://app.factorylm.com'
const AUTH_PATH = join(__dirname, 'auth.json')

// Real routes verified live 2026-06-28 via demo/discover_nav.mjs. The old
// mission-control tabs (Dashboard/Terminal/…) no longer exist — the app is now
// the MIRA/CMMS Hub. Navigation goes by route (see main), not sidebar label,
// so a future sidebar reshuffle won't silently land every tab on the default board.
const TAB_META = {
  '01_command_board':  { label: 'Command Board',  route: '/feed/' },
  '02_command_center': { label: 'Command Center', route: '/command-center/' },
  '03_namespace':      { label: 'Namespace',      route: '/namespace/' },
  '04_knowledge':      { label: 'Knowledge',      route: '/knowledge/' },
  '05_channels':       { label: 'Channels',       route: '/channels/' },
  '06_assets':         { label: 'Assets',         route: '/assets/' },
  '07_workorders':     { label: 'Work Orders',    route: '/workorders/' },
  '08_scan':           { label: 'Scan',           route: '/scan/' },
}

// ---------------------------------------------------------------------------
// Arg validation
// ---------------------------------------------------------------------------

const slug = process.argv[2]
if (!slug || !TAB_META[slug]) {
  console.error(`Usage: node demo/record_tab.mjs <slug>`)
  console.error(`Slugs: ${Object.keys(TAB_META).join('  ')}`)
  process.exit(1)
}

if (!existsSync(AUTH_PATH)) {
  console.error(`ERROR: ${AUTH_PATH} not found.`)
  console.error('Run: HUB_EMAIL=x HUB_PASSWORD=y node demo/login.mjs')
  process.exit(1)
}

const { label, route } = TAB_META[slug]
const TAB_DIR = join(__dirname, 'tabs', slug)
const SCRIPT_PATH = join(TAB_DIR, 'script.md')
const RAW_DIR = join(TAB_DIR, 'raw')
const TIMECODES_PATH = join(TAB_DIR, 'timecodes.json')

mkdirSync(RAW_DIR, { recursive: true })

// ---------------------------------------------------------------------------
// Script parser (same as record.mjs)
// ---------------------------------------------------------------------------

function parseTimestamp(ts) {
  const [h, m, s] = ts.split(':').map(Number)
  return h * 3600 + m * 60 + s
}

function parseScript(path) {
  const lines = readFileSync(path, 'utf8').split('\n')
  const segments = []
  for (const line of lines) {
    const match = line.match(/^\[(\d{2}:\d{2}:\d{2})\]\s+\[([^\]]+)\]\s+(.+)$/)
    if (!match) continue
    const [, ts, action, narration] = match
    segments.push({ ts, t: parseTimestamp(ts), action: action.trim(), narration: narration.trim() })
  }
  for (let i = 0; i < segments.length; i++) {
    segments[i].duration_s = i < segments.length - 1
      ? segments[i + 1].t - segments[i].t
      : 0
  }
  return segments.filter(s => s.action !== 'END')
}

// ---------------------------------------------------------------------------
// Action executor — same as record.mjs but with production-safe selectors
// ---------------------------------------------------------------------------

async function executeAction(page, action) {
  if (action === 'PAUSE') return

  if (action.startsWith('NAV:')) {
    const routeKey = action.slice(4)
    // Try sidebar NavLink click first (works regardless of base URL structure)
    const linkLabel = Object.values(TAB_META).find(m => m.route === routeKey)?.label
    if (linkLabel) {
      try {
        await page.click(`a:has-text("${linkLabel}")`, { timeout: 3000 })
        await page.waitForTimeout(800)
        return
      } catch (_) {}
    }
    // Fallback: goto relative to current origin
    const origin = new URL(page.url()).origin
    await page.goto(`${origin}${routeKey}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(800)
    return
  }

  if (action.startsWith('CLICK:')) {
    const selector = action.slice(6)
    try { await page.click(selector, { timeout: 2000 }) } catch (_) {
      console.warn(`  WARN: CLICK failed: ${selector}`)
    }
    return
  }

  if (action.startsWith('FILL:')) {
    const rest = action.slice(5)
    const colonIdx = rest.indexOf(':')
    if (colonIdx === -1) return
    const selector = rest.slice(0, colonIdx)
    const value = rest.slice(colonIdx + 1)
    try { await page.fill(selector, value, { timeout: 2000 }) } catch (_) {
      console.warn(`  WARN: FILL failed: ${selector}`)
    }
    return
  }

  if (action.startsWith('HOVER:')) {
    const selector = action.slice(6)
    try { await page.hover(selector, { timeout: 2000 }) } catch (_) {
      console.warn(`  WARN: HOVER failed: ${selector}`)
    }
    return
  }

  if (action.startsWith('SCROLL:')) {
    const delta = parseInt(action.slice(7), 10)
    // mouse.wheel scrolls the element under the cursor — works for the app's
    // inner scroll containers, which window.scrollBy() does NOT move.
    await page.mouse.move(960, 540)
    await page.mouse.wheel(0, delta)
    await page.waitForTimeout(600)
    return
  }

  console.warn(`  WARN: Unknown action: ${action}`)
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const segments = parseScript(SCRIPT_PATH)
const totalDuration = segments.reduce((a, s) => a + s.duration_s, 0)

console.log(`\nMission Control — Recording: ${slug} (${label})`)
console.log(`Segments  : ${segments.length}`)
console.log(`Duration  : ${totalDuration}s (~${Math.round(totalDuration / 60)}min)`)
console.log(`Target    : ${HUB_URL}`)
console.log(`Video out : ${RAW_DIR}/\n`)

const browser = await chromium.launch({
  headless: false,
  args: ['--start-maximized'],
})

const ctx = await browser.newContext({
  storageState: AUTH_PATH,
  recordVideo: {
    dir: RAW_DIR,
    size: { width: 1920, height: 1080 },
  },
  viewport: { width: 1920, height: 1080 },
})

const page = await ctx.newPage()

// Navigate directly to this tab's real route. Direct goto is robust against
// sidebar redesigns — the old label-click approach silently left every tab on
// the default board once the sidebar labels changed.
const targetUrl = HUB_URL.replace(/\/$/, '') + route
console.log(`Nav       : ${targetUrl}`)
await page.goto(targetUrl, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000) // let the SPA + data settle before narration starts

const timecodes = []

for (let i = 0; i < segments.length; i++) {
  const seg = segments[i]
  console.log(`[${String(i + 1).padStart(2, '0')}/${segments.length}] ${seg.ts} [${seg.action}] (${seg.duration_s}s)`)

  await executeAction(page, seg.action)
  timecodes.push({ t: seg.t, duration_s: seg.duration_s, narration: seg.narration })

  if (seg.duration_s > 0) {
    await page.waitForTimeout(seg.duration_s * 1000)
  }
}

writeFileSync(TIMECODES_PATH, JSON.stringify(timecodes, null, 2))

await ctx.close()
await browser.close()

console.log(`\nDone. Video → ${RAW_DIR}/`)
console.log(`Next: TTS_PROVIDER=macos python demo/voice.py --tab ${slug}`)
