/**
 * Auth context: register/login/logout + current user.
 * The JWT access token lives in localStorage and is attached to every
 * request by the axios interceptor in api/client.js.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import api, { getToken, setToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [initializing, setInitializing] = useState(true)

  // restore the session on first load if a token exists
  useEffect(() => {
    if (!getToken()) {
      setInitializing(false)
      return
    }
    api
      .get('/auth/me/')
      .then((res) => setUser(res.data))
      .catch(() => setToken(null))
      .finally(() => setInitializing(false))
  }, [])

  const register = useCallback(async (username, password, email = '') => {
    const { data } = await api.post('/auth/register/', { username, password, email })
    setToken(data.access)
    const me = await api.get('/auth/me/')
    setUser(me.data)
    return me.data
  }, [])

  const login = useCallback(async (username, password) => {
    const { data } = await api.post('/auth/login/', { username, password })
    setToken(data.access)
    const me = await api.get('/auth/me/')
    setUser(me.data)
    return me.data
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, initializing, register, login, logout }),
    [user, initializing, register, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
