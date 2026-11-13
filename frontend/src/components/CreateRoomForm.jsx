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
