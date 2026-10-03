import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { Link, MemoryRouter, Routes, Route } from 'react-router'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import Home from './Home'
import Login from './Login'
import { clearTokens, REFRESH_STORAGE_KEY } from '@/api/client'

const mockUser = {
  id: 1,
  email: 'a@b.com',
  nickname: 'Test',
  telegram_id: null,
  telegram_linked: false,
}

describe('Login', () => {
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
  })

  it('shows error on login failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 401,
          text: () => Promise.resolve(JSON.stringify({ detail: 'Invalid credentials' })),
        })
      )
    )
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(within(container).getByRole('heading', { name: /login/i })).toBeInTheDocument()
    })
    const emailInput = container.querySelector('#email')
    const passwordInput = container.querySelector('#password')
    if (emailInput) fireEvent.change(emailInput, { target: { value: 'a@b.com' } })
    if (passwordInput) fireEvent.change(passwordInput, { target: { value: 'wrong' } })
    fireEvent.click(within(container).getByRole('button', { name: /login/i }))
    await waitFor(() => {
      expect(within(container).getByRole('alert')).toHaveTextContent(/invalid credentials/i)
    })
  })

  it('navigates to home on login success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/auth/login'))
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                user: mockUser,
                access_token: 'tok',
                refresh_token: 'ref',
              }),
          } as Response)
        return Promise.resolve({ ok: false, status: 401 })
      })
    )
    const { container } = render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )
    const emailInput = container.querySelector('#email')
    const passwordInput = container.querySelector('#password')
    if (emailInput) fireEvent.change(emailInput, { target: { value: 'a@b.com' } })
    if (passwordInput) fireEvent.change(passwordInput, { target: { value: 'pass1234' } })
    fireEvent.click(within(container).getByRole('button', { name: /login/i }))
    await waitFor(() => {
      expect(within(container).getByRole('heading', { name: /diplomacy/i })).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('sends an already signed-in user home', async () => {
    localStorage.setItem(REFRESH_STORAGE_KEY, JSON.stringify({ refresh_token: 'ref' }))
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        const body = url.includes('/auth/refresh')
          ? { access_token: 'tok', refresh_token: 'ref' }
          : { id: 1, email: 'a@b.com', nickname: 'Test', telegram_id: null, telegram_linked: false }
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response)
      })
    )
    function LinkOnceSignedIn() {
      const { user } = useAuth()
      return user ? <Link to="/login">go</Link> : null
    }
    const { container } = render(
      <MemoryRouter initialEntries={['/start']}>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<p>home page</p>} />
            <Route path="/start" element={<LinkOnceSignedIn />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )
    // Open the page only once the session is restored: it then mounts with the
    // user already known, which is when a navigate() during render is lost.
    fireEvent.click(await within(container).findByRole('link', { name: 'go' }))
    await waitFor(() => {
      expect(container).toHaveTextContent('home page')
    })
    expect(container.querySelector('#email')).toBeNull()
  })
})
