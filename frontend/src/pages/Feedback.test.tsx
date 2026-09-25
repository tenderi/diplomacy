import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Feedback from './Feedback'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Feedback />
    </MemoryRouter>
  )
}

describe('Feedback', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  afterEach(cleanup)

  beforeEach(() => {
    fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'ok', id: 7 }),
        text: () => Promise.resolve('{"status":"ok","id":7}'),
      } as Response)
    )
    vi.stubGlobal('fetch', fetchMock)
  })

  it('sends the text with the game from the link, then thanks the player', async () => {
    const { container } = renderAt('/feedback?game=42')
    expect(within(container).getByText(/game 42 and its current phase are attached/i)).toBeInTheDocument()
    fireEvent.change(within(container).getByLabelText(/your feedback/i), { target: { value: '  map is wrong  ' } })
    fireEvent.click(within(container).getByRole('button', { name: /send/i }))
    await waitFor(() => {
      expect(within(container).getByText(/sent to the maintainer/i)).toBeInTheDocument()
    })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/feedback$/)
    expect(JSON.parse(init.body)).toEqual({ text: 'map is wrong', game_id: '42', source: 'web' })
    expect(within(container).getByRole('link', { name: /back to game 42/i })).toHaveAttribute('href', '/games/42')
  })

  it('cannot send an empty report', () => {
    const { container } = renderAt('/feedback')
    fireEvent.change(within(container).getByLabelText(/your feedback/i), { target: { value: '   ' } })
    expect(within(container).getByRole('button', { name: /send/i })).toBeDisabled()
  })

  it('shows the server refusal', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 429,
          text: () => Promise.resolve(JSON.stringify({ detail: 'That is a lot of feedback in one hour' })),
        })
      )
    )
    const { container } = renderAt('/feedback')
    fireEvent.change(within(container).getByLabelText(/your feedback/i), { target: { value: 'again' } })
    fireEvent.click(within(container).getByRole('button', { name: /send/i }))
    await waitFor(() => {
      expect(within(container).getByRole('alert')).toHaveTextContent(/a lot of feedback/i)
    })
  })
})
