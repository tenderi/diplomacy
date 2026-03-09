import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { apiJson, API_BASE } from '@/api/client'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

const POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

type Player = { power: string; user_id: number | null; is_active: boolean; full_name?: string }
type GameState = {
  current_year?: number
  current_season?: string
  current_phase?: string
  current_turn?: number
  phase_code?: string
  powers?: Record<string, { power_name?: string; units?: unknown[]; orders_submitted?: boolean }>
  orders?: Record<string, unknown[]>
}
type Message = { id?: number; sender_user_id?: number; recipient_power?: string; text?: string; is_broadcast?: boolean }

export default function GameView() {
  const { gameId } = useParams<{ gameId: string }>()
  const { user } = useAuth()
  const [state, setState] = useState<GameState | null>(null)
  const [players, setPlayers] = useState<Player[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [mapUrl, setMapUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [joinPower, setJoinPower] = useState('')
  const [joining, setJoining] = useState(false)
  const [ordersText, setOrdersText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [messageText, setMessageText] = useState('')
  const [messageRecipient, setMessageRecipient] = useState('')
  const [broadcast, setBroadcast] = useState(false)
  const [sendingMsg, setSendingMsg] = useState(false)

  const load = useCallback(() => {
    if (!gameId) return
    setLoading(true)
    setError('')
    Promise.all([
      apiJson<GameState>(`/games/${gameId}/state`),
      apiJson<Player[]>(`/games/${gameId}/players`),
    ])
      .then(([s, p]) => {
        setState(s)
        setPlayers(Array.isArray(p) ? p : [])
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [gameId])

  const myPower = user ? players.find((p) => p.user_id === user.id)?.power : null
  const takenPowers = new Set(players.filter((p) => p.user_id).map((p) => p.power))
  const availablePowers = POWERS.filter((p) => !takenPowers.has(p))

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!gameId) return
    setMapUrl(`${API_BASE}/games/${gameId}/map?t=${Date.now()}`)
  }, [gameId])

  useEffect(() => {
    if (!gameId || !user) return
    apiJson<{ messages?: Message[] }>(`/games/${gameId}/messages`)
      .then((d) => setMessages(d.messages || []))
      .catch(() => {})
  }, [gameId, user, state?.current_turn])

  useEffect(() => {
    if (!gameId || !myPower) return
    apiJson<{ orders?: string[] }>(`/games/${gameId}/orders/${myPower}`)
      .then((d) => setOrdersText((d.orders || []).join('\n')))
      .catch(() => {})
  }, [gameId, myPower])

  async function handleJoin() {
    if (!gameId || !joinPower) return
    setJoining(true)
    setError('')
    try {
      await apiJson(`/games/${gameId}/join`, {
        method: 'POST',
        body: JSON.stringify({ game_id: parseInt(gameId, 10), power: joinPower }),
      })
      setJoinPower('')
      load()
      setMapUrl(`${API_BASE}/games/${gameId}/map?t=${Date.now()}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Join failed')
    } finally {
      setJoining(false)
    }
  }

  async function handleSubmitOrders() {
    if (!gameId || !myPower) return
    const orders = ordersText.split('\n').map((s) => s.trim()).filter(Boolean)
    if (orders.length === 0) return
    setSubmitting(true)
    setError('')
    try {
      await apiJson('/games/set_orders', {
        method: 'POST',
        body: JSON.stringify({ game_id: gameId, power: myPower, orders }),
      })
      toast.success('Orders submitted')
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submit orders failed')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleProcessTurn() {
    if (!gameId) return
    setProcessing(true)
    setError('')
    try {
      await apiJson(`/games/${gameId}/process_turn`, { method: 'POST' })
      toast.success('Turn processed')
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Process turn failed')
    } finally {
      setProcessing(false)
    }
  }

  async function handleSendMessage() {
    if (!gameId || !messageText.trim()) return
    setSendingMsg(true)
    setError('')
    try {
      if (broadcast) {
        await apiJson(`/games/${gameId}/broadcast`, {
          method: 'POST',
          body: JSON.stringify({ text: messageText.trim() }),
        })
      } else {
        if (!messageRecipient) return
        await apiJson(`/games/${gameId}/message`, {
          method: 'POST',
          body: JSON.stringify({ recipient_power: messageRecipient, text: messageText.trim() }),
        })
      }
      setMessageText('')
      toast.success('Message sent')
      const res = await apiJson<{ messages?: Message[] }>(`/games/${gameId}/messages`)
      setMessages(res.messages || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Send failed')
    } finally {
      setSendingMsg(false)
    }
  }

  if (loading && !error) return <div className="p-5">Loading...</div>
  if (error && !state) {
    return (
      <div className="max-w-xl mx-auto">
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <p><Link to="/games" className="text-primary underline underline-offset-2">Back to games</Link></p>
      </div>
    )
  }
  if (!state) return <div className="p-5">Loading...</div>

  return (
    <div className="max-w-4xl mx-auto">
      <p className="mb-4">
        <Link to="/games" className="text-primary underline underline-offset-2">Back to games</Link>
      </p>
      <h1 className="text-2xl font-semibold mb-2">Game {gameId}</h1>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <p className="text-muted-foreground mb-4">
        {String(state.current_year)} {String(state.current_season)} {String(state.current_phase)} — Turn {String(state.current_turn)}
      </p>
      {mapUrl && (
        <div className="mb-6">
          <img src={mapUrl} alt="Game map" className="max-w-full h-auto" />
        </div>
      )}

      {!myPower && availablePowers.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Join game</h2>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={joinPower}
              onChange={(e) => setJoinPower(e.target.value)}
              className={cn(
                "h-8 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              )}
            >
              <option value="">Select power</option>
              {availablePowers.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <Button onClick={handleJoin} disabled={!joinPower || joining}>
              {joining ? 'Joining...' : 'Join'}
            </Button>
          </div>
        </section>
      )}

      {myPower && (
        <>
          <p className="font-medium mb-4">Your power: {myPower}</p>
          <section className="mb-6">
            <h2 className="text-lg font-medium mb-2">Orders</h2>
            <p className="text-sm text-muted-foreground mb-2">One order per line (e.g. A PAR - BUR, F LON H)</p>
            <Textarea
              value={ordersText}
              onChange={(e) => setOrdersText(e.target.value)}
              rows={4}
              className="max-w-md mb-2"
              placeholder="A PAR - BUR&#10;F LON H"
            />
            <Button onClick={handleSubmitOrders} disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit orders'}
            </Button>
          </section>
        </>
      )}

      <section className="mb-6">
        <Button onClick={handleProcessTurn} disabled={processing}>
          {processing ? 'Processing...' : 'Process turn'}
        </Button>
      </section>

      <section className="mb-6">
        <h2 className="text-lg font-medium mb-2">Messages</h2>
        <ul className="list-none p-2 max-h-48 overflow-auto border border-border rounded-lg space-y-1">
          {messages.length === 0 && <li className="text-muted-foreground text-sm">No messages yet.</li>}
          {messages.map((m, i) => (
            <li key={m.id ?? i} className="text-sm">
              {m.recipient_power ? `To ${m.recipient_power}: ` : '(Broadcast) '}{m.text}
            </li>
          ))}
        </ul>
        <div className="mt-2 space-y-2">
          <Label className="flex items-center gap-2">
            <input type="checkbox" checked={broadcast} onChange={(e) => setBroadcast(e.target.checked)} />
            Broadcast to all
          </Label>
          {!broadcast && (
            <select
              value={messageRecipient}
              onChange={(e) => setMessageRecipient(e.target.value)}
              className={cn(
                "block h-8 w-full max-w-xs rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              )}
            >
              <option value="">To power...</option>
              {POWERS.filter((p) => p !== myPower).map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          )}
          <Textarea
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            rows={2}
            className="max-w-md"
            placeholder="Type a message..."
          />
          <Button
            onClick={handleSendMessage}
            disabled={!messageText.trim() || sendingMsg || (!broadcast && !messageRecipient)}
          >
            {sendingMsg ? 'Sending...' : 'Send'}
          </Button>
        </div>
      </section>
    </div>
  )
}
