import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, within, waitFor, fireEvent, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router'
import { AuthContext } from '@/contexts/AuthContext'
import GameView from './GameView'
import { toast } from 'sonner'

vi.mock('sonner', async (orig) => {
  const mod = await orig<typeof import('sonner')>()
  return { ...mod, toast: Object.assign(vi.fn(), mod.toast, { success: vi.fn(), warning: vi.fn() }) }
})

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
  nickname: 'Test',
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
        json: () => Promise.resolve([{ power: 'FRANCE', user_id: 1, is_active: true, nickname: 'Test' }]),
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

  it('puts the order entry before the secondary cards (BQ6)', async () => {
    const franceUnits = [{ kind: 'A', power: 'FRANCE', location: 'MAR' }]
    const st = {
      game_id: '2', map_name: 'standard', phase: 'S1901M', year: 1901, season: 'SPRING',
      phase_type: 'MOVEMENT', status: 'ACTIVE', units: franceUnits,
      units_by_power: { FRANCE: franceUnits }, ownership: { MAR: 'FRANCE' },
      supply_centers: { MAR: 'FRANCE' }, dislodged: [], contested: [],
      players: { FRANCE: { user_id: 1, is_active: true } }, orders: {},
    }
    const legal = {
      phase: 'S1901M', phase_type: 'MOVEMENT', power: 'FRANCE',
      units: [{ kind: 'A', location: 'MAR', province: 'MAR', coast: null }],
      orders_by_unit: { 'A MAR': ['A MAR H'] }, orders: ['A MAR H'],
    }
    vi.stubGlobal('fetch', stubFetchFor(st, legal))
    const { container } = render(
      <MemoryRouter initialEntries={['/games/2']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )
    const orders = await within(container).findByRole('heading', { name: 'Orders' })
    const players = within(container).getByRole('heading', { name: 'Players' })
    const follows = orders.compareDocumentPosition(players) & Node.DOCUMENT_POSITION_FOLLOWING
    expect(follows).toBeTruthy()
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
  const francePlayers = [{ power: 'FRANCE', user_id: 1, is_active: true, nickname: 'Test' }]

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
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Other' }]
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
    myGames?: Record<string, unknown>[]
    lastResolution?: Record<string, unknown>
    deadline?: Record<string, unknown>
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
    if (url.includes('/deadline'))
      return jsonResponse(opts.deadline ?? { status: 'ok', deadline: null, schedule: null })
    if (url.includes('/draw_vote_status'))
      return jsonResponse({
        phase: 'S1901M', game_status: 'ACTIVE', required: [], votes: [], missing: [], quorum_reached: false,
      })
    if (url.includes('/map/orders'))
      return Promise.resolve({
        ok: true,
        status: 200,
        blob: () => Promise.resolve(new Blob(['png'], { type: 'image/png' })),
      } as Response)
    if (url.includes('/legal_orders/'))
      return jsonResponse(opts.legalOrders ?? { orders: [], orders_by_unit: {} })
    if (url.includes('/users/me/games')) return jsonResponse({ games: opts.myGames ?? [] })
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
const francePlayers = [{ power: 'FRANCE', user_id: 1, is_active: true, nickname: 'Test' }]

describe('GameView — process turn: the creator only, and confirmed', () => {
  it('hides it from a seated player who did not create the game, and says why', async () => {
    const state = { ...activeMovementState, created_by_user_id: 2 }
    vi.stubGlobal('fetch', stubFetchActive(state, francePlayers))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    expect(await within(container).findByText(/Only the game.s creator can process it early/i)).toBeInTheDocument()
    expect(
      within(container).queryByRole('button', { name: /resolve orders and advance/i })
    ).not.toBeInTheDocument()
  })

  it('hides the process-turn action entirely for a user with no power in the game', async () => {
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Other' }]
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

  it('shows it to the creator of an anonymous game, whose state names no creator', async () => {
    const state = { ...activeMovementState, anonymous: true, created_by_user_id: null }
    const myGames = [{ game_id: 10, power: 'FRANCE', is_creator: true }]
    vi.stubGlobal('fetch', stubFetchActive(state, francePlayers, { myGames }))

    render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    expect(await screen.findByRole('button', { name: /resolve orders and advance/i })).toBeInTheDocument()
  })

  it('requires confirmation before calling process_turn for the creator', async () => {
    const onProcessTurn = vi.fn()
    const state = { ...activeMovementState, created_by_user_id: 1 }
    vi.stubGlobal('fetch', stubFetchActive(state, francePlayers, { onProcessTurn }))

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
      { power: 'FRANCE', user_id: 1, is_active: true, nickname: 'Alice' },
      { power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Bob' },
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

describe('GameView — civil-disorder dummies (W9)', () => {
  it('labels a dummy seat and keeps it out of the join menu', async () => {
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Bob' }]
    const state = { ...activeMovementState, dummy_powers: ['AUSTRIA', 'TURKEY'] }
    vi.stubGlobal('fetch', stubFetchActive(state, otherPlayers))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    const select = await within(container).findByLabelText('Power to join as')
    const offered = Array.from((select as HTMLSelectElement).options).map((o) => o.value)
    expect(offered).not.toContain('AUSTRIA')
    expect(offered).not.toContain('TURKEY')
    expect(offered).toContain('FRANCE')
    const austriaRow = within(container).getByText('AUSTRIA').closest('li')
    expect(within(austriaRow as HTMLElement).getByText('Civil disorder')).toBeInTheDocument()
    expect(within(container).getByText(/1 \/ 5 powers claimed/)).toBeInTheDocument()
  })
})

describe('GameView — auto-processing and wait flags (W10)', () => {
  it('shows who asked to wait and lets a player raise their own flag', async () => {
    const posts: { url: string; body: unknown }[] = []
    const base = stubFetchActive(activeMovementState, francePlayers, {
      ordersStatus: {
        phase: 'S1901M', active_powers: ['FRANCE', 'GERMANY'], submitted: ['FRANCE'], missing: ['GERMANY'],
        waiting: ['GERMANY'], auto_process: true,
      },
    })
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.includes('/wait') && init?.method === 'POST') {
        posts.push({ url, body: JSON.parse(String(init.body)) })
        return jsonResponse({ status: 'ok', waiting: ['FRANCE', 'GERMANY'], auto_processed: 0 })
      }
      return base(url, init)
    }))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    expect(await within(container).findByText(/GERMANY asked to wait/)).toBeInTheDocument()
    fireEvent.click(within(container).getByRole('button', { name: /still negotiating/i }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0].url).toContain('/games/10/wait')
    expect(posts[0].body).toEqual({ power: 'FRANCE', waiting: true })
  })
})

describe('GameView — private games (W8)', () => {
  it('shows a refused join next to the Join form, not in the page banner (BR6)', async () => {
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Bob' }]
    const base = stubFetchActive({ ...activeMovementState, private: true }, otherPlayers)
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.includes('/join') && init?.method === 'POST') {
        return jsonResponse({ detail: 'Wrong join password for game 10.' }, 403)
      }
      return base(url, init)
    }))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    await within(container).findByText(/Private game/)
    fireEvent.change(within(container).getByLabelText('Power to join as'), { target: { value: 'FRANCE' } })
    fireEvent.change(within(container).getByLabelText('Game password'), { target: { value: 'nope' } })
    fireEvent.click(within(container).getByRole('button', { name: /^join$/i }))
    const alert = await within(container).findByText('Wrong join password for game 10.')
    expect(within(container).getAllByText('Wrong join password for game 10.')).toHaveLength(1)
    expect(alert.closest('section')).toContainElement(within(container).getByLabelText('Game password'))
    expect(alert).toHaveFocus()
  })


  it('asks for the password and sends it with the join', async () => {
    const posts: unknown[] = []
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Bob' }]
    const base = stubFetchActive({ ...activeMovementState, private: true }, otherPlayers)
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.includes('/join') && init?.method === 'POST') {
        posts.push(JSON.parse(String(init.body)))
        return jsonResponse({ status: 'ok', player_id: 5 })
      }
      return base(url, init)
    }))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    expect(await within(container).findByText(/Private game/)).toBeInTheDocument()
    fireEvent.change(within(container).getByLabelText('Power to join as'), { target: { value: 'FRANCE' } })
    fireEvent.change(within(container).getByLabelText('Game password'), { target: { value: 'hunter2' } })
    fireEvent.click(within(container).getByRole('button', { name: /^join$/i }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toMatchObject({ power: 'FRANCE', join_password: 'hunter2' })
  })
})

describe('GameView — random powers', () => {
  it('offers one join button and sends no power', async () => {
    const posts: Record<string, unknown>[] = []
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Bob' }]
    const base = stubFetchActive({ ...activeMovementState, random_powers: true }, otherPlayers)
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.includes('/join') && init?.method === 'POST') {
        posts.push(JSON.parse(String(init.body)))
        return jsonResponse({ status: 'ok', player_id: 5, power: 'ITALY' })
      }
      return base(url, init)
    }))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    expect(await within(container).findByText(/Powers are dealt at random/)).toBeInTheDocument()
    expect(within(container).queryByLabelText('Power to join as')).toBeNull()
    fireEvent.click(within(container).getByRole('button', { name: 'Join (random power)' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).not.toHaveProperty('power')
  })
})

describe('GameView — deadline schedule', () => {
  it("shows the game's weekly deadline schedule under the countdown", async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchActive(activeMovementState, francePlayers, {
        deadline: {
          status: 'ok',
          deadline: null,
          schedule: {
            timezone: 'Europe/Helsinki',
            slots: [{ day: 'MON', time: '16:00' }],
            description: 'Mon, Wed, Fri at 16:00 (Europe/Helsinki)',
          },
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

    expect(
      await within(container).findByText('Deadlines every Mon, Wed, Fri at 16:00 (Europe/Helsinki).')
    ).toBeInTheDocument()
  })

  it('shows no schedule line when the game has none', async () => {
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

    expect(await within(container).findByText('No deadline set for this phase.')).toBeInTheDocument()
    expect(within(container).queryByText(/Deadlines every/)).not.toBeInTheDocument()
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

  it('tells a power with nothing to order this phase so, instead of asking for orders', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchActive(activeMovementState, francePlayers, {
        ordersStatus: {
          phase: 'S1901R',
          active_powers: ['GERMANY'],
          submitted: [],
          missing: ['GERMANY'],
          nothing_to_do: ['FRANCE'],
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
      expect(within(container).getByText('FRANCE has nothing to order this phase.')).toBeInTheDocument()
    })
    expect(within(container).queryByText(/You still need to submit orders/)).toBeNull()
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
      expect(within(container).getByText('Build army – MAR')).toBeInTheDocument()
    })
    expect(within(container).getByText('Waive (build nothing)')).toBeInTheDocument()
    expect(within(container).queryAllByText('Build / Destroy')).toHaveLength(0)
  })
})

describe('GameView — 409 conflict handling', () => {
  it('shows a human message instead of the raw StaleGameError text and reloads state', async () => {
    const rawStaleMessage =
      "game 10: expected phase 'S1901M' but the persisted phase is 'F1901M' -- already processed concurrently"
    let processTurnCalls = 0
    const fetchMock = stubFetchActive({ ...activeMovementState, created_by_user_id: 1 }, francePlayers, {
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

describe('GameView — processing a game with empty seats (BA6)', () => {
  it("shows the server's message naming the unseated powers", async () => {
    const detail = '2 powers are unseated (Austria, Turkey): seat players or mark them as dummies.'
    vi.stubGlobal(
      'fetch',
      stubFetchActive({ ...activeMovementState, created_by_user_id: 1 }, francePlayers, {
        processTurnResponse: () =>
          jsonResponse({ detail }, 409).then(
            (r) => ({ ...r, headers: new Headers({ 'X-Error-Code': 'seats_unfilled' }) }) as Response
          ),
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

    fireEvent.click(await screen.findByRole('button', { name: /resolve orders and advance/i }))
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /^process turn$/i }))

    await waitFor(() => {
      expect(within(container).getByText(detail)).toBeInTheDocument()
    })
    expect(within(container).queryByText(/someone else updated this game/i)).not.toBeInTheDocument()
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

  it('shows the movement results before the retreat ones, or alone when the power did not retreat (BR3)', async () => {
    const res = (power: string, type: string, order_str: string, result: string, extra = {}) => ({
      order: { type, power, unit: 'PAR', dest: 'BUR' },
      result,
      dislodged: false,
      retreat_options: [],
      power,
      order_str,
      ...extra,
    })
    const lastResolution = {
      results: [res('GERMANY', 'RETREAT', 'A MUN R KIE', 'OK')],
      movement: { results: [res('FRANCE', 'MOVE', 'A PAR - BUR', 'OK'), res('GERMANY', 'HOLD', 'A MUN H', 'OK')] },
    }
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, francePlayers, { lastResolution }))

    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

    // FRANCE (the viewer) had no retreat: only the movement block, with its move.
    expect(await within(container).findByText('A PAR - BUR')).toBeInTheDocument()
    expect(within(container).getByRole('heading', { name: 'Movement' })).toBeInTheDocument()
    expect(within(container).queryByRole('heading', { name: 'Retreats' })).toBeNull()
    expect(within(container).queryByText(/had no orders recorded/)).toBeNull()
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

  it('lets the viewer switch the board image between board / own pending orders / last resolution', async () => {
    const fetchMock = stubFetchActive(activeMovementState, francePlayers)
    vi.stubGlobal('fetch', fetchMock)
    // jsdom has no object URLs; the orders map is shown from one.
    URL.createObjectURL = vi.fn(() => 'blob:orders-map')
    URL.revokeObjectURL = vi.fn()

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
      const el = container.querySelector('[data-testid="map-inline"]') as HTMLImageElement | null
      expect(el).not.toBeNull()
      return el as HTMLImageElement
    })
    expect(img.src).toContain('/games/10/map?')
    expect(img.src).not.toContain('/map/orders')
    expect(img.src).not.toContain('/map/resolution')

    // Pending orders are secret: the image is fetched with credentials (a bare
    // <img src> sends none) and shown from a blob URL.
    fireEvent.click(within(container).getByRole('button', { name: 'My pending orders' }))
    await waitFor(() => {
      expect((container.querySelector('[data-testid="map-inline"]') as HTMLImageElement).src).toBe(
        'blob:orders-map'
      )
    })
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/games/10/map/orders'))).toBe(true)

    fireEvent.click(within(container).getByRole('button', { name: 'Last resolution' }))
    await waitFor(() => {
      expect((container.querySelector('[data-testid="map-inline"]') as HTMLImageElement).src).toContain(
        '/games/10/map/resolution?'
      )
    })
  })

  it('offers the pending-orders map only to a player seated in the game', async () => {
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, [
      { power: 'ENGLAND', user_id: 99, is_active: true, nickname: 'Someone else' },
    ]))

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
      expect(within(container).getByRole('button', { name: 'Last resolution' })).toBeInTheDocument()
    })
    expect(within(container).queryByRole('button', { name: 'My pending orders' })).toBeNull()
  })

  // Track I1: the map is downscaled to ~47% in this max-w-4xl column, so it must be
  // openable at full size. Covered in isolation by MapViewer.test.tsx; this asserts the
  // game screen actually wires it up, and names the overlay and phase it opened.
  it('opens the full-size map viewer when the inline map is clicked', async () => {
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

    const trigger = await waitFor(() =>
      within(container).getByRole('button', { name: 'Enlarge map: Board — S1901M' })
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    fireEvent.click(trigger)
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Map viewer: Board — S1901M')

    fireEvent.click(screen.getByRole('button', { name: 'Close map viewer' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
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
      expect((container.querySelector('[data-testid="map-inline"]') as HTMLImageElement).src).toContain(
        '/games/10/map/resolution?'
      )
    })
  })
})

/** Wrap a GET stub so every POST is recorded ({url, body}) and answered with `answer`. */
function recordingPosts(base: ReturnType<typeof stubFetchActive>, answer: (url: string) => unknown = () => ({ status: 'ok' })) {
  const posts: { url: string; body: Record<string, unknown> }[] = []
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      posts.push({ url, body: JSON.parse(String(init.body ?? '{}')) })
      return jsonResponse(answer(url))
    }
    return base(url, init)
  })
  return { posts, fetchMock }
}

function renderGame10() {
  return render(
    <MemoryRouter initialEntries={['/games/10']}>
      <AuthContext.Provider value={mockAuth}>
        <Routes>
          <Route path="/games/:gameId" element={<GameView />} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('GameView — player actions', () => {
  it('submits typed orders (the fallback when legal orders cannot be listed) as the whole set', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    const { posts, fetchMock } = recordingPosts(
      vi.fn((url: string, init?: RequestInit) =>
        url.includes('/legal_orders/') ? jsonResponse({ detail: 'Not Found' }, 404) : base(url, init)
      ) as unknown as ReturnType<typeof stubFetchActive>,
      () => ({ results: [] })
    )
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    const box = await within(container).findByPlaceholderText(/A PAR - BUR/)
    fireEvent.change(box, { target: { value: 'A PAR - BUR\n\n   F BRE H  \n' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Submit orders' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toEqual({
      url: '/api/games/set_orders',
      body: { game_id: '10', power: 'FRANCE', orders: ['A PAR - BUR', 'F BRE H'] },
    })
  })

  it('says which orders the server refused instead of "Orders submitted"', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    const { posts, fetchMock } = recordingPosts(
      vi.fn((url: string, init?: RequestInit) =>
        url.includes('/legal_orders/') ? jsonResponse({ detail: 'Not Found' }, 404) : base(url, init)
      ) as unknown as ReturnType<typeof stubFetchActive>,
      () => ({
        results: [
          { order: 'A PAR - BUR', success: true, error: null },
          { order: 'A PAR - LON', success: false, error: 'LON is not adjacent to PAR' },
        ],
      })
    )
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    const box = await within(container).findByPlaceholderText(/A PAR - BUR/)
    fireEvent.change(box, { target: { value: 'A PAR - BUR\nA PAR - LON' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Submit orders' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(
      await within(container).findByText('Not accepted: A PAR - LON (LON is not adjacent to PAR)')
    ).toBeInTheDocument()
  })

  it('shows the server note on an accepted but replaced order', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    const { posts, fetchMock } = recordingPosts(
      vi.fn((url: string, init?: RequestInit) =>
        url.includes('/legal_orders/') ? jsonResponse({ detail: 'Not Found' }, 404) : base(url, init)
      ) as unknown as ReturnType<typeof stubFetchActive>,
      () => ({
        results: [
          { order: 'BUILD F STP/SC', success: true, error: null, note: 'replaced by a later order in this submission: BUILD F STP/NC' },
          { order: 'BUILD F STP/NC', success: true, error: null },
        ],
      })
    )
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()
    const box = await within(container).findByPlaceholderText(/A PAR - BUR/)
    fireEvent.change(box, { target: { value: 'BUILD F STP/SC\nBUILD F STP/NC' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Submit orders' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    await waitFor(() =>
      expect(toast.warning).toHaveBeenCalledWith(
        'Orders submitted',
        expect.objectContaining({
          description: 'BUILD F STP/SC: Replaced by a later order in this submission: BUILD F STP/NC',
        })
      )
    )
  })

  it('still shows an accepted order\'s note when another order was refused', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    const { posts, fetchMock } = recordingPosts(
      vi.fn((url: string, init?: RequestInit) =>
        url.includes('/legal_orders/') ? jsonResponse({ detail: 'Not Found' }, 404) : base(url, init)
      ) as unknown as ReturnType<typeof stubFetchActive>,
      () => ({
        results: [
          { order: 'BUILD F STP/SC', success: true, error: null, note: 'replaced by a later order' },
          { order: 'BUILD A XXX', success: false, error: 'bad province' },
        ],
      })
    )
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()
    const box = await within(container).findByPlaceholderText(/A PAR - BUR/)
    fireEvent.change(box, { target: { value: 'BUILD F STP/SC\nBUILD A XXX' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Submit orders' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    await waitFor(() =>
      expect(toast.warning).toHaveBeenCalledWith(
        'Some orders were accepted',
        expect.objectContaining({ description: 'BUILD F STP/SC: Replaced by a later order' })
      )
    )
    expect(await within(container).findByText('Not accepted: BUILD A XXX (bad province)')).toBeInTheDocument()
  })

  it('relays the note that a fully refused submission changed nothing', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    const { posts, fetchMock } = recordingPosts(
      vi.fn((url: string, init?: RequestInit) =>
        url.includes('/legal_orders/') ? jsonResponse({ detail: 'Not Found' }, 404) : base(url, init)
      ) as unknown as ReturnType<typeof stubFetchActive>,
      () => ({
        results: [
          { order: 'A PAR - LON', success: false, error: 'LON is not adjacent to PAR', note: 'none of these orders was accepted, so nothing was changed. Your earlier orders stand: A PAR H' },
        ],
      })
    )
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    const box = await within(container).findByPlaceholderText(/A PAR - BUR/)
    fireEvent.change(box, { target: { value: 'A PAR - LON' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Submit orders' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(
      await within(container).findByText(
        'Not accepted: A PAR - LON (LON is not adjacent to PAR) none of these orders was accepted, so nothing was changed. Your earlier orders stand: A PAR H'
      )
    ).toBeInTheDocument()
  })

  it.each([
    ['Quit (step away)', /^quit$/i, '/games/10/quit'],
    ['Concede', /^concede$/i, '/games/10/concede'],
  ])('%s asks first, then acts only for your own power', async (opener, confirm, endpoint) => {
    const { posts, fetchMock } = recordingPosts(stubFetchActive(activeMovementState, francePlayers))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    fireEvent.click(await within(container).findByRole('button', { name: opener }))
    const dialog = await screen.findByRole('alertdialog')
    expect(posts).toEqual([])
    fireEvent.click(within(dialog).getByRole('button', { name: confirm }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toEqual({ url: `/api${endpoint}`, body: { power: 'FRANCE' } })
  })

  it('sends a broadcast and reloads the message list', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    const { posts, fetchMock } = recordingPosts(base)
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    fireEvent.click(await within(container).findByRole('checkbox'))
    fireEvent.change(within(container).getByPlaceholderText('Type a message...'), { target: { value: '  Peace in our time  ' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toEqual({ url: '/api/games/10/broadcast', body: { text: 'Peace in our time' } })
    await waitFor(() => expect(within(container).getByPlaceholderText('Type a message...')).toHaveValue(''))
    expect(fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/games/10/messages')).length).toBeGreaterThanOrEqual(2)
  })

  it('sends a broadcast as an anonymous rumour when asked, then resets the toggle', async () => {
    const { posts, fetchMock } = recordingPosts(stubFetchActive(activeMovementState, francePlayers))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    fireEvent.click(await within(container).findByRole('checkbox', { name: 'Broadcast to all' }))
    const rumour = within(container).getByRole('checkbox', { name: 'Send anonymously (rumour)' })
    expect(rumour).toHaveAccessibleDescription('Nobody is told who sent it.')
    fireEvent.click(rumour)
    fireEvent.change(within(container).getByPlaceholderText('Type a message...'), { target: { value: 'Russia is lying' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toEqual({ url: '/api/games/10/broadcast', body: { text: 'Russia is lying', anonymous: true } })
    await waitFor(() =>
      expect(within(container).getByRole('checkbox', { name: 'Send anonymously (rumour)' })).not.toBeChecked()
    )
  })

  it('offers no rumour toggle for a private message, and never sends one', async () => {
    const players = [...francePlayers, { power: 'GERMANY', user_id: 2, is_active: true, nickname: null }]
    const { posts, fetchMock } = recordingPosts(stubFetchActive(activeMovementState, players))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    // Ticked on a broadcast, then switched back to a private message: the toggle goes
    // away and the private message stays signed.
    const toEveryone = await within(container).findByRole('checkbox', { name: 'Broadcast to all' })
    fireEvent.click(toEveryone)
    fireEvent.click(within(container).getByRole('checkbox', { name: 'Send anonymously (rumour)' }))
    fireEvent.click(toEveryone)
    const recipient = within(container).getByLabelText('Message recipient power')
    expect(within(container).queryByRole('checkbox', { name: 'Send anonymously (rumour)' })).toBeNull()
    await waitFor(() => expect(within(recipient as HTMLElement).getByRole('option', { name: 'GERMANY' })).toBeInTheDocument())
    fireEvent.change(recipient, { target: { value: 'GERMANY' } })
    fireEvent.change(within(container).getByPlaceholderText('Type a message...'), { target: { value: 'Ally?' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(posts[0]).toEqual({ url: '/api/games/10/message', body: { recipient_power: 'GERMANY', text: 'Ally?' } })
  })

  it('will not send a blank or whitespace-only message', async () => {
    const { posts, fetchMock } = recordingPosts(stubFetchActive(activeMovementState, francePlayers))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    fireEvent.click(await within(container).findByRole('checkbox', { name: 'Broadcast to all' }))
    const box = within(container).getByPlaceholderText('Type a message...')
    const send = within(container).getByRole('button', { name: 'Send' })
    expect(send).toBeDisabled()
    fireEvent.change(box, { target: { value: ' \n\t ' } })
    expect(send).toBeDisabled()
    fireEvent.click(send)
    fireEvent.change(box, { target: { value: ' x ' } })
    expect(send).toBeEnabled()
    expect(posts).toEqual([])
  })

  it('caps a message at the API limit and counts down near it', async () => {
    const { posts, fetchMock } = recordingPosts(stubFetchActive(activeMovementState, francePlayers))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    fireEvent.click(await within(container).findByRole('checkbox', { name: 'Broadcast to all' }))
    const box = within(container).getByPlaceholderText('Type a message...')
    // The API's MAX_MESSAGE_LENGTH, in UTF-16 units: the unit maxLength counts.
    expect(box).toHaveAttribute('maxLength', '3500')

    // Well under the limit, no counter.
    fireEvent.change(box, { target: { value: 'x'.repeat(2999) } })
    expect(within(container).queryByText(/characters left/)).toBeNull()
    expect(box).not.toHaveAttribute('aria-describedby')

    // Near it, the counter appears and describes the box. An emoji outside the BMP is two units.
    fireEvent.change(box, { target: { value: 'x'.repeat(3000) + '😀' } })
    expect(box).toHaveAccessibleDescription('498 characters left')

    fireEvent.change(box, { target: { value: 'x'.repeat(3500) } })
    expect(box).toHaveAccessibleDescription('0 characters left')
    const send = within(container).getByRole('button', { name: 'Send' })
    expect(send).toBeEnabled()

    // Text set past the limit some other way than typing is not sent either.
    fireEvent.change(box, { target: { value: 'x'.repeat(3501) } })
    expect(send).toBeDisabled()
    fireEvent.click(send)
    expect(posts).toEqual([])
  })

  it('a refused action shows the server\'s reason', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) =>
      init?.method === 'POST' ? jsonResponse({ detail: 'You are not authorized to act for this power.' }, 403) : base(url, init)
    ))
    const { container } = renderGame10()

    fireEvent.click(await within(container).findByRole('button', { name: 'Concede' }))
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: /^concede$/i }))
    expect(await within(container).findByText('You are not authorized to act for this power.')).toBeInTheDocument()
  })
})

describe('GameView — anonymous and public games', () => {
  const anonymousState = {
    ...activeMovementState,
    anonymous: true,
    players: { FRANCE: { user_id: null, is_active: true, seated: true } },
  }
  // An anonymous game's player list carries seats, never who holds them.
  const anonymousPlayers = [
    { power: 'FRANCE', user_id: null, is_active: true, nickname: null, seated: true },
    { power: 'GERMANY', user_id: null, is_active: true, nickname: null, seated: true },
  ]

  function withMessages(
    base: ReturnType<typeof stubFetchActive>,
    messages: Record<string, unknown>[],
    myGames: Record<string, unknown>[] = []
  ) {
    return vi.fn((url: string, init?: RequestInit) => {
      if (url.includes('/users/me/games')) return jsonResponse({ games: myGames })
      if (url.includes('/messages')) return jsonResponse({ messages })
      return base(url, init)
    })
  }

  it('shows held seats without names, and finds the viewer\'s own power from their games list', async () => {
    vi.stubGlobal(
      'fetch',
      withMessages(stubFetchActive(anonymousState, anonymousPlayers), [], [{ game_id: 10, power: 'FRANCE' }])
    )
    const { container } = renderGame10()

    expect(await within(container).findByText('Anonymous')).toBeInTheDocument()
    const roster = within(container).getByRole('heading', { name: 'Players' }).closest('section') as HTMLElement
    await waitFor(() => expect(within(roster).getByText('FRANCE (you)')).toBeInTheDocument())
    const germanyRow = within(roster).getByText('GERMANY').closest('li') as HTMLElement
    expect(within(germanyRow).getByText('Taken')).toBeInTheDocument()
    const austriaRow = within(roster).getByText('AUSTRIA').closest('li') as HTMLElement
    expect(within(austriaRow).getByText('Open')).toBeInTheDocument()
    // A held seat is not offered to join, though no user id says who holds it.
    const select = within(container).queryByLabelText('Power to join as')
    expect(select).toBeNull()
  })

  it('names a message sender by power alone in an anonymous game', async () => {
    const messages = [{ id: 1, sender_user_id: null, sender_power: 'GERMANY', sender_name: null, recipient_power: 'FRANCE', text: 'Ally?' }]
    vi.stubGlobal(
      'fetch',
      withMessages(stubFetchActive(anonymousState, anonymousPlayers), messages, [{ game_id: 10, power: 'FRANCE' }])
    )
    const { container } = renderGame10()

    expect(await within(container).findByText('GERMANY → FRANCE: Ally?')).toBeInTheDocument()
  })

  it('shows a rumour without its sender, and the sender their own rumour with their power', async () => {
    const messages = [
      { id: 1, sender_user_id: null, sender_power: null, sender_name: null, recipient_power: null, text: 'Italy plans a stab', anonymous: true },
      { id: 2, sender_user_id: 1, sender_power: 'FRANCE', sender_name: null, recipient_power: null, text: 'England is weak', anonymous: true },
    ]
    vi.stubGlobal('fetch', withMessages(stubFetchActive(activeMovementState, francePlayers), messages))
    const { container } = renderGame10()

    expect(await within(container).findByText('🕵️ Rumour → ALL: Italy plans a stab')).toBeInTheDocument()
    expect(within(container).getByText('🕵️ Rumour (you, FRANCE) → ALL: England is weak')).toBeInTheDocument()
  })

  it('shows each message phase, marks new ones and counts them in a jump link (BR5)', async () => {
    window.localStorage.setItem('diplomacy:messages-seen:10', '1')
    const messages = [
      { id: 1, sender_user_id: 2, sender_power: 'GERMANY', recipient_power: null, text: 'Old news', phase_code: 'S1901M', timestamp: '2026-10-24T09:05:00' },
      { id: 2, sender_user_id: 2, sender_power: 'GERMANY', recipient_power: null, text: 'Fresh news', phase_code: 'F1901M', timestamp: '2026-10-24T10:05:00' },
    ]
    vi.stubGlobal('fetch', withMessages(stubFetchActive(activeMovementState, francePlayers), messages))
    const { container } = renderGame10()

    const link = await within(container).findByRole('link', { name: 'Messages (1 new)' })
    expect(link.getAttribute('href')).toBe('#messages')
    const section = within(container).getByRole('heading', { name: 'Messages' }).closest('section') as HTMLElement
    const items = within(section).getAllByRole('listitem')
    expect(items[0].textContent).toMatch(/^S1901M · .*GERMANY → ALL: Old news$/)
    expect(items[0].textContent).not.toContain('NEW')
    expect(items[1].textContent).toMatch(/^F1901M · .*NEWGERMANY → ALL: Fresh news$/)
    window.localStorage.clear()
  })

  describe('seen marking (BR5)', () => {
    type FakeObserver = { el: Element | null; cb: IntersectionObserverCallback; disconnected: boolean }
    let observers: FakeObserver[] = []
    let visibleNow = false
    afterEach(() => {
      vi.unstubAllGlobals()
      window.localStorage.clear()
    })
    function stubObserver() {
      observers = []
      visibleNow = false
      vi.stubGlobal(
        'IntersectionObserver',
        class {
          rec: FakeObserver
          constructor(cb: IntersectionObserverCallback) {
            this.rec = { el: null, cb, disconnected: false }
            observers.push(this.rec)
          }
          observe(el: Element) {
            this.rec.el = el
            // A real observer reports its initial state straight away.
            if (visibleNow) this.report(true)
          }
          disconnect() {
            this.rec.disconnected = true
          }
          report(v: boolean) {
            this.rec.cb([{ isIntersecting: v } as IntersectionObserverEntry], this as unknown as IntersectionObserver)
          }
        }
      )
    }
    const live = () => observers.filter((o) => !o.disconnected)
    const msg = (id: number) => ({ id, sender_user_id: 2, sender_power: 'GERMANY', recipient_power: null, text: `m${id}`, phase_code: 'S1901M', timestamp: '2026-10-24T09:05:00' })

    it('observes the mounted messages section, and marks it seen when it scrolls into view', async () => {
      stubObserver()
      vi.stubGlobal('fetch', withMessages(stubFetchActive(activeMovementState, francePlayers), [msg(1), msg(2)]))
      const { container } = renderGame10()
      await within(container).findByRole('link', { name: 'Messages (2 new)' })

      await waitFor(() => expect(live().some((o) => (o.el as HTMLElement | null)?.id === 'messages' && o.el?.isConnected)).toBe(true))
      expect(window.localStorage.getItem('diplomacy:messages-seen:10')).toBeNull()
      const o = live().find((x) => (x.el as HTMLElement | null)?.id === 'messages')!
      o.cb([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
      expect(window.localStorage.getItem('diplomacy:messages-seen:10')).toBe('2')
    })

    it('does not mark a message that arrives while the log is on screen as seen', async () => {
      stubObserver()
      let list = [msg(1), msg(2)]
      const base = stubFetchActive(activeMovementState, francePlayers)
      vi.stubGlobal(
        'fetch',
        vi.fn((url: string, init?: RequestInit) => {
          if (url.includes('/users/me/games')) return jsonResponse({ games: [] })
          if (url.endsWith('/games/10/broadcast')) {
            list = [...list, msg(3)]
            return jsonResponse({ status: 'ok' })
          }
          if (url.includes('/messages')) return jsonResponse({ messages: list })
          return base(url, init)
        })
      )
      const { container } = renderGame10()
      await within(container).findByRole('link', { name: 'Messages (2 new)' })
      await waitFor(() => expect(live().length).toBeGreaterThan(0))
      visibleNow = true
      live().forEach((o) => o.cb([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver))
      expect(window.localStorage.getItem('diplomacy:messages-seen:10')).toBe('2')

      fireEvent.click(within(container).getByRole('checkbox'))
      fireEvent.change(within(container).getByPlaceholderText('Type a message...'), { target: { value: 'hi' } })
      fireEvent.click(within(container).getByRole('button', { name: 'Send' }))
      await within(container).findByText('GERMANY → ALL: m3')
      expect(window.localStorage.getItem('diplomacy:messages-seen:10')).toBe('2')
    })
  })

  it('puts messages after order entry and before the players list', async () => {
    vi.stubGlobal('fetch', withMessages(stubFetchActive(activeMovementState, francePlayers), []))
    const { container } = renderGame10()

    await within(container).findByRole('heading', { name: 'Messages' })
    const titles = within(container).getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(titles.indexOf('Orders')).toBeLessThan(titles.indexOf('Messages'))
    expect(titles.indexOf('Messages')).toBeLessThan(titles.indexOf('Players'))
  })

  it('names a message sender by power and name in a public game', async () => {
    const messages = [{ id: 1, sender_user_id: 2, sender_power: 'GERMANY', sender_name: 'Bob', recipient_power: null, text: 'Hello all' }]
    vi.stubGlobal('fetch', withMessages(stubFetchActive(activeMovementState, francePlayers), messages))
    const { container } = renderGame10()

    expect(await within(container).findByText('GERMANY (Bob) → ALL: Hello all')).toBeInTheDocument()
    expect(within(container).queryByText('Anonymous')).toBeNull()
  })
})

describe('GameView — the Telegram group (BB2b)', () => {
  /** stubFetchActive plus GET /games/10/channel, which the API answers only for a player. */
  function withChannel(base: ReturnType<typeof stubFetchActive>) {
    return vi.fn((url: string, init?: RequestInit) =>
      url.endsWith('/games/10/channel')
        ? jsonResponse({ status: 'ok', linked: true, bot_username: 'TestBot', channel_id: '-1001', channel_name: 'Friday Diplomacy' })
        : base(url, init)
    )
  }

  it('shows a player of the game its group and an Unlink button', async () => {
    vi.stubGlobal('fetch', withChannel(stubFetchActive(activeMovementState, francePlayers)))
    const { container } = renderGame10()

    expect(await within(container).findByText('Friday Diplomacy')).toBeInTheDocument()
    expect(within(container).getByRole('button', { name: 'Unlink' })).toBeInTheDocument()
  })

  it('shows a non-player no group control and does not ask for it', async () => {
    const otherPlayers = [{ power: 'GERMANY', user_id: 2, is_active: true, nickname: 'Other' }]
    const fetchMock = withChannel(stubFetchActive(activeMovementState, otherPlayers))
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()

    expect(await within(container).findByText(/Join game/i)).toBeInTheDocument()
    expect(within(container).queryByText('Telegram group')).toBeNull()
    expect(fetchMock.mock.calls.some(([url]) => (url as string).endsWith('/channel'))).toBe(false)
  })
})

describe('GameView — nickname affordance', () => {
  const noNick = { ...mockAuth, user: { ...mockUser, nickname: null } }
  const renderWith = (auth: typeof mockAuth | typeof noNick) =>
    render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={auth}>
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )

  it('offers the nickname form to a seated player without a nickname', async () => {
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, [{ power: 'FRANCE', user_id: 1, is_active: true, nickname: null }]))
    const { container } = renderWith(noNick)
    expect(await within(container).findByText(/You have no nickname, so other players see only FRANCE/)).toBeInTheDocument()
    expect(within(container).getByLabelText('Nickname')).toBeInTheDocument()
  })

  it('offers nothing to a player who has a nickname', async () => {
    vi.stubGlobal('fetch', stubFetchActive(activeMovementState, francePlayers))
    const { container } = renderWith(mockAuth)
    await within(container).findByText('Players')
    expect(within(container).queryByText(/You have no nickname/)).toBeNull()
  })
})

describe('GameView — turn status stays current (BQ3)', () => {
  const pending = { phase: 'S1901M', active_powers: ['FRANCE'], submitted: [], missing: ['FRANCE'] }
  const done = { phase: 'S1901M', active_powers: ['FRANCE'], submitted: ['FRANCE'], missing: [] }

  /** Stub whose orders_status answer can be swapped; counts state GETs. */
  function mutableStub(initial: Record<string, unknown>) {
    const box = { status: initial, stateGets: 0, stateGate: null as Promise<void> | null }
    const base = stubFetchActive(activeMovementState, francePlayers)
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return jsonResponse({ results: [{ order: 'A PAR - BUR', success: true, error: null }] })
      if (url.includes('/orders_status')) return jsonResponse(box.status)
      if (url.endsWith('/state')) {
        box.stateGets++
        if (box.stateGate) await box.stateGate
      }
      if (url.includes('/legal_orders/')) return jsonResponse({ detail: 'Not Found' }, 404)
      return base(url, init)
    })
    return { box, fetchMock }
  }

  function setVisibility(v: 'visible' | 'hidden') {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => v })
    document.dispatchEvent(new Event('visibilitychange'))
  }

  afterEach(() => {
    vi.useRealTimers()
    setVisibility('visible')
  })

  it('refreshes the status card right after a submission', async () => {
    const { box, fetchMock } = mutableStub(pending)
    vi.stubGlobal('fetch', fetchMock)
    const { container } = renderGame10()
    const textbox = await within(container).findByPlaceholderText(/A PAR - BUR/)
    await within(container).findByText(/You still need to submit orders for FRANCE/)
    box.status = done
    fireEvent.change(textbox, { target: { value: 'A PAR - BUR' } })
    fireEvent.click(within(container).getByRole('button', { name: 'Submit orders' }))
    expect(await within(container).findByText('Your orders are in for FRANCE.')).toBeInTheDocument()
  })

  it('polls every 30 s while visible, pauses while hidden, refreshes on becoming visible', async () => {
    const { box, fetchMock } = mutableStub(pending)
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    const { container } = renderGame10()
    await within(container).findByText(/You still need to submit orders for FRANCE/)
    const before = box.stateGets
    box.status = done
    await vi.advanceTimersByTimeAsync(29_000)
    expect(box.stateGets).toBe(before)
    await vi.advanceTimersByTimeAsync(1_000)
    expect(box.stateGets).toBe(before + 1)
    expect(await within(container).findByText('Your orders are in for FRANCE.')).toBeInTheDocument()

    setVisibility('hidden')
    await vi.advanceTimersByTimeAsync(90_000)
    expect(box.stateGets).toBe(before + 1)
    setVisibility('visible')
    await vi.advanceTimersByTimeAsync(0)
    expect(box.stateGets).toBe(before + 2)
  })

  it('does not start a refresh while the previous one is still in flight', async () => {
    const { box, fetchMock } = mutableStub(pending)
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    const { container } = renderGame10()
    await within(container).findByText(/You still need to submit orders for FRANCE/)
    const before = box.stateGets
    let release!: () => void
    box.stateGate = new Promise<void>((r) => { release = r })
    await vi.advanceTimersByTimeAsync(30_000)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(box.stateGets).toBe(before + 1)
    box.stateGate = null
    release()
    await vi.advanceTimersByTimeAsync(30_000)
    expect(box.stateGets).toBe(before + 2)
  })

  it('a poll that returns a new phase clears the old order text and refetches the deadline', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    let phase = 'S1901M'
    let deadlineGets = 0
    let savedOrders: string[] = []
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/state'))
        return jsonResponse({ ...activeMovementState, phase, season: phase === 'S1901M' ? 'SPRING' : 'FALL' })
      if (url.includes('/deadline')) deadlineGets++
      if (url.includes('/orders/FRANCE')) return jsonResponse({ orders: savedOrders })
      if (url.includes('/legal_orders/')) return jsonResponse({ detail: 'Not Found' }, 404)
      return base(url, init)
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    const { container } = renderGame10()
    const textbox = await within(container).findByPlaceholderText(/A PAR - BUR/)
    fireEvent.change(textbox, { target: { value: 'A PAR - BUR' } })
    expect(textbox).toHaveValue('A PAR - BUR')
    const before = deadlineGets
    phase = 'F1901M'
    await vi.advanceTimersByTimeAsync(30_000)
    await vi.advanceTimersByTimeAsync(0)
    expect(within(container).getByPlaceholderText(/A PAR - BUR/)).toHaveValue('')
    // The poll refetches it, and so does the effect keyed on the new phase.
    expect(deadlineGets).toBe(before + 2)
  })

  it('ignores a poll still in flight when the game changes', async () => {
    const base = stubFetchActive(activeMovementState, francePlayers)
    let release!: () => void
    const gate = new Promise<void>((r) => { release = r })
    let stateGets = 0
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/games/10/state') && ++stateGets === 2) {
        await gate
        return jsonResponse({ ...activeMovementState, game_id: '10', phase: 'F1901M' })
      }
      if (url.endsWith('/games/11/state'))
        return jsonResponse({ ...activeMovementState, game_id: '11' })
      if (url.includes('/legal_orders/')) return jsonResponse({ detail: 'Not Found' }, 404)
      return base(url.replace('/games/11/', '/games/10/'), init)
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    function GoTo() {
      const navigate = useNavigate()
      return <button onClick={() => navigate('/games/11')}>go</button>
    }
    const { container } = render(
      <MemoryRouter initialEntries={['/games/10']}>
        <AuthContext.Provider value={mockAuth}>
          <GoTo />
          <Routes>
            <Route path="/games/:gameId" element={<GameView />} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )
    await within(container).findByText(/You still need to submit orders for FRANCE/)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(stateGets).toBe(2)
    fireEvent.click(within(container).getByText('go'))
    await vi.advanceTimersByTimeAsync(0)
    release()
    await vi.advanceTimersByTimeAsync(0)
    expect(within(container).queryByText(/F1901M/)).toBeNull()
    expect(within(container).getByText(/Spring 1901 · S1901M/)).toBeInTheDocument()
  })
})
