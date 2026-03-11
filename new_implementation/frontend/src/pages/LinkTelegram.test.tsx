import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '@/contexts/AuthContext'
import LinkTelegram from './LinkTelegram'

describe('LinkTelegram', () => {
  const mockUser = {
    id: 1,
    email: 'a@b.com',
    full_name: 'Test',
    telegram_id: null,
    telegram_linked: false,
  }

  const mockAuth = (overrides?: Partial<{ telegram_linked: boolean }>) => ({
    user: { ...mockUser, ...overrides },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  })

  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 401 }))
    )
  })

  it('renders heading and generate code button', () => {
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth()}>
          <LinkTelegram />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByRole('heading', { name: /link telegram/i })).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: /generate link code/i })).toBeInTheDocument()
  })

  it('shows code after generate success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/auth/me/link_code'))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ code: 'ABC123', expires_in_seconds: 300 }),
            text: () => Promise.resolve('{"code":"ABC123","expires_in_seconds":300}'),
          } as Response)
        return Promise.resolve({ ok: false, status: 401 })
      })
    )
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth()}>
          <LinkTelegram />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    fireEvent.click(within(container).getByRole('button', { name: /generate link code/i }))
    await waitFor(() => {
      expect(within(container).getByText('ABC123')).toBeInTheDocument()
    })
  })

  it('shows already linked when user has telegram_linked', () => {
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth({ telegram_linked: true })}>
          <LinkTelegram />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByText(/already linked to telegram/i)).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: /unlink telegram/i })).toBeInTheDocument()
  })
})
