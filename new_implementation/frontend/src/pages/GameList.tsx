import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiJson } from '../api/client'

type Game = { game_id: number; map_name: string; power: string; current_turn: number; status: string }
type AllGame = { id: number; map_name: string; current_turn: number; status: string; player_count: number }

export default function GameList() {
  const [myGames, setMyGames] = useState<Game[]>([])
  const [allGames, setAllGames] = useState<AllGame[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      apiJson<{ games: Game[] }>('/users/me/games'),
      apiJson<{ games: AllGame[] }>('/games'),
    ])
      .then(([me, all]) => {
        setMyGames(me.games || [])
        setAllGames(all.games || [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ padding: 20 }}>Loading...</div>

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <h1>Games</h1>
      <p><Link to="/">Home</Link></p>
      <h2>My games</h2>
      {myGames.length === 0 ? (
        <p>You are not in any games.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {myGames.map((g) => (
            <li key={g.game_id} style={{ marginBottom: 8 }}>
              <Link to={`/games/${g.game_id}`}>
                Game {g.game_id} — {g.power} — turn {g.current_turn}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <h2>All games</h2>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {allGames.map((g) => (
          <li key={g.id} style={{ marginBottom: 8 }}>
            <Link to={`/games/${g.id}`}>
              Game {g.id} — {g.map_name} — {g.player_count}/7 — turn {g.current_turn}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
