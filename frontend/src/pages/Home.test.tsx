import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, within, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext, AuthProvider } from '@/contexts/AuthContext'
import Home from './Home'
import { clearTokens } from '@/api/client'

describe('Home', () => {
  beforeEach(() => {
    clearTokens()
    const store: Record<string, string> = {}
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => { store[k] = v },
      removeItem: (k: string) => { delete store[k] },
      length: 0,
      key: () => null,
      clear: () => {},
    })
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 401 })))
  })

  it('shows Login and Register when not logged in', async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <Home />
        </AuthProvider>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(within(container).getByRole('link', { name: /login/i })).toBeInTheDocument()
      expect(within(container).getByRole('link', { name: /register/i })).toBeInTheDocument()
    })
  })

  it('shows greeting and Games / Link Telegram / Logout when logged in', () => {
    const mockUser = {
      id: 1,
      email: 'a@b.com',
      full_name: 'Test User',
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
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <Home />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByText(/hello.*test user/i)).toBeInTheDocument()
    expect(within(container).getByRole('link', { name: /games/i })).toBeInTheDocument()
    expect(within(container).getByRole('link', { name: /link telegram/i })).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: /logout/i })).toBeInTheDocument()
  })

  it('shows Loading when loading', () => {
    const mockAuth = {
      user: null,
      loading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    }
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <Home />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByText(/loading/i)).toBeInTheDocument()
  })
})
