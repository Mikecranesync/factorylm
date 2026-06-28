/**
 * Mission Control — Section Screenshotter
 *
 * Visits each given route on the live Hub (with saved auth) and captures a
 * full-viewport screenshot into demo/qc/shots/<name>.jpg, so narration can be
 * written against what's ACTUALLY on screen.
 *
 * Usage (from apps/mission-control/):
 *   node demo/shoot_sections.mjs            # default candidate sections
 *   node demo/shoot_sections.mjs /knowledge/ /scan/   # specific routes
 */
import { chromium } from 'playwright'
import { existsSync, mkdirSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const HUB_URL = process.env.HUB_URL || 'https://app.factorylm.com'
const AUTH_PATH = join(__dirname, 'auth.json')
const SHOTS = join(__dirname, 'qc', 'shots')

const DEFAULT = [
  ['command_board', '/feed/'],
  ['namespace', '/namespace/'],
  ['command_center', '/command-center/'],
  ['channels', '/channels/'],
  ['knowledge', '/knowledge/'],
  ['assets', '/assets/'],
  ['workorders', '/workorders/'],
  ['scan', '/scan/'],
]

const args = process.argv.slice(2)
const routes = args.length
  ? args.map(r => [r.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, ''), r])
  : DEFAULT

if (!existsSync(AUTH_PATH)) { console.error('ERROR: auth.json missing'); process.exit(1) }
if (!existsSync(SHOTS)) mkdirSync(SHOTS, { recursive: true })

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({
  storageState: AUTH_PATH,
  viewport: { width: 1920, height: 1080 },
})
const page = await ctx.newPage()

for (const [name, route] of routes) {
  const url = HUB_URL.replace(/\/$/, '') + route
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(3500) // let SPA + data load
    const out = join(SHOTS, name + '.jpg')
    await page.screenshot({ path: out, quality: 70, type: 'jpeg' })
    console.log(`OK   ${route} -> qc/shots/${name}.jpg`)
  } catch (e) {
    console.log(`FAIL ${route} : ${e.message.split('\n')[0]}`)
  }
}

await ctx.close()
await browser.close()
