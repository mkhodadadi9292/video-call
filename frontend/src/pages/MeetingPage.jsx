import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useChat } from '../hooks/useChat'
import { useMeetingSession } from '../hooks/useMeetingSession'
import ChatPanel from '../components/ChatPanel'
import JitsiIframe from '../components/JitsiIframe'

// Jitsi is served from the same host over HTTPS (self-signed cert for LAN use).
const JITSI_BASE_URL = `https://${window.location.hostname}:8443`

export default function MeetingPage() {
  const { roomId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const roomIdNum = parseInt(roomId, 10)

  const { room, token, loading, error } = useMeetingSession(roomIdNum)
  const chat = useChat(roomIdNum)
  const [panelOpen, setPanelOpen] = useState(window.innerWidth >= 1024)

  const handleLeave = () => navigate('/rooms')

  if (loading) {
    return (
      <div className="h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-400">Joining meeting…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-screen bg-gray-950 flex flex-col items-center justify-center gap-4">
        <p className="text-gray-400">{error}</p>
        <button
          onClick={() => navigate('/rooms')}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition"
        >
          Back to Rooms
        </button>
      </div>
    )
  }

  return (
    <div className="h-screen bg-gray-950 flex flex-col">
      <header className="bg-gray-900 border-b border-gray-800 h-14 shrink-0 flex items-center justify-between px-3 lg:px-4">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={handleLeave}
            className="flex items-center gap-1 px-2 py-1 text-xs text-red-400 hover:bg-red-400/10 rounded transition shrink-0"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span className="hidden sm:inline">Leave</span>
          </button>
          <h1 className="text-white font-semibold text-sm truncate" data-testid="room-name">
            {room?.name}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 hidden sm:flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            {room?.participants?.length ?? 0}
          </span>
          <button
            onClick={() => setPanelOpen((p) => !p)}
            className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-white hover:bg-gray-800 rounded transition lg:hidden"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 9z" />
            </svg>
            Chat
          </button>
        </div>
      </header>

      <div className="flex-1 flex min-h-0 relative">
        <div className="flex-1 bg-black">
          {room && token && (
            <JitsiIframe jitsiBaseUrl={JITSI_BASE_URL} roomName={room.jitsi_room_id} jwt={token} />
          )}
        </div>

        {panelOpen && (
          <div
            className="lg:hidden fixed inset-0 z-20 bg-black/50"
            onClick={() => setPanelOpen(false)}
          />
        )}

        <div
          className={`
            fixed inset-y-0 right-0 z-30 w-80
            bg-gray-900 border-l border-gray-800 flex flex-col
            transition-transform duration-200
            ${panelOpen
              ? 'translate-x-0 lg:relative lg:w-80 lg:shrink-0 lg:inset-auto lg:z-auto'
              : 'translate-x-full lg:hidden'
            }
          `}
        >
          <div className="flex items-center border-b border-gray-800">
            <span className="flex-1 py-2.5 text-xs font-medium text-indigo-400 text-center border-b-2 border-indigo-500">
              Chat
            </span>
            <button
              onClick={() => setPanelOpen(false)}
              className="px-2.5 py-2 text-gray-500 hover:text-white transition"
              title="Close panel"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            <ChatPanel
              messages={chat.messages}
              sending={chat.sending}
              onSend={chat.send}
              currentUsername={user?.username}
            />
          </div>
        </div>

        {!panelOpen && (
          <button
            onClick={() => setPanelOpen(true)}
            className="hidden lg:flex shrink-0 w-8 bg-gray-900 border-l border-gray-800 items-center justify-center text-gray-500 hover:text-white hover:bg-gray-800 transition"
            title="Open panel"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
