// Phase 2 E2E: meeting page (Jitsi iframe embed, chat send/receive, leave).
import {
  BASE_URL,
  createRoomViaApi,
  launchBrowser,
  login,
  mockJitsiIframe,
  summarize,
  test,
} from './helpers.mjs'

const run = async () => {
  const { browser, context, page } = await launchBrowser()
  const unique = Date.now()
  const username = `e2e-${unique}`
  const password = 'pw'

  await login(page, username, password)
  await mockJitsiIframe(page)
  const room = await createRoomViaApi(page, `meeting-${unique}`)

  await test('meeting page renders room name and a Jitsi iframe with JWT', async () => {
    await page.goto(`${BASE_URL}/meeting/${room.id}`)
    await page.waitForSelector('[data-testid="jitsi-iframe"]')

    const name = await page.textContent('[data-testid="room-name"]')
    if (name !== `meeting-${unique}`) throw new Error(`room name mismatch: ${name}`)

    const src = await page.getAttribute('[data-testid="jitsi-iframe"]', 'src')
    if (!src.includes(room.jitsi_room_id)) throw new Error('iframe src missing jitsi_room_id')
    if (!src.includes('jwt=')) throw new Error('iframe src missing jwt token')
  })

  await test('sending a chat message shows it in the panel', async () => {
    await page.fill('[aria-label="Chat message"]', 'hello from e2e')
    await page.click('button:has-text("Send")')
    const message = page.locator('[data-testid="chat-message"]', { hasText: 'hello from e2e' })
    await message.waitFor()
    const text = await message.textContent()
    if (!text.includes(username)) throw new Error('message missing sender username')
  })

  await test('a second user sees the first user in participants', async () => {
    const observer = `e2e-observer-${unique}`
    const second = await context.newPage()
    await mockJitsiIframe(second)
    await second.goto(`${BASE_URL}/login`)
    await second.fill('#username', observer)
    await second.fill('#password', password)
    await second.click('button[type="submit"]')
    await second.waitForURL('**/rooms')

    // Both users stay on the meeting page — leaving it fires leaveRoom.
    await second.goto(`${BASE_URL}/meeting/${room.id}`)
    await second.waitForSelector('[data-testid="jitsi-iframe"]')

    const token = await second.evaluate(() => localStorage.getItem('access_token'))
    const res = await second.request.get(`${BASE_URL}/api/rooms/${room.id}/participants`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.status() !== 200) throw new Error(`participants fetch failed: ${res.status()}`)
    const names = (await res.json()).map((p) => p.username)
    if (!names.includes(username)) throw new Error(`missing ${username} in participants`)
    if (!names.includes(observer)) throw new Error(`missing ${observer} in participants`)
    await second.close()
  })

  await test('leaving the meeting returns to the rooms page', async () => {
    await page.goto(`${BASE_URL}/meeting/${room.id}`)
    await page.waitForSelector('[data-testid="jitsi-iframe"]')
    await page.click('button:has-text("Leave")')
    await page.waitForURL('**/rooms')
  })

  await test('joining an ended meeting shows the ended state', async () => {
    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    const response = await page.request.delete(`${BASE_URL}/api/rooms/${room.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (response.status() !== 204) throw new Error(`end room failed: ${response.status()}`)

    await page.goto(`${BASE_URL}/meeting/${room.id}`)
    await page.waitForSelector('text=This meeting has ended.')
  })

  await test('visiting a nonexistent meeting shows not-found state', async () => {
    await page.goto(`${BASE_URL}/meeting/999999`)
    await page.waitForSelector('text=Room not found.')
  })

  await browser.close()
  summarize('phase2-meeting-chat')
}

run().catch((err) => {
  console.error(err)
  process.exit(1)
})
