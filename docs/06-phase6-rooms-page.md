# Phase 6 — RoomsPage: list, create, end (Playwright e2e)

**Status: ✅ complete** · TDD layer: **Playwright e2e** · Tests: `frontend/tests/phase1-auth-rooms.mjs` (8 tests)

**Goal:** the rooms dashboard — create a meeting, see active rooms with live
participant counts (10s polling), join, end, sign out.

---

## 1. Architecture

```
RoomsPage (composition)
 ├── useAuth()          → user, logout
 ├── useRooms()         → rooms, loading, error, createRoom, endRoom (10s poll)
 ├── CreateRoomForm     → presentational (props: onSubmit, creating)
 └── RoomCard           → presentational (props: room, onJoin, onEnd)
```

Data-fetching lives in the hook; components are pure props-in/events-out (SRP).

## 2. TDD cycle

### Step 1 — the test harness

`frontend/tests/helpers.mjs`:

```js
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
```

### Step 2 — the failing tests (write these BEFORE the page)

`frontend/tests/phase1-auth-rooms.mjs`:

```js
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
```

### Step 3 — run them (red: pages don't exist)

```bash
# backend on :8000 + vite on :5173 (see docs/00)
node tests/phase1-auth-rooms.mjs
```

### Step 4 — implement

`frontend/src/hooks/useRooms.js`:

```js
// Data-fetching logic for the rooms list, separated from presentation (SRP).
import { useCallback, useEffect, useState } from 'react'
import { roomsApi } from '../api/roomsApi'

export function useRooms({ pollMs = 10000 } = {}) {
  const [rooms, setRooms] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchRooms = useCallback(async () => {
    try {
      const data = await roomsApi.list()
      setRooms(data.items)
      setError('')
    } catch {
      setError('Failed to load rooms')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRooms()
    const interval = setInterval(fetchRooms, pollMs)
    return () => clearInterval(interval)
  }, [fetchRooms, pollMs])

  const createRoom = useCallback(async (name) => roomsApi.create(name), [])

  const endRoom = useCallback(async (id) => {
    await roomsApi.end(id)
    setRooms((prev) => prev.filter((r) => r.id !== id))
  }, [])

  return { rooms, loading, error, fetchRooms, createRoom, endRoom }
}
```

`frontend/src/components/RoomCard.jsx`:

```jsx
// Presentational component: props in, events out. No data fetching.
export default function RoomCard({ room, onJoin, onEnd }) {
  const participants = room.participant_count ?? 0
  return (
    <div
      data-testid="room-card"
      className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-3
                 hover:border-gray-700 transition flex items-center gap-4"
    >
      <div className="flex-1 min-w-0">
        <p className="text-white font-medium truncate">{room.name}</p>
        <p className="text-xs text-gray-500 mt-0.5">
          {participants} participant{participants !== 1 ? 's' : ''}
          {' · '}Created {new Date(room.created_at).toLocaleDateString()}
        </p>
      </div>
      <button
        onClick={onJoin}
        className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg
                   transition shrink-0"
      >
        Join
      </button>
      <button
        onClick={onEnd}
        className="px-3 py-2 text-sm text-red-400 hover:bg-red-400/10 rounded-lg transition shrink-0"
      >
        End
      </button>
    </div>
  )
}
```

`frontend/src/components/CreateRoomForm.jsx`:

```jsx
// Presentational form: local input state only, submits via callback.
import { useState } from 'react'

export default function CreateRoomForm({ onSubmit, creating }) {
  const [name, setName] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    onSubmit(trimmed)
    setName('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 mb-8">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Room name…"
        maxLength={200}
        aria-label="Room name"
        className="flex-1 px-4 py-2.5 rounded-xl bg-gray-800 border border-gray-700 text-white
                   placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition"
      />
      <button
        type="submit"
        disabled={creating || !name.trim()}
        className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white
                   font-medium rounded-xl transition shrink-0"
      >
        {creating ? 'Creating…' : 'New Room'}
      </button>
    </form>
  )
}
```

`frontend/src/pages/RoomsPage.jsx`:

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useRooms } from '../hooks/useRooms'
import CreateRoomForm from '../components/CreateRoomForm'
import RoomCard from '../components/RoomCard'

export default function RoomsPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { rooms, loading, error, createRoom, endRoom } = useRooms()
  const [creating, setCreating] = useState(false)

  const handleCreate = async (name) => {
    setCreating(true)
    try {
      const room = await createRoom(name)
      navigate(`/meeting/${room.id}`)
    } catch {
      alert('Failed to create room.')
    } finally {
      setCreating(false)
    }
  }

  const handleEnd = async (id) => {
    if (!window.confirm('End this room? It will no longer be accessible.')) return
    try {
      await endRoom(id)
    } catch {
      alert('Failed to end room.')
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <header className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <h1 className="text-white font-semibold text-lg">Meetings</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-400 text-sm" data-testid="current-user">
              <span className="text-white font-medium">{user?.username}</span>
            </span>
            <button
              onClick={logout}
              className="text-xs text-gray-500 hover:text-white transition"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 py-8">
        <CreateRoomForm onSubmit={handleCreate} creating={creating} />

        {error && <p className="text-sm text-red-400 mb-4">{error}</p>}

        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
            ))}
          </div>
        )}

        {!loading && rooms.length === 0 && (
          <div className="text-center py-16 text-gray-500">
            <p className="text-lg">No active meetings</p>
            <p className="text-sm mt-1">Create one above to get started.</p>
          </div>
        )}

        {!loading &&
          rooms.map((room) => (
            <RoomCard
              key={room.id}
              room={room}
              onJoin={() => navigate(`/meeting/${room.id}`)}
              onEnd={() => handleEnd(room.id)}
            />
          ))}
      </main>
    </div>
  )
}
```

### Step 5 — run them (green)

```bash
node tests/phase1-auth-rooms.mjs
# phase1-auth-rooms: 8 passed, 0 failed
```

---

## 3. Design notes

- **Polling for participant counts** (10s) mirrors MediaService's `RoomList` —
  simplest live-update mechanism without WebSockets; the interval is owned by
  the hook, so swapping to SSE/WebSocket later touches one file.
- **`data-testid` attributes** are the contract between the UI and the e2e
  suite — tests never depend on CSS classes.
- **Unique usernames per run** (`e2e-${Date.now()}`) make the suite re-runnable
  against a persistent dev DB.
- **End uses `window.confirm`** and the test handles the native dialog with
  `page.once('dialog', d => d.accept())`.
