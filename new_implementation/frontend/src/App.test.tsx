import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext, AuthProvider } from '@/contexts/AuthContext'
import App from '@/App'
import { clearTokens } from '@/api/client'

describe('App', () => {
  describe('ProtectedRoute', () => {
    beforeEach(() => {
      clearTokens()
      const store: Record<string, string> = {}
      vi.stubGlobal('localStorage', {
        getItem: (k: string) => store[k] ?? null,
        setItem: (k: string, v: string) => {
          store[k] = v
        },
        removeItem: (k: string) => {
          delete store[k]
        },
        length: 0,
        key: () => null,
        clear: () => {},
      })
      vi.stubGlobal(
        'fetch',
        vi.fn(() => Promise.resolve({ ok: false, status: 401 }))
      )
    })

    it('redirects to login when unauthenticated and visiting /games', async () => {
      const { container } = render(
        <MemoryRouter initialEntries={['/games']}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </MemoryRouter>
      )
      await waitFor(() => {
        expect(within(container).getByRole('heading', { name: /login/i })).toBeInTheDocument()
      })
    })

    it('renders protected content when user is set', async () => {
      const mockUser = {
        id: 1,
        email: 'a@b.com',
        full_name: 'Test',
        telegram_id: null,
        telegram_linked: false,
      }
      const mockAuth = {
        user: mockUser,
        loading: false,
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        refreshUser: vi.fn(),
      }
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string) => {
          if (url.includes('/users/me/games') || url.includes('/games'))
            return Promise.resolve({
              ok: true,
              json: () => Promise.resolve({ games: [] }),
              text: () => Promise.resolve('{"games":[]}'),
            } as Response)
          return Promise.resolve({ ok: false, status: 401 })
        })
      )
      const { container } = render(
        <MemoryRouter initialEntries={['/games']}>
          <AuthContext.Provider value={mockAuth}>
            <App />
          </AuthContext.Provider>
        </MemoryRouter>
      )
      await waitFor(() => {
        expect(within(container).getByRole('heading', { name: 'Games', level: 1 })).toBeInTheDocument()
      })
    })
  })
})
