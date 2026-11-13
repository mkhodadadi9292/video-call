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
