/**
 * The sandbox: a scratch board on which the player orders every power, resolves the
 * phase and steps on through retreats and adjustments -- to see how the rules resolve
 * a position, or to play out what the neighbours might do.
 *
 * It starts from a game's current board (`/sandbox?game=<id>`) or from the opening
 * position (`/sandbox`). Nothing is stored anywhere: the server is stateless for the
 * sandbox (see `server/api/routes/sandbox.py`) and the board, the orders and the
 * history of resolved phases live only in this component, so leaving the page ends
 * the session.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch, apiJson } from '@/api/client'
import {
  provinceNamesFromResponse,
  type ProvinceInfo,
  type ProvinceNames,
} from '@/lib/provinceNames'
import { groupLegalOrdersByType, extractUnitFromOrderString, type GroupedByType } from '@/lib/orderParsing'
import { type OrderResultEntry } from '@/lib/resultText'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import MapViewer from '@/components/MapViewer'
import {
  POWERS,
  PHASE_BADGE_CLASS,
  PHASE_LABEL,
  type DislodgedOut,
  type LegalOrdersView,
  type NewUnit,
  type PhaseType,
  BuildOrdersSection,
  ResultList,
  UnitOrdersSection,
  toUnitOut,
} from '@/components/OrderEntry'

/** `GameService.sandbox_view`: the board, plus who has something to order this phase. */
export type SandboxView = {
  phase: string
  year: number
  season: string
  phase_type: PhaseType
  status: 'ACTIVE' | 'COMPLETED'
  winners: string[] | null
  units_by_power: Record<string, NewUnit[]>
  ownership: Record<string, string>
  dislodged: DislodgedOut[]
  powers_to_order: string[]
}

/** The serialized engine `GameState` (opaque here) and its view. The state is what
 * every sandbox request sends back: the server keeps nothing between requests. */
type Board = { state: Record<string, unknown>; view: SandboxView }

type OrderCheck = { order: string; ok: boolean; reason: string | null }

type AdjudicateResponse = Board & {
  order_results: Record<string, OrderCheck[]>
  resolution: { results: OrderResultEntry[] }
}

/** Orders being written for the current phase: per unit (movement, retreat) and per
 * adjustment slot, each keyed by power. */
type Draft = {
  byUnit: Record<string, Record<string, string>>
  slots: Record<string, string[]>
}

/** One resolved phase, kept so "Step back" can restore the board and its orders. */
type Turn = {
  before: Board
  draft: Draft
  orders: Record<string, string[]>
  results: OrderResultEntry[]
  refused: { power: string; order: string; reason: string }[]
}

type MapMode = 'board' | 'orders' | 'resolution'
const MAP_MODE_LABELS: Record<MapMode, string> = {
  board: 'Board',
  orders: 'Orders',
  resolution: 'Last resolution',
}

const EMPTY_DRAFT: Draft = { byUnit: {}, slots: {} }
const NO_ORDERS: Record<string, string[]> = {}

/** The orders to send: every non-empty pick, per power. */
function draftOrders(draft: Draft, phaseType: PhaseType): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const power of POWERS) {
    const orders =
      phaseType === 'ADJUSTMENT'
        ? (draft.slots[power] ?? []).filter(Boolean)
        : Object.values(draft.byUnit[power] ?? {}).filter(Boolean)
    if (orders.length > 0) out[power] = orders
  }
  return out
}

/** How many decisions `power` has this phase: units to order, units to retreat. */
function unitsToOrder(view: SandboxView, power: string): number {
  if (view.phase_type === 'RETREAT') return view.dislodged.filter((d) => d.unit.power === power).length
  return (view.units_by_power[power] ?? []).length
}

export default function Sandbox() {
  const [searchParams] = useSearchParams()
  const sourceGameId = searchParams.get('game')
  const [start, setStart] = useState<Board | null>(null)
  const [board, setBoard] = useState<Board | null>(null)
  const [history, setHistory] = useState<Turn[]>([])
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [power, setPower] = useState<string>(POWERS[0])
  const [legal, setLegal] = useState<Record<string, LegalOrdersView>>({})
  const [legalLoading, setLegalLoading] = useState(false)
  const [error, setError] = useState('')
  const [resolving, setResolving] = useState(false)
  const [mapMode, setMapMode] = useState<MapMode>('board')
  const [mapUrl, setMapUrl] = useState<string | null>(null)
  /** A render takes a moment; say so rather than leave the previous picture looking current. */
  const [mapLoading, setMapLoading] = useState(false)
  const [orderText, setOrderText] = useState('')
  const [provinceNames, setProvinceNames] = useState<ProvinceNames>({})
  const mapUrlRef = useRef<string | null>(null)

  const view = board?.view ?? null
  const lastTurn = history.length > 0 ? history[history.length - 1] : null
  const orders = useMemo(() => (view ? draftOrders(draft, view.phase_type) : NO_ORDERS), [draft, view])
  // Only the orders overlay depends on the picks; the other maps must not re-render on each.
  const mapOrders = mapMode === 'orders' ? orders : NO_ORDERS

  /** A new board: fresh orders, fresh legal-order menus, and a power that can act. */
  const enterBoard = useCallback((next: Board, nextDraft: Draft = EMPTY_DRAFT) => {
    setBoard(next)
    setDraft(nextDraft)
    setLegal({})
    setPower((current) =>
      next.view.powers_to_order.length === 0 || next.view.powers_to_order.includes(current)
        ? current
        : next.view.powers_to_order[0]
    )
  }, [])

  useEffect(() => {
    setError('')
    apiJson<Board>('/sandbox/start', {
      method: 'POST',
      body: JSON.stringify(sourceGameId ? { game_id: sourceGameId } : {}),
    })
      .then((b) => {
        const initial = { state: b.state, view: b.view }
        setStart(initial)
        setHistory([])
        setMapMode('board')
        enterBoard(initial)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not start the sandbox'))
  }, [sourceGameId, enterBoard])

  useEffect(() => {
    apiJson<{ provinces?: Record<string, ProvinceInfo> }>('/maps/standard/provinces')
      .then((body) => setProvinceNames(provinceNamesFromResponse(body)))
      .catch(() => setProvinceNames({}))
  }, [])

  // The selected power's legal orders, fetched once per phase.
  useEffect(() => {
    if (!board || legal[power] || board.view.status !== 'ACTIVE') return
    let cancelled = false
    setLegalLoading(true)
    apiJson<LegalOrdersView>('/sandbox/legal_orders', {
      method: 'POST',
      body: JSON.stringify({ state: board.state, power }),
    })
      .then((lo) => {
        if (!cancelled) setLegal((prev) => ({ ...prev, [power]: lo }))
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load legal orders')
      })
      .finally(() => {
        if (!cancelled) setLegalLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [board, power, legal])

  // The map is a POST (the board travels with the request), so it arrives as a blob.
  // Order picks re-render the orders overlay, debounced so a burst of picks is one render.
  useEffect(() => {
    if (!board) return
    const mode: MapMode = mapMode === 'resolution' && !lastTurn ? 'board' : mapMode
    const body =
      mode === 'resolution' && lastTurn
        ? { state: lastTurn.before.state, orders: lastTurn.orders, overlay: 'resolution' }
        : { state: board.state, orders: mapOrders, overlay: mode }
    let cancelled = false
    const timer = setTimeout(() => {
      setMapLoading(true)
      apiFetch('/sandbox/map', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
        .then(async (res) => {
          if (cancelled || !res.ok) return
          const url = URL.createObjectURL(await res.blob())
          if (cancelled) {
            URL.revokeObjectURL(url)
            return
          }
          if (mapUrlRef.current) URL.revokeObjectURL(mapUrlRef.current)
          mapUrlRef.current = url
          setMapUrl(url)
        })
        .catch(() => {})
        .finally(() => {
          if (!cancelled) setMapLoading(false)
        })
    }, mode === 'orders' ? 400 : 0)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [board, mapMode, lastTurn, mapOrders])

  useEffect(
    () => () => {
      if (mapUrlRef.current) URL.revokeObjectURL(mapUrlRef.current)
    },
    []
  )

  const legalByUnit = useMemo(() => {
    const next: Record<string, { orders: string[]; grouped: GroupedByType }> = {}
    for (const [key, list] of Object.entries(legal[power]?.orders_by_unit ?? {})) {
      next[key] = { orders: list, grouped: groupLegalOrdersByType(list) }
    }
    return next
  }, [legal, power])

  async function handleResolve() {
    if (!board) return
    setResolving(true)
    setError('')
    try {
      const r = await apiJson<AdjudicateResponse>('/sandbox/adjudicate', {
        method: 'POST',
        body: JSON.stringify({ state: board.state, orders }),
      })
      const refused = Object.entries(r.order_results).flatMap(([p, checks]) =>
        checks.filter((c) => !c.ok).map((c) => ({ power: p, order: c.order, reason: c.reason ?? 'invalid' }))
      )
      // Grouped by power, so a power's orders read together.
      const results = [...r.resolution.results].sort(
        (a, b) => a.power.localeCompare(b.power) || a.order_str.localeCompare(b.order_str)
      )
      setHistory((prev) => [...prev, { before: board, draft, orders, results, refused }])
      enterBoard({ state: r.state, view: r.view })
      setMapMode('resolution')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not resolve the phase')
    } finally {
      setResolving(false)
    }
  }

  function handleStepBack() {
    if (!lastTurn) return
    setHistory((prev) => prev.slice(0, -1))
    enterBoard(lastTurn.before, lastTurn.draft)
    setMapMode('orders')
  }

  function handleStartOver() {
    if (!start) return
    setHistory([])
    enterBoard(start)
    setMapMode('board')
  }

  /** Replace the selected power's orders with the typed ones, one per line. */
  function handleSetOrdersFromText() {
    if (!view) return
    const lines = orderText.split('\n').map((l) => l.trim().toUpperCase()).filter(Boolean)
    if (view.phase_type === 'ADJUSTMENT') {
      setDraft((d) => ({ ...d, slots: { ...d.slots, [power]: lines } }))
    } else {
      const byUnit: Record<string, string> = {}
      for (const line of lines) byUnit[extractUnitFromOrderString(line) ?? line] = line
      setDraft((d) => ({ ...d, byUnit: { ...d.byUnit, [power]: byUnit } }))
    }
    setOrderText('')
  }

  function clearPower() {
    setDraft((d) => ({
      byUnit: { ...d.byUnit, [power]: {} },
      slots: { ...d.slots, [power]: [] },
    }))
  }

  const exitTo = sourceGameId ? `/games/${sourceGameId}` : '/games'
  const exitLink = (
    <Link to={exitTo} className="text-primary underline underline-offset-2">
      {sourceGameId ? `Exit sandbox (back to game ${sourceGameId})` : 'Exit sandbox'}
    </Link>
  )

  if (error && !board) {
    return (
      <div className="max-w-xl mx-auto">
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <p>{exitLink}</p>
      </div>
    )
  }
  if (!board || !view) return <div className="p-5">Loading...</div>

  const phaseLabel = PHASE_LABEL[view.phase_type]
  const seasonLabel = view.season.charAt(0) + view.season.slice(1).toLowerCase()
  const powerUnits = [
    ...(view.units_by_power[power] ?? []).map((u) => toUnitOut(u)),
    ...view.dislodged.filter((d) => d.unit.power === power).map((d) => toUnitOut(d.unit, true)),
  ]
  const canAct = view.powers_to_order.includes(power)
  // Plain holds that stood are most of a turn's results; the rest is what happened.
  const isQuietHold = (r: OrderResultEntry) => r.order.type === 'HOLD' && r.result === 'OK' && !r.dislodged
  const holds = lastTurn ? lastTurn.results.filter(isQuietHold) : []
  const eventful = lastTurn ? lastTurn.results.filter((r) => !isQuietHold(r)) : []
  const active = view.status === 'ACTIVE'

  return (
    <div className="max-w-4xl mx-auto">
      <p className="mb-4">{exitLink}</p>

      <div className="mb-4">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h1 className="text-2xl font-semibold">Sandbox</h1>
          <span
            className={cn(
              'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
              PHASE_BADGE_CLASS[view.phase_type]
            )}
          >
            {phaseLabel}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {seasonLabel} {view.year} · {view.phase} ·{' '}
          {sourceGameId ? `started from game ${sourceGameId}` : 'started from the opening position'}
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          Order every power, resolve, and step on through retreats and builds. Nothing here
          touches a real game or is saved — leaving the page ends the sandbox.
        </p>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!active && (
        <Alert className="mb-4">
          <AlertDescription>
            This board&apos;s game is over
            {view.winners && view.winners.length > 0 ? ` — ${view.winners.join(', ')}` : ''}. Step
            back or start over to keep experimenting.
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap gap-2 mb-6">
        <Button onClick={handleResolve} disabled={resolving || !active}>
          {resolving ? 'Resolving...' : `Resolve ${view.phase}`}
        </Button>
        <Button variant="outline" onClick={handleStepBack} disabled={!lastTurn || resolving}>
          Step back
        </Button>
        <Button variant="outline" onClick={handleStartOver} disabled={history.length === 0 || resolving}>
          Start over
        </Button>
      </div>

      {mapUrl && (
        <div className="mb-6">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            {(Object.entries(MAP_MODE_LABELS) as [MapMode, string][])
              .filter(([mode]) => mode !== 'resolution' || lastTurn)
              .map(([mode, label]) => (
                <Button
                  key={mode}
                  type="button"
                  size="sm"
                  variant={mapMode === mode ? 'default' : 'outline'}
                  onClick={() => setMapMode(mode)}
                >
                  {label}
                </Button>
              ))}
            {mapLoading && <span className="text-sm text-muted-foreground">Updating map…</span>}
          </div>
          <MapViewer src={mapUrl} alt={`Sandbox ${MAP_MODE_LABELS[mapMode]} — ${view.phase}`} />
        </div>
      )}

      {lastTurn && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">What happened in {lastTurn.before.view.phase}</h2>
          {lastTurn.refused.length > 0 && (
            <Alert variant="destructive" className="mb-3">
              <AlertDescription>
                Not accepted (the unit held instead):{' '}
                {lastTurn.refused.map((r) => `${r.power}: ${r.order} (${r.reason})`).join('; ')}
              </AlertDescription>
            </Alert>
          )}
          {lastTurn.results.length === 0 ? (
            <p className="text-sm text-muted-foreground">No orders were resolved.</p>
          ) : (
            <>
              {eventful.length > 0 && <ResultList entries={eventful} showPower provinceNames={provinceNames} />}
              {holds.length > 0 && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
                    Units that held ({holds.length})
                  </summary>
                  <div className="mt-2">
                    <ResultList entries={holds} showPower provinceNames={provinceNames} />
                  </div>
                </details>
              )}
            </>
          )}
        </section>
      )}

      {active && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Orders</h2>
          <div className="flex flex-wrap gap-2 mb-3" role="group" aria-label="Power to order">
            {POWERS.map((p) => {
              const count = (orders[p] ?? []).length
              return (
                <Button
                  key={p}
                  type="button"
                  size="sm"
                  variant={p === power ? 'default' : 'outline'}
                  className={cn(!view.powers_to_order.includes(p) && 'opacity-50')}
                  aria-pressed={p === power}
                  onClick={() => setPower(p)}
                >
                  {p}
                  {count > 0 ? ` (${count})` : ''}
                </Button>
              )
            })}
          </div>
          {!canAct ? (
            <p className="text-sm text-muted-foreground">
              {power} has nothing to order in this {phaseLabel.toLowerCase()} phase.
            </p>
          ) : (
            <>
              {view.phase_type === 'ADJUSTMENT' ? (
                <BuildOrdersSection
                  adjustment={legal[power]?.adjustment}
                  orders={legal[power]?.orders ?? []}
                  buildOrderSlots={draft.slots[power] ?? []}
                  setBuildOrderSlots={(update) =>
                    setDraft((d) => {
                      const prev = d.slots[power] ?? []
                      const next = typeof update === 'function' ? update(prev) : update
                      return { ...d, slots: { ...d.slots, [power]: next } }
                    })
                  }
                  loading={legalLoading && !legal[power]}
                />
              ) : (
                <UnitOrdersSection
                  phase={phaseLabel}
                  myUnits={powerUnits}
                  orderByUnit={draft.byUnit[power] ?? {}}
                  setOrderByUnit={(update) =>
                    setDraft((d) => {
                      const prev = d.byUnit[power] ?? {}
                      const next = typeof update === 'function' ? update(prev) : update
                      return { ...d, byUnit: { ...d.byUnit, [power]: next } }
                    })
                  }
                  legalOrdersByUnit={legalByUnit}
                  loading={legalLoading && !legal[power]}
                />
              )}
              <p className="text-sm text-muted-foreground mb-2">
                {view.phase_type === 'ADJUSTMENT'
                  ? 'A build left unchosen is waived; a disband left unchosen is made by the civil-disorder rule.'
                  : `${unitsToOrder(view, power) - (orders[power] ?? []).length > 0 ? 'Units without an order hold' : 'Every unit has an order'}${view.phase_type === 'RETREAT' ? ' (an unordered retreat disbands).' : '.'}`}
              </p>
              <details className="mb-2">
                <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
                  Type {power}&apos;s orders instead
                </summary>
                <div className="mt-2 space-y-2">
                  <Textarea
                    value={orderText}
                    onChange={(e) => setOrderText(e.target.value)}
                    rows={3}
                    className="max-w-md"
                    aria-label={`Orders for ${power}, one per line`}
                    placeholder="A PAR - BUR&#10;F BRE - MAO"
                  />
                  <Button size="sm" variant="outline" onClick={handleSetOrdersFromText} disabled={!orderText.trim()}>
                    Use these orders
                  </Button>
                </div>
              </details>
              <Button size="sm" variant="ghost" onClick={clearPower} disabled={(orders[power] ?? []).length === 0}>
                Clear {power}&apos;s orders
              </Button>
            </>
          )}
          {Object.keys(orders).length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium mb-1">Orders this phase</h3>
              <ul className="text-sm space-y-0.5" aria-label="Orders this phase">
                {Object.entries(orders).flatMap(([p, list]) =>
                  list.map((o) => (
                    <li key={`${p}:${o}`}>
                      <span className="text-muted-foreground">{p}:</span> {o}
                    </li>
                  ))
                )}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
