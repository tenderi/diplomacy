import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ResetPassword from './ResetPassword'

describe('ResetPassword', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 401 }))
    )
  })

  it('shows invalid reset link when no token', () => {
    const { container } = render(
      <MemoryRouter>
        <ResetPassword />
      </MemoryRouter>
    )
    expect(within(container).getByRole('heading', { name: /invalid reset link/i })).toBeInTheDocument()
  })

  it('renders form when token in query', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/reset-password?token=abc123']}>
        <ResetPassword />
      </MemoryRouter>
    )
    expect(within(container).getByRole('heading', { name: /set new password/i })).toBeInTheDocument()
    expect(container.querySelector('#password')).toBeInTheDocument()
    expect(container.querySelector('#confirm')).toBeInTheDocument()
  })

  it('shows error when passwords do not match', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/reset-password?token=abc123']}>
        <ResetPassword />
      </MemoryRouter>
    )
    const newPass = container.querySelector('#password')
    const confirmPass = container.querySelector('#confirm')
    if (newPass) fireEvent.change(newPass, { target: { value: 'password123' } })
    if (confirmPass) fireEvent.change(confirmPass, { target: { value: 'different' } })
    fireEvent.click(within(container).getByRole('button', { name: /reset password/i }))
    await waitFor(() => {
      expect(within(container).getByRole('alert')).toHaveTextContent(/do not match/i)
    })
  })

  it('shows success and redirect message on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ message: 'OK' }),
          text: () => Promise.resolve('{"message":"OK"}'),
        } as Response)
      )
    )
    const { container } = render(
      <MemoryRouter initialEntries={['/reset-password?token=abc123']}>
        <ResetPassword />
      </MemoryRouter>
    )
    const newPass = container.querySelector('#password')
    const confirmPass = container.querySelector('#confirm')
    if (newPass) fireEvent.change(newPass, { target: { value: 'password123' } })
    if (confirmPass) fireEvent.change(confirmPass, { target: { value: 'password123' } })
    fireEvent.click(within(container).getByRole('button', { name: /reset password/i }))
    await waitFor(() => {
      expect(within(container).getByText(/password has been reset/i)).toBeInTheDocument()
    })
  })
})
