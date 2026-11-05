/**
 * Plain-language translation for the engine's `ResultCode` enum (see
 * `engine/types.py::ResultCode`). A player should never have to know what
 * "BOUNCE" or "NO_CONVOY" means -- these are the only nine codes the engine
 * emits (movement, retreat, and adjustment adjudication); do not invent new
 * categories here without adding them engine-side first.
 */

/** Mirrors `engine.types.ResultCode` exactly -- one entry per enum value. */
export type ResultCode =
  | 'OK'
  | 'BOUNCE'
  | 'CUT'
  | 'VOID'
  | 'NO_CONVOY'
  | 'DISLODGED'
  | 'DISBAND'
  | 'BUILD'
  | 'WAIVE'

/** Mirrors `engine.types.OrderType` -- used to make an "OK" message specific
 * (a successful move reads differently from a successful support). */
export type OrderTypeCode =
  | 'HOLD'
  | 'MOVE'
  | 'SUPPORT_HOLD'
  | 'SUPPORT_MOVE'
  | 'CONVOY'
  | 'RETREAT'
  | 'DISBAND'
  | 'BUILD'
  | 'WAIVE'

/** One decorated result entry from `GET /games/{id}/last_resolution` (see
 * `GameService.last_resolution_view`), trimmed to the fields the UI needs. */
export interface OrderResultEntry {
  order: { type: OrderTypeCode | string; power: string; [key: string]: unknown }
  result: ResultCode | string
  dislodged: boolean
  retreat_options: string[]
  /** True on a `DISBAND` the engine made that the power never ordered: in an
   * adjustment, too few disbands were ordered; in a retreat phase, a dislodged unit
   * had no order (that one keeps its `retreat_options`). Absent on results stored
   * before v3.0.82. */
  civil_disorder?: boolean
  /** Why the order failed, when the code alone would mislead: a void support
   * onto the supporter's own unit ("it would dislodge your own F TRI") or a
   * convoy broken by a dislodged fleet ("F NTH was dislodged"). Derived by the
   * server (`GameService.result_reason`), the same text the bot's DM uses. */
  reason?: string
  /** On a bounced move: the unit that kept the destination ("RUSSIA's A GAL") ... */
  bounced_off?: string
  /** ... and/or the other units that moved there too (["RUSSIA's A WAR"]). Derived by
   * the server (`bounce_rivals`), the same units the bot's DM names. */
  bounced_with?: string[]
  power: string
  order_str: string
}

/** A short, plain-English sentence for one result entry -- no raw enum values. */
export function describeResult(entry: OrderResultEntry, allResults: OrderResultEntry[] = []): string {
  const orderType = entry.order.type
  switch (entry.result) {
    case 'OK':
      switch (orderType) {
        case 'MOVE':
          return 'Move succeeded.'
        case 'SUPPORT_HOLD':
        case 'SUPPORT_MOVE':
          return 'Support held.'
        case 'CONVOY':
          return 'Convoy succeeded.'
        case 'RETREAT':
          return 'Retreat succeeded.'
        case 'HOLD':
          return 'Held position.'
        default:
          return 'Order succeeded.'
      }
    case 'BOUNCE':
      if (orderType === 'RETREAT') {
        return 'Retreat bounced: another unit retreated to the same province, and the unit was disbanded.'
      }
      if (entry.bounced_off) {
        return `Move was blocked (bounced off ${entry.bounced_off}) — the unit stayed in place.`
      }
      if (entry.bounced_with?.length) {
        return `Move was blocked (bounced; ${entry.bounced_with.join(' and ')} also moved there) — the unit stayed in place.`
      }
      return 'Move was blocked (bounced) — the unit stayed in place.'
    case 'CUT':
      return 'Support was cut by an attack and had no effect.'
    case 'VOID':
      if (entry.reason) return `Had no effect: ${entry.reason}.`
      return 'Order was invalid and was not carried out.'
    case 'NO_CONVOY':
      if (entry.reason) return `Convoy failed — ${entry.reason}, so the move did not happen.`
      return 'Convoy failed — no surviving path, so the move did not happen.'
    case 'DISLODGED':
      return `Unit was dislodged${dislodgedBy(entry, allResults)}.`
    case 'DISBAND':
      if (entry.civil_disorder) {
        return entry.retreat_options.length > 0
          ? 'Disbanded by civil disorder: no retreat was ordered.'
          : 'Disbanded by civil disorder: too few disbands were ordered.'
      }
      return orderType === 'RETREAT'
        ? 'The retreat was not legal — the unit was disbanded.'
        : 'Unit was disbanded.'
    case 'BUILD':
      return 'Build succeeded.'
    case 'WAIVE':
      return 'Build was waived.'
    default:
      return String(entry.result)
  }
}

/** Badge color classes per result, grouped by "good / neutral / bad" so the
 * panel reads at a glance without parsing every sentence. */
export function resultBadgeClass(result: ResultCode | string): string {
  switch (result) {
    case 'OK':
    case 'BUILD':
      return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
    case 'WAIVE':
    case 'VOID':
      return 'bg-muted text-muted-foreground'
    case 'BOUNCE':
    case 'CUT':
    case 'NO_CONVOY':
      return 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
    case 'DISLODGED':
    case 'DISBAND':
      return 'bg-red-500/15 text-red-700 dark:text-red-400'
    default:
      return 'bg-muted text-muted-foreground'
  }
}

/** " by A SER (RUSSIA)": the successful move into the province of a dislodged unit,
 * found among the turn's results (the bot's `_dislodger`); "" when none is named. */
export function dislodgedBy(entry: OrderResultEntry, results: OrderResultEntry[]): string {
  const unit = entry.order.unit
  if (typeof unit !== 'string') return ''
  const province = unit.split('/')[0]
  for (const r of results) {
    const dest = r.order.dest
    if (r.order.type === 'MOVE' && r.result === 'OK' && typeof dest === 'string' && dest.split('/')[0] === province) {
      return ` by ${r.order_str.split(' - ')[0]} (${r.power})`
    }
  }
  return ''
}

/** True when `results` are an adjustment phase's: every order is a build, waive or disband. */
export function isAdjustmentResults(results: OrderResultEntry[]): boolean {
  return (
    results.length > 0 &&
    results.every((r) => r.order.type === 'BUILD' || r.order.type === 'WAIVE' || r.order.type === 'DISBAND')
  )
}

/** What to say when `power` has no entry in a turn's results. The engine records a result
 * for every build (an unused entitlement is an implicit waive) and every disband (a
 * shortfall is civil disorder), so in an adjustment phase a power with none owed nothing. */
export function noResultsText(power: string, results: OrderResultEntry[]): string {
  return isAdjustmentResults(results)
    ? `${power} had nothing to build or disband.`
    : `${power} had no orders recorded for that turn.`
}
