import { TAP_LINK, TAP_ROW } from '@/lib/touch'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'

type Game = { game_id: number; map_name: string; power: string; current_turn: number; phase_code?: string | null; status: string }
type AllGame = {
  id: number
  map_name: string
  current_turn: number
  status: string
  player_count: number
  max_players?: number
  private?: boolean
  anonymous?: boolean
  random_powers?: boolean
  phase_code?: string | null
}

const SEASONS: Record<string, string> = { S: 'Spring', F: 'Fall', W: 'Winter' }

/** "S1901M" -> "Spring 1901"; falls back to the turn number when the code is unknown. */
function when(code: string | null | undefined, turn: number): string {
  const m = code ? /^([SFW])(\d{4})[MRA]$/.exec(code) : null
  return m ? `${SEASONS[m[1]]} ${m[2]}` : `turn ${turn}`
}

const POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

/** The creator's own seat, which creating a game takes (DV4c). */
type Seat = { status: 'ok' | 'already_joined' | 'not_seated'; power: string | null; reason: string | null }

export default function GameList() {
  const navigate = useNavigate()
  const [myGames, setMyGames] = useState<Game[]>([])
  const [allGames, setAllGames] = useState<AllGame[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  // Powers to leave to civil disorder from the start (W9) -- for tables of 3-6.
  const [dummies, setDummies] = useState<string[]>([])
  // W10: process each turn as soon as all orders are in.
  const [autoProcess, setAutoProcess] = useState(false)
  // W8: optional join password; blank = open game.
  const [joinPassword, setJoinPassword] = useState('')
  // Anonymous: players are known only by their power. Fixed once the game exists.
  const [anonymous, setAnonymous] = useState(false)
  // Random powers: joiners don't choose; the server deals each an open power.
  const [randomPowers, setRandomPowers] = useState(false)
  // The power the creator plays: creating the game seats them in it (DV4c).
  // Not asked in a random-powers game, where they are dealt one.
  const [myPower, setMyPower] = useState('')
  const needsPower = !randomPowers && !myPower

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
      const res = await apiJson<{ game_id: string; seat?: Seat | null }>('/games/create', {
        method: 'POST',
        body: JSON.stringify({
          map_name: 'standard',
          dummy_powers: dummies,
          auto_process: autoProcess,
          anonymous,
          random_powers: randomPowers,
          ...(randomPowers ? {} : { power: myPower }),
          ...(joinPassword ? { join_password: joinPassword } : {}),
        }),
      })
      const seat = res.seat
      if (seat && seat.status !== 'not_seated') toast.success(`Game created: you play ${seat.power}`)
      else toast.warning(`Game created, but you weren't seated: ${seat?.reason ?? 'no reason given'}`)
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
        <Link to="/" className={TAP_LINK}>Home</Link>
      </p>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
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
                    <Link to={`/games/${g.game_id}`} className={TAP_LINK}>
                      Game {g.game_id} — {g.power} — {when(g.phase_code, g.current_turn)}
                    </Link>
                  </CardTitle>
                </CardHeader>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <div className="mb-6 space-y-2">
        <h2 className="text-lg font-medium mb-2">Create a game</h2>
        <fieldset>
          <legend className="text-sm text-muted-foreground mb-1">
            Fewer than seven players? Leave these powers to civil disorder (they hold, and
            disband when they must):
          </legend>
          <div className="flex flex-wrap gap-x-4">
            {POWERS.map((p) => (
              <label key={p} className={`flex items-center gap-2 text-sm ${TAP_ROW}`}>
                <input
                  type="checkbox"
                  className="size-5 shrink-0"
                  checked={dummies.includes(p)}
                  disabled={!dummies.includes(p) && dummies.length >= POWERS.length - 1}
                  onChange={(e) => {
                    setDummies((d) => (e.target.checked ? [...d, p] : d.filter((x) => x !== p)))
                    if (e.target.checked && p === myPower) setMyPower('')
                  }}
                />
                {p}
              </label>
            ))}
          </div>
        </fieldset>
        <label className={`flex items-center gap-2 text-sm ${TAP_ROW}`}>
          <input type="checkbox" className="size-5 shrink-0" checked={autoProcess} onChange={(e) => setAutoProcess(e.target.checked)} />
          Process each turn as soon as all orders are in (players can ask to wait)
        </label>
        <label className={`flex items-center gap-2 text-sm ${TAP_ROW}`}>
          <input type="checkbox" className="size-5 shrink-0" checked={randomPowers} onChange={(e) => setRandomPowers(e.target.checked)} />
          Assign powers at random — players join without choosing one (can't be changed later)
        </label>
        {!randomPowers && (
          <label className={`flex flex-wrap items-center gap-2 text-sm ${TAP_ROW}`}>
            Your power (you join the game as it):
            <select
              value={myPower}
              onChange={(e) => setMyPower(e.target.value)}
              aria-label="Your power"
              className="h-10 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm"
            >
              <option value="">Choose...</option>
              {POWERS.filter((p) => !dummies.includes(p)).map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
        )}
        <fieldset>
          <legend className="text-sm text-muted-foreground mb-1">
            Player names (can't be changed once the game exists):
          </legend>
          <div className="flex flex-wrap gap-x-4">
            <label className={`flex items-center gap-2 text-sm ${TAP_ROW}`}>
              <input type="radio" className="size-5 shrink-0" name="naming" checked={!anonymous} onChange={() => setAnonymous(false)} />
              Public — nicknames are shown next to powers
            </label>
            <label className={`flex items-center gap-2 text-sm ${TAP_ROW}`}>
              <input type="radio" className="size-5 shrink-0" name="naming" checked={anonymous} onChange={() => setAnonymous(true)} />
              Anonymous — players are known only by their power
            </label>
          </div>
        </fieldset>
        <label className={`flex flex-wrap items-center gap-2 text-sm ${TAP_ROW}`}>
          Private game password (optional, 4–64 characters):
          <input
            type="password"
            value={joinPassword}
            onChange={(e) => setJoinPassword(e.target.value)}
            aria-label="Private game password"
            autoComplete="new-password"
            className="h-8 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm"
          />
        </label>
        {needsPower && (
          <p className="text-sm text-muted-foreground">Choose your power to create the game.</p>
        )}
        <Button onClick={handleCreateGame} disabled={creating || needsPower}>
          {creating ? 'Creating...' : 'Create new game'}
        </Button>
      </div>
      <h2 className="text-lg font-medium mb-2">All games</h2>
      {allGames.length === 0 && (
        <p className="text-sm text-muted-foreground">No games yet. Create one above.</p>
      )}
      <ul className="list-none p-0 space-y-2">
        {allGames.map((g) => (
          <li key={g.id}>
            <Card className="hover:bg-muted/50 transition-colors">
              <CardHeader className="py-2">
                <CardTitle className="text-sm font-medium">
                  <Link to={`/games/${g.id}`} className={TAP_LINK}>
                    {g.private ? '🔒 ' : ''}{g.anonymous ? '🕶️ ' : ''}{g.random_powers ? '🎲 ' : ''}Game {g.id} — {g.map_name} — {g.player_count}/{g.max_players ?? 7} — {when(g.phase_code, g.current_turn)}
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
