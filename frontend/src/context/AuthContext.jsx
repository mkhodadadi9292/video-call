import { createContext, useContext, useState } from 'react'
import { authApi } from '../api/authApi'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const username = authApi.getUsername()
    const token = authApi.getToken()
    return username && token ? { username, role: authApi.getRole() || 'user' } : null
  })

  const login = async (username, password) => {
    const data = await authApi.login(username, password)
    setUser({ username: data.username, role: data.role })
    return data
  }

  const logout = () => {
    authApi.logout()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
