import { describe, it, expect } from 'vitest'
import {
  parseLegalOrder,
  groupLegalOrdersByType,
  getOrderTypesFromGrouped,
  getTargetOptionsForType,
  extractUnitFromOrderString,
  type GroupedByType,
} from './orderParsing'

describe('parseLegalOrder', () => {
  it('returns null for empty or whitespace', () => {
    expect(parseLegalOrder('')).toBeNull()
    expect(parseLegalOrder('   ')).toBeNull()
  })

  it('parses hold orders', () => {
    const parsed = parseLegalOrder('FRANCE A PAR H')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('hold')
    expect(parsed!.targetLabel).toBe('Hold')
    expect(parsed!.targetValue).toBe('')
    expect(parsed!.fullOrder).toBe('FRANCE A PAR H')
  })

  it('parses move orders', () => {
    const parsed = parseLegalOrder('A PAR - BUR')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('move')
    expect(parsed!.targetLabel).toBe('BUR')
    expect(parsed!.targetValue).toBe('BUR')
  })

  it('parses retreat orders', () => {
    const parsed = parseLegalOrder('A PAR R PIC')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('retreat')
    expect(parsed!.targetLabel).toBe('PIC')
    expect(parsed!.targetValue).toBe('PIC')
  })

  it('parses support (move)', () => {
    const parsed = parseLegalOrder('FRANCE A MAR S A PAR - BUR')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('support')
    expect(parsed!.targetLabel).toContain('→')
    expect(parsed!.targetValue).toBe('FRANCE A MAR S A PAR - BUR')
  })

  it('parses convoy orders', () => {
    const parsed = parseLegalOrder('F ENG C A LON - BEL')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('convoy')
    expect(parsed!.targetLabel).toContain('→')
  })

  it('parses coasted move orders, coast intact', () => {
    const parsed = parseLegalOrder('F STP/SC - BOT')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('move')
    expect(parsed!.fullOrder).toBe('F STP/SC - BOT')
  })

  it('parses coasted support orders, coast intact', () => {
    const parsed = parseLegalOrder('A MOS S F STP/SC - BOT')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('support')
    expect(parsed!.targetValue).toBe('A MOS S F STP/SC - BOT')
  })

  it('parses coasted convoy orders, coast intact', () => {
    const parsed = parseLegalOrder('F BUL/EC C A CON - SEV')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('convoy')
  })

  // Leading-verb forms: the engine's grammar is verb-first for builds/disbands/waives.
  it('parses "D A PAR" (leading-verb disband)', () => {
    const parsed = parseLegalOrder('D A PAR')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('destroy')
    expect(parsed!.targetLabel).toBe('A PAR')
    expect(parsed!.fullOrder).toBe('D A PAR')
  })

  it('parses "DISBAND A PAR" (leading-verb disband, long form)', () => {
    const parsed = parseLegalOrder('DISBAND A PAR')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('destroy')
    expect(parsed!.targetLabel).toBe('A PAR')
  })

  it('parses "BUILD F BRE" (leading-verb build)', () => {
    const parsed = parseLegalOrder('BUILD F BRE')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('build')
    expect(parsed!.targetLabel).toBe('F BRE')
    expect(parsed!.fullOrder).toBe('BUILD F BRE')
  })

  it('parses "BUILD F STP/SC" (leading-verb build, coast intact)', () => {
    const parsed = parseLegalOrder('BUILD F STP/SC')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('build')
    expect(parsed!.targetLabel).toBe('F STP/SC')
    expect(parsed!.fullOrder).toBe('BUILD F STP/SC')
  })

  it('parses bare "WAIVE"', () => {
    const parsed = parseLegalOrder('WAIVE')
    expect(parsed).not.toBeNull()
    expect(parsed!.type).toBe('waive')
    expect(parsed!.fullOrder).toBe('WAIVE')
  })
})

describe('groupLegalOrdersByType', () => {
  it('groups orders by type', () => {
    const orders = ['A PAR H', 'A PAR - BUR', 'A MAR S A PAR - BUR']
    const grouped = groupLegalOrdersByType(orders)
    expect(grouped.hold).toHaveLength(1)
    expect(grouped.move).toHaveLength(1)
    expect(grouped.support).toHaveLength(1)
  })

  it('returns empty arrays for missing types', () => {
    const grouped = groupLegalOrdersByType([])
    const empty: GroupedByType = {
      hold: [], move: [], support: [], convoy: [], retreat: [], build: [], destroy: [], waive: [],
    }
    expect(grouped).toEqual(empty)
  })
})

describe('getOrderTypesFromGrouped', () => {
  it('includes retreat only for Retreat phase', () => {
    const grouped = groupLegalOrdersByType(['A PAR R PIC'])
    expect(getOrderTypesFromGrouped(grouped, 'Retreat')).toContain('retreat')
    expect(getOrderTypesFromGrouped(grouped, 'Movement')).not.toContain('retreat')
  })
})

describe('getTargetOptionsForType', () => {
  it('returns options for given order type', () => {
    const grouped = groupLegalOrdersByType(['A PAR - BUR', 'A PAR - GAS'])
    const options = getTargetOptionsForType(grouped, 'move')
    expect(options).toHaveLength(2)
    expect(options.map((o) => o.targetLabel)).toEqual(['BUR', 'GAS'])
  })
})

describe('extractUnitFromOrderString', () => {
  it('extracts unit from army order', () => {
    expect(extractUnitFromOrderString('A PAR - BUR')).toBe('A PAR')
  })
  it('returns null for build orders', () => {
    expect(extractUnitFromOrderString('FRANCE BUILD A PAR')).toBeNull()
  })
})
