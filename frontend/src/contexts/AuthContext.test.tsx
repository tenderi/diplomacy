import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthContext'
import { clearTokens, getAccessToken, REFRESH_STORAGE_KEY } from '@/api/client'

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

  let store: Record<string, string> = {}

  beforeEach(() => {
    store = {}
    clearTokens()
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
  function renderAuth() {
    const view = render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    )
    const text = (id: string) => view.container.querySelector(`[data-testid="${id}"]`)?.textContent
    return { ...view, text }
  }

  function refreshReturns(body: object) {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/auth/refresh')) return Promise.resolve({ ok: 'access_token' in body, json: () => Promise.resolve(body) } as Response)
        if (url.includes('/auth/me')) return Promise.resolve({ ok: true, json: () => Promise.resolve(mockUser) } as Response)
        return Promise.resolve({ ok: false, status: 401 } as Response)
      })
    )
  }

  it('login keeps the session for the next page load, logout forgets it', async () => {
    const { container, text } = renderAuth()
    await waitFor(() => expect(text('loading')).toBe('no'))
    fireEvent.click(container.querySelector('button[type="button"]')!)
    await waitFor(() => expect(text('user')).toBe('a@b.com'))
    expect(JSON.parse(store[REFRESH_STORAGE_KEY])).toEqual({ refresh_token: 'refresh' })
    fireEvent.click(Array.from(container.querySelectorAll('button')).find((b) => b.textContent === 'Logout')!)
    await waitFor(() => expect(text('user')).toBe('null'))
    expect(store[REFRESH_STORAGE_KEY]).toBeUndefined()
  })

  it('a reload with a stored session signs back in and keeps the new refresh token', async () => {
    store[REFRESH_STORAGE_KEY] = JSON.stringify({ refresh_token: 'from-last-week' })
    refreshReturns({ access_token: 'fresh-access', refresh_token: 'fresh-refresh' })
    const { text } = renderAuth()
    await waitFor(() => expect(text('user')).toBe('a@b.com'))
    expect(getAccessToken()).toBe('fresh-access')
    // The API's refresh tokens slide; keeping last week's would log out an everyday player.
    expect(JSON.parse(store[REFRESH_STORAGE_KEY])).toEqual({ refresh_token: 'fresh-refresh' })
  })

  it('a refused stored session is forgotten, not retried on every load', async () => {
    store[REFRESH_STORAGE_KEY] = JSON.stringify({ refresh_token: 'expired' })
    refreshReturns({ detail: 'Invalid or expired refresh token' })
    const { text } = renderAuth()
    await waitFor(() => expect(text('loading')).toBe('no'))
    expect(text('user')).toBe('null')
    expect(store[REFRESH_STORAGE_KEY]).toBeUndefined()
  })

  it('an unreadable stored session is dropped', async () => {
    store[REFRESH_STORAGE_KEY] = '{not json'
    const { text } = renderAuth()
    await waitFor(() => expect(text('loading')).toBe('no'))
    expect(text('user')).toBe('null')
    expect(store[REFRESH_STORAGE_KEY]).toBeUndefined()
  })
})
