import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, waitFor, fireEvent, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import Sandbox, { type SandboxView } from './Sandbox'

afterEach(() => cleanup())

const ALL = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

function view(overrides: Partial<SandboxView> = {}): SandboxView {
  return {
    phase: 'S1901M',
    year: 1901,
    season: 'SPRING',
    phase_type: 'MOVEMENT',
    status: 'ACTIVE',
    winners: null,
    units_by_power: {
      FRANCE: [
        { kind: 'A', power: 'FRANCE', location: 'PAR' },
        { kind: 'F', power: 'FRANCE', location: 'BRE' },
      ],
      GERMANY: [{ kind: 'A', power: 'GERMANY', location: 'MUN' }],
    },
    ownership: { PAR: 'FRANCE', MUN: 'GERMANY' },
    dislodged: [],
    powers_to_order: ALL,
    ...overrides,
  }
}

const OPENING = { state: { tag: 'opening' }, view: view() }

const LEGAL_AUSTRIA = {
  phase: 'S1901M',
  phase_type: 'MOVEMENT',
  power: 'AUSTRIA',
  units: [],
  orders_by_unit: {},
  orders: [],
}

type Call = { url: string; body: Record<string, unknown> | null }

function json(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    blob: () => Promise.resolve(new Blob(['png'])),
  } as Response)
}

/** A fetch stub for every sandbox endpoint; records each call with its JSON body. */
function stubFetch(handlers: { start?: () => Promise<Response>; adjudicate?: () => Promise<Response> } = {}) {
  const calls: Call[] = []
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null })
    if (url.includes('/sandbox/start')) return handlers.start ? handlers.start() : json(OPENING)
    if (url.includes('/sandbox/legal_orders')) return json(LEGAL_AUSTRIA)
    if (url.includes('/sandbox/adjudicate')) return handlers.adjudicate ? handlers.adjudicate() : json({})
    if (url.includes('/sandbox/map')) return json({})
    if (url.includes('/provinces')) return json({ provinces: {} })
    return json({}, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/sandbox" element={<Sandbox />} />
      </Routes>
    </MemoryRouter>
  )
}

function typeOrders(power: string, text: string) {
  fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${power}`) }))
  fireEvent.change(screen.getByLabelText(`Orders for ${power}, one per line`), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Use these orders' }))
}

beforeEach(() => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:map'), revokeObjectURL: vi.fn() }))
})

afterEach(() => vi.unstubAllGlobals())

describe('Sandbox', () => {
  it('starts from the opening position and shows its map', async () => {
    const calls = stubFetch()
    renderAt('/sandbox')

    expect(await screen.findByRole('button', { name: 'Resolve S1901M' })).toBeInTheDocument()
    expect(screen.getByText(/started from the opening position/)).toBeInTheDocument()
    expect(calls.find((c) => c.url.includes('/sandbox/start'))?.body).toEqual({})
    await waitFor(() => expect(screen.getByTestId('map-inline')).toHaveAttribute('src', 'blob:map'))
    expect(calls.find((c) => c.url.includes('/sandbox/map'))?.body).toEqual({
      state: { tag: 'opening' },
      orders: {},
      overlay: 'board',
    })
    expect(screen.getByRole('link', { name: 'Exit sandbox' })).toHaveAttribute('href', '/games')
  })

  it("starts from a game's board and exits back to that game", async () => {
    const calls = stubFetch()
    renderAt('/sandbox?game=7')

    expect(await screen.findByText(/started from game 7/)).toBeInTheDocument()
    expect(calls.find((c) => c.url.includes('/sandbox/start'))?.body).toEqual({ game_id: '7' })
    expect(screen.getByRole('link', { name: 'Exit sandbox (back to game 7)' })).toHaveAttribute(
      'href',
      '/games/7'
    )
  })

  it('shows why the sandbox could not start', async () => {
    stubFetch({ start: () => json({ detail: 'Game not found' }, 404) })
    renderAt('/sandbox?game=99')

    expect(await screen.findByText('Game not found')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Resolve/ })).not.toBeInTheDocument()
  })

  it('fetches legal orders for the selected power', async () => {
    const calls = stubFetch()
    renderAt('/sandbox')
    await screen.findByRole('button', { name: 'Resolve S1901M' })

    await waitFor(() =>
      expect(calls.find((c) => c.url.includes('/sandbox/legal_orders'))?.body).toEqual({
        state: { tag: 'opening' },
        power: 'AUSTRIA',
      })
    )
  })

  it('resolves every power, reports the outcome, and steps back and starts over', async () => {
    const next = view({ phase: 'F1901M', season: 'FALL' })
    const calls = stubFetch({
      adjudicate: () =>
        json({
          state: { tag: 'fall' },
          view: next,
          order_results: {
            FRANCE: [{ order: 'A PAR - BUR', ok: true, reason: null }],
            GERMANY: [{ order: 'A MUN - PAR', ok: false, reason: 'PAR is not adjacent to MUN' }],
          },
          resolution: {
            results: [
              {
                order: { type: 'HOLD', power: 'GERMANY' },
                result: 'OK',
                dislodged: false,
                retreat_options: [],
                power: 'GERMANY',
                order_str: 'A MUN H',
              },
              {
                order: { type: 'MOVE', power: 'FRANCE' },
                result: 'OK',
                dislodged: false,
                retreat_options: [],
                power: 'FRANCE',
                order_str: 'A PAR - BUR',
              },
            ],
          },
        }),
    })
    renderAt('/sandbox')
    await screen.findByRole('button', { name: 'Resolve S1901M' })

    typeOrders('FRANCE', 'a par - bur\nF BRE - MAO')
    typeOrders('GERMANY', 'A MUN - PAR')
    expect(screen.getByRole('button', { name: 'FRANCE (2)' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Orders this phase' })).toHaveTextContent(
      'FRANCE: A PAR - BURFRANCE: F BRE - MAOGERMANY: A MUN - PAR'
    )
    fireEvent.click(screen.getByRole('button', { name: 'Resolve S1901M' }))

    expect(await screen.findByText('What happened in S1901M')).toBeInTheDocument()
    expect(calls.find((c) => c.url.includes('/sandbox/adjudicate'))?.body).toEqual({
      state: { tag: 'opening' },
      orders: { FRANCE: ['A PAR - BUR', 'F BRE - MAO'], GERMANY: ['A MUN - PAR'] },
    })
    expect(
      screen.getByText('Not accepted (the unit held instead): GERMANY: A MUN - PAR (PAR is not adjacent to MUN)')
    ).toBeInTheDocument()
    expect(screen.getByText('FRANCE: A PAR - BUR')).toBeInTheDocument()
    expect(screen.getByText('Units that held (1)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resolve F1901M' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Orders this phase' })).not.toBeInTheDocument()
    await waitFor(() =>
      expect(calls.filter((c) => c.url.includes('/sandbox/map')).slice(-1)[0]?.body).toEqual({
        state: { tag: 'opening' },
        orders: { FRANCE: ['A PAR - BUR', 'F BRE - MAO'], GERMANY: ['A MUN - PAR'] },
        overlay: 'resolution',
      })
    )

    fireEvent.click(screen.getByRole('button', { name: 'Step back' }))
    expect(screen.getByRole('button', { name: 'Resolve S1901M' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Orders this phase' })).toHaveTextContent('GERMANY: A MUN - PAR')

    fireEvent.click(screen.getByRole('button', { name: 'Resolve S1901M' }))
    await screen.findByRole('button', { name: 'Resolve F1901M' })
    fireEvent.click(screen.getByRole('button', { name: 'Start over' }))
    expect(screen.getByRole('button', { name: 'Resolve S1901M' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Orders this phase' })).not.toBeInTheDocument()
    expect(screen.queryByText('What happened in S1901M')).not.toBeInTheDocument()
  })

  it('clears one power’s orders', async () => {
    stubFetch()
    renderAt('/sandbox')
    await screen.findByRole('button', { name: 'Resolve S1901M' })

    typeOrders('FRANCE', 'A PAR H')
    fireEvent.click(screen.getByRole('button', { name: "Clear FRANCE's orders" }))

    expect(screen.getByRole('button', { name: 'FRANCE' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Orders this phase' })).not.toBeInTheDocument()
  })

  it('sends adjustment orders as build slots, and says who has nothing to do', async () => {
    const winter = view({ phase: 'W1901A', season: 'WINTER', phase_type: 'ADJUSTMENT', powers_to_order: ['FRANCE'] })
    const calls = stubFetch({
      start: () => json({ state: { tag: 'winter' }, view: winter }),
      adjudicate: () => json({ detail: "this board's game is over" }, 409),
    })
    renderAt('/sandbox')
    await screen.findByRole('button', { name: 'Resolve W1901A' })

    // The first power that can act is selected; the others say so.
    fireEvent.click(screen.getByRole('button', { name: 'ENGLAND' }))
    expect(screen.getByText('ENGLAND has nothing to order in this adjustment phase.')).toBeInTheDocument()
    typeOrders('FRANCE', 'A PAR B')
    fireEvent.click(screen.getByRole('button', { name: 'Resolve W1901A' }))

    await waitFor(() =>
      expect(calls.find((c) => c.url.includes('/sandbox/adjudicate'))?.body).toEqual({
        state: { tag: 'winter' },
        orders: { FRANCE: ['A PAR B'] },
      })
    )
    expect(await screen.findByText("this board's game is over")).toBeInTheDocument()
  })

  it('offers only stepping back once the game on the board is over', async () => {
    stubFetch({
      start: () => json({ state: {}, view: view({ status: 'COMPLETED', winners: ['FRANCE'], powers_to_order: [] }) }),
    })
    renderAt('/sandbox')

    expect(await screen.findByText(/This board's game is over — FRANCE/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resolve S1901M' })).toBeDisabled()
    expect(screen.queryByRole('heading', { name: 'Orders' })).not.toBeInTheDocument()
  })
})
