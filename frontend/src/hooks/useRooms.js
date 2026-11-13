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
