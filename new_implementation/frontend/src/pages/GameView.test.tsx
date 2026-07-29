import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthContext } from '@/contexts/AuthContext'
import GameView from './GameView'

const mockUser = {
  id: 1,
  email: 'a@b.com',
  full_name: 'Test',
  telegram_id: null,
  telegram_linked: false,
}

const mockAuth = {
  user: mockUser,
  loading: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
}

const franceUnits = [{ kind: 'A', power: 'FRANCE', location: 'PAR' }]
const minimalGameState = {
  game_id: '1',
  map_name: 'standard',
  phase: 'S1901M',
  year: 1901,
  season: 'SPRING',
  phase_type: 'MOVEMENT',
  status: 'ACTIVE',
  units: franceUnits,
  units_by_power: { FRANCE: franceUnits },
  ownership: { PAR: 'FRANCE' },
  supply_centers: { PAR: 'FRANCE' },
  dislodged: [],
  contested: [],
  players: { FRANCE: { user_id: 1, is_active: true } },
  orders: {},
}

describe('GameView', () => {
  const mockPlayers = [
    { power: 'FRANCE', user_id: 1, is_active: true, full_name: 'Test' },
  ]

  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/state'))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(minimalGameState),
            text: () => Promise.resolve(JSON.stringify(minimalGameState)),
          } as Response)
        if (url.includes('/players'))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockPlayers),
            text: () => Promise.resolve(JSON.stringify(mockPlayers)),
          } as Response)
        if (url.includes('/orders/'))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ orders: [] }),
            text: () => Promise.resolve('{"orders":[]}'),
          } as Response)
        if (url.includes('legal_orders'))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ orders: ['FRANCE A PAR H', 'FRANCE A PAR - BUR'] }),
            text: () => Promise.resolve('{"orders":["FRANCE A PAR H","FRANCE A PAR - BUR"]}'),
          } as Response)
        if (url.includes('/messages'))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ messages: [] }),
            text: () => Promise.resolve('{"messages":[]}'),
          } as Response)
        return Promise.resolve({ ok: false, status: 401 })
      })
    )
  })

  it('renders and shows loading initially', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/games/1']}>
        <AuthContext.Provider value={mockAuth}>
          <GameView />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByText(/loading/i)).toBeInTheDocument()
  })

})

/** Build a `fetch` stub keyed on the pieces GameView needs: /state, /players, /orders,
 * /messages, and the single GET /games/{id}/legal_orders/{power} response from PR2. */
function stubFetchFor(gameState: Record<string, unknown>, legalOrders: Record<string, unknown>) {
  return vi.fn((url: string) => {
    if (url.includes('/legal_orders/'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(legalOrders),
        text: () => Promise.resolve(JSON.stringify(legalOrders)),
      } as Response)
    if (url.includes('/state'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(gameState),
        text: () => Promise.resolve(JSON.stringify(gameState)),
      } as Response)
    if (url.includes('/players'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve([{ power: 'FRANCE', user_id: 1, is_active: true, full_name: 'Test' }]),
        text: () => Promise.resolve('[]'),
      } as Response)
    if (url.includes('/orders/'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ orders: [] }),
        text: () => Promise.resolve('{"orders":[]}'),
      } as Response)
    if (url.includes('/messages'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ messages: [] }),
        text: () => Promise.resolve('{"messages":[]}'),
      } as Response)
    return Promise.resolve({ ok: false, status: 401 } as Response)
  })
}

describe('GameView — RETREAT phase', () => {
  it('renders the dislodged unit with retreat options, no crash', async () => {
    const franceUnits = [{ kind: 'A', power: 'FRANCE', location: 'MAR' }]
    const retreatState = {
      game_id: '2',
      map_name: 'standard',
      phase: 'S1901R',
      year: 1901,
      season: 'SPRING',
      phase_type: 'RETREAT',
      status: 'ACTIVE',
      units: franceUnits,
      units_by_power: { FRANCE: franceUnits },
      ownership: { MAR: 'FRANCE', PAR: 'FRANCE' },
      supply_centers: { MAR: 'FRANCE', PAR: 'FRANCE' },
      dislodged: [
        { unit: { kind: 'A', power: 'FRANCE', location: 'PAR' }, attacker_origin: 'BUR', retreats: ['PIC', 'GAS'] },
      ],
      contested: [],
      players: { FRANCE: { user_id: 1, is_active: true } },
      orders: {},
    }
    const legalOrders = {
      phase: 'S1901R',
      phase_type: 'RETREAT',
      power: 'FRANCE',
      units: [{ kind: 'A', location: 'PAR', province: 'PAR', coast: null }],
      orders_by_unit: { 'A PAR': ['A PAR R PIC', 'A PAR R GAS', 'D A PAR'] },
      orders: ['A PAR R PIC', 'A PAR R GAS', 'D A PAR'],
    }
    vi.stubGlobal('fetch', stubFetchFor(retreatState, legalOrders))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/2']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/Retreat/)).toBeInTheDocument()
    })
    // Only the dislodged unit is offered — the non-dislodged army at MAR is not shown.
    expect(within(container).getByText('A PAR')).toBeInTheDocument()
    expect(within(container).queryByText('A MAR')).not.toBeInTheDocument()
  })
})

describe('GameView — ADJUSTMENT phase', () => {
  it('renders exactly `slots` build slots with build-string options', async () => {
    const franceUnits = [{ kind: 'A', power: 'FRANCE', location: 'PAR' }]
    const adjustmentState = {
      game_id: '3',
      map_name: 'standard',
      phase: 'W1901A',
      year: 1901,
      season: 'WINTER',
      phase_type: 'ADJUSTMENT',
      status: 'ACTIVE',
      units: franceUnits,
      units_by_power: { FRANCE: franceUnits },
      ownership: { PAR: 'FRANCE', MAR: 'FRANCE', BRE: 'FRANCE' },
      supply_centers: { PAR: 'FRANCE', MAR: 'FRANCE', BRE: 'FRANCE' },
      dislodged: [],
      contested: [],
      players: { FRANCE: { user_id: 1, is_active: true } },
      orders: {},
    }
    const legalOrders = {
      phase: 'W1901A',
      phase_type: 'ADJUSTMENT',
      power: 'FRANCE',
      units: [{ kind: 'A', location: 'PAR', province: 'PAR', coast: null }],
      orders_by_unit: {
        'A MAR': ['BUILD A MAR'],
        'F BRE': ['BUILD F BRE'],
      },
      orders: ['BUILD A MAR', 'BUILD F BRE', 'WAIVE'],
      adjustment: { delta: 2, action: 'build', slots: 2 },
    }
    vi.stubGlobal('fetch', stubFetchFor(adjustmentState, legalOrders))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/3']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getAllByText(/^Slot \d+$/)).toHaveLength(2)
    })
    // Exactly `slots` (2) slots — no phantom slot from a stale Math.max floor.
    expect(within(container).getAllByText(/^Slot \d+$/)).toHaveLength(2)
    // Each slot's dropdown is populated from build/waive strings, not left empty-only.
    const comboboxes = within(container).getAllByRole('combobox')
    expect(comboboxes.length).toBeGreaterThanOrEqual(2)
  })

  it('renders without throwing for a power with zero units in an Adjustment phase', async () => {
    const adjustmentState = {
      game_id: '4',
      map_name: 'standard',
      phase: 'W1901A',
      year: 1901,
      season: 'WINTER',
      phase_type: 'ADJUSTMENT',
      status: 'ACTIVE',
      units: [],
      units_by_power: { FRANCE: [] },
      ownership: {},
      supply_centers: {},
      dislodged: [],
      contested: [],
      players: { FRANCE: { user_id: 1, is_active: true } },
      orders: {},
    }
    const legalOrders = {
      phase: 'W1901A',
      phase_type: 'ADJUSTMENT',
      power: 'FRANCE',
      units: [],
      orders_by_unit: {},
      orders: [],
      adjustment: { delta: 0, action: 'none', slots: 0 },
    }
    vi.stubGlobal('fetch', stubFetchFor(adjustmentState, legalOrders))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/4']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/No builds or disbands/i)).toBeInTheDocument()
    })
    expect(within(container).queryAllByText(/^Slot \d+$/)).toHaveLength(0)
  })
})

/** Fetch stub for the draw-vote tests: /state, /players, /orders, /messages, /legal_orders
 * plus GET /draw_vote_status and POST /draw_vote. `drawStatusResponses` is consumed in
 * order across successive GET /draw_vote_status calls (the second call happens after a
 * vote is cast) -- the last entry is reused for any calls beyond the list. */
function stubFetchForDrawVote(
  gameState: Record<string, unknown>,
  players: Record<string, unknown>[],
  drawStatusResponses: Record<string, unknown>[],
  postDrawVoteResponse: Record<string, unknown> = { status: 'recorded', game_status: 'ACTIVE', quorum_reached: false }
) {
  let drawStatusCallCount = 0
  return vi.fn((url: string, init?: RequestInit) => {
    if (url.includes('/draw_vote_status')) {
      const body = drawStatusResponses[Math.min(drawStatusCallCount, drawStatusResponses.length - 1)]
      drawStatusCallCount += 1
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(body),
        text: () => Promise.resolve(JSON.stringify(body)),
      } as Response)
    }
    if (url.includes('/draw_vote') && init?.method === 'POST')
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(postDrawVoteResponse),
        text: () => Promise.resolve(JSON.stringify(postDrawVoteResponse)),
      } as Response)
    if (url.includes('/legal_orders/'))
      // Real API responses always include `orders_by_unit` (see
      // src/server/legal_orders.py -- it's set unconditionally for every
      // phase type), so the mock must too, or GameView's
      // `Object.entries(legalOrders.orders_by_unit)` throws on render.
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ orders: [], orders_by_unit: {} }),
        text: () => Promise.resolve('{"orders":[],"orders_by_unit":{}}'),
      } as Response)
    if (url.includes('/state'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(gameState),
        text: () => Promise.resolve(JSON.stringify(gameState)),
      } as Response)
    if (url.includes('/players'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(players),
        text: () => Promise.resolve(JSON.stringify(players)),
      } as Response)
    if (url.includes('/orders/'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ orders: [] }),
        text: () => Promise.resolve('{"orders":[]}'),
      } as Response)
    if (url.includes('/messages'))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ messages: [] }),
        text: () => Promise.resolve('{"messages":[]}'),
      } as Response)
    return Promise.resolve({ ok: false, status: 401 } as Response)
  })
}

describe('GameView — draw vote', () => {
  const franceUnits = [{ kind: 'A', power: 'FRANCE', location: 'PAR' }]
  const baseGameState = {
    game_id: '5',
    map_name: 'standard',
    phase: 'S1901M',
    year: 1901,
    season: 'SPRING',
    phase_type: 'MOVEMENT',
    status: 'ACTIVE',
    units: franceUnits,
    units_by_power: { FRANCE: franceUnits },
    ownership: { PAR: 'FRANCE' },
    supply_centers: { PAR: 'FRANCE' },
    dislodged: [],
    contested: [],
    players: { FRANCE: { user_id: 1, is_active: true } },
    orders: {},
  }
  const francePlayers = [{ power: 'FRANCE', user_id: 1, is_active: true, full_name: 'Test' }]

  it('renders the current draw-vote tally for the logged-in user', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchForDrawVote(baseGameState, francePlayers, [
        {
          phase: 'S1901M',
          game_status: 'ACTIVE',
          required: ['FRANCE', 'GERMANY', 'ENGLAND'],
          votes: ['GERMANY'],
          missing: ['FRANCE', 'ENGLAND'],
          quorum_reached: false,
        },
      ])
    )

    const { container } = render(
      <MemoryRouter initialEntries={['/games/5']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/1\/3 powers have voted for a draw/)).toBeInTheDocument()
    })
    expect(within(container).getByText(/GERMANY/)).toBeInTheDocument()
    // FRANCE (this user's power) hasn't voted yet -> offered the "vote" action, not "withdraw".
    expect(within(container).getByRole('button', { name: /vote for draw/i })).toBeInTheDocument()
  })

  it('casts a draw vote and reflects the updated tally', async () => {
    const fetchMock = stubFetchForDrawVote(baseGameState, francePlayers, [
      {
        phase: 'S1901M', game_status: 'ACTIVE',
        required: ['FRANCE', 'GERMANY'], votes: [], missing: ['FRANCE', 'GERMANY'],
        quorum_reached: false,
      },
      {
        phase: 'S1901M', game_status: 'ACTIVE',
        required: ['FRANCE', 'GERMANY'], votes: ['FRANCE'], missing: ['GERMANY'],
        quorum_reached: false,
      },
    ])
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(
      <MemoryRouter initialEntries={['/games/5']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/0\/2 powers have voted for a draw/)).toBeInTheDocument()
    })

    fireEvent.click(within(container).getByRole('button', { name: /vote for draw/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/games/5/draw_vote'),
        expect.objectContaining({ method: 'POST' })
      )
    })
    const postCall = fetchMock.mock.calls.find(
      ([url, init]) => (url as string).endsWith('/games/5/draw_vote') && (init as RequestInit)?.method === 'POST'
    )
    expect(postCall).toBeDefined()
    expect(JSON.parse((postCall![1] as RequestInit).body as string)).toEqual({
      power: 'FRANCE',
      vote: true,
    })

    await waitFor(() => {
      expect(within(container).getByText(/1\/2 powers have voted for a draw/)).toBeInTheDocument()
    })
    // Having voted, the control now offers withdrawal instead.
    expect(within(container).getByRole('button', { name: /withdraw draw vote/i })).toBeInTheDocument()
  })

  it('does not show the draw-vote control for a user with no power in the game', async () => {
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, full_name: 'Other' }]
    const noOwnPowerState = { ...baseGameState, units: [], units_by_power: {} }
    vi.stubGlobal('fetch', stubFetchForDrawVote(noOwnPowerState, otherPlayers, [
      { phase: 'S1901M', game_status: 'ACTIVE', required: ['GERMANY'], votes: [], missing: ['GERMANY'], quorum_reached: false },
    ]))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/5']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/Join game/i)).toBeInTheDocument()
    })
    expect(within(container).queryByText(/Draw vote/i)).not.toBeInTheDocument()
  })
})
