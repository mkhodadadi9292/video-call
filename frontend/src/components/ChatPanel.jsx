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
