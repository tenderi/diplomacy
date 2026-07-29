import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { apiJson, apiFetch, API_BASE, ApiError } from '@/api/client'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
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
/** A unit as returned by the new GameState-native API view. */
type NewUnit = { kind: 'A' | 'F'; power: string; location: string }
type DislodgedOut = { unit: NewUnit; attacker_origin: string | null; retreats: string[] }
/**
 * The GameState-native view returned by GET /games/{id}/state (see GameService.view).
 * `phase` is a code like "S1901M"; `phase_type` drives the order UI.
 */
type GameState = {
  game_id: string
  map_name: string
  phase: string
  year: number
  season: string
  phase_type: 'MOVEMENT' | 'RETREAT' | 'ADJUSTMENT'
  status: 'ACTIVE' | 'COMPLETED'
  units: NewUnit[]
  units_by_power: Record<string, NewUnit[]>
  ownership: Record<string, string>
  supply_centers: Record<string, string>
  dislodged: DislodgedOut[]
  contested: string[]
  players: Record<string, { user_id: number | null; is_active: boolean }>
  orders: Record<string, string[]>
}
type Message = { id?: number; sender_user_id?: number; recipient_power?: string; text?: string; is_broadcast?: boolean }
/**
 * GET /games/{id}/draw_vote_status response (see GameService.get_draw_votes).
 * `required` is every surviving power that still has a unit; `votes` is who among
 * them has voted yes so far. A draw is not the same as a concede -- a concede
 * removes one power's units but leaves the rest playing on, while a draw (reached
 * when `votes` covers all of `required`) ends the game immediately.
 */
type DrawVoteStatus = {
  phase: string
  game_status: string
  required: string[]
  votes: string[]
  missing: string[]
  quorum_reached: boolean
}
/**
 * GET /games/{id}/orders_status response (see GameService.orders_status). Powers
 * with no units this phase are never "missing" -- there's nothing for them to order.
 */
type OrdersStatus = {
  phase: string
  active_powers: string[]
  submitted: string[]
  missing: string[]
}
/** Adjustment-phase summary from the legal-orders view: how many build/disband slots. */
type AdjustmentInfo = { delta: number; action: 'build' | 'disband' | 'none'; slots: number }
/**
 * Response shape of GET /games/{id}/legal_orders/{power} (see server.legal_orders).
 * `orders_by_unit` keys are exactly `${kind} ${location}` (coast included); every string in
 * a bucket either starts with that key (hold/move/support/convoy/retreat) or ends with it
 * (verb-first build/disband, e.g. "D A PAR", "BUILD F BRE") — callers must not assume a
 * prefix match and should just use the bucket the backend already built. `WAIVE` has no
 * unit and appears only in the flat `orders` list. `adjustment` is present only in an
 * ADJUSTMENT phase.
 */
type LegalOrdersView = {
  phase: string
  phase_type: 'MOVEMENT' | 'RETREAT' | 'ADJUSTMENT'
  power: string
  units: { kind: 'A' | 'F'; location: string; province: string; coast: string | null }[]
  orders_by_unit: Record<string, string[]>
  orders: string[]
  adjustment?: AdjustmentInfo
}

/** Human phase label used by the order-entry UI and legal-order grouping. */
const PHASE_LABEL: Record<GameState['phase_type'], string> = {
  MOVEMENT: 'Movement',
  RETREAT: 'Retreat',
  ADJUSTMENT: 'Adjustment',
}

/** Badge color per phase type so the current phase reads at a glance, not as a muted aside. */
const PHASE_BADGE_CLASS: Record<GameState['phase_type'], string> = {
  MOVEMENT: 'bg-primary/10 text-primary',
  RETREAT: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
  ADJUSTMENT: 'bg-violet-500/15 text-violet-700 dark:text-violet-400',
}

/** Split a location string ("PAR" or "SPA/SC") into province and optional coast. */
function splitLocation(loc: string): { province: string; coast?: string } {
  const [province, coast] = loc.split('/')
  return coast ? { province, coast } : { province }
}

/** Adapt a new-view unit into the internal UnitOut shape the order UI consumes. */
function toUnitOut(u: NewUnit, isDislodged = false): UnitOut {
  const { province, coast } = splitLocation(u.location)
  return { unit_type: u.kind, province, coast, is_dislodged: isDislodged }
}

/** Unit id matching the backend's `orders_by_unit` keys: `${kind} ${location}`, coast included. */
function unitKey(u: UnitOut): string {
  return `${u.unit_type} ${u.province}${u.coast ? `/${u.coast}` : ''}`
}

/** Render a submission/order deadline as a short relative countdown. */
function formatDeadline(iso: string | null, now: number): string {
  if (!iso) return 'No deadline set for this phase.'
  const target = new Date(iso).getTime()
  if (Number.isNaN(target)) return 'No deadline set for this phase.'
  const ms = target - now
  if (ms <= 0) return 'Deadline has passed — waiting for the turn to be processed.'
  const totalMinutes = Math.round(ms / 60000)
  const days = Math.floor(totalMinutes / 1440)
  const hours = Math.floor((totalMinutes % 1440) / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (days > 0 || hours > 0) parts.push(`${hours}h`)
  parts.push(`${minutes}m`)
  return `${parts.join(' ')} left this phase`
}

/** A 409 StaleGameError carries a raw backend string (see game_repo.py) not meant for
 * display; translate it and any other action error into something a player can act on. */
function describeActionError(e: unknown, fallback: string): string {
  if (e instanceof ApiError && e.status === 409) {
    return 'Someone else updated this game a moment ago. The latest state has been reloaded — please check before trying again.'
  }
  return e instanceof Error ? e.message : fallback
}

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
          const unitId = unitKey(unit)
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
            <li
              key={unitId}
              className="grid grid-cols-1 items-start gap-2 border-b border-border pb-3 sm:grid-cols-[5rem_8rem_1fr] sm:items-center"
            >
              <span className="font-medium">{unitId}</span>
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
                <SelectTrigger className="w-full" aria-label={`Order type for ${unitId}`}>
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
                  <SelectTrigger className="w-full" aria-label={`Target for ${unitId} order`}>
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
  adjustment,
  orders,
  buildOrderSlots,
  setBuildOrderSlots,
  loading,
  onSubmit,
  submitting,
}: {
  adjustment?: AdjustmentInfo
  orders: string[]
  buildOrderSlots: string[]
  setBuildOrderSlots: React.Dispatch<React.SetStateAction<string[]>>
  loading: boolean
  onSubmit: () => void
  submitting: boolean
}) {
  const grouped = groupLegalOrdersByType(orders)
  const options: ParsedLegalOrder[] = [...grouped.build, ...grouped.destroy, ...grouped.waive]
  const slots = Array.from({ length: adjustment?.slots ?? 0 }, (_, i) => i)
  return (
    <>
      <p className="text-sm text-muted-foreground mb-2">
        {adjustment?.action === 'build'
          ? 'Build: select one order per slot, or waive.'
          : adjustment?.action === 'disband'
            ? 'Disband: select a unit to remove per slot.'
            : 'No builds or disbands this turn.'}
      </p>
      {loading ? (
        <p className="text-sm text-muted-foreground mb-2">Loading options…</p>
      ) : null}
      <ul className="space-y-3 mb-4">
        {slots.map((i) => (
          <li
            key={i}
            className="grid grid-cols-1 items-start gap-2 border-b border-border pb-3 sm:grid-cols-[5rem_1fr] sm:items-center"
          >
            <span className="font-medium">Slot {i + 1}</span>
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
              <SelectTrigger className="w-full" aria-label={`Build or destroy order for slot ${i + 1}`}>
                <SelectValue placeholder="Build / Destroy" />
              </SelectTrigger>
              <SelectContent>
                {options.map((opt) => (
                  <SelectItem key={opt.fullOrder} value={opt.fullOrder}>
                    {opt.targetLabel}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </li>
        ))}
      </ul>
      <Button onClick={onSubmit} disabled={submitting || slots.length === 0}>
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
  /** Single GET /games/{id}/legal_orders/{power} response for the current phase. */
  const [legalOrders, setLegalOrders] = useState<LegalOrdersView | null>(null)
  const [legalOrdersLoading, setLegalOrdersLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [messageText, setMessageText] = useState('')
  const [messageRecipient, setMessageRecipient] = useState('')
  const [broadcast, setBroadcast] = useState(false)
  const [sendingMsg, setSendingMsg] = useState(false)
  const [drawStatus, setDrawStatus] = useState<DrawVoteStatus | null>(null)
  const [votingDraw, setVotingDraw] = useState(false)
  const [ordersStatus, setOrdersStatus] = useState<OrdersStatus | null>(null)
  const [deadlineIso, setDeadlineIso] = useState<string | null>(null)
  const [leaving, setLeaving] = useState(false)
  /** Ticks every 30s so the deadline countdown doesn't go stale while the tab sits open. */
  const [now, setNow] = useState(() => Date.now())

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
    const id = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!gameId) return
    setMapUrl(`${API_BASE}/games/${gameId}/map?t=${Date.now()}`)
  }, [gameId, state?.phase])

  useEffect(() => {
    if (!gameId || !user) return
    apiJson<{ messages?: Message[] }>(`/games/${gameId}/messages`)
      .then((d) => setMessages(d.messages || []))
      .catch(() => {})
  }, [gameId, user, state?.phase])

  useEffect(() => {
    if (!gameId || !myPower || !state || state.status !== 'ACTIVE') {
      setDrawStatus(null)
      return
    }
    apiJson<DrawVoteStatus>(`/games/${gameId}/draw_vote_status`)
      .then(setDrawStatus)
      .catch(() => setDrawStatus(null))
  }, [gameId, myPower, state?.status, state?.phase])

  // orders_status and deadline are unauthenticated status reads (same as draw_vote_status) --
  // fetch them for every viewer, not just the logged-in power, so anyone watching the game
  // can see who's still expected to submit and how long is left.
  useEffect(() => {
    if (!gameId || !state || state.status !== 'ACTIVE') {
      setOrdersStatus(null)
      setDeadlineIso(null)
      return
    }
    apiJson<OrdersStatus>(`/games/${gameId}/orders_status`)
      .then(setOrdersStatus)
      .catch(() => setOrdersStatus(null))
    apiJson<{ deadline: string | null }>(`/games/${gameId}/deadline`)
      .then((d) => setDeadlineIso(d.deadline ?? null))
      .catch(() => setDeadlineIso(null))
  }, [gameId, state?.status, state?.phase])

  // Depends on state.phase (not just gameId/myPower) so that: (a) a phase change refetches
  // and resets selections instead of letting a previous phase's picks survive into the new
  // one, and (b) reloading mid-phase restores whatever was already submitted -- including
  // Adjustment build/disband slots, which otherwise only ever came from local UI state and
  // looked "lost" on refresh even though the server still had them.
  useEffect(() => {
    if (!gameId || !myPower || !state) return
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
        setBuildOrderSlots(state.phase_type === 'ADJUSTMENT' ? orders : [])
      })
      .catch(() => {})
  }, [gameId, myPower, state?.phase])

  const phase = state ? PHASE_LABEL[state.phase_type] : ''
  const seasonLabel = state ? state.season.charAt(0) + state.season.slice(1).toLowerCase() : ''
  const myUnits: UnitOut[] =
    state && myPower
      ? [
          ...(state.units_by_power[myPower] ?? []).map((u) => toUnitOut(u)),
          ...state.dislodged
            .filter((d) => d.unit.power === myPower)
            .map((d) => toUnitOut(d.unit, true)),
        ]
      : []

  useEffect(() => {
    if (!gameId || !myPower || !state || useOrdersFallback) {
      setLegalOrders(null)
      return
    }
    setLegalOrdersLoading(true)
    const path = `/games/${gameId}/legal_orders/${encodeURIComponent(myPower)}`
    apiFetch(path)
      .then(async (res) => {
        if (res.status === 404) {
          setUseOrdersFallback(true)
          setLegalOrders(null)
          return
        }
        if (!res.ok) {
          setLegalOrders(null)
          return
        }
        setLegalOrders((await res.json()) as LegalOrdersView)
      })
      .catch(() => setLegalOrders(null))
      .finally(() => setLegalOrdersLoading(false))
  }, [gameId, myPower, state?.phase_type, state?.phase, useOrdersFallback])

  /** Per-unit legal orders derived from `legalOrders.orders_by_unit`: unitId -> { orders, grouped }. */
  const legalOrdersByUnit = useMemo(() => {
    const next: Record<string, { orders: string[]; grouped: GroupedByType }> = {}
    if (legalOrders) {
      for (const [key, orders] of Object.entries(legalOrders.orders_by_unit)) {
        next[key] = { orders, grouped: groupLegalOrdersByType(orders) }
      }
    }
    return next
  }, [legalOrders])

  const iHaveSubmitted = !!(myPower && ordersStatus?.submitted.includes(myPower))

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
      setError(describeActionError(e, 'Join failed'))
    } finally {
      setJoining(false)
    }
  }

  async function handleSubmitOrders() {
    if (!gameId || !myPower) return
    const orders: string[] = useOrdersFallback
      ? ordersFallbackText.split('\n').map((s) => s.trim()).filter(Boolean)
      : (() => {
          if (state?.phase_type === 'ADJUSTMENT') {
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
      setError(describeActionError(e, 'Submit orders failed'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleProcessTurn() {
    if (!gameId || !myPower) return
    setProcessing(true)
    setError('')
    try {
      await apiJson(`/games/${gameId}/process_turn`, { method: 'POST' })
      toast.success('Turn processed')
      load()
    } catch (e) {
      // `load()` clears `error` as its first step, so on a 409 it must run
      // *before* the friendly message is set, not after -- otherwise the
      // reload silently wipes the message we just showed the user.
      if (e instanceof ApiError && e.status === 409) load()
      setError(describeActionError(e, 'Process turn failed'))
    } finally {
      setProcessing(false)
    }
  }

  /** Cast (`vote: true`) or withdraw (`vote: false`) this power's draw vote.
   * Distinct from a concede: a draw only ends the game once every surviving
   * power has voted yes -- it never removes anyone's units on its own. */
  async function handleDrawVote(vote: boolean) {
    if (!gameId || !myPower) return
    setVotingDraw(true)
    setError('')
    try {
      const result = await apiJson<{ quorum_reached: boolean; winners?: string[] }>(
        `/games/${gameId}/draw_vote`,
        {
          method: 'POST',
          body: JSON.stringify({ power: myPower, vote }),
        }
      )
      if (result.quorum_reached) {
        toast.success('Draw vote reached quorum — the game has ended in a draw.')
        setDrawStatus(null)
      } else {
        toast.success(vote ? 'Draw vote cast' : 'Draw vote withdrawn')
        const ds = await apiJson<DrawVoteStatus>(`/games/${gameId}/draw_vote_status`)
        setDrawStatus(ds)
      }
      load()
    } catch (e) {
      // See handleProcessTurn: load() must run before setError on a 409, since
      // load() itself clears `error` first.
      if (e instanceof ApiError && e.status === 409) load()
      setError(describeActionError(e, 'Draw vote failed'))
    } finally {
      setVotingDraw(false)
    }
  }

  /** Unassign this user from `myPower`; units stay on the board and the slot becomes
   * open for a replacement. Does not end the game or touch anyone else's units. */
  async function handleQuit() {
    if (!gameId || !myPower) return
    setLeaving(true)
    setError('')
    try {
      await apiJson(`/games/${gameId}/quit`, {
        method: 'POST',
        body: JSON.stringify({ power: myPower }),
      })
      toast.success(`You have quit as ${myPower}`)
      load()
    } catch (e) {
      setError(describeActionError(e, 'Quit failed'))
    } finally {
      setLeaving(false)
    }
  }

  /** Voluntarily leave the game as `myPower`: removes all its units immediately.
   * Unlike a draw, the other six powers keep playing -- this never ends the game. */
  async function handleConcede() {
    if (!gameId || !myPower) return
    setLeaving(true)
    setError('')
    try {
      await apiJson(`/games/${gameId}/concede`, {
        method: 'POST',
        body: JSON.stringify({ power: myPower }),
      })
      toast.success(`${myPower} has conceded`)
      load()
    } catch (e) {
      setError(describeActionError(e, 'Concede failed'))
    } finally {
      setLeaving(false)
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
      setError(describeActionError(e, 'Send failed'))
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

      <div className="mb-4">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h1 className="text-2xl font-semibold">Game {gameId}</h1>
          <span
            className={cn(
              'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
              PHASE_BADGE_CLASS[state.phase_type]
            )}
          >
            {phase}
          </span>
          {state.status === 'COMPLETED' && (
            <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-semibold text-muted-foreground">
              Game over
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {seasonLabel} {state.year} · {state.phase}
        </p>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {state.status === 'ACTIVE' && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Turn status</CardTitle>
            <CardDescription>{formatDeadline(deadlineIso, now)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {myPower && (
              <p
                className={cn(
                  'text-sm font-medium',
                  iHaveSubmitted
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-amber-600 dark:text-amber-400'
                )}
              >
                {iHaveSubmitted
                  ? `Your orders are in for ${myPower}.`
                  : `You still need to submit orders for ${myPower}.`}
              </p>
            )}
            {ordersStatus && (
              <p className="text-sm text-muted-foreground">
                {ordersStatus.submitted.length}/{ordersStatus.active_powers.length} powers have
                submitted orders this phase
                {ordersStatus.missing.length > 0
                  ? ` — waiting on ${ordersStatus.missing.join(', ')}.`
                  : '.'}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <section className="mb-6">
        <h2 className="text-lg font-medium mb-2">Players</h2>
        <ul className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {POWERS.map((p) => {
            const pl = players.find((x) => x.power === p)
            const label = pl?.user_id ? pl.full_name || `Player #${pl.user_id}` : 'Open'
            return (
              <li
                key={p}
                className="flex items-center justify-between border-b border-border/50 py-1"
              >
                <span className="font-medium">
                  {p}
                  {p === myPower ? ' (you)' : ''}
                </span>
                <span className={cn('text-muted-foreground', !pl?.user_id && 'italic')}>
                  {label}
                </span>
              </li>
            )
          })}
        </ul>
      </section>

      {mapUrl && (
        <div className="mb-6">
          <img src={mapUrl} alt="Game map" className="max-w-full h-auto" />
        </div>
      )}

      {!myPower && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Join game</h2>
          {availablePowers.length > 0 ? (
            <>
              <p className="text-sm text-muted-foreground mb-2">
                {takenPowers.size} / {POWERS.length} powers claimed
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={joinPower}
                  onChange={(e) => setJoinPower(e.target.value)}
                  aria-label="Power to join as"
                  className={cn(
                    'h-8 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
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
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              This game is full — all seven powers are claimed. You can still follow its
              progress here.
            </p>
          )}
        </section>
      )}

      {myPower && (
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
            ) : phase === 'Adjustment' ? (
              <BuildOrdersSection
                adjustment={legalOrders?.adjustment}
                orders={legalOrders?.orders ?? []}
                buildOrderSlots={buildOrderSlots}
                setBuildOrderSlots={setBuildOrderSlots}
                loading={legalOrdersLoading}
                onSubmit={handleSubmitOrders}
                submitting={submitting}
              />
            ) : (
              <UnitOrdersSection
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

      {myPower && state.status === 'ACTIVE' && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Draw vote</h2>
          {drawStatus ? (
            <>
              <p className="text-sm text-muted-foreground mb-2">
                {drawStatus.votes.length}/{drawStatus.required.length} powers have voted for a draw
                {drawStatus.votes.length > 0 ? `: ${drawStatus.votes.join(', ')}` : ''}
              </p>
              {drawStatus.votes.includes(myPower) ? (
                <Button variant="outline" onClick={() => handleDrawVote(false)} disabled={votingDraw}>
                  {votingDraw ? 'Updating...' : 'Withdraw draw vote'}
                </Button>
              ) : (
                <Button onClick={() => handleDrawVote(true)} disabled={votingDraw}>
                  {votingDraw ? 'Voting...' : 'Vote for draw'}
                </Button>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Loading draw-vote status…</p>
          )}
        </section>
      )}

      {myPower && state.status === 'ACTIVE' && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Leave game</h2>
          <p className="text-sm text-muted-foreground mb-2">
            Quitting hands your slot back for someone else to take over — your units stay on
            the board. Conceding removes {myPower}&apos;s units immediately; the other powers
            keep playing either way.
          </p>
          <div className="flex flex-wrap gap-2">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" disabled={leaving}>Quit (step away)</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Quit as {myPower}?</AlertDialogTitle>
                  <AlertDialogDescription>
                    You&apos;ll be unassigned from {myPower} and its slot will be open for a
                    replacement. Your units stay on the board exactly as they are — this does
                    not end the game or remove anything.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleQuit}>Quit</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" disabled={leaving}>Concede</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Concede as {myPower}?</AlertDialogTitle>
                  <AlertDialogDescription>
                    All of {myPower}&apos;s units are removed from the board immediately. The
                    other six powers keep playing — this is not a draw and does not end the
                    game. This cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleConcede}>Concede</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </section>
      )}

      {myPower && state.status === 'ACTIVE' && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Process turn</h2>
          <p className="text-sm text-muted-foreground mb-2">
            Resolves every power&apos;s orders for {state.phase} right now and advances the
            game. Any unit without a submitted order will hold. This affects all seven powers
            and cannot be undone.
          </p>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" disabled={processing}>
                {processing ? 'Processing...' : 'Resolve orders and advance the game'}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Resolve {state.phase} for all powers?</AlertDialogTitle>
                <AlertDialogDescription>
                  This adjudicates every power&apos;s orders for this phase right now, not just
                  yours. Any power that hasn&apos;t submitted orders will have its units hold.
                  This cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleProcessTurn}>Process turn</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
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
              aria-label="Message recipient power"
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
