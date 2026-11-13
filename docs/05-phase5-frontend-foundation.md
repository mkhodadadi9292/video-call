# Phase 5 — Frontend foundation: Vite app, API modules, auth

**Status: ✅ complete** · Verification: `npm run build` + manual login flow

**Goal:** the React shell — routing, the three SOLID API modules, an auth context,
and the login page. No room features yet (phases 6–7).

---

## 1. File map

```
frontend/
├── package.json            # react 19, react-router 7, axios, tailwind v4, vite, playwright
├── vite.config.js          # /api proxy → localhost:8000
├── index.html
├── src/
│   ├── main.jsx            # entry — renders App in StrictMode
│   ├── index.css           # @import "tailwindcss"
│   ├── App.jsx             # routes + ProtectedRoute
│   ├── api/
│   │   ├── httpClient.js   # transport only (SRP)
│   │   ├── authApi.js      # auth only (SRP)
│   │   └── roomsApi.js     # rooms only (SRP)
│   ├── context/
│   │   └── AuthContext.jsx # auth state provider + useAuth()
│   └── pages/
│       └── LoginPage.jsx   # login form
```

## 2. How SOLID applies to the frontend

| Principle | Application |
|---|---|
| **S** | `httpClient` = transport; `authApi` = credentials; `roomsApi` = room resources. Pages never touch axios or localStorage directly. |
| **O** | Adding a new resource = a new `*Api` module; the client is untouched. |
| **L** | The API modules are plain objects with stable signatures — a future WebSocket chat transport can replace `roomsApi.sendMessage` without changing callers. |
| **I** | Components receive only the props they use (`RoomCard` gets `room`/`onJoin`/`onEnd`, not the whole hook result). |
| **D** | Pages depend on hooks; hooks depend on API modules; API modules depend on `httpClient`. Dependencies point one way, toward the transport. |

---

## 3. Key files (full code)

### `frontend/package.json`

```json
{
  "name": "video-call-system-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test:e2e": "node tests/phase1-auth-rooms.mjs && node tests/phase2-meeting-chat.mjs"
  },
  "dependencies": {
    "axios": "^1.7.9",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.1.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "playwright": "^1.49.1",
    "tailwindcss": "^4.0.0",
    "vite": "^6.0.0"
  }
}
```

### `frontend/vite.config.js`

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### `frontend/src/api/httpClient.js`

```js
// Transport concern only: base URL, auth header, 401 handling.
// Resource-specific calls live in authApi.js / roomsApi.js (SRP).
import axios from 'axios'

const httpClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

httpClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginCall = error.config?.url?.includes('/auth/login')
    if (error.response?.status === 401 && !isLoginCall) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('username')
      localStorage.removeItem('role')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default httpClient
```

### `frontend/src/api/authApi.js`

```js
// Auth concern: login/logout + token storage. No UI code here.
import httpClient from './httpClient'

const TOKEN_KEY = 'access_token'
const USERNAME_KEY = 'username'
const ROLE_KEY = 'role'

export const authApi = {
  async login(username, password) {
    const { data } = await httpClient.post('/auth/login', { username, password })
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(USERNAME_KEY, data.username)
    localStorage.setItem(ROLE_KEY, data.role)
    return data
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(ROLE_KEY)
  },

  getToken: () => localStorage.getItem(TOKEN_KEY),
  getUsername: () => localStorage.getItem(USERNAME_KEY),
  getRole: () => localStorage.getItem(ROLE_KEY),
}
```

### `frontend/src/api/roomsApi.js`

```js
// Rooms concern: every room endpoint in one module.
import httpClient from './httpClient'

export const roomsApi = {
  list: () => httpClient.get('/rooms').then((r) => r.data),

  get: (id) => httpClient.get(`/rooms/${id}`).then((r) => r.data),

  create: (name) => httpClient.post('/rooms', { name }).then((r) => r.data),

  end: (id) => httpClient.delete(`/rooms/${id}`),

  join: (id) => httpClient.post(`/rooms/${id}/join`),

  leave: (id) => httpClient.post(`/rooms/${id}/leave`),

  participants: (id) => httpClient.get(`/rooms/${id}/participants`).then((r) => r.data),

  messages: (id, page = 1, size = 50) =>
    httpClient.get(`/rooms/${id}/messages`, { params: { page, size } }).then((r) => r.data),

  sendMessage: (id, text) =>
    httpClient.post(`/rooms/${id}/messages`, { message: text }).then((r) => r.data),

  token: (id) => httpClient.post(`/rooms/${id}/token`).then((r) => r.data),
}
```

### `frontend/src/context/AuthContext.jsx`

```jsx
import { createContext, useContext, useState } from 'react'
import { authApi } from '../api/authApi'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const username = authApi.getUsername()
    const token = authApi.getToken()
    return username && token ? { username, role: authApi.getRole() || 'user' } : null
  })

  const login = async (username, password) => {
    const data = await authApi.login(username, password)
    setUser({ username: data.username, role: data.role })
    return data
  }

  const logout = () => {
    authApi.logout()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
```

### `frontend/src/App.jsx`

```jsx
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import LoginPage from './pages/LoginPage'
import RoomsPage from './pages/RoomsPage'
import MeetingPage from './pages/MeetingPage'

function ProtectedRoute({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/rooms"
            element={
              <ProtectedRoute>
                <RoomsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/meeting/:roomId"
            element={
              <ProtectedRoute>
                <MeetingPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/rooms" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
```

### `frontend/src/pages/LoginPage.jsx`

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    setError('')
    try {
      await login(username.trim(), password)
      navigate('/rooms')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-600 flex items-center justify-center mb-4">
            <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-white">Video Call System</h1>
          <p className="text-gray-500 text-sm mt-1">Sign in to join or create meetings</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
          <div>
            <label htmlFor="username" className="block text-xs font-medium text-gray-400 mb-1.5">
              Username
            </label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="alice"
              autoComplete="username"
              className="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-white
                         placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-xs font-medium text-gray-400 mb-1.5">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              className="w-full px-3 py-2 rounded-xl bg-gray-800 border border-gray-700 text-white
                         placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition"
            />
          </div>

          {error && (
            <p className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white
                       font-medium rounded-xl transition"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="text-[11px] text-gray-600 text-center">
            First login creates your account automatically
          </p>
        </form>
      </div>
    </div>
  )
}
```

---

## 4. Verification

```bash
cd frontend
npm install
npm run build            # must succeed
npm run dev              # http://localhost:5173 — login → /rooms
```

The Playwright suites in phases 6–7 cover the login flow end-to-end
(`unauthenticated redirect`, `wrong password error`, `sign out`).
