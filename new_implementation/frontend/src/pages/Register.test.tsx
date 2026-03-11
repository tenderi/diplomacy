import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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

  it('renders form with email, password, full name', () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <Register />
        </AuthProvider>
      </MemoryRouter>
    )
    expect(within(container).getByRole('heading', { name: /register/i })).toBeInTheDocument()
    expect(within(container).getByLabelText(/email/i)).toBeInTheDocument()
    expect(within(container).getByLabelText(/password/i)).toBeInTheDocument()
    expect(within(container).getByLabelText(/full name/i)).toBeInTheDocument()
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
