import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { OrderNotes, helperNotes, type OrderNotesView } from './OrderNotes'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function respond(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response)
}

const VIEW: OrderNotesView = {
  orders: [
    {
      order: 'A LON - NWY',
      ok: true,
      notes: [
        {
          kind: 'warning',
          code: 'needs_convoy',
          text: "A LON - NWY needs a convoy: it can succeed only if France's F NTH convoys it",
        },
      ],
    },
    {
      order: 'F EDI - PAR',
      ok: false,
      notes: [{ kind: 'impossible', code: 'fleet_inland', text: 'F EDI cannot move to PAR: it is inland' }],
    },
  ],
  notes: [{ kind: 'warning', code: 'unordered', text: 'A LVP has no order, so it will hold' }],
}

describe('helperNotes', () => {
  it('lists per-order notes, then set notes, each once', () => {
    const twice = { ...VIEW, notes: [...VIEW.notes, ...VIEW.notes] }
    expect(helperNotes(twice).map((n) => n.code)).toEqual(['needs_convoy', 'fleet_inland', 'unordered'])
    expect(helperNotes(null)).toEqual([])
  })
})

describe('OrderNotes', () => {
  it('posts the draft and shows every note as a sentence', async () => {
    const fetchMock = vi.fn(() => respond(VIEW))
    vi.stubGlobal('fetch', fetchMock)
    render(<OrderNotes gameId="7" power="ENGLAND" orders={['A LON - NWY', 'F EDI - PAR']} />)
    expect(
      await screen.findByText("A LON - NWY needs a convoy: it can succeed only if France's F NTH convoys it.")
    ).toBeTruthy()
    expect(screen.getByText('F EDI cannot move to PAR: it is inland.').closest('li')?.className).toContain(
      'text-destructive'
    )
    expect(screen.getByText('A LVP has no order, so it will hold.')).toBeTruthy()
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/games/7/orders/ENGLAND/notes')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ orders: ['A LON - NWY', 'F EDI - PAR'] })
  })

  it('asks nothing for an empty draft and shows nothing when the helper fails', async () => {
    const fetchMock = vi.fn(() => respond({ detail: 'nope' }, 500))
    vi.stubGlobal('fetch', fetchMock)
    const { container, rerender } = render(<OrderNotes gameId="7" power="ENGLAND" orders={[]} />)
    await new Promise((r) => setTimeout(r, 350))
    expect(fetchMock).not.toHaveBeenCalled()
    rerender(<OrderNotes gameId="7" power="ENGLAND" orders={['A LON H']} />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(container.textContent).toBe('')
  })

  it('calls a half-filled unit incomplete instead of saying it will hold (DW3)', async () => {
    const view: OrderNotesView = {
      orders: [],
      notes: [{ kind: 'warning', code: 'unordered', text: 'A BUD has no order, so it will hold' }],
    }
    vi.stubGlobal('fetch', vi.fn(() => respond(view)))
    render(<OrderNotes gameId="7" power="AUSTRIA" orders={['A VIE H']} incomplete={['A BUD']} />)
    expect(await screen.findByText('A BUD is incomplete: choose a target.')).toBeTruthy()
    expect(screen.queryByText('A BUD has no order, so it will hold.')).toBeNull()
  })

  it('shows the incomplete note even when no finished order was sent (DW3)', () => {
    const fetchMock = vi.fn(() => respond(VIEW))
    vi.stubGlobal('fetch', fetchMock)
    render(<OrderNotes gameId="7" power="AUSTRIA" orders={[]} incomplete={['A BUD']} />)
    expect(screen.getByText('A BUD is incomplete: choose a target.')).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
