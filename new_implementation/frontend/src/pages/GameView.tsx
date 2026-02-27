import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiJson } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const API_BASE = import.meta.env.VITE_API_URL || ''
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

  const myPower = user ? players.find((p) => p.user_id === user.id)?.power : null
  const takenPowers = new Set(players.filter((p) => p.user_id).map((p) => p.power))
  const availablePowers = POWERS.filter((p) => !takenPowers.has(p))

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
      const res = await apiJson<{ messages?: Message[] }>(`/games/${gameId}/messages`)
      setMessages(res.messages || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Send failed')
    } finally {
      setSendingMsg(false)
    }
  }

  if (loading || !state) return <div style={{ padding: 20 }}>Loading...</div>

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
      <p><Link to="/games">Back to games</Link></p>
      <h1>Game {gameId}</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <p>
        {String(state.current_year)} {String(state.current_season)} {String(state.current_phase)} — Turn {String(state.current_turn)}
      </p>
      {mapUrl && (
        <div style={{ marginBottom: 16 }}>
          <img src={mapUrl} alt="Game map" style={{ maxWidth: '100%', height: 'auto' }} />
        </div>
      )}

      {!myPower && availablePowers.length > 0 && (
        <section style={{ marginBottom: 24 }}>
          <h2>Join game</h2>
          <select value={joinPower} onChange={(e) => setJoinPower(e.target.value)}>
            <option value="">Select power</option>
            {availablePowers.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <button type="button" onClick={handleJoin} disabled={!joinPower || joining} style={{ marginLeft: 8 }}>
            {joining ? 'Joining...' : 'Join'}
          </button>
        </section>
      )}

      {myPower && (
        <>
          <p><strong>Your power: {myPower}</strong></p>
          <section style={{ marginBottom: 24 }}>
            <h2>Orders</h2>
            <p>One order per line (e.g. A PAR - BUR, F LON H)</p>
            <textarea
              value={ordersText}
              onChange={(e) => setOrdersText(e.target.value)}
              rows={4}
              style={{ width: '100%', maxWidth: 400, display: 'block', marginBottom: 8 }}
              placeholder="A PAR - BUR&#10;F LON H"
            />
            <button type="button" onClick={handleSubmitOrders} disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit orders'}
            </button>
          </section>
        </>
      )}

      <section style={{ marginBottom: 24 }}>
        <button type="button" onClick={handleProcessTurn} disabled={processing}>
          {processing ? 'Processing...' : 'Process turn'}
        </button>
      </section>

      <section style={{ marginBottom: 24 }}>
        <h2>Messages</h2>
        <ul style={{ listStyle: 'none', padding: 0, maxHeight: 200, overflow: 'auto', border: '1px solid #ccc', padding: 8 }}>
          {messages.length === 0 && <li style={{ color: '#666' }}>No messages yet.</li>}
          {messages.map((m, i) => (
            <li key={m.id ?? i} style={{ marginBottom: 4 }}>
              {m.recipient_power ? `To ${m.recipient_power}: ` : '(Broadcast) '}{m.text}
            </li>
          ))}
        </ul>
        <label>
          <input type="checkbox" checked={broadcast} onChange={(e) => setBroadcast(e.target.checked)} />
          Broadcast to all
        </label>
        {!broadcast && (
          <select value={messageRecipient} onChange={(e) => setMessageRecipient(e.target.value)} style={{ display: 'block', marginTop: 4 }}>
            <option value="">To power...</option>
            {POWERS.filter((p) => p !== myPower).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        )}
        <textarea
          value={messageText}
          onChange={(e) => setMessageText(e.target.value)}
          rows={2}
          style={{ width: '100%', maxWidth: 400, display: 'block', marginTop: 4 }}
          placeholder="Type a message..."
        />
        <button type="button" onClick={handleSendMessage} disabled={!messageText.trim() || sendingMsg || (!broadcast && !messageRecipient)} style={{ marginTop: 4 }}>
          {sendingMsg ? 'Sending...' : 'Send'}
        </button>
      </section>
    </div>
  )
}
