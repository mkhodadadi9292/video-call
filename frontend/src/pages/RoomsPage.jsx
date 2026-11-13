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
