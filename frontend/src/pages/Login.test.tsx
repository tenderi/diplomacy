import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import Home from './Home'
import Login from './Login'
import { clearTokens } from '@/api/client'

const mockUser = {
  id: 1,
  email: 'a@b.com',
  full_name: 'Test',
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

  it('renders form with email, password, submit', () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 401 })))
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>
    )
    expect(within(container).getByRole('heading', { name: /login/i })).toBeInTheDocument()
    expect(within(container).getByLabelText(/email/i)).toBeInTheDocument()
    expect(within(container).getByLabelText(/password/i)).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: /login/i })).toBeInTheDocument()
    expect(within(container).getByRole('link', { name: /register/i })).toBeInTheDocument()
    expect(within(container).getByRole('link', { name: /forgot password/i })).toBeInTheDocument()
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
})
