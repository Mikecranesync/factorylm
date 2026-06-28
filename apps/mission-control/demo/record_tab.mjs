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

const TAB_META = {
  '01_chat_relay':   { label: 'Chat Relay',   route: '/' },
  '02_dashboard':    { label: 'Dashboard',    route: '/dashboard' },
  '03_terminal':     { label: 'Terminal',     route: '/terminal' },
  '04_worker_swarm': { label: 'Worker Swarm', route: '/workers' },
  '05_ralph_loop':   { label: 'Ralph Loop',   route: '/ralph' },
  '06_agents':       { label: 'Agents',       route: '/agents' },
  '07_tools':        { label: 'Tools',        route: '/tools' },
  '08_hub':          { label: 'Ladder Logic', route: '/hub' },
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
    await page.evaluate((dy) => window.scrollBy({ top: dy, behavior: 'smooth' }), delta)
    await page.waitForTimeout(400)
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

// Navigate to Hub root, then to the correct tab
await page.goto(HUB_URL, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)

// Navigate to this tab via sidebar click
try {
  await page.click(`a:has-text("${label}")`, { timeout: 5000 })
  await page.waitForTimeout(1500)
} catch (_) {
  console.warn(`  WARN: Could not click sidebar link for "${label}" — proceeding from root`)
}

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
