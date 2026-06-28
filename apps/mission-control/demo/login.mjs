/**
 * Mission Control — One-Time Login
 *
 * Logs in to the production Hub, saves the session to auth.json.
 * Run once; auth.json is reused by record_tab.mjs for all 8 recordings.
 *
 * Usage:
 *   HUB_EMAIL=you@factorylm.com HUB_PASSWORD=secret node demo/login.mjs
 *
 * Or via Doppler:
 *   doppler run -p factorylm -c dev -- node demo/login.mjs
 *   (requires HUB_EMAIL and HUB_PASSWORD in that Doppler config)
 */

import { chromium } from 'playwright'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const AUTH_PATH = join(__dirname, 'auth.json')
const HUB_URL = process.env.HUB_URL || 'https://app.factorylm.com'

const email = process.env.HUB_EMAIL
const password = process.env.HUB_PASSWORD

if (!email || !password) {
  console.error('ERROR: Set HUB_EMAIL and HUB_PASSWORD env vars')
  console.error('  HUB_EMAIL=you@factorylm.com HUB_PASSWORD=secret node demo/login.mjs')
  process.exit(1)
}

const browser = await chromium.launch({ headless: false })
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } })
const page = await ctx.newPage()

console.log(`Navigating to ${HUB_URL} …`)
await page.goto(HUB_URL, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)

// The "Sign in with password" accordion must be clicked first
console.log('Expanding password login form …')
const expandBtn = page.locator('button[aria-controls="password-signin-form"]')
if (await expandBtn.count() > 0) {
  await expandBtn.click()
  await page.waitForTimeout(600)
}

// Fill the expanded password form
const passwordInput = page.locator('input[type="password"]').first()
await passwordInput.waitFor({ timeout: 10000 })

// The password form has its own email field; prefer the one inside the expanded section
const emailInPasswordForm = page.locator('#password-signin-form input[type="email"], #password-signin-form input[name="email"]').first()
const emailInput = (await emailInPasswordForm.count() > 0)
  ? emailInPasswordForm
  : page.locator('input[type="email"], input[name="email"]').last()

console.log('Filling credentials …')
await emailInput.fill(email)
await passwordInput.fill(password)
await page.keyboard.press('Enter')

console.log('Waiting for post-login redirect …')
try {
  // Wait for URL to change away from login page
  await page.waitForURL(url => !url.toString().includes('login') && !url.toString().includes('signin'), {
    timeout: 20000,
  })
} catch (_) {
  // If no URL change, just wait for the page to settle
  await page.waitForTimeout(4000)
}

const finalUrl = page.url()
console.log(`Landed at: ${finalUrl}`)

await ctx.storageState({ path: AUTH_PATH })
await browser.close()

console.log(`\nauth.json saved → ${AUTH_PATH}`)
console.log('Run recordings with: node demo/record_tab.mjs <slug>')
