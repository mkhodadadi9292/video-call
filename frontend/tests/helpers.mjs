// Shared Playwright harness: browser setup, login, Jitsi iframe mocking,
// and a tiny pass/fail test runner.
import { chromium } from 'playwright'

export const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

let passed = 0
let failed = 0

export async function test(name, fn) {
  try {
    await fn()
    console.log(`  ✓ ${name}`)
    passed += 1
  } catch (err) {
    console.error(`  ✗ ${name}`)
    console.error(`    ${err.message.split('\n')[0]}`)
    failed += 1
  }
}

export function summarize(suite) {
  console.log(`\n${suite}: ${passed} passed, ${failed} failed`)
  if (failed > 0) process.exit(1)
}

export async function launchBrowser() {
  // Playwright's browser CDN is geo-blocked in some regions — use system
  // Chrome instead (same approach as the MediaService test suite).
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const context = await browser.newContext()
  const page = await context.newPage()
  return { browser, context, page }
}

export async function login(page, username, password = 'pw') {
  await page.goto(`${BASE_URL}/login`)
  await page.fill('#username', username)
  await page.fill('#password', password)
  await page.click('button[type="submit"]')
  await page.waitForURL('**/rooms')
}

// The Jitsi iframe targets https://<host>:8443 — without a running Jitsi
// container (or trusted cert) that would hang/fail. For UI e2e we mock it:
// the iframe still renders with the real src, the network call is answered.
export async function mockJitsiIframe(page) {
  await page.route(/https?:\/\/[^/]+:8443\/.*/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<html><body style="background:#000">jitsi-mock</body></html>',
    }),
  )
}

export async function createRoomViaApi(page, name) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const response = await page.request.post(`${BASE_URL}/api/rooms`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name },
  })
  if (response.status() !== 201) throw new Error(`create room failed: ${response.status()}`)
  return response.json()
}
