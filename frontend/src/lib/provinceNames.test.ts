import { describe, it, expect } from 'vitest'
import {
  glossOrder,
  provinceLabel,
  provinceName,
  provinceNamesFromResponse,
} from './provinceNames'

const NAMES = {
  BER: 'Berlin',
  KIE: 'Kiel',
  MUN: 'Munich',
  STP: 'St Petersburg',
  NTH: 'North Sea',
  ENG: 'English Channel',
  SIL: 'Silesia',
}

describe('provinceNamesFromResponse', () => {
  it('reduces the endpoint payload to code -> name', () => {
    expect(
      provinceNamesFromResponse({
        provinces: {
          BER: { name: 'Berlin', type: 'COAST', is_supply_center: true, coasts: [] },
          NTH: { name: 'North Sea', type: 'WATER', is_supply_center: false, coasts: [] },
        },
      })
    ).toEqual({ BER: 'Berlin', NTH: 'North Sea' })
  })

  it('returns an empty map for a missing or empty provinces field', () => {
    expect(provinceNamesFromResponse({})).toEqual({})
    expect(provinceNamesFromResponse({ provinces: {} })).toEqual({})
  })
})

describe('provinceLabel', () => {
  it('shows the name and keeps the code, because orders need the code', () => {
    expect(provinceLabel('BER', NAMES)).toBe('Berlin (BER)')
  })

  it('keeps a coast qualifier in the code half', () => {
    expect(provinceLabel('STP/SC', NAMES)).toBe('St Petersburg (STP/SC)')
  })

  it('passes an unknown code through unchanged rather than rendering undefined', () => {
    // The table is fetched asynchronously, so every caller renders at least
    // once before it arrives.
    expect(provinceLabel('BER', {})).toBe('BER')
    expect(provinceLabel('ZZZ', NAMES)).toBe('ZZZ')
  })

  it('handles the empty string without throwing', () => {
    expect(provinceLabel('', NAMES)).toBe('')
  })
})

describe('provinceName', () => {
  it('returns the bare name for prose', () => {
    expect(provinceName('NTH', NAMES)).toBe('North Sea')
    expect(provinceName('STP/NC', NAMES)).toBe('St Petersburg')
  })

  it('falls back to the code when unknown', () => {
    expect(provinceName('ZZZ', NAMES)).toBe('ZZZ')
  })
})

describe('glossOrder', () => {
  it('reads a move in plain English', () => {
    expect(glossOrder('A BER - KIE', NAMES)).toBe('Army Berlin → Kiel')
  })

  it('reads a hold', () => {
    expect(glossOrder('A BER H', NAMES)).toBe('Army Berlin holds')
  })

  it('reads a support-move', () => {
    expect(glossOrder('A MUN S A BER - SIL', NAMES)).toBe(
      'Army Munich supports Army Berlin → Silesia'
    )
  })

  it('reads a convoy', () => {
    expect(glossOrder('F NTH C A BER - KIE', NAMES)).toBe(
      'Fleet North Sea convoys Army Berlin → Kiel'
    )
  })

  it('reads a retreat', () => {
    expect(glossOrder('A MUN R SIL', NAMES)).toBe('Army Munich retreats to Silesia')
  })

  it('returns null when nothing could be expanded, so no empty second line renders', () => {
    expect(glossOrder('A BER - KIE', {})).toBeNull()
    expect(glossOrder('WAIVE', NAMES)).toBeNull()
    expect(glossOrder('', NAMES)).toBeNull()
  })

  it('leaves unrecognised tokens alone instead of dropping them', () => {
    expect(glossOrder('A BER - KIE VIA CONVOY', NAMES)).toBe(
      'Army Berlin → Kiel VIA CONVOY'
    )
  })

  it('never emits a province code that a player could paste as an order', () => {
    // The gloss is display-only; G1's whole finding was that full province names
    // do not parse, so this string must never be mistaken for a submittable order.
    const gloss = glossOrder('A BER - KIE', NAMES)
    expect(gloss).not.toContain('BER')
    expect(gloss).not.toContain('KIE')
  })
})
