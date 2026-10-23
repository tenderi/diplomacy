/**
 * Order entry and order-result display shared by a real game (`GameView`) and the
 * sandbox (`Sandbox`): the per-unit order pickers, the adjustment-phase slot pickers,
 * the adjudicated-result list, and the unit/legal-order types they work on.
 */
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { glossOrder, provinceLabel, provinceName, type ProvinceNames } from '@/lib/provinceNames'
import {
  type OrderType,
  type ParsedLegalOrder,
  type GroupedByType,
  parseLegalOrder,
  groupLegalOrdersByType,
  getOrderTypesFromGrouped,
  orderTypeLabel,
  getTargetOptionsForType,
} from '@/lib/orderParsing'
import { type OrderResultEntry, describeResult, resultBadgeClass } from '@/lib/resultText'

export const POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

export type PhaseType = 'MOVEMENT' | 'RETREAT' | 'ADJUSTMENT'
export type UnitOut = { unit_type: string; province: string; coast?: string; is_dislodged?: boolean }
/** A unit as returned by the new GameState-native API view. */
export type NewUnit = { kind: 'A' | 'F'; power: string; location: string }
export type DislodgedOut = { unit: NewUnit; attacker_origin: string | null; retreats: string[] }
/** Adjustment-phase summary from the legal-orders view: how many build/disband slots. */
export type AdjustmentInfo = {
  delta: number
  action: 'build' | 'disband' | 'none'
  slots: number
  /** Supply centres and units the power holds, the two numbers `delta` is the difference of. */
  centers?: number
  units?: number
}

const COAST_NAMES: Record<string, string> = { NC: 'north coast', SC: 'south coast', EC: 'east coast' }

/** "BUILD F STP/SC" -> "Build fleet – St Petersburg (south coast)"; "D A MUN" -> "Disband A MUN – Munich". */
export function describeAdjustmentOrder(order: string, names: ProvinceNames): string {
  const m = order.trim().match(/^(BUILD|D|DISBAND)\s+([AF])\s+([A-Z]{3})(?:\/([A-Z]{2}))?$/i)
  if (!m) return order.trim().toUpperCase() === 'WAIVE' ? 'Waive (build nothing)' : order
  const [, verb, kind, prov, coast] = m
  const name = names[prov.toUpperCase()] ?? prov.toUpperCase()
  const where = coast ? `${name} (${COAST_NAMES[coast.toUpperCase()] ?? coast})` : name
  if (verb.toUpperCase() === 'BUILD') return `Build ${kind.toUpperCase() === 'A' ? 'army' : 'fleet'} – ${where}`
  return `Disband ${kind.toUpperCase()} ${prov.toUpperCase()}${coast ? `/${coast.toUpperCase()}` : ''} – ${where}`
}

function adjustmentSummary(a?: AdjustmentInfo): string {
  if (!a || a.action === 'none') return 'No builds or disbands this turn.'
  const noun = a.action === 'build' ? 'build' : 'disband'
  const count = `${a.slots} ${noun}${a.slots === 1 ? '' : 's'}`
  const why =
    a.centers != null && a.units != null
      ? `: ${a.centers} centre${a.centers === 1 ? '' : 's'}, ${a.units} unit${a.units === 1 ? '' : 's'}`
      : ''
  const limited =
    a.action === 'build' && a.slots < a.delta
      ? ` (only ${a.slots} free home centre${a.slots === 1 ? '' : 's'} to build on)`
      : ''
  const hint = a.action === 'build' ? ' Select one order per slot, or waive.' : ' Select a unit to remove per slot.'
  return `${count[0].toUpperCase()}${count.slice(1)}${why}${limited}.${hint}`
}
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

/** "NTH" -> "NTH – North Sea"; a code with no known name stays as it is. */
function codeWithName(code: string, names: ProvinceNames): string {
  const name = provinceName(code, names)
  return name === code ? code : `${code} – ${name}`
}

/**
 * Target text for the picker: the engine-built label with province names added.
 * A support/convoy names whose unit is supported ("A BUR (FRANCE)") when `owners`
 * (province -> power) knows it. Display only: the order string is untouched.
 */
export function describeTarget(
  opt: ParsedLegalOrder,
  names: ProvinceNames,
  owners: Record<string, string> = {}
): string {
  if (opt.type === 'move' || opt.type === 'retreat') {
    const by = opt.targetLabel.endsWith(' (by convoy)') ? ' (by convoy)' : ''
    return codeWithName(opt.targetValue, names) + by
  }
  if (opt.type === 'support' || opt.type === 'convoy') {
    const m = opt.targetLabel.match(/^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?)(?: (\(hold\)|→ ([A-Z]{3}(?:\/[A-Z]{2})?)))?$/)
    if (m) {
      const owner = owners[m[2].split('/')[0]]
      const who = owner ? ` (${owner})` : ''
      const unit = `${m[1]} ${m[2]}${who}`
      if (m[4]) return `${unit} → ${codeWithName(m[4], names)}`
      return m[3] ? `${unit} (hold)` : unit
    }
  }
  return opt.targetLabel
}

/** Types that are not complete until a target is chosen. */
function needsTarget(t: OrderType | ''): boolean {
  return t !== '' && t !== 'hold'
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
  provinceNames = {},
  unitOwners = {},
  phaseCode,
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
  /** code -> full name, for target labels (BQ5). */
  provinceNames?: ProvinceNames
  /** province -> power, so a support option says whose unit it backs (BQ5). */
  unitOwners?: Record<string, string>
  /** Phase code ("S1901M"); a new one discards half-made choices, as the orders are replaced. */
  phaseCode?: string
}) {
  // An order type chosen but with no target yet. It is not an order, so it lives here
  // and never reaches `orderByUnit` (BQ1).
  const [pendingType, setPendingType] = useState<Record<string, OrderType>>({})
  const [pendingPhase, setPendingPhase] = useState(phaseCode)
  if (pendingPhase !== phaseCode) {
    setPendingPhase(phaseCode)
    setPendingType({})
  }
  const unitsToShow = phase === 'Retreat' ? myUnits.filter((u) => u.is_dislodged) : myUnits
  const incomplete = unitsToShow.filter((u) => {
    const id = unitKey(u)
    return !orderByUnit[id] && needsTarget(pendingType[id] ?? '')
  })
  return (
    <>
      <p className="text-sm text-muted-foreground mb-2">
        One row per unit. Choose order type, then target. {phase === 'Retreat'
          ? 'A dislodged unit with no order is disbanded.'
          : 'A unit with no order holds.'}
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
          const selectedOrderType: OrderType | '' = parsedCurrent?.type ?? pendingType[unitId] ?? ''
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
                value={selectedOrderType}
                onValueChange={(t) => {
                  if (!t) return
                  const type = t as OrderType
                  // Hold is complete by itself; every other type waits for a chosen target.
                  // A retreat-phase disband likewise names its unit and needs no target.
                  const complete = type === 'hold' || (type === 'destroy' && phase === 'Retreat')
                  const hold = complete ? getTargetOptionsForType(grouped!, type)[0] : undefined
                  setPendingType((prev) => ({ ...prev, [unitId]: type }))
                  setOrderByUnit((prev) => ({ ...prev, [unitId]: hold?.fullOrder ?? '' }))
                }}
                disabled={!grouped || loading}
              >
                <SelectTrigger className="w-full" aria-label={`Order type for ${unitId}`}>
                  <SelectValue placeholder={phase === 'Retreat' ? 'No order (disbands)' : 'No order (holds)'} />
                </SelectTrigger>
                <SelectContent>
                  {orderTypes.map((t) => (
                    <SelectItem key={t} value={t}>
                      {orderTypeLabel(t, phase)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedOrderType && selectedOrderType !== 'hold' && !(selectedOrderType === 'destroy' && phase === 'Retreat') && (
                <Select
                  value={targetValue}
                  onValueChange={(fullOrder) => {
                    setPendingType((prev) => {
                      const { [unitId]: _done, ...rest } = prev
                      return rest
                    })
                    setOrderByUnit((prev) => ({ ...prev, [unitId]: fullOrder }))
                  }}
                  disabled={!grouped || loading}
                >
                  <SelectTrigger className="w-full" aria-label={`Target for ${unitId} order`}>
                    <SelectValue placeholder="Choose target" />
                  </SelectTrigger>
                  <SelectContent>
                    {targetOptions.map((opt) => (
                      <SelectItem key={opt.fullOrder} value={opt.fullOrder}>
                        {describeTarget(opt, provinceNames, unitOwners)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {selectedOrderType === 'hold' && targetOptions.length > 0 && (
                <span className="text-muted-foreground text-sm">Hold</span>
              )}
              {selectedOrderType === 'destroy' && phase === 'Retreat' && (
                <span className="text-muted-foreground text-sm">Disband</span>
              )}
            </li>
          )
        })}
      </ul>
      {onSubmit && (
        <>
          <Button onClick={onSubmit} disabled={submitting || incomplete.length > 0}>
            {submitting ? 'Submitting...' : 'Submit orders'}
          </Button>
          {incomplete.length > 0 && (
            <p className="mt-2 text-sm text-amber-700 dark:text-amber-400">
              Choose a target for {incomplete.map(unitKey).join(', ')} before submitting.
            </p>
          )}
        </>
      )}
    </>
  )
}

export function BuildOrdersSection({
  adjustment,
  orders,
  provinceNames = {},
  buildOrderSlots,
  setBuildOrderSlots,
  loading,
  onSubmit,
  submitting,
}: {
  adjustment?: AdjustmentInfo
  orders: string[]
  provinceNames?: ProvinceNames
  buildOrderSlots: string[]
  setBuildOrderSlots: React.Dispatch<React.SetStateAction<string[]>>
  loading: boolean
  onSubmit?: () => void
  submitting?: boolean
}) {
  const grouped = groupLegalOrdersByType(orders)
  const options: ParsedLegalOrder[] = [...grouped.build, ...grouped.destroy, ...grouped.waive]
  const slots = Array.from({ length: adjustment?.slots ?? 0 }, (_, i) => i)
  // One order per province: a build in STP/SC and one in STP/NC would collide, the
  // server keeping only the later. Hide a province (any coast) another slot has chosen.
  const provinceOf = (order: string): string | null => {
    const m = order.match(/^(?:BUILD|D|DISBAND)\s+[AF]\s+([A-Z]{3})/i)
    return m ? m[1].toUpperCase() : null
  }
  const takenByOtherSlot = (opt: ParsedLegalOrder, slot: number): boolean => {
    const prov = provinceOf(opt.fullOrder)
    if (!prov) return false
    return buildOrderSlots.some((o, j) => j !== slot && !!o && provinceOf(o) === prov)
  }
  return (
    <>
      <p className="text-sm text-muted-foreground mb-2">
        {adjustmentSummary(adjustment)}
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
                {options
                  .filter((opt) => !takenByOtherSlot(opt, i))
                  .map((opt) => (
                  <SelectItem key={opt.fullOrder} value={opt.fullOrder}>
                    {describeAdjustmentOrder(opt.fullOrder, provinceNames)}
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
