import { describe, it, expect } from 'vitest'
import { describeResult, resultBadgeClass, type OrderResultEntry } from './resultText'

function entry(overrides: Partial<OrderResultEntry> = {}): OrderResultEntry {
  return {
    order: { type: 'MOVE', power: 'FRANCE', unit: 'PAR', dest: 'BUR' },
    result: 'OK',
    dislodged: false,
    retreat_options: [],
    power: 'FRANCE',
    order_str: 'A PAR - BUR',
    ...overrides,
  }
}

describe('describeResult', () => {
  it('never leaks a raw enum value for any of the nine engine result codes', () => {
    const codes = [
      'OK', 'BOUNCE', 'CUT', 'VOID', 'NO_CONVOY', 'DISLODGED', 'DISBAND', 'BUILD', 'WAIVE',
    ] as const
    for (const result of codes) {
      const text = describeResult(entry({ result }))
      expect(text).not.toBe(result)
      expect(text.length).toBeGreaterThan(0)
    }
  })

  it('describes a blocked move in plain language, not "BOUNCE"', () => {
    expect(describeResult(entry({ result: 'BOUNCE' }))).toMatch(/blocked/i)
  })

  it('describes a cut support', () => {
    expect(
      describeResult(entry({ order: { type: 'SUPPORT_HOLD', power: 'FRANCE' }, result: 'CUT' }))
    ).toMatch(/cut/i)
  })

  it('distinguishes a disbanded retreat from a general disband', () => {
    const retreatDisband = describeResult(
      entry({ order: { type: 'RETREAT', power: 'FRANCE' }, result: 'DISBAND' })
    )
    const adjustmentDisband = describeResult(
      entry({ order: { type: 'DISBAND', power: 'FRANCE' }, result: 'DISBAND' })
    )
    expect(retreatDisband).toMatch(/no legal retreat/i)
    expect(adjustmentDisband).not.toMatch(/no legal retreat/i)
  })

  it('gives a successful build its own message', () => {
    expect(
      describeResult(entry({ order: { type: 'BUILD', power: 'FRANCE' }, result: 'BUILD' }))
    ).toMatch(/build succeeded/i)
  })
})

describe('resultBadgeClass', () => {
  it('returns a non-empty class string for every known code', () => {
    const codes = [
      'OK', 'BOUNCE', 'CUT', 'VOID', 'NO_CONVOY', 'DISLODGED', 'DISBAND', 'BUILD', 'WAIVE',
    ]
    for (const code of codes) {
      expect(resultBadgeClass(code).length).toBeGreaterThan(0)
    }
  })

  it('falls back gracefully for an unknown code instead of throwing', () => {
    expect(() => resultBadgeClass('SOMETHING_NEW')).not.toThrow()
  })
})
