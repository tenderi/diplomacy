import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthContext'
import { clearTokens, REFRESH_STORAGE_KEY } from '@/api/client'

function TestConsumer() {
  const { user, loading, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="loading">{loading ? 'yes' : 'no'}</span>
      <span data-testid="user">{user ? user.email ?? 'no-email' : 'null'}</span>
      <button type="button" onClick={() => login('a@b.com', 'pass')}>
        Login
      </button>
      <button type="button" onClick={logout}>
        Logout
      </button>
    </div>
  )
}

describe('AuthContext', () => {
  const mockUser = {
    id: 1,
    email: 'a@b.com',
    full_name: 'Test',
    telegram_id: null,
    telegram_linked: false,
  }

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
      clear: () => {
        for (const k of Object.keys(store)) delete store[k]
      },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/auth/login')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                user: mockUser,
                access_token: 'access',
                refresh_token: 'refresh',
              }),
          } as Response)
        }
        if (url.includes('/auth/me')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockUser),
          } as Response)
        }
        return Promise.resolve({ ok: false, status: 401 })
      })
    )
  })

  it('starts with loading then no user when no stored refresh', async () => {
    const { container } = render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )
    await waitFor(() => {
      expect(container.querySelector('[data-testid="loading"]')).toHaveTextContent('no')
    })
    expect(container.querySelector('[data-testid="user"]')).toHaveTextContent('null')
  })

  it('login sets user', async () => {
    const { container } = render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )
    await waitFor(() => {
      expect(container.querySelector('[data-testid="loading"]')).toHaveTextContent('no')
    })
    fireEvent.click(container.querySelector('button[type="button"]')!)
    await waitFor(() => {
      expect(container.querySelector('[data-testid="user"]')).toHaveTextContent('a@b.com')
    })
  })

  it('logout clears user', async () => {
    const { container } = render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )
    await waitFor(() => {
      expect(container.querySelector('[data-testid="loading"]')).toHaveTextContent('no')
    })
    fireEvent.click(container.querySelector('button[type="button"]')!)
    await waitFor(() => {
      expect(container.querySelector('[data-testid="user"]')).toHaveTextContent('a@b.com')
    })
    const logoutBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent === 'Logout'
    )
    fireEvent.click(logoutBtn!)
    await waitFor(() => {
      expect(container.querySelector('[data-testid="user"]')).toHaveTextContent('null')
    })
  })
})
