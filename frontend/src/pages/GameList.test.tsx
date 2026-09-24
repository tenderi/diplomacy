import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthContext } from '@/contexts/AuthContext'
import GameList from './GameList'

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

describe('GameList', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ games: [] }),
          text: () => Promise.resolve('{"games":[]}'),
        } as Response)
      )
    )
  })

  it('shows Loading initially then content', async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(within(container).getByText(/loading/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(within(container).getByRole('heading', { name: 'Games', level: 1 })).toBeInTheDocument()
    })
  })

  it('shows empty state and Create new game button when loaded', async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(within(container).getByText(/you are not in any games/i)).toBeInTheDocument()
    })
    expect(within(container).getByRole('button', { name: /create new game/i })).toBeInTheDocument()
  })

  it('shows my games when API returns data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.includes('/users/me/games'))
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                games: [
                  {
                    game_id: 1,
                    map_name: 'standard',
                    power: 'FRANCE',
                    current_turn: 2,
                    status: 'active',
                  },
                ],
              }),
            text: () => Promise.resolve('{"games":[{"game_id":1,"map_name":"standard","power":"FRANCE","current_turn":2,"status":"active"}]}'),
          } as Response)
        if (url.includes('/games') && !url.includes('/users/me'))
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ games: [] }),
            text: () => Promise.resolve('{"games":[]}'),
          } as Response)
        return Promise.resolve({ ok: false, status: 401 })
      })
    )
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(within(container).getByRole('link', { name: /game 1.*france/i })).toBeInTheDocument()
    })
  })

  it('creating a game opens it', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string, opts?: RequestInit) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(opts?.method === 'POST' && url.includes('/games/create') ? { game_id: '99' } : { games: [] }),
      } as Response)
    ))
    const { container } = render(
      <MemoryRouter initialEntries={['/games']}>
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route path="/games" element={<GameList />} />
            <Route path="/games/:gameId" element={<p>game page</p>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    )
    fireEvent.click(await within(container).findByRole('button', { name: /create new game/i }))
    expect(await within(container).findByText('game page')).toBeInTheDocument()
  })

  it('a refused create says why and stays on the list', async () => {
    vi.stubGlobal('fetch', vi.fn((_url: string, opts?: RequestInit) =>
      Promise.resolve(opts?.method === 'POST'
        ? ({ ok: false, status: 400, text: () => Promise.resolve('{"detail":"Leave at least one power to a human"}') } as Response)
        : ({ ok: true, json: () => Promise.resolve({ games: [] }) } as Response))
    ))
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    fireEvent.click(await within(container).findByRole('button', { name: /create new game/i }))
    expect(await within(container).findByText('Leave at least one power to a human')).toBeInTheDocument()
  })

  it('lists every open game with its seats and a lock on private ones', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(url.includes('/users/me/games') ? { games: [] } : {
          games: [
            { id: 5, map_name: 'standard', player_count: 3, max_players: 5, current_turn: 0, private: true },
            { id: 6, map_name: 'standard', player_count: 7, current_turn: 4, private: false },
          ],
        }),
      } as Response)
    ))
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    expect(await within(container).findByRole('link', { name: '🔒 Game 5 — standard — 3/5 — turn 0' })).toHaveAttribute('href', '/games/5')
    expect(within(container).getByRole('link', { name: 'Game 6 — standard — 7/7 — turn 4' })).toBeInTheDocument()
  })

  it('sends the powers ticked for civil disorder with the create request (W9)', async () => {
    const fetchMock = vi.fn((url: string, opts?: RequestInit) => {
      if (opts?.method === 'POST' && url.includes('/games/create'))
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ game_id: '99' }),
          text: () => Promise.resolve('{"game_id":"99"}'),
        } as Response)
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ games: [] }),
        text: () => Promise.resolve('{"games":[]}'),
      } as Response)
    })
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    const turkey = await within(container).findByLabelText('TURKEY')
    fireEvent.click(turkey)
    fireEvent.click(within(container).getByLabelText('ITALY'))
    fireEvent.click(within(container).getByRole('button', { name: /create new game/i }))
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([u, o]) => String(u).includes('/games/create') && o?.method === 'POST')
      expect(call).toBeDefined()
      expect(JSON.parse(String(call![1]!.body)).dummy_powers).toEqual(['TURKEY', 'ITALY'])
    })
  })
})
