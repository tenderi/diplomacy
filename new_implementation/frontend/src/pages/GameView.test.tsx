import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
