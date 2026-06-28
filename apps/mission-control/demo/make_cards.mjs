/**
 * Mission Control — Branded Intro/Outro Card Renderer
 *
 * Renders 1920x1080 brand cards as PNGs via Playwright (this host's ffmpeg lacks
 * drawtext/subtitles, so we render text in HTML for pixel-perfect brand type/color).
 *
 * Usage (from apps/mission-control/):  node demo/make_cards.mjs <slug>
 * Output: demo/tabs/<slug>/brand/intro.png + outro.png
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

const LABELS = {
  '01_command_board': 'Command Board',
  '02_command_center': 'Command Center',
  '03_namespace': 'Namespace',
  '04_knowledge': 'Knowledge',
  '05_channels': 'Channels',
  '06_assets': 'Assets',
  '07_workorders': 'Work Orders',
  '08_scan': 'Scan',
}

const slug = process.argv[2]
const label = LABELS[slug]
if (!label) {
  console.error(`Usage: node demo/make_cards.mjs <slug>\nSlugs: ${Object.keys(LABELS).join(' ')}`)
  process.exit(1)
}

const OUT = join(__dirname, 'tabs', slug, 'brand')
mkdirSync(OUT, { recursive: true })

const shell = (inner) => `<!doctype html><html><body style="margin:0">
<div style="width:1920px;height:1080px;box-sizing:border-box;
  background:linear-gradient(135deg,#0c4a6e 0%,#1a237e 100%);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;color:#fff;text-align:center">
  <div style="width:148px;height:148px;border-radius:30px;background:#1a237e;
    border:3px solid #0ea5e9;display:flex;align-items:center;justify-content:center;
    font-size:68px;font-weight:800;letter-spacing:-2px;box-shadow:0 12px 48px rgba(14,165,233,.35)">FL</div>
  ${inner}
</div></body></html>`

const introHTML = shell(`
  <div style="font-size:92px;font-weight:800;letter-spacing:-3px;margin-top:44px">FactoryLM</div>
  <div style="font-size:46px;font-weight:600;color:#7dd3fc;margin-top:10px">${label}</div>
  <div style="font-size:24px;color:#94a3b8;margin-top:48px;letter-spacing:4px;text-transform:uppercase">
    Maintenance Intelligence &amp; Resource Assistant</div>`)

const outroHTML = shell(`
  <div style="font-size:88px;font-weight:800;letter-spacing:-3px;margin-top:44px">FactoryLM</div>
  <div style="font-size:42px;font-weight:500;color:#e2e8f0;margin-top:28px">See it on your own machines</div>
  <div style="font-size:46px;font-weight:700;color:#0ea5e9;margin-top:18px">app.factorylm.com/hub</div>`)

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
for (const [name, html] of [['intro', introHTML], ['outro', outroHTML]]) {
  await page.setContent(html, { waitUntil: 'load' })
  await page.screenshot({ path: join(OUT, name + '.png') })
  console.log(`OK  tabs/${slug}/brand/${name}.png`)
}
await browser.close()
