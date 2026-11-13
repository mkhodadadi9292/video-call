// Auth concern: login/logout + token storage. No UI code here.
import httpClient from './httpClient'

const TOKEN_KEY = 'access_token'
const USERNAME_KEY = 'username'
const ROLE_KEY = 'role'

export const authApi = {
  async login(username, password) {
    const { data } = await httpClient.post('/auth/login', { username, password })
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(USERNAME_KEY, data.username)
    localStorage.setItem(ROLE_KEY, data.role)
    return data
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(ROLE_KEY)
  },

  getToken: () => localStorage.getItem(TOKEN_KEY),
  getUsername: () => localStorage.getItem(USERNAME_KEY),
  getRole: () => localStorage.getItem(ROLE_KEY),
}
