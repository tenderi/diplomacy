import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useState } from 'react'
import { render, within, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
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

    it('returns to the protected page after logging in (DW1)', async () => {
      const mockUser = { id: 1, email: 'a@b.com', nickname: 'Test', telegram_id: null, telegram_linked: false }
      vi.stubGlobal(
        'fetch',
        vi.fn(() =>
          Promise.resolve({
            ok: false,
            status: 404,
            text: () => Promise.resolve(JSON.stringify({ detail: 'Game not found' })),
          } as Response)
        )
      )
      function Host() {
        const [user, setUser] = useState<typeof mockUser | null>(null)
        const auth = {
          user,
          loading: false,
          login: async () => setUser(mockUser),
          register: vi.fn(),
          logout: vi.fn(),
          refreshUser: vi.fn(),
        }
        return (
          <AuthContext.Provider value={auth}>
            <App />
          </AuthContext.Provider>
        )
      }
      const { container } = render(
        <MemoryRouter initialEntries={['/games/1']}>
          <Host />
        </MemoryRouter>
      )
      const c = within(container)
      await c.findByRole('heading', { name: 'Login' })
      fireEvent.change(container.querySelector('#email')!, { target: { value: 'a@b.com' } })
      fireEvent.change(container.querySelector('#password')!, { target: { value: 'secret123' } })
      fireEvent.click(c.getByRole('button', { name: 'Login' }))
      // /games/1 (here: its "Game not found" page), not the /games list.
      expect(await c.findByText('Game not found')).toBeInTheDocument()
      expect(c.queryByRole('heading', { name: 'Games', level: 1 })).toBeNull()
    })

    it('renders protected content when user is set', async () => {
      const mockUser = {
        id: 1,
        email: 'a@b.com',
        nickname: 'Test',
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

  it('shows a Page not found page with a link home for unknown routes (DW5)', () => {
    clearTokens()
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 401 })))
    const { container } = render(
      <MemoryRouter initialEntries={['/nonexistent']}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    )
    expect(within(container).getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(within(container).getByRole('link', { name: 'Back to home' }).getAttribute('href')).toBe('/')
  })
})
