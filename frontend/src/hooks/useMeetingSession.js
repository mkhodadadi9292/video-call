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
