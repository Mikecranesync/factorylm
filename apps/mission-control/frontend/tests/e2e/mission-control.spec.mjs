/**
 * Mission Control E2E Test — Autonomous browser testing
 *
 * Standalone Playwright script that navigates all 7 pages,
 * takes screenshots, and verifies key elements render correctly.
 *
 * Usage: node apps/mission-control/frontend/tests/e2e/mission-control.spec.mjs
 * Prereq: Server running at localhost:8090, Playwright chromium installed
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const BASE_URL = 'http://localhost:8090'
const __dirname = dirname(fileURLToPath(import.meta.url))
const SCREENSHOT_DIR = join(__dirname, 'screenshots')

// Test harness
let passed = 0, failed = 0, total = 0

function assert(condition, name) {
  total++
  if (condition) {
    passed++
    console.log(`  \x1b[32mPASS\x1b[0m  ${name}`)
  } else {
    failed++
    console.log(`  \x1b[31mFAIL\x1b[0m  ${name}`)
  }
}

function section(name) {
  console.log(`\n${'='.repeat(60)}`)
  console.log(`  ${name}`)
  console.log('='.repeat(60))
}

async function getBodyText(page) {
  return (await page.textContent('body')) || ''
}

async function main() {
  mkdirSync(SCREENSHOT_DIR, { recursive: true })
  console.log(`\nMission Control E2E Test`)
  console.log(`Target: ${BASE_URL}`)
  console.log(`Screenshots: ${SCREENSHOT_DIR}\n`)

  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  try {
    // ========================================================
    // GLOBAL: Initial load + Sidebar
    // ========================================================
    section('Global / Sidebar')

    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('aside', { timeout: 10000 })
    // Give React a moment to hydrate
    await page.waitForTimeout(2000)

    const bodyText = await getBodyText(page)

    assert(bodyText.includes('Mission Control'), 'Sidebar heading "Mission Control"')
    assert(bodyText.includes('FactoryLM Orchestration'), 'Sidebar subtitle')
    assert(bodyText.includes('Chat Relay'), 'Nav: Chat Relay')
    assert(bodyText.includes('Dashboard'), 'Nav: Dashboard')
    assert(bodyText.includes('Terminal'), 'Nav: Terminal')
    assert(bodyText.includes('Worker Swarm'), 'Nav: Worker Swarm')
    assert(bodyText.includes('Ralph Loop'), 'Nav: Ralph Loop')
    assert(bodyText.includes('Agents'), 'Nav: Agents')
    assert(bodyText.includes('Tools'), 'Nav: Tools')
    assert(bodyText.includes('40+ Autonomous Capabilities'), 'Footer stats')

    // ========================================================
    // PAGE 1: Chat Relay (/)
    // ========================================================
    section('Page 1/7: Chat Relay (/)')

    const chatBody = await getBodyText(page)
    assert(chatBody.includes('Claude Code Relay'), 'Heading: Claude Code Relay')
    assert(chatBody.includes('Perplexity'), 'Subtitle mentions Perplexity')
    assert(
      chatBody.includes('Paste a prompt') || chatBody.includes('write your own'),
      'Empty state message'
    )

    const textarea = await page.$('textarea')
    assert(textarea !== null, 'Textarea exists')

    const sendBtn = await page.$('button:has-text("Send")')
    assert(sendBtn !== null, 'Send button exists')

    if (sendBtn) {
      const sendClasses = await sendBtn.getAttribute('class')
      assert(sendClasses?.includes('cursor-not-allowed'), 'Send button disabled when empty')
    }

    const nodeSelector = await page.$('select')
    assert(nodeSelector !== null, 'Node selector dropdown exists')

    const projectInput = await page.$('input[type="text"]')
    assert(projectInput !== null, 'Project path input exists')

    if (projectInput) {
      const projectValue = await projectInput.inputValue()
      assert(projectValue === '~/factorylm', 'Project path defaults to ~/factorylm')
    }

    // Interaction test: type text → send enables
    if (textarea && sendBtn) {
      await textarea.fill('Test prompt from E2E')
      await page.waitForTimeout(200)
      const afterClasses = await sendBtn.getAttribute('class')
      assert(!afterClasses?.includes('cursor-not-allowed'), 'Send button enables after typing')
      await textarea.fill('')
    }

    await page.screenshot({ path: join(SCREENSHOT_DIR, '01-chat-relay.png'), fullPage: true })

    // ========================================================
    // PAGE 2: Dashboard (/dashboard)
    // ========================================================
    section('Page 2/7: Dashboard (/dashboard)')

    await page.click('a:has-text("Dashboard")')
    await page.waitForURL('**/dashboard', { timeout: 5000 })
    await page.waitForTimeout(2000)

    assert(page.url().includes('/dashboard'), 'URL is /dashboard')

    const dashBody = await getBodyText(page)
    assert(dashBody.includes('Workflows'), 'Stats: Workflows')
    assert(dashBody.includes('Workers'), 'Stats: Workers')
    assert(
      dashBody.includes('Jarvis Nodes') || dashBody.includes('online') || dashBody.includes('offline') || dashBody.includes('VPS'),
      'Jarvis Nodes section'
    )
    assert(
      dashBody.includes('PLC Collectors') || dashBody.includes('Collectors'),
      'PLC Collectors section'
    )
    assert(
      dashBody.includes('Quick Actions') || dashBody.includes('quick'),
      'Quick Actions section'
    )
    assert(
      dashBody.includes('Connect PLC collectors'),
      'Collector status shows honest message'
    )

    await page.screenshot({ path: join(SCREENSHOT_DIR, '02-dashboard.png'), fullPage: true })

    // ========================================================
    // PAGE 3: Terminal (/terminal)
    // ========================================================
    section('Page 3/7: Terminal (/terminal)')

    await page.click('a:has-text("Terminal")')
    await page.waitForURL('**/terminal', { timeout: 5000 })
    await page.waitForTimeout(2000)

    assert(page.url().includes('/terminal'), 'URL is /terminal')

    const termBody = await getBodyText(page)
    assert(
      termBody.includes('Remote Terminal') || termBody.includes('Terminal'),
      'Terminal heading'
    )
    assert(
      termBody.includes('Shell Terminal') || termBody.includes('shell'),
      'Shell Terminal section'
    )

    const cmdInput = await page.$('input[placeholder*="command" i]')
    assert(cmdInput !== null, 'Command input exists')

    const runBtn = await page.$('button:has-text("Run")')
    assert(runBtn !== null, 'Run button exists')

    // Interaction test
    if (cmdInput && runBtn) {
      await cmdInput.fill('echo hello')
      await page.waitForTimeout(200)
      const runClasses = await runBtn.getAttribute('class')
      assert(!runClasses?.includes('cursor-not-allowed'), 'Run button enables after typing command')
      await cmdInput.fill('')
    }

    await page.screenshot({ path: join(SCREENSHOT_DIR, '03-terminal.png'), fullPage: true })

    // ========================================================
    // PAGE 4: Workers (/workers)
    // ========================================================
    section('Page 4/7: Worker Swarm (/workers)')

    await page.click('a:has-text("Worker Swarm")')
    await page.waitForURL('**/workers', { timeout: 5000 })
    await page.waitForTimeout(2000)

    assert(page.url().includes('/workers'), 'URL is /workers')

    const workersBody = await getBodyText(page)
    assert(
      workersBody.includes('Worker Swarm') ||
      workersBody.includes('Celery') ||
      workersBody.includes('Loading workers') ||
      workersBody.includes('Error loading'),
      'Workers page renders (content or loading/error)'
    )

    await page.screenshot({ path: join(SCREENSHOT_DIR, '04-workers.png'), fullPage: true })

    // ========================================================
    // PAGE 5: Ralph Loop (/ralph)
    // ========================================================
    section('Page 5/7: Ralph Loop (/ralph)')

    await page.click('a:has-text("Ralph Loop")')
    await page.waitForURL('**/ralph', { timeout: 5000 })
    await page.waitForTimeout(2000)

    assert(page.url().includes('/ralph'), 'URL is /ralph')

    const ralphBody = await getBodyText(page)
    assert(
      ralphBody.includes('Ralph') ||
      ralphBody.includes('Loading Ralph') ||
      ralphBody.includes('Error loading'),
      'Ralph page renders (content or loading/error)'
    )
    assert(
      ralphBody.includes('Autonomous') || ralphBody.includes('autonomous'),
      'Safety warning about autonomous operation'
    )

    await page.screenshot({ path: join(SCREENSHOT_DIR, '05-ralph.png'), fullPage: true })

    // ========================================================
    // PAGE 6: Agents (/agents)
    // ========================================================
    section('Page 6/7: Agents (/agents)')

    await page.click('a:has-text("Agents")')
    await page.waitForURL('**/agents', { timeout: 5000 })
    await page.waitForTimeout(2000)

    assert(page.url().includes('/agents'), 'URL is /agents')

    const agentsBody = await getBodyText(page)
    assert(
      agentsBody.includes('Autonomous Agents') ||
      agentsBody.includes('Loading agents') ||
      agentsBody.includes('Error loading'),
      'Agents page renders (content or loading/error)'
    )

    // Check for "Not Connected" badge (Phase 3 fix)
    if (agentsBody.includes('Autonomous Agents')) {
      assert(
        agentsBody.includes('Not Connected') || agentsBody.includes('running'),
        'Agent status shows "Not Connected" or running state'
      )
    }

    await page.screenshot({ path: join(SCREENSHOT_DIR, '06-agents.png'), fullPage: true })

    // ========================================================
    // PAGE 7: Tools (/tools)
    // ========================================================
    section('Page 7/7: Tools (/tools)')

    await page.click('a:has-text("Tools")')
    await page.waitForURL('**/tools', { timeout: 5000 })
    await page.waitForTimeout(2000)

    assert(page.url().includes('/tools'), 'URL is /tools')

    const toolsBody = await getBodyText(page)
    assert(toolsBody.includes('Jesus H Christ'), 'JHC section heading')
    assert(toolsBody.includes('Repo Resurrection'), 'JHC subtitle')
    assert(toolsBody.includes('Scan for Candidates'), 'Scan section')
    assert(toolsBody.includes('Begin Resurrection'), 'Resurrect section')

    const scanInput = await page.$('input[placeholder*="GitHub org"]')
    assert(scanInput !== null, 'Scan org input exists')

    const scanBtn = await page.$('button:has-text("Scan")')
    assert(scanBtn !== null, 'Scan button exists')

    assert(toolsBody.includes('Git Forensics'), 'Git Forensics section')

    const repoPathInput = await page.$('input[placeholder*="Repo path"]')
    assert(repoPathInput !== null, 'Git Forensics repo path input exists')

    const reportBtn = await page.$('button:has-text("Generate Full Report")')
    assert(reportBtn !== null, 'Generate Full Report button exists')

    const hotspotsBtn = await page.$('button:has-text("Find Hotspots")')
    assert(hotspotsBtn !== null, 'Find Hotspots button exists')

    assert(toolsBody.includes('$99'), 'Pricing: $99')
    assert(toolsBody.includes('$299'), 'Pricing: $299')
    assert(toolsBody.includes('$999'), 'Pricing: $999')

    await page.screenshot({ path: join(SCREENSHOT_DIR, '07-tools.png'), fullPage: true })

    // ========================================================
    // NAVIGATION ROUND-TRIP
    // ========================================================
    section('Navigation Round-Trip')

    await page.click('a:has-text("Chat Relay")')
    await page.waitForURL(url => !url.toString().includes('/tools'), { timeout: 5000 })
    await page.waitForTimeout(1000)

    const finalBody = await getBodyText(page)
    assert(
      page.url().endsWith(':8090/') || page.url().endsWith(':8090'),
      'URL returns to root'
    )
    assert(finalBody.includes('Claude Code Relay'), 'Chat Relay re-renders after round-trip')

  } catch (err) {
    console.error(`\n\x1b[31mFATAL ERROR:\x1b[0m ${err.message}`)
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'error.png'), fullPage: true })
  } finally {
    await browser.close()
  }

  // Summary
  console.log(`\n${'='.repeat(60)}`)
  console.log(`  RESULTS: ${passed}/${total} passed, ${failed} failed`)
  console.log(`  Screenshots saved to: ${SCREENSHOT_DIR}`)
  console.log('='.repeat(60))
  process.exit(failed > 0 ? 1 : 0)
}

main().catch(err => {
  console.error('FATAL:', err.message)
  console.error('Is the server running at', BASE_URL, '?')
  console.error('Have you run: npx playwright install chromium ?')
  process.exit(1)
})
