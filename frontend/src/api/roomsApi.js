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
