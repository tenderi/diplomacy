import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { apiJson, apiFetch, API_BASE } from '@/api/client'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import {
  type OrderType,
  type ParsedLegalOrder,
  type GroupedByType,
  parseLegalOrder,
  groupLegalOrdersByType,
  getOrderTypesFromGrouped,
  getTargetOptionsForType,
  ORDER_TYPE_LABELS,
  extractUnitFromOrderString,
} from '@/lib/orderParsing'

const POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

type Player = { power: string; user_id: number | null; is_active: boolean; full_name?: string }
type UnitOut = { unit_type: string; province: string; coast?: string; is_dislodged?: boolean }
type GameState = {
  current_year?: number
  current_season?: string
  current_phase?: string
  current_turn?: number
  phase_code?: string
  powers?: Record<string, { power_name?: string; units?: UnitOut[]; orders_submitted?: boolean; controlled_supply_centers?: string[] }>
  orders?: Record<string, unknown[]>
}
type Message = { id?: number; sender_user_id?: number; recipient_power?: string; text?: string; is_broadcast?: boolean }

function UnitOrdersSection({
  phase,
  myUnits,
  orderByUnit,
  setOrderByUnit,
  legalOrdersByUnit,
  loading,
  onSubmit,
  submitting,
}: {
  gameId: string
  myPower: string
  phase: string
  myUnits: UnitOut[]
  orderByUnit: Record<string, string>
  setOrderByUnit: React.Dispatch<React.SetStateAction<Record<string, string>>>
  legalOrdersByUnit: Record<string, { orders: string[]; grouped: GroupedByType }>
  loading: boolean
  onSubmit: () => void
  submitting: boolean
}) {
  const unitsToShow = phase === 'Retreat' ? myUnits.filter((u) => u.is_dislodged) : myUnits
  return (
    <>
      <p className="text-sm text-muted-foreground mb-2">
        One row per unit. Choose order type, then target.
      </p>
      {loading ? (
        <p className="text-sm text-muted-foreground mb-2">Loading legal orders…</p>
      ) : null}
      <ul className="space-y-3 mb-4">
        {unitsToShow.map((unit) => {
          const unitId = `${unit.unit_type} ${unit.province}`
          const data = legalOrdersByUnit[unitId]
          const grouped = data?.grouped
          const currentOrder = orderByUnit[unitId]
          const parsedCurrent = currentOrder ? parseLegalOrder(currentOrder) : null
          const selectedOrderType: OrderType | '' = parsedCurrent?.type ?? ''
          const orderTypes = grouped ? getOrderTypesFromGrouped(grouped, phase) : []
          const targetOptions: ParsedLegalOrder[] = selectedOrderType
            ? getTargetOptionsForType(grouped!, selectedOrderType)
            : []
          const targetValue = parsedCurrent?.fullOrder ?? ''
          return (
            <li key={unitId} className="flex flex-wrap items-center gap-2 border-b border-border pb-2">
              <span className="font-medium min-w-[4rem]">{unitId}</span>
              <Select
                value={selectedOrderType || undefined}
                onValueChange={(t) => {
                  if (!t) return
                  const opts = getTargetOptionsForType(grouped!, t as OrderType)
                  const first = opts[0]
                  setOrderByUnit((prev) => ({
                    ...prev,
                    [unitId]: first?.fullOrder ?? '',
                  }))
                }}
                disabled={!grouped || loading}
              >
                <SelectTrigger className="w-[7rem]">
                  <SelectValue placeholder="Order type" />
                </SelectTrigger>
                <SelectContent>
                  {orderTypes.map((t) => (
                    <SelectItem key={t} value={t}>
                      {ORDER_TYPE_LABELS[t]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedOrderType && selectedOrderType !== 'hold' && (
                <Select
                  value={targetValue || undefined}
                  onValueChange={(fullOrder) => {
                    setOrderByUnit((prev) => ({ ...prev, [unitId]: fullOrder }))
                  }}
                  disabled={!grouped || loading}
                >
                  <SelectTrigger className="min-w-[10rem] max-w-xs">
                    <SelectValue placeholder="Target" />
                  </SelectTrigger>
                  <SelectContent>
                    {targetOptions.map((opt) => (
                      <SelectItem key={opt.fullOrder} value={opt.fullOrder}>
                        {opt.targetLabel}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {selectedOrderType === 'hold' && targetOptions.length > 0 && (
                <span className="text-muted-foreground text-sm">Hold</span>
              )}
            </li>
          )
        })}
      </ul>
      <Button onClick={onSubmit} disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit orders'}
      </Button>
    </>
  )
}

function BuildOrdersSection({
  myPower,
  powerState,
  legalOrdersByUnit,
  buildOrderSlots,
  setBuildOrderSlots,
  loading,
  onSubmit,
  submitting,
}: {
  gameId: string
  myPower: string
  powerState?: { units?: UnitOut[]; controlled_supply_centers?: string[] }
  legalOrdersByUnit: Record<string, { orders: string[]; grouped: GroupedByType }>
  buildOrderSlots: string[]
  setBuildOrderSlots: React.Dispatch<React.SetStateAction<string[]>>
  loading: boolean
  onSubmit: () => void
  submitting: boolean
}) {
  const buildData = legalOrdersByUnit['_build']
  const orders = buildData?.orders ?? []
  const unitCount = powerState?.units?.length ?? 0
  const scCount = powerState?.controlled_supply_centers?.length ?? 0
  const slotCount = scCount > unitCount ? scCount - unitCount : unitCount > scCount ? unitCount - scCount : 0
  const slots = Array.from({ length: Math.max(slotCount, buildOrderSlots.length, 1) }, (_, i) => i)
  return (
    <>
      <p className="text-sm text-muted-foreground mb-2">
        Build or destroy: select one order per slot.
      </p>
      {loading ? (
        <p className="text-sm text-muted-foreground mb-2">Loading options…</p>
      ) : null}
      <ul className="space-y-3 mb-4">
        {slots.map((i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 border-b border-border pb-2">
            <span className="font-medium min-w-[4rem]">Slot {i + 1}</span>
            <Select
              value={buildOrderSlots[i] ?? ''}
              onValueChange={(fullOrder) => {
                setBuildOrderSlots((prev) => {
                  const next = [...prev]
                  next[i] = fullOrder
                  return next
                })
              }}
              disabled={loading}
            >
              <SelectTrigger className="min-w-[12rem]">
                <SelectValue placeholder="Build / Destroy" />
              </SelectTrigger>
              <SelectContent>
                {orders.map((order) => (
                  <SelectItem key={order} value={order}>
                    {order.replace(new RegExp(`^${myPower}\\s+`, 'i'), '').trim()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </li>
        ))}
      </ul>
      <Button onClick={onSubmit} disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit orders'}
      </Button>
    </>
  )
}

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
  /** One order string per unit (unit id e.g. "A PAR"); used for Movement and Retreat. */
  const [orderByUnit, setOrderByUnit] = useState<Record<string, string>>({})
  /** Build/Adjustment phase: selected build or destroy order per slot. */
  const [buildOrderSlots, setBuildOrderSlots] = useState<string[]>([])
  /** When legal_orders API is unavailable (e.g. game not in memory), fall back to textarea. */
  const [ordersFallbackText, setOrdersFallbackText] = useState('')
  const [useOrdersFallback, setUseOrdersFallback] = useState(false)
  /** Per-unit legal orders from API: unitId -> { orders, grouped } */
  const [legalOrdersByUnit, setLegalOrdersByUnit] = useState<Record<string, { orders: string[]; grouped: GroupedByType }>>({})
  const [legalOrdersLoading, setLegalOrdersLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [starting, setStarting] = useState(false)
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
  }, [gameId, state?.current_phase, state?.phase_code])

  useEffect(() => {
    if (!gameId || !user) return
    apiJson<{ messages?: Message[] }>(`/games/${gameId}/messages`)
      .then((d) => setMessages(d.messages || []))
      .catch(() => {})
  }, [gameId, user, state?.current_turn])

  useEffect(() => {
    if (!gameId || !myPower) return
    apiJson<{ orders?: string[] }>(`/games/${gameId}/orders/${myPower}`)
      .then((d) => {
        const orders = d.orders || []
        const byUnit: Record<string, string> = {}
        for (const order of orders) {
          const unitId = extractUnitFromOrderString(order)
          if (unitId) byUnit[unitId] = order
        }
        setOrderByUnit(byUnit)
        setOrdersFallbackText(orders.join('\n'))
      })
      .catch(() => {})
  }, [gameId, myPower])

  const phase = state?.current_phase ?? ''
  const isPregame = phase === 'Pregame'
  const canStartGame = takenPowers.size >= 1
  const myUnits = (state?.powers && myPower ? state.powers[myPower]?.units : undefined) ?? []

  useEffect(() => {
    if (!gameId || !myPower || !state || useOrdersFallback) return
    const phase = state.current_phase ?? ''
    const isMovementOrRetreat = phase === 'Movement' || phase === 'Retreat'
    const isBuildPhase = phase === 'Builds' || phase === 'Adjustment'
    const unitsToFetch: { id: string; unit: UnitOut }[] = []
    if (isMovementOrRetreat) {
      for (const u of myUnits) {
        const id = `${u.unit_type} ${u.province}`
        if (phase === 'Retreat' && !u.is_dislodged) continue
        unitsToFetch.push({ id, unit: u })
      }
    }
    if (unitsToFetch.length === 0 && !isBuildPhase) {
      setLegalOrdersByUnit({})
      return
    }
    setLegalOrdersLoading(true)
    const toFetch = isBuildPhase
      ? [{ id: '_build', unit: myUnits[0] } as { id: string; unit: UnitOut }]
      : unitsToFetch
    if (toFetch.length === 0) {
      setLegalOrdersLoading(false)
      return
    }
    Promise.all(
      toFetch.map(async ({ id, unit }) => {
        const unitStr = `${unit.unit_type} ${unit.province}`
        const path = `/games/${gameId}/legal_orders/${encodeURIComponent(myPower)}/${encodeURIComponent(unitStr)}`
        try {
          const res = await apiFetch(path)
          if (res.status === 404) return { id, orders: [] as string[], is404: true }
          if (!res.ok) return { id, orders: [] as string[] }
          const data = (await res.json()) as { orders?: string[] }
          return { id, orders: data.orders ?? [] }
        } catch {
          return { id, orders: [] as string[] }
        }
      })
    )
      .then((results) => {
        const any404 = results.some((r) => 'is404' in r && r.is404)
        if (any404) setUseOrdersFallback(true)
        const next: Record<string, { orders: string[]; grouped: GroupedByType }> = {}
        for (const r of results) {
          next[r.id] = { orders: r.orders, grouped: groupLegalOrdersByType(r.orders) }
        }
        setLegalOrdersByUnit(next)
      })
      .finally(() => setLegalOrdersLoading(false))
  }, [gameId, myPower, state?.current_phase, state?.powers, useOrdersFallback])

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
    const orders: string[] = useOrdersFallback
      ? ordersFallbackText.split('\n').map((s) => s.trim()).filter(Boolean)
      : (() => {
          const phase = state?.current_phase ?? ''
          if (phase === 'Builds' || phase === 'Adjustment') {
            return buildOrderSlots.filter(Boolean)
          }
          return Object.values(orderByUnit).filter(Boolean)
        })()
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

  async function handleStartGame() {
    if (!gameId) return
    setStarting(true)
    setError('')
    try {
      await apiJson(`/games/${gameId}/start`, { method: 'POST' })
      toast.success('Game started')
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Start game failed')
    } finally {
      setStarting(false)
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
        {isPregame
          ? 'Phase 0 — Lobby (join one or more powers below; you can Start game with any number. Unjoined powers get default units and do not receive orders.)'
          : `${String(state.current_year)} ${String(state.current_season)} ${String(state.current_phase)} — Turn ${String(state.current_turn)}`}
      </p>
      {mapUrl && (
        <div className="mb-6">
          <img src={mapUrl} alt="Game map" className="max-w-full h-auto" />
        </div>
      )}

      {(isPregame || !myPower) && availablePowers.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Join game</h2>
          {isPregame && (
            <p className="text-sm text-muted-foreground mb-2">
              {takenPowers.size} / {POWERS.length} powers joined
            </p>
          )}
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

      {isPregame && myPower && (
        <p className="font-medium mb-4">Your power: {myPower}</p>
      )}

      {isPregame && canStartGame && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Ready to start</h2>
          <p className="text-sm text-muted-foreground mb-2">
            At least one power has joined. Start the game to enter the first order phase. Unjoined powers will have default units on the map but will not receive orders.
          </p>
          <Button onClick={handleStartGame} disabled={starting}>
            {starting ? 'Starting...' : 'Start game'}
          </Button>
        </section>
      )}

      {myPower && !isPregame && (
        <>
          <p className="font-medium mb-4">Your power: {myPower}</p>
          <section className="mb-6">
            <h2 className="text-lg font-medium mb-2">Orders</h2>
            {useOrdersFallback ? (
              <>
                <p className="text-sm text-muted-foreground mb-2">
                  Game state not in memory — enter orders as text (one per line, e.g. A PAR - BUR, F LON H).
                </p>
                <Textarea
                  value={ordersFallbackText}
                  onChange={(e) => setOrdersFallbackText(e.target.value)}
                  rows={4}
                  className="max-w-md mb-2"
                  placeholder="A PAR - BUR&#10;F LON H"
                />
                <div className="flex gap-2 items-center">
                  <Button onClick={handleSubmitOrders} disabled={submitting}>
                    {submitting ? 'Submitting...' : 'Submit orders'}
                  </Button>
                  <button
                    type="button"
                    className="text-sm text-muted-foreground underline"
                    onClick={() => setUseOrdersFallback(false)}
                  >
                    Try dropdowns again
                  </button>
                </div>
              </>
            ) : (phase === 'Builds' || phase === 'Adjustment') ? (
              <BuildOrdersSection
                gameId={gameId!}
                myPower={myPower}
                powerState={state.powers?.[myPower]}
                legalOrdersByUnit={legalOrdersByUnit}
                buildOrderSlots={buildOrderSlots}
                setBuildOrderSlots={setBuildOrderSlots}
                loading={legalOrdersLoading}
                onSubmit={handleSubmitOrders}
                submitting={submitting}
              />
            ) : (
              <UnitOrdersSection
                gameId={gameId!}
                myPower={myPower}
                phase={phase}
                myUnits={myUnits}
                orderByUnit={orderByUnit}
                setOrderByUnit={setOrderByUnit}
                legalOrdersByUnit={legalOrdersByUnit}
                loading={legalOrdersLoading}
                onSubmit={handleSubmitOrders}
                submitting={submitting}
              />
            )}
          </section>
        </>
      )}

      {!isPregame && (
        <section className="mb-6">
          <Button onClick={handleProcessTurn} disabled={processing}>
            {processing ? 'Processing...' : 'Process turn'}
          </Button>
        </section>
      )}

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
              {POWERS.filter((p) => p !== myPower && takenPowers.has(p)).map((p) => (
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
