/**
 * Order entry and order-result display shared by a real game (`GameView`) and the
 * sandbox (`Sandbox`): the per-unit order pickers, the adjustment-phase slot pickers,
 * the adjudicated-result list, and the unit/legal-order types they work on.
 */
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { glossOrder, provinceLabel, type ProvinceNames } from '@/lib/provinceNames'
import {
  type OrderType,
  type ParsedLegalOrder,
  type GroupedByType,
  parseLegalOrder,
  groupLegalOrdersByType,
  getOrderTypesFromGrouped,
  getTargetOptionsForType,
  ORDER_TYPE_LABELS,
} from '@/lib/orderParsing'
import { type OrderResultEntry, describeResult, resultBadgeClass } from '@/lib/resultText'

export const POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

export type PhaseType = 'MOVEMENT' | 'RETREAT' | 'ADJUSTMENT'
export type UnitOut = { unit_type: string; province: string; coast?: string; is_dislodged?: boolean }
/** A unit as returned by the new GameState-native API view. */
export type NewUnit = { kind: 'A' | 'F'; power: string; location: string }
export type DislodgedOut = { unit: NewUnit; attacker_origin: string | null; retreats: string[] }
/** Adjustment-phase summary from the legal-orders view: how many build/disband slots. */
export type AdjustmentInfo = { delta: number; action: 'build' | 'disband' | 'none'; slots: number }
/**
 * Response shape of GET /games/{id}/legal_orders/{power} (see server.legal_orders).
 * `orders_by_unit` keys are exactly `${kind} ${location}` (coast included); every string in
 * a bucket either starts with that key (hold/move/support/convoy/retreat) or ends with it
 * (verb-first build/disband, e.g. "D A PAR", "BUILD F BRE") — callers must not assume a
 * prefix match and should just use the bucket the backend already built. `WAIVE` has no
 * unit and appears only in the flat `orders` list. `adjustment` is present only in an
 * ADJUSTMENT phase.
 */
export type LegalOrdersView = {
  phase: string
  phase_type: PhaseType
  power: string
  units: { kind: 'A' | 'F'; location: string; province: string; coast: string | null }[]
  orders_by_unit: Record<string, string[]>
  orders: string[]
  adjustment?: AdjustmentInfo
}

/** Human phase label used by the order-entry UI and legal-order grouping. */
export const PHASE_LABEL: Record<PhaseType, string> = {
  MOVEMENT: 'Movement',
  RETREAT: 'Retreat',
  ADJUSTMENT: 'Adjustment',
}

/** Badge color per phase type so the current phase reads at a glance, not as a muted aside. */
export const PHASE_BADGE_CLASS: Record<PhaseType, string> = {
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
export function toUnitOut(u: NewUnit, isDislodged = false): UnitOut {
  const { province, coast } = splitLocation(u.location)
  return { unit_type: u.kind, province, coast, is_dislodged: isDislodged }
}

/** Unit id matching the backend's `orders_by_unit` keys: `${kind} ${location}`, coast included. */
export function unitKey(u: UnitOut): string {
  return `${u.unit_type} ${u.province}${u.coast ? `/${u.coast}` : ''}`
}

export function UnitOrdersSection({
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
  /** Omitted where there is nothing to submit (the sandbox holds orders locally). */
  onSubmit?: () => void
  submitting?: boolean
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
          // A unit can have an order before its menu has loaded (orders are fetched
          // separately), so the menu may still be missing here.
          const targetOptions: ParsedLegalOrder[] =
            selectedOrderType && grouped ? getTargetOptionsForType(grouped, selectedOrderType) : []
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
      {onSubmit && (
        <Button onClick={onSubmit} disabled={submitting}>
          {submitting ? 'Submitting...' : 'Submit orders'}
        </Button>
      )}
    </>
  )
}

export function BuildOrdersSection({
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
  onSubmit?: () => void
  submitting?: boolean
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
      {onSubmit && (
        <Button onClick={onSubmit} disabled={submitting || slots.length === 0}>
          {submitting ? 'Submitting...' : 'Submit orders'}
        </Button>
      )}
    </>
  )
}

/** One result row: the truthful order string (already "F"/"A"-correct — see
 * GameService.last_resolution_view), a plain-language outcome badge, and — when the
 * ordering unit was dislodged — a prominent call-out with its retreat options, since a
 * dislodged unit demands action next phase. `showPower` prefixes the owning power for
 * the "other powers" list, where it isn't otherwise obvious. */
export function ResultList({
  entries,
  showPower = false,
  provinceNames = {},
}: {
  entries: OrderResultEntry[]
  showPower?: boolean
  provinceNames?: ProvinceNames
}) {
  return (
    <ul className="space-y-2">
      {entries.map((r, i) => {
        // A readable second line, never a replacement: the canonical order string
        // stays exactly as the engine produced it, because that is what a player
        // would retype and full province names do not parse (G1/G2).
        const gloss = glossOrder(r.order_str, provinceNames)
        return (
          <li key={i} className="border-b border-border/50 pb-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">
                {showPower ? `${r.power}: ` : ''}
                {r.order_str}
              </span>
              <span
                className={cn(
                  'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold',
                  resultBadgeClass(r.result)
                )}
              >
                {describeResult(r)}
              </span>
            </div>
            {gloss && <p className="text-xs text-muted-foreground">{gloss}</p>}
            {r.dislodged && (
              <p className="mt-1 text-amber-700 dark:text-amber-400">
                This unit was dislodged and must retreat or disband next phase
                {r.retreat_options.length > 0
                  ? ` — retreat options: ${r.retreat_options
                      .map((opt) => provinceLabel(opt, provinceNames))
                      .join(', ')}.`
                  : ' — no legal retreat is available; it will be disbanded.'}
              </p>
            )}
          </li>
        )
      })}
    </ul>
  )
}
