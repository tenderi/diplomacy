import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { apiJson, API_BASE, clearTokens, getAccessToken, REFRESH_STORAGE_KEY, setTokens } from '../api/client'

export type User = {
  id: number
  email: string | null
  full_name: string | null
  telegram_id: string | null
  telegram_linked: boolean
}

type AuthState = {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName?: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const u = await apiJson<User>('/auth/me')
      setUser(u)
    } catch {
      clearTokens()
      localStorage.removeItem(REFRESH_STORAGE_KEY)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const stored = localStorage.getItem(REFRESH_STORAGE_KEY)
    if (stored) {
      try {
        const { refresh_token } = JSON.parse(stored)
        if (refresh_token) {
          fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token }),
          })
            .then((r) => r.json())
            .then((data) => {
              if (data.access_token) {
                setTokens(data.access_token, data.refresh_token || refresh_token)
                return refreshUser()
              }
            })
            .catch(() => {
              localStorage.removeItem(REFRESH_STORAGE_KEY)
              clearTokens()
            })
            .finally(() => setLoading(false))
          return
        }
      } catch {
        localStorage.removeItem(REFRESH_STORAGE_KEY)
      }
    }
    setLoading(false)
  }, [refreshUser])

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiJson<{ user: User; access_token: string; refresh_token: string }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) }
    )
    setTokens(data.access_token, data.refresh_token)
    localStorage.setItem(REFRESH_STORAGE_KEY, JSON.stringify({ refresh_token: data.refresh_token }))
    setUser(data.user)
  }, [])

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    const data = await apiJson<{ user: User; access_token: string; refresh_token: string }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify({ email, password, full_name: fullName || null }) }
    )
    setTokens(data.access_token, data.refresh_token)
    localStorage.setItem(REFRESH_STORAGE_KEY, JSON.stringify({ refresh_token: data.refresh_token }))
    setUser(data.user)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    localStorage.removeItem(REFRESH_STORAGE_KEY)
    setUser(null)
  }, [])

  const value: AuthState = {
    user,
    loading,
    login,
    register,
    logout,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
