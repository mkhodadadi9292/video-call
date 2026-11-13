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
