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
