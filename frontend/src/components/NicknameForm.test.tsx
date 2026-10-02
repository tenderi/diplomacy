import { fireEvent, render, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext } from '@/contexts/AuthContext'
import { NicknameForm } from './NicknameForm'

describe('NicknameForm', () => {
  it('saves the trimmed nickname and refreshes the user', async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response))
    vi.stubGlobal('fetch', fetchMock)
    const refreshUser = vi.fn(() => Promise.resolve())
    const auth = {
      user: { id: 1, email: 'a@b.com', nickname: null, telegram_id: null, telegram_linked: false },
      loading: false, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshUser,
    }
    const { container } = render(
      <AuthContext.Provider value={auth}>
        <NicknameForm />
      </AuthContext.Provider>
    )
    fireEvent.change(within(container).getByLabelText('Nickname'), { target: { value: '  Talleyrand ' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(refreshUser).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/auth/me')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(String(init.body))).toEqual({ nickname: 'Talleyrand' })
  })
})
