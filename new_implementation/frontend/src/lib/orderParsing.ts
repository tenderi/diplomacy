/**
 * Parse legal order strings from the backend into order type and target for dropdown UI.
 * Backend format: "POWER A PAR - BUR", "POWER A PAR H", "POWER A PAR S A BUR - BUR", etc.
 */

export type OrderType = 'hold' | 'move' | 'support' | 'convoy' | 'retreat' | 'build' | 'destroy' | 'waive'

export interface ParsedLegalOrder {
  type: OrderType
  /** Human-readable label for target dropdown (e.g. "BUR", "A BUR → MUN", "A BUR (hold)") */
  targetLabel: string
  /** Value for target dropdown: full order string for support/convoy, province for move/retreat, empty for hold */
  targetValue: string
  /** Original full order string (for submission) */
  fullOrder: string
}

/**
 * Parse a single legal order string into type and target info.
 * Handles: Hold (H), Move (-), Support (S), Convoy (C), Retreat (R), BUILD, DESTROY.
 */
export function parseLegalOrder(orderString: string): ParsedLegalOrder | null {
  const s = orderString.trim()
  if (!s) return null

  const parts = s.split(/\s+/)
  // Strip optional power prefix (first word if it's a power name, then unit type + province)
  const powerNames = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']
  let i = 0
  if (powerNames.includes(parts[0]?.toUpperCase() ?? '')) {
    i = 1
  }
  const unitType = parts[i]
  const unitProvince = parts[i + 1]

  // Leading-verb forms, checked BEFORE the null-guard below: the engine's grammar is
  // verb-first for builds/disbands/waives, unlike every other order (which is unit-first).
  // "D A PAR" / "DISBAND A PAR", "BUILD F BRE" / "BUILD F STP/SC", bare "WAIVE".
  const leadVerb = parts[i]?.toUpperCase()
  if (leadVerb === 'WAIVE') {
    return { type: 'waive', targetLabel: 'Waive', targetValue: '', fullOrder: s }
  }
  if (leadVerb === 'D' || leadVerb === 'DISBAND') {
    const unitPart = parts.slice(i + 1, i + 3).join(' ')
    return { type: 'destroy', targetLabel: unitPart, targetValue: s, fullOrder: s }
  }
  if (leadVerb === 'BUILD') {
    const unitPart = parts.slice(i + 1, i + 3).join(' ')
    return { type: 'build', targetLabel: unitPart, targetValue: s, fullOrder: s }
  }

  if (!unitType || !unitProvince) return null

  // Support: " S A BUR - BUR" or " S A BUR H". Checked before Hold/Move/Retreat since a
  // supported-hold string contains no trailing " H"/" - " of its own today, but keeping
  // this ordering defensive against future formats that might.
  if (s.includes(' S ')) {
    const afterS = s.substring(s.indexOf(' S ') + 3).trim()
    const supportedUnit = afterS.split(/\s+/).slice(0, 2).join(' ') // e.g. "A BUR"
    const rest = afterS.substring(supportedUnit.length).trim()
    let label: string
    if (rest === 'H' || rest === '') {
      label = `${supportedUnit} (hold)`
    } else {
      const toMatch = rest.match(/^-\s*([A-Za-z/]+)/)
      label = toMatch ? `${supportedUnit} → ${toMatch[1]}` : afterS
    }
    return { type: 'support', targetLabel: label, targetValue: s, fullOrder: s }
  }

  // Convoy: " C A LON - BEL"
  if (s.includes(' C ')) {
    const afterC = s.substring(s.indexOf(' C ') + 3).trim()
    const convoyedUnit = afterC.split(/\s+/).slice(0, 2).join(' ')
    const toMatch = afterC.match(/-\s*([A-Za-z/]+)/)
    const dest = toMatch ? toMatch[1] : ''
    const label = dest ? `${convoyedUnit} → ${dest}` : afterC
    return { type: 'convoy', targetLabel: label, targetValue: s, fullOrder: s }
  }

  // Hold: ends with " H" or " H" at end of line
  if (s.endsWith(' H') || /\sH$/.test(s)) {
    return { type: 'hold', targetLabel: 'Hold', targetValue: '', fullOrder: s }
  }

  // Retreat: "A PAR R PIC" (unit R province)
  const retreatMatch = s.match(/\sR\s+([A-Za-z/]+)\s*$/)
  if (retreatMatch) {
    const prov = retreatMatch[1].trim()
    return { type: 'retreat', targetLabel: prov, targetValue: prov, fullOrder: s }
  }

  // Move: " - BUR" or " - BUR" (dash then target province)
  const moveMatch = s.match(/\s-\s+([A-Za-z/]+)\s*$/)
  if (moveMatch) {
    const prov = moveMatch[1].trim()
    return { type: 'move', targetLabel: prov, targetValue: prov, fullOrder: s }
  }

  // Build: "FRANCE BUILD A PAR" or "FRANCE BUILD F SPA/NC" (power-prefixed form)
  if (s.toUpperCase().includes('BUILD')) {
    const buildPart = s.substring(s.indexOf('BUILD') + 5).trim()
    return { type: 'build', targetLabel: buildPart, targetValue: s, fullOrder: s }
  }

  // Destroy: "FRANCE DESTROY A PAR" (power-prefixed form)
  if (s.toUpperCase().includes('DESTROY')) {
    const destroyPart = s.substring(s.indexOf('DESTROY') + 7).trim()
    return { type: 'destroy', targetLabel: destroyPart, targetValue: s, fullOrder: s }
  }

  return null
}

export interface GroupedByType {
  hold: ParsedLegalOrder[]
  move: ParsedLegalOrder[]
  support: ParsedLegalOrder[]
  convoy: ParsedLegalOrder[]
  retreat: ParsedLegalOrder[]
  build: ParsedLegalOrder[]
  destroy: ParsedLegalOrder[]
  waive: ParsedLegalOrder[]
}

/**
 * Group an array of legal order strings by order type.
 */
export function groupLegalOrdersByType(orders: string[]): GroupedByType {
  const result: GroupedByType = {
    hold: [],
    move: [],
    support: [],
    convoy: [],
    retreat: [],
    build: [],
    destroy: [],
    waive: [],
  }
  for (const order of orders) {
    const parsed = parseLegalOrder(order)
    if (parsed && result[parsed.type]) {
      result[parsed.type].push(parsed)
    }
  }
  return result
}

/** Order type label for UI */
export const ORDER_TYPE_LABELS: Record<OrderType, string> = {
  hold: 'Hold',
  move: 'Move',
  support: 'Support',
  convoy: 'Convoy',
  retreat: 'Retreat',
  build: 'Build',
  destroy: 'Destroy',
  waive: 'Waive',
}

/**
 * Get unique order types present in the grouped orders (for dropdown).
 */
export function getOrderTypesFromGrouped(grouped: GroupedByType, phase: string): OrderType[] {
  const types: OrderType[] = []
  if (grouped.hold.length) types.push('hold')
  if (grouped.move.length) types.push('move')
  if (grouped.support.length) types.push('support')
  if (grouped.convoy.length) types.push('convoy')
  if (phase === 'Retreat' && grouped.retreat.length) types.push('retreat')
  if ((phase === 'Builds' || phase === 'Adjustment') && grouped.build.length) types.push('build')
  if ((phase === 'Builds' || phase === 'Adjustment') && grouped.destroy.length) types.push('destroy')
  if ((phase === 'Builds' || phase === 'Adjustment') && grouped.waive.length) types.push('waive')
  return types
}

/**
 * Get target options for a given order type from grouped orders.
 */
export function getTargetOptionsForType(
  grouped: GroupedByType,
  orderType: OrderType
): ParsedLegalOrder[] {
  const list = grouped[orderType] ?? []
  return list
}

/**
 * Extract unit id (e.g. "A PAR") from an order string for matching to state units.
 */
export function extractUnitFromOrderString(orderString: string): string | null {
  const s = orderString.trim()
  const parts = s.split(/\s+/)
  const powerNames = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']
  let i = 0
  if (powerNames.includes(parts[0]?.toUpperCase() ?? '')) {
    i = 1
  }
  const unitType = parts[i]
  const unitProvince = parts[i + 1]
  if (unitType && unitProvince && /^[AF]$/i.test(unitType)) {
    return `${unitType.toUpperCase()} ${unitProvince}`
  }
  // Build/Destroy don't have a "unit" in the same sense; return null
  if (s.toUpperCase().includes('BUILD') || s.toUpperCase().includes('DESTROY')) {
    return null
  }
  return null
}
