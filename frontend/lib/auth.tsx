'use client'
import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { apiFetch, setAuthTokens, clearAuthTokens } from '@/lib/api'

interface User {
  id: number
  email: string
  name: string
  role: string
  is_active: boolean
  created_at: string
}

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, name: string, password: string) => Promise<void>
  logout: () => Promise<void>
  isAdmin: boolean
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    if (!token) { setLoading(false); return }
    try {
      const me = await apiFetch<User>('/auth/me')
      setUser(me)
    } catch {
      clearAuthTokens()
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchMe() }, [fetchMe])

  const login = async (email: string, password: string) => {
    const res = await apiFetch<{ access_token: string; refresh_token: string }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
    )
    setAuthTokens(res.access_token, res.refresh_token)
    const me = await apiFetch<User>('/auth/me')
    setUser(me)
  }

  const register = async (email: string, name: string, password: string) => {
    const res = await apiFetch<{ access_token: string; refresh_token: string }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify({ email, name, password }) },
    )
    setAuthTokens(res.access_token, res.refresh_token)
    const me = await apiFetch<User>('/auth/me')
    setUser(me)
  }

  const logout = async () => {
    const refresh = typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null
    if (refresh) {
      try { await apiFetch('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: refresh }) }) }
      catch { /* ignore */ }
    }
    clearAuthTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
