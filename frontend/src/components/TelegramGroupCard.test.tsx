import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { TelegramGroupCard } from './TelegramGroupCard'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response)
}

const LINKED = { status: 'ok', linked: true, bot_username: 'TestBot', channel_id: '-1001', channel_name: 'Friday Diplomacy' }
const UNLINKED = { status: 'ok', linked: false, bot_username: 'TestBot' }

describe('TelegramGroupCard', () => {
  it('links an unlinked game through the bot, in a new tab, with one line of help', async () => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse(UNLINKED)))
    const { container } = render(<TelegramGroupCard gameId="7" />)
    const link = await within(container).findByRole('link', { name: 'Link a Telegram group' })
    expect(link).toHaveAttribute('href', 'https://t.me/TestBot?startgroup=link_7')
    expect(link).toHaveAttribute('target', '_blank')
    expect(within(container).getByText(/Opens Telegram to pick a group/)).toBeInTheDocument()
    expect(within(container).queryByRole('button', { name: 'Unlink' })).toBeNull()
  })

  function unlinkableGroup() {
    let linked = true
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/games/7/channel/unlink') && init?.method === 'DELETE') {
        linked = false
        return jsonResponse({ status: 'ok' })
      }
      if (url.endsWith('/games/7/channel')) return jsonResponse(linked ? LINKED : UNLINKED)
      return jsonResponse({ detail: 'unexpected' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('names the linked group and unlinks it once confirmed', async () => {
    const fetchMock = unlinkableGroup()
    const { container } = render(<TelegramGroupCard gameId="7" />)

    expect(await within(container).findByText('Friday Diplomacy')).toBeInTheDocument()
    expect(within(container).queryByRole('link', { name: 'Link a Telegram group' })).toBeNull()
    fireEvent.click(within(container).getByRole('button', { name: 'Unlink' }))
    // The dialog is portalled out of `container`.
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/stop getting this game's maps and deadline reminders/)).toBeInTheDocument()
    expect(within(dialog).getByText(/open for anyone to join/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Unlink' }))

    expect(await within(container).findByRole('link', { name: 'Link a Telegram group' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(1)
    expect(within(container).queryByText('Friday Diplomacy')).toBeNull()
  })

  it('does not unlink when the confirmation is cancelled', async () => {
    const fetchMock = unlinkableGroup()
    const { container } = render(<TelegramGroupCard gameId="7" />)

    fireEvent.click(await within(container).findByRole('button', { name: 'Unlink' }))
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(0)
    expect(within(container).getByText('Friday Diplomacy')).toBeInTheDocument()
  })

  it('names the group by its id when the API has no title', async () => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse({ ...LINKED, channel_name: null })))
    const { container } = render(<TelegramGroupCard gameId="7" />)
    expect(await within(container).findByText('group -1001')).toBeInTheDocument()
  })

  it('shows nothing when the API refuses (not a player)', async () => {
    const fetchMock = vi.fn(() => jsonResponse({ detail: 'Only a player in this game can change its Telegram group' }, 403))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<TelegramGroupCard gameId="7" />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(container).toBeEmptyDOMElement()
  })
})
