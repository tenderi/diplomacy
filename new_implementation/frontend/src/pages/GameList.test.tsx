import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
      vi.fn((url: string, opts?: RequestInit) => {
        if (url.includes('/users/me/games') || url.includes('/games')) {
          if (opts?.method === 'POST') return Promise.resolve({ ok: false, status: 401 })
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ games: [] }),
            text: () => Promise.resolve('{"games":[]}'),
          } as Response)
        }
        if (url.includes('/games/create') && opts?.method === 'POST') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ game_id: '42' }),
            text: () => Promise.resolve('{"game_id":"42"}'),
          } as Response)
        }
        return Promise.resolve({ ok: false, status: 401 })
      })
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

  it('calls create API on Create new game click', async () => {
    const fetchMock = vi.fn((url: string, opts?: RequestInit) => {
      if (url.includes('/users/me/games') || url.includes('/games')) {
        if (opts?.method === 'POST' && url.includes('create'))
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
      }
      return Promise.resolve({ ok: false, status: 401 })
    })
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuth}>
          <GameList />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(within(container).getByRole('button', { name: /create new game/i })).toBeInTheDocument()
    })
    fireEvent.click(within(container).getByRole('button', { name: /create new game/i }))
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/games/create'),
        expect.objectContaining({ method: 'POST' })
      )
    })
  })
})
