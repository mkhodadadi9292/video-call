// Phase 1 E2E: auth + rooms page (login, redirect, create, list, end).
import { BASE_URL, launchBrowser, login, summarize, test } from './helpers.mjs'

const run = async () => {
  const { browser, context, page } = await launchBrowser()
  const unique = Date.now()
  const username = `e2e-${unique}`
  const password = 'pw'

  await test('unauthenticated visit to /rooms redirects to /login', async () => {
    await page.goto(`${BASE_URL}/rooms`)
    await page.waitForURL('**/login')
  })

  await test('first login with new user lands on /rooms and shows username', async () => {
    await login(page, username, password)
    const header = await page.textContent('[data-testid="current-user"]')
    if (!header.includes(username)) throw new Error(`header does not contain ${username}`)
  })

  await test('wrong password on second login shows an error', async () => {
    await page.goto(`${BASE_URL}/login`)
    await page.fill('#username', username)
    await page.fill('#password', 'wrong-password')
    await page.click('button[type="submit"]')
    await page.waitForSelector('text=Invalid username or password')
  })

  await test('create room navigates to the meeting page', async () => {
    await page.goto(`${BASE_URL}/login`)
    await page.fill('#username', username)
    await page.fill('#password', password)
    await page.click('button[type="submit"]')
    await page.waitForURL('**/rooms')

    await page.fill('[aria-label="Room name"]', `standup-${unique}`)
    await page.click('button[type="submit"]')
    await page.waitForURL('**/meeting/**')
  })

  await test('room appears in the rooms list with participant count', async () => {
    await page.goto(`${BASE_URL}/rooms`)
    await page.waitForSelector('[data-testid="room-card"]')
    const card = page.locator('[data-testid="room-card"]', { hasText: `standup-${unique}` })
    await card.waitFor()
    const text = await card.textContent()
    if (!text.includes('participant')) throw new Error('participant count not rendered')
  })

  await test('end room removes it from the list', async () => {
    await page.goto(`${BASE_URL}/rooms`)
    const card = page.locator('[data-testid="room-card"]', { hasText: `standup-${unique}` })
    await card.waitFor()
    page.once('dialog', (dialog) => dialog.accept())
    await card.getByRole('button', { name: 'End' }).click()
    await card.waitFor({ state: 'detached' })
  })

  await test('empty room name keeps the button disabled', async () => {
    await page.goto(`${BASE_URL}/rooms`)
    const submit = page.locator('form button[type="submit"]')
    await page.fill('[aria-label="Room name"]', '   ')
    const disabled = await submit.isDisabled()
    if (!disabled) throw new Error('submit button should be disabled for blank name')
  })

  await test('sign out returns to the login page', async () => {
    await page.goto(`${BASE_URL}/rooms`)
    await page.click('text=Sign out')
    await page.waitForURL('**/login')
    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    if (token) throw new Error('token still present after logout')
  })

  await browser.close()
  summarize('phase1-auth-rooms')
}

run().catch((err) => {
  console.error(err)
  process.exit(1)
})
