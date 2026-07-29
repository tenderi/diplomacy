import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, within, waitFor, fireEvent, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthContext } from '@/contexts/AuthContext'
import GameView from './GameView'

/** Minimal ok-response Response stub for a JSON body, used across the tests below. */
function jsonResponse(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response)
}

// This suite's setup does not enable Testing Library's automatic per-test cleanup
// (that requires vitest's `globals: true`, which this project doesn't set), so without
// this every test's rendered DOM accumulates in `document.body`. Scoped `within(container)`
// queries tolerate that, but `screen.*` queries below (needed to reach AlertDialog's
// portal, which renders outside `container`) would otherwise match stale nodes from
// earlier tests in this file.
afterEach(() => cleanup())

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
      // The tally text itself includes the voter list, e.g. "1/3 ... a draw: GERMANY" --
      // GERMANY also appears in the players roster, so match on the full tally line rather
      // than a bare /GERMANY/ regex to avoid an ambiguous multi-match.
      expect(
        within(container).getByText(/1\/3 powers have voted for a draw: GERMANY/)
      ).toBeInTheDocument()
    })
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

/** Fetch stub used by the process-turn / roster / orders-status tests below: covers
 * every endpoint GameView calls for an ACTIVE game, plus an optional `onProcessTurn`
 * spy so tests can assert the confirmation gate actually blocks the real POST. */
function stubFetchActive(
  state: Record<string, unknown>,
  players: Record<string, unknown>[],
  opts: {
    onProcessTurn?: () => void
    processTurnResponse?: () => Promise<Response>
    ordersStatus?: Record<string, unknown>
    savedOrders?: string[]
    legalOrders?: Record<string, unknown>
    lastResolution?: Record<string, unknown>
  } = {}
) {
  return vi.fn((url: string, init?: RequestInit) => {
    if (url.includes('/process_turn') && init?.method === 'POST') {
      opts.onProcessTurn?.()
      return opts.processTurnResponse ? opts.processTurnResponse() : jsonResponse({ status: 'ok' })
    }
    if (url.includes('/last_resolution')) return jsonResponse(opts.lastResolution ?? { results: [] })
    if (url.includes('/orders_status'))
      return jsonResponse(
        opts.ordersStatus ?? { phase: 'S1901M', active_powers: [], submitted: [], missing: [] }
      )
    if (url.includes('/deadline')) return jsonResponse({ status: 'ok', deadline: null })
    if (url.includes('/draw_vote_status'))
      return jsonResponse({
        phase: 'S1901M', game_status: 'ACTIVE', required: [], votes: [], missing: [], quorum_reached: false,
      })
    if (url.includes('/legal_orders/'))
      return jsonResponse(opts.legalOrders ?? { orders: [], orders_by_unit: {} })
    if (url.includes('/state')) return jsonResponse(state)
    if (url.includes('/players')) return jsonResponse(players)
    if (url.includes('/orders/')) return jsonResponse({ orders: opts.savedOrders ?? [] })
    if (url.includes('/messages')) return jsonResponse({ messages: [] })
    return Promise.resolve({ ok: false, status: 401 } as Response)
  })
}

const activeMovementState = {
  game_id: '10',
  map_name: 'standard',
  phase: 'S1901M',
  year: 1901,
  season: 'SPRING',
  phase_type: 'MOVEMENT',
  status: 'ACTIVE',
  units: [{ kind: 'A', power: 'FRANCE', location: 'PAR' }],
  units_by_power: { FRANCE: [{ kind: 'A', power: 'FRANCE', location: 'PAR' }] },
  ownership: { PAR: 'FRANCE' },
  supply_centers: { PAR: 'FRANCE' },
  dislodged: [],
  contested: [],
  players: { FRANCE: { user_id: 1, is_active: true } },
  orders: {},
}
const francePlayers = [{ power: 'FRANCE', user_id: 1, is_active: true, full_name: 'Test' }]

describe('GameView — process turn: gated on membership and confirmed', () => {
  it('hides the process-turn action entirely for a user with no power in the game', async () => {
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, full_name: 'Other' }]
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, otherPlayers))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
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
    expect(within(container).queryByText(/Process turn/i)).not.toBeInTheDocument()
    expect(
      within(container).queryByRole('button', { name: /resolve orders and advance/i })
    ).not.toBeInTheDocument()
  })

  it('requires confirmation before calling process_turn for a member', async () => {
    const onProcessTurn = vi.fn()
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, francePlayers, { onProcessTurn }))

    render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    const trigger = await screen.findByRole('button', { name: /resolve orders and advance/i })
    fireEvent.click(trigger)
    // Opening the confirmation dialog must not itself call process_turn.
    expect(onProcessTurn).not.toHaveBeenCalled()

    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /^process turn$/i }))

    await waitFor(() => {
      expect(onProcessTurn).toHaveBeenCalledTimes(1)
    })
  })
})

describe('GameView — roster', () => {
  it('renders every power with its controlling player or Open', async () => {
    const rosterPlayers = [
      { power: 'FRANCE', user_id: 1, is_active: true, full_name: 'Alice' },
      { power: 'GERMANY', user_id: 2, is_active: true, full_name: 'Bob' },
    ]
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, rosterPlayers))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText('Alice')).toBeInTheDocument()
    })
    expect(within(container).getByText('Bob')).toBeInTheDocument()
    // AUSTRIA is unclaimed in this fixture -- its roster row must say so.
    const austriaRow = within(container).getByText('AUSTRIA').closest('li')
    expect(austriaRow).not.toBeNull()
    expect(within(austriaRow as HTMLElement).getByText('Open')).toBeInTheDocument()
  })
})

describe('GameView — orders status', () => {
  it("shows the logged-in power's submission status and who is still missing", async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchActive(activeMovementState, francePlayers, {
        ordersStatus: {
          phase: 'S1901M',
          active_powers: ['FRANCE', 'GERMANY'],
          submitted: ['GERMANY'],
          missing: ['FRANCE'],
        },
      })
    )

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(
        within(container).getByText(/You still need to submit orders for FRANCE/)
      ).toBeInTheDocument()
    })
    expect(
      within(container).getByText(/1\/2 powers have submitted orders this phase — waiting on FRANCE\./)
    ).toBeInTheDocument()
  })

  it("shows the logged-in power as submitted once it's in the submitted list", async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchActive(activeMovementState, francePlayers, {
        ordersStatus: {
          phase: 'S1901M',
          active_powers: ['FRANCE', 'GERMANY'],
          submitted: ['FRANCE', 'GERMANY'],
          missing: [],
        },
      })
    )

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/Your orders are in for FRANCE/)).toBeInTheDocument()
    })
  })
})

describe('GameView — Adjustment build slots restored from the server', () => {
  it('pre-fills build/waive slots from GET /orders/{power} instead of leaving them empty', async () => {
    const adjustmentState = {
      ...activeMovementState,
      game_id: '12',
      phase: 'W1901A',
      season: 'WINTER',
      phase_type: 'ADJUSTMENT',
      ownership: { PAR: 'FRANCE', MAR: 'FRANCE', BRE: 'FRANCE' },
      supply_centers: { PAR: 'FRANCE', MAR: 'FRANCE', BRE: 'FRANCE' },
    }
    const legalOrders = {
      phase: 'W1901A',
      phase_type: 'ADJUSTMENT',
      power: 'FRANCE',
      units: [{ kind: 'A', location: 'PAR', province: 'PAR', coast: null }],
      orders_by_unit: { 'A MAR': ['BUILD A MAR'], 'F BRE': ['BUILD F BRE'] },
      orders: ['BUILD A MAR', 'BUILD F BRE', 'WAIVE'],
      adjustment: { delta: 2, action: 'build', slots: 2 },
    }
    // The power already submitted these two slots earlier this same phase.
    const savedOrders = ['BUILD A MAR', 'WAIVE']
    vi.stubGlobal(
      'fetch',
      stubFetchActive(adjustmentState, francePlayers, { legalOrders, savedOrders })
    )

    const { container } = render(
      <MemoryRouter initialEntries={['/games/12']}>
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
    // Restored from the server, not left on the "Build / Destroy" placeholder.
    await waitFor(() => {
      expect(within(container).getByText('A MAR')).toBeInTheDocument()
    })
    expect(within(container).getByText('Waive')).toBeInTheDocument()
    expect(within(container).queryAllByText('Build / Destroy')).toHaveLength(0)
  })
})

describe('GameView — 409 conflict handling', () => {
  it('shows a human message instead of the raw StaleGameError text and reloads state', async () => {
    const rawStaleMessage =
      "game 10: expected phase 'S1901M' but the persisted phase is 'F1901M' -- already processed concurrently"
    let processTurnCalls = 0
    const fetchMock = stubFetchActive(activeMovementState, francePlayers, {
      processTurnResponse: () => {
        processTurnCalls += 1
        return jsonResponse({ detail: rawStaleMessage }, 409)
      },
    })
    vi.stubGlobal('fetch', fetchMock)

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    const trigger = await screen.findByRole('button', { name: /resolve orders and advance/i })
    fireEvent.click(trigger)
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /^process turn$/i }))

    await waitFor(() => {
      expect(processTurnCalls).toBe(1)
    })
    await waitFor(() => {
      expect(within(container).getByText(/someone else updated this game/i)).toBeInTheDocument()
    })
    // The raw backend string must never reach the user.
    expect(within(container).queryByText(/expected phase/i)).not.toBeInTheDocument()
    // The state GET is called again (initial load + post-409 reload) to pick up the
    // phase someone else already advanced past.
    const stateCalls = fetchMock.mock.calls.filter(([url]) => (url as string).includes('/state'))
    expect(stateCalls.length).toBeGreaterThanOrEqual(2)
  })
})

describe('GameView — results panel (E4)', () => {
  it('renders nothing for a fresh game with {"results": []} -- no empty scary panel', async () => {
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, francePlayers))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    // Wait for the roster (always present) so the initial load has settled, then assert
    // the results heading never appeared.
    await waitFor(() => {
      expect(within(container).getByText('AUSTRIA')).toBeInTheDocument()
    })
    expect(within(container).queryByText(/what happened last turn/i)).not.toBeInTheDocument()
  })

  it("leads with the viewer's own power in plain language, not raw result codes", async () => {
    const lastResolution = {
      results: [
        {
          order: { type: 'MOVE', power: 'FRANCE', unit: 'PAR', dest: 'BUR' },
          result: 'OK',
          dislodged: false,
          retreat_options: [],
          power: 'FRANCE',
          order_str: 'A PAR - BUR',
        },
        {
          order: { type: 'MOVE', power: 'GERMANY', unit: 'MUN', dest: 'BUR' },
          result: 'BOUNCE',
          dislodged: false,
          retreat_options: [],
          power: 'GERMANY',
          order_str: 'A MUN - BUR',
        },
      ],
    }
    vi.stubGlobal(
      'fetch',
      stubFetchActive(activeMovementState, francePlayers, { lastResolution })
    )

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/what happened last turn/i)).toBeInTheDocument()
    })
    // The viewer's own result is visible immediately, in plain language.
    expect(within(container).getByText('A PAR - BUR')).toBeInTheDocument()
    expect(within(container).getByText(/move succeeded/i)).toBeInTheDocument()
    expect(within(container).queryByText(/^OK$/)).not.toBeInTheDocument()
    // The other power's result is not shown by default -- it's tucked behind a disclosure.
    expect(within(container).queryByText('A MUN - BUR')).not.toBeInTheDocument()
    expect(within(container).getByText(/other powers.*results \(1\)/i)).toBeInTheDocument()

    // Expanding it reveals the raw-code-free description for the other power too.
    fireEvent.click(within(container).getByText(/other powers.*results \(1\)/i))
    expect(within(container).getByText(/GERMANY: A MUN - BUR/)).toBeInTheDocument()
    expect(within(container).getByText(/blocked \(bounced\)/i)).toBeInTheDocument()
    expect(within(container).queryByText(/^BOUNCE$/)).not.toBeInTheDocument()
  })

  it('surfaces a dislodged unit and its retreat options prominently', async () => {
    const lastResolution = {
      results: [
        {
          order: { type: 'HOLD', power: 'FRANCE', unit: 'PAR' },
          result: 'DISLODGED',
          dislodged: true,
          retreat_options: ['PIC', 'GAS'],
          power: 'FRANCE',
          order_str: 'A PAR H',
        },
      ],
    }
    vi.stubGlobal(
      'fetch',
      stubFetchActive(activeMovementState, francePlayers, { lastResolution })
    )

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(within(container).getByText(/must retreat or disband/i)).toBeInTheDocument()
    })
    expect(within(container).getByText(/PIC, GAS/)).toBeInTheDocument()
  })

  it('lets the viewer switch the board image between board / pending orders / last resolution', async () => {
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, francePlayers))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    const img = await waitFor(() => {
      const el = container.querySelector('img[alt^="Game map"]') as HTMLImageElement | null
      expect(el).not.toBeNull()
      return el as HTMLImageElement
    })
    expect(img.src).toContain('/games/10/map?')
    expect(img.src).not.toContain('/map/orders')
    expect(img.src).not.toContain('/map/resolution')

    fireEvent.click(within(container).getByRole('button', { name: 'Pending orders' }))
    await waitFor(() => {
      expect((container.querySelector('img[alt^="Game map"]') as HTMLImageElement).src).toContain(
        '/games/10/map/orders?'
      )
    })

    fireEvent.click(within(container).getByRole('button', { name: 'Last resolution' }))
    await waitFor(() => {
      expect((container.querySelector('img[alt^="Game map"]') as HTMLImageElement).src).toContain(
        '/games/10/map/resolution?'
      )
    })
  })

  it('defaults the map to the resolution overlay once a processed turn has results', async () => {
    const lastResolution = {
      results: [
        {
          order: { type: 'HOLD', power: 'FRANCE', unit: 'PAR' },
          result: 'OK',
          dislodged: false,
          retreat_options: [],
          power: 'FRANCE',
          order_str: 'A PAR H',
        },
      ],
    }
    vi.stubGlobal(
      'fetch',
      stubFetchActive(activeMovementState, francePlayers, { lastResolution })
    )

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect((container.querySelector('img[alt^="Game map"]') as HTMLImageElement).src).toContain(
        '/games/10/map/resolution?'
      )
    })
  })
})
