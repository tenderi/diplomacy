import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ForgotPassword from './ForgotPassword'

describe('ForgotPassword', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 401 }))
    )
  })

  it('renders form and heading', () => {
    const { container } = render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    )
    expect(within(container).getByRole('heading', { name: /forgot password/i })).toBeInTheDocument()
    expect(within(container).getByLabelText(/email/i)).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: /send reset link/i })).toBeInTheDocument()
  })

  it('shows success message after submit', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: 'Sent' }),
          text: () => Promise.resolve('{"message":"Sent"}'),
        } as Response)
      )
    )
    const { container } = render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    )
    const emailInput = container.querySelector('#email') ?? within(container).getByRole('textbox', { name: /email/i })
    fireEvent.change(emailInput, { target: { value: 'a@b.com' } })
    fireEvent.click(within(container).getByRole('button', { name: /send reset link/i }))
    await waitFor(() => {
      expect(within(container).getByText(/if an account exists|in development mode/i)).toBeInTheDocument()
    })
  })

  it('shows error on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 404,
          text: () => Promise.resolve(JSON.stringify({ detail: 'Not found' })),
        })
      )
    )
    const { container } = render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>
    )
    const emailInput = container.querySelector('#email') ?? within(container).getByRole('textbox', { name: /email/i })
    fireEvent.change(emailInput, { target: { value: 'a@b.com' } })
    fireEvent.click(within(container).getByRole('button', { name: /send reset link/i }))
    await waitFor(() => {
      expect(within(container).getByRole('alert')).toHaveTextContent(/not found/i)
    })
  })
})
