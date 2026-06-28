/**
 * Mission Control — Nav Discovery
 *
 * Loads the live Hub with saved auth and dumps every navigable link
 * (text + href/route) plus any items hidden behind a "More" menu, so the
 * promo recorder's TAB_META can be re-pointed at the REAL current sections.
 *
 * Usage (from apps/mission-control/):  node demo/discover_nav.mjs
 * Output: JSON to stdout + demo/qc/nav.json
 */
import { chromium } from 'playwright'
import { writeFileSync, existsSync, mkdirSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const HUB_URL = process.env.HUB_URL || 'https://app.factorylm.com'
const AUTH_PATH = join(__dirname, 'auth.json')

if (!existsSync(AUTH_PATH)) {
  console.error(`ERROR: ${AUTH_PATH} not found. Run demo/login.mjs first.`)
  process.exit(1)
}

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({
  storageState: AUTH_PATH,
  viewport: { width: 1920, height: 1080 },
})
const page = await ctx.newPage()
await page.goto(HUB_URL, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000)

// Try to reveal anything behind a "More" / overflow menu
for (const sel of ['button:has-text("More")', '[aria-label="More"]', 'button:has-text("⋯")']) {
  try { await page.click(sel, { timeout: 1000 }); await page.waitForTimeout(500) } catch (_) {}
}

const collect = async () => page.evaluate(() => {
  const seen = new Set()
  const out = []
  for (const a of document.querySelectorAll('a[href]')) {
    const text = (a.textContent || '').trim().replace(/\s+/g, ' ')
    const href = a.getAttribute('href') || ''
    if (!text || text.length > 40) continue
    const key = text + '|' + href
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ text, href })
  }
  // Also capture button-driven nav (SPA sidebars often use buttons)
  const buttons = []
  for (const b of document.querySelectorAll('nav button, aside button, [role="navigation"] button')) {
    const text = (b.textContent || '').trim().replace(/\s+/g, ' ')
    if (text && text.length <= 40) buttons.push(text)
  }
  return { links: out, navButtons: [...new Set(buttons)], url: location.href, title: document.title }
})

const result = await collect()
await ctx.close()
await browser.close()

const QC_DIR = join(__dirname, 'qc')
if (!existsSync(QC_DIR)) mkdirSync(QC_DIR, { recursive: true })
writeFileSync(join(QC_DIR, 'nav.json'), JSON.stringify(result, null, 2))
console.log(JSON.stringify(result, null, 2))
