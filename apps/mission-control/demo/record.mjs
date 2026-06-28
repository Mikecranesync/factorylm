/**
 * Mission Control Demo Recorder
 *
 * Drives the live app via Playwright, pausing on each feature for
 * exactly as long as the narration segment lasts, then records the
 * full session as a webm video.
 *
 * Usage:
 *   # From repo root:
 *   node apps/mission-control/demo/record.mjs
 *
 * Prerequisites:
 *   cd apps/mission-control/frontend && npm install playwright
 *   npx playwright install chromium
 *   Mission Control backend running: uvicorn backend.main:app --port 8090
 */

import { chromium } from 'playwright'
import { readFileSync, writeFileSync, mkdirSync } from 'fs'
import { dirname, join, resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const BASE_URL = 'http://localhost:8090'
const SCRIPT_PATH = join(__dirname, 'script.md')
const RAW_DIR = join(__dirname, 'raw')
const TIMECODES_PATH = join(__dirname, 'timecodes.json')

mkdirSync(RAW_DIR, { recursive: true })

// ---------------------------------------------------------------------------
// Script parser
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

  // Compute duration_s for each segment from next segment's timestamp
  for (let i = 0; i < segments.length; i++) {
    if (i < segments.length - 1) {
      segments[i].duration_s = segments[i + 1].t - segments[i].t
    } else {
      segments[i].duration_s = 0
    }
  }

  return segments.filter(s => s.action !== 'END')
}

// ---------------------------------------------------------------------------
// Action executor
// ---------------------------------------------------------------------------

async function executeAction(page, action) {
  if (action === 'PAUSE') return

  if (action.startsWith('NAV:')) {
    const route = action.slice(4)
    // Prefer clicking the sidebar link — more visually demonstrative than goto
    const routeToLabel = {
      '/': 'Chat Relay',
      '/dashboard': 'Dashboard',
      '/terminal': 'Terminal',
      '/workers': 'Worker Swarm',
      '/ralph': 'Ralph Loop',
      '/agents': 'Agents',
      '/tools': 'Tools',
      '/hub': 'Ladder Logic',
    }
    const label = routeToLabel[route]
    if (label) {
      try {
        await page.click(`a:has-text("${label}")`, { timeout: 3000 })
        await page.waitForTimeout(800) // let React render
        return
      } catch (_) { /* fall through to goto */ }
    }
    await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(800)
    return
  }

  if (action.startsWith('CLICK:')) {
    const selector = action.slice(6)
    try {
      await page.click(selector, { timeout: 2000 })
    } catch (_) {
      console.warn(`  WARN: CLICK failed for selector: ${selector}`)
    }
    return
  }

  if (action.startsWith('FILL:')) {
    // Format: FILL:selector:value (value may contain colons)
    const rest = action.slice(5)
    const colonIdx = rest.indexOf(':')
    if (colonIdx === -1) return
    const selector = rest.slice(0, colonIdx)
    const value = rest.slice(colonIdx + 1)
    try {
      await page.fill(selector, value, { timeout: 2000 })
    } catch (_) {
      console.warn(`  WARN: FILL failed for selector: ${selector}`)
    }
    return
  }

  if (action.startsWith('HOVER:')) {
    const selector = action.slice(6)
    try {
      await page.hover(selector, { timeout: 2000 })
    } catch (_) {
      console.warn(`  WARN: HOVER failed for selector: ${selector}`)
    }
    return
  }

  if (action.startsWith('SCROLL:')) {
    const delta = parseInt(action.slice(7), 10)
    await page.evaluate((dy) => window.scrollBy({ top: dy, behavior: 'smooth' }), delta)
    await page.waitForTimeout(400) // let smooth scroll settle
    return
  }

  console.warn(`  WARN: Unknown action: ${action}`)
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const segments = parseScript(SCRIPT_PATH)
  console.log(`\nMission Control Demo Recorder`)
  console.log(`Segments: ${segments.length}`)
  console.log(`Estimated duration: ${segments.reduce((a, s) => a + s.duration_s, 0)}s`)
  console.log(`Video output: ${RAW_DIR}/\n`)

  const browser = await chromium.launch({
    headless: false,
    args: ['--start-maximized'],
  })

  const ctx = await browser.newContext({
    recordVideo: {
      dir: RAW_DIR,
      size: { width: 1920, height: 1080 },
    },
    viewport: { width: 1920, height: 1080 },
  })

  const page = await ctx.newPage()

  // Initial load
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('aside', { timeout: 10000 })
  await page.waitForTimeout(1500) // let React hydrate

  const timecodes = []

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i]
    const pct = Math.round(((i + 1) / segments.length) * 100)
    console.log(`[${String(i + 1).padStart(2, '0')}/${segments.length}] ${seg.ts} [${seg.action}] (${seg.duration_s}s) — ${seg.narration.slice(0, 60)}…`)

    await executeAction(page, seg.action)

    // Record timecode for A/V sync reference
    timecodes.push({ t: seg.t, duration_s: seg.duration_s, narration: seg.narration })

    // Hold on this feature for the duration of the narration segment
    if (seg.duration_s > 0) {
      await page.waitForTimeout(seg.duration_s * 1000)
    }
  }

  // Write timecodes sidecar for sync reference
  writeFileSync(TIMECODES_PATH, JSON.stringify(timecodes, null, 2))
  console.log(`\nTimecodes written: ${TIMECODES_PATH}`)

  await ctx.close()
  await browser.close()

  console.log(`\nDone. Raw video saved to: ${RAW_DIR}/`)
  console.log(`Next step: node demo/voice.py  →  bash demo/sync.sh`)
}

main().catch(err => {
  console.error('\nFATAL:', err.message)
  console.error('Is Mission Control running at', BASE_URL, '?')
  console.error('Have you run: npx playwright install chromium ?')
  process.exit(1)
})
