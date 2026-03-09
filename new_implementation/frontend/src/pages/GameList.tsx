import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'

type Game = { game_id: number; map_name: string; power: string; current_turn: number; status: string }
type AllGame = { id: number; map_name: string; current_turn: number; status: string; player_count: number }

export default function GameList() {
  const navigate = useNavigate()
  const [myGames, setMyGames] = useState<Game[]>([])
  const [allGames, setAllGames] = useState<AllGame[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const load = () => {
    Promise.all([
      apiJson<{ games: Game[] }>('/users/me/games'),
      apiJson<{ games: AllGame[] }>('/games'),
    ])
      .then(([me, all]) => {
        setMyGames(me.games || [])
        setAllGames(all.games || [])
        setError('')
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleCreateGame() {
    setCreating(true)
    setError('')
    try {
      const res = await apiJson<{ game_id: string }>('/games/create', {
        method: 'POST',
        body: JSON.stringify({ map_name: 'standard' }),
      })
      toast.success('Game created')
      navigate(`/games/${res.game_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <div className="p-5">Loading...</div>

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Games</h1>
      <p className="mb-4">
        <Link to="/" className="text-primary underline underline-offset-2">Home</Link>
      </p>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="mb-6">
        <Button onClick={handleCreateGame} disabled={creating}>
          {creating ? 'Creating...' : 'Create new game'}
        </Button>
      </div>
      <h2 className="text-lg font-medium mb-2">My games</h2>
      {myGames.length === 0 ? (
        <p className="text-muted-foreground mb-6">You are not in any games.</p>
      ) : (
        <ul className="list-none p-0 space-y-2 mb-6">
          {myGames.map((g) => (
            <li key={g.game_id}>
              <Card className="hover:bg-muted/50 transition-colors">
                <CardHeader className="py-2">
                  <CardTitle className="text-sm font-medium">
                    <Link to={`/games/${g.game_id}`} className="text-primary underline underline-offset-2">
                      Game {g.game_id} — {g.power} — turn {g.current_turn}
                    </Link>
                  </CardTitle>
                </CardHeader>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <h2 className="text-lg font-medium mb-2">All games</h2>
      <ul className="list-none p-0 space-y-2">
        {allGames.map((g) => (
          <li key={g.id}>
            <Card className="hover:bg-muted/50 transition-colors">
              <CardHeader className="py-2">
                <CardTitle className="text-sm font-medium">
                  <Link to={`/games/${g.id}`} className="text-primary underline underline-offset-2">
                    Game {g.id} — {g.map_name} — {g.player_count}/7 — turn {g.current_turn}
                  </Link>
                </CardTitle>
              </CardHeader>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  )
}
