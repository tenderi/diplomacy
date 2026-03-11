import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, within, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext, AuthProvider } from '@/contexts/AuthContext'
import { AppLayout } from './AppLayout'
import { clearTokens } from '@/api/client'

describe('AppLayout', () => {
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

  it('shows Login and Register links when user is null', async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <AppLayout>
            <div>Content</div>
          </AppLayout>
        </AuthProvider>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(within(container).getByRole('link', { name: /login/i })).toBeInTheDocument()
      expect(within(container).getByRole('link', { name: /register/i })).toBeInTheDocument()
    })
  })

  it('shows Games, Link Telegram, Logout when user is set', () => {
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
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <AppLayout>
            <div>Content</div>
          </AppLayout>
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByRole('link', { name: /games/i })).toBeInTheDocument()
    expect(within(container).getByRole('link', { name: /link telegram/i })).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: /logout/i })).toBeInTheDocument()
  })

  it('shows Loading in nav when loading is true', () => {
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
          <AppLayout>
            <div>Content</div>
          </AppLayout>
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByText(/loading/i)).toBeInTheDocument()
  })
})
