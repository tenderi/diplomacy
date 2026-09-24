import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import Register from './Register'
import { clearTokens } from '@/api/client'

describe('Register', () => {
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

  it('registers with the name given and goes home signed in', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          user: { id: 7, email: 'new@b.com', full_name: 'Ann-Marie', telegram_id: null, telegram_linked: false },
          access_token: 'a', refresh_token: 'r',
        }),
      } as Response)
    )
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(
      <MemoryRouter initialEntries={['/register']}>
        <AuthProvider>
          <Routes>
            <Route path="/register" element={<Register />} />
            <Route path="/" element={<p>home</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    )
    fireEvent.change(await within(container).findByLabelText(/email/i), { target: { value: 'new@b.com' } })
    fireEvent.change(within(container).getByLabelText(/^password/i), { target: { value: 'long enough' } })
    fireEvent.change(within(container).getByLabelText(/full name/i), { target: { value: 'Ann-Marie' } })
    fireEvent.click(within(container).getByRole('button', { name: /register/i }))
    expect(await within(container).findByText('home')).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/auth/register')
    expect(JSON.parse(String(init.body))).toEqual({ email: 'new@b.com', password: 'long enough', full_name: 'Ann-Marie' })
  })
  it('shows error when password is less than 8 characters', async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <Register />
        </AuthProvider>
      </MemoryRouter>
    )
    await waitFor(() => expect(within(container).getByRole('heading', { name: /register/i })).toBeInTheDocument())
    const emailInput = container.querySelector('#email')
    const passwordInput = container.querySelector('#password')
    if (emailInput) fireEvent.change(emailInput, { target: { value: 'a@b.com' } })
    if (passwordInput) fireEvent.change(passwordInput, { target: { value: 'short' } })
    fireEvent.click(within(container).getByRole('button', { name: /register/i }))
    await waitFor(() => {
      expect(within(container).getByRole('alert')).toHaveTextContent(/at least 8/i)
    })
  })

  it('shows error on registration failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 422,
          text: () =>
            Promise.resolve(JSON.stringify({ detail: [{ msg: 'Email already registered' }] })),
        })
      )
    )
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <Register />
        </AuthProvider>
      </MemoryRouter>
    )
    await waitFor(() => expect(within(container).getByRole('heading', { name: /register/i })).toBeInTheDocument())
    const emailInput = container.querySelector('#email')
    const passwordInput = container.querySelector('input[type="password"]')
    if (emailInput) fireEvent.change(emailInput, { target: { value: 'a@b.com' } })
    if (passwordInput) fireEvent.change(passwordInput, { target: { value: 'password123' } })
    fireEvent.click(within(container).getByRole('button', { name: /register/i }))
    await waitFor(() => {
      expect(within(container).getByRole('alert')).toHaveTextContent(/email already registered/i)
    })
  })
})
