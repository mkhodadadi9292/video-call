# Phase 7 — MeetingPage: Jitsi iframe, chat, join/leave lifecycle

**Status: ✅ complete** · TDD layer: **Playwright e2e** · Tests: `frontend/tests/phase2-meeting-chat.mjs` (6 tests)

**Goal:** the meeting screen — Jitsi iframe embed with JWT, per-meeting chat with
3s polling, join/leave lifecycle, ended/not-found states.

---

## 1. Architecture

```
MeetingPage (composition)
 ├── useAuth()            → current user
 ├── useMeetingSession()  → room, token, loading, error
 │     get room → join → token; cleanup: leave  (mirrors MediaService MeetingRoom)
 ├── useChat()            → messages (3s poll), send, bottomRef
 ├── JitsiIframe          → presentational (props: jitsiBaseUrl, roomName, jwt)
 └── ChatPanel            → presentational (props: messages, sending, onSend)
```

## 2. TDD cycle

### Step 1 — the failing tests

`frontend/tests/phase2-meeting-chat.mjs`:

```js
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
```

### Step 2 — run them (red: meeting page missing)

### Step 3 — implement

`frontend/src/hooks/useMeetingSession.js`:

```js
// Data-fetching lifecycle for a meeting: load room, join, fetch token, leave on cleanup.
import { useEffect, useState } from 'react'
import { roomsApi } from '../api/roomsApi'

export function useMeetingSession(roomId) {
  const [room, setRoom] = useState(null)
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    const init = async () => {
      try {
        const data = await roomsApi.get(roomId)
        if (!data.is_active) {
          if (!cancelled) {
            setError('This meeting has ended.')
            setLoading(false)
          }
          return
        }
        if (!cancelled) setRoom(data)
        await roomsApi.join(roomId)
        const tokenData = await roomsApi.token(roomId)
        if (!cancelled) {
          setToken(tokenData.token)
          setLoading(false)
        }
      } catch {
        if (!cancelled) {
          setError('Room not found.')
          setLoading(false)
        }
      }
    }

    init()
    return () => {
      cancelled = true
      roomsApi.leave(roomId).catch(() => {})
    }
  }, [roomId])

  return { room, token, loading, error }
}
```

`frontend/src/hooks/useChat.js`:

```js
// Chat data-fetching: 3s polling + send. Presentation lives in ChatPanel.
import { useCallback, useEffect, useRef, useState } from 'react'
import { roomsApi } from '../api/roomsApi'

export function useChat(roomId, { pollMs = 3000 } = {}) {
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const bottomRef = useRef(null)

  const fetchMessages = useCallback(async () => {
    try {
      const data = await roomsApi.messages(roomId)
      setMessages(data.items)
    } catch {
      /* polling is best-effort */
    }
  }, [roomId])

  useEffect(() => {
    fetchMessages()
    const interval = setInterval(fetchMessages, pollMs)
    return () => clearInterval(interval)
  }, [fetchMessages, pollMs])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(
    async (text) => {
      const trimmed = text.trim()
      if (!trimmed) return
      setSending(true)
      try {
        await roomsApi.sendMessage(roomId, trimmed)
        await fetchMessages()
      } finally {
        setSending(false)
      }
    },
    [roomId, fetchMessages],
  )

  return { messages, sending, send, bottomRef }
}
```

`frontend/src/components/JitsiIframe.jsx`:

```jsx
// Isolated Jitsi embed: takes jitsiBaseUrl, roomName and jwt as props.
// The iframe loads Jitsi over HTTPS (camera/mic require a secure context).
export default function JitsiIframe({ jitsiBaseUrl, roomName, jwt }) {
  const src = `${jitsiBaseUrl}/${roomName}?jwt=${encodeURIComponent(jwt)}#config.prejoinPageEnabled=false&config.disableDeepLinking=true`

  return (
    <iframe
      data-testid="jitsi-iframe"
      src={src}
      allow="camera *; microphone *; display-capture *; fullscreen *; autoplay *"
      className="w-full h-full border-0"
      title="Meeting"
    />
  )
}
```

`frontend/src/components/ChatPanel.jsx`:

```jsx
// Presentational chat: messages + onSend callback. State lives in useChat.
import { useState } from 'react'

export default function ChatPanel({ messages, sending, onSend, currentUsername }) {
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim()) return
    onSend(input)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2.5 border-b border-gray-700">
        <span className="text-xs text-gray-400 font-medium uppercase tracking-wide">Chat</span>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3" data-testid="chat-messages">
        {messages.length === 0 && (
          <p className="text-sm text-gray-600 text-center py-8">No messages yet.</p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className="text-sm" data-testid="chat-message">
            <div className="flex items-baseline gap-2">
              <span className="text-indigo-400 font-medium text-xs">{msg.username}</span>
              <span className="text-gray-600 text-[10px]">
                {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <p className="text-gray-200 mt-0.5 break-words">{msg.text}</p>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="p-2 border-t border-gray-700 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          aria-label="Chat message"
          className="flex-1 px-3 py-1.5 text-sm rounded-lg bg-gray-800 border border-gray-700 text-white
                     placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="px-3 py-1.5 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white
                     rounded-lg transition"
        >
          Send
        </button>
      </form>
    </div>
  )
}
```

`frontend/src/pages/MeetingPage.jsx` — full code in the repo (see
`frontend/src/pages/MeetingPage.jsx`); key parts:

```jsx
const JITSI_BASE_URL = `https://${window.location.hostname}:8443`
// ...
const { room, token, loading, error } = useMeetingSession(roomIdNum)
const chat = useChat(roomIdNum)
// ...
{room && token && (
  <JitsiIframe jitsiBaseUrl={JITSI_BASE_URL} roomName={room.jitsi_room_id} jwt={token} />
)}
```

Layout mirrors MediaService's `MeetingRoom`: top bar (Leave / room name /
participant count / chat toggle), Jitsi iframe fills the main area, chat panel
slides in from the right (overlay on mobile, fixed column on ≥1024px).

### Step 4 — run them (green)

```bash
node tests/phase2-meeting-chat.mjs
# phase2-meeting-chat: 6 passed, 0 failed
```

---

## 3. Design notes

- **`useMeetingSession` owns the join/leave lifecycle.** The cleanup function
  calls `leaveRoom` on unmount (same fix MediaService needed: the cleanup
  closure must capture `roomId`, not a stale `room` object — here the effect
  depends directly on `roomId`).
- **Jitsi URL construction** follows MediaService exactly:
  `https://<host>:8443/<jitsi_room_id>?jwt=<token>#config.prejoinPageEnabled=false&config.disableDeepLinking=true`
  — the hash disables the prejoin screen and deep linking; the `allow` attribute
  uses Permissions-Policy syntax (`camera *`).
- **iframe mocking in e2e:** `mockJitsiIframe` intercepts `:8443` requests so
  the suite runs without Docker Jitsi (and without trusting a self-signed cert).
  With the full stack running, remove the mock and the same tests drive the
  real Jitsi UI.
- **Ended vs not-found states** are distinct UI branches tested separately —
  the backend returns `is_active: false` (200) for ended rooms and 404 for
  missing rooms, and the hook maps them to different messages.
- **Chat polling (3s)** reuses the paginated messages endpoint (page 1 =
  newest 50, rendered oldest-first — the API already returns them in display
  order).
