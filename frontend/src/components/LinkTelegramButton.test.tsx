import { render, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext } from '@/contexts/AuthContext'
import { LinkTelegramButton } from './LinkTelegramButton'

function renderAs(telegramLinked: boolean) {
  const auth = {
    user: { id: 1, email: 'a@b.com', nickname: null, telegram_id: telegramLinked ? '42' : null, telegram_linked: telegramLinked },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  }
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={auth}>
        <LinkTelegramButton />
      </AuthContext.Provider>
    </MemoryRouter>
  ).container
}

describe('LinkTelegramButton', () => {
  it('links to the linking page until the account is linked', () => {
    const container = renderAs(false)
    expect(within(container).getByRole('link', { name: 'Link Telegram' })).toHaveAttribute('href', '/link-telegram')
    expect(within(container).queryByText('You are already linked')).toBeNull()
  })

  it('is an inactive button that says so once linked', () => {
    const container = renderAs(true)
    expect(within(container).queryByRole('link', { name: 'Link Telegram' })).toBeNull()
    expect(within(container).getByRole('button', { name: 'Link Telegram' })).toBeDisabled()
    expect(within(container).getByText('You are already linked')).toBeInTheDocument()
  })
})
