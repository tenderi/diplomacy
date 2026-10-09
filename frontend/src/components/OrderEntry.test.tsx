import { render, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { type OrderResultEntry } from '@/lib/resultText'
import { ResultList } from './OrderEntry'

function disband(unit: string, civil_disorder: boolean): OrderResultEntry {
  return {
    order: { type: 'DISBAND', power: 'GERMANY', unit },
    result: 'DISBAND',
    dislodged: false,
    retreat_options: [],
    civil_disorder,
    power: 'GERMANY',
    order_str: `D A ${unit}`,
  }
}

describe('ResultList', () => {
  it('tells a civil-disorder disband from an ordered one', () => {
    const { container } = render(
      <ResultList entries={[disband('MUN', true), disband('BER', false)]} showPower />
    )
    const items = within(container).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0].textContent).toBe(
      'GERMANY: D A MUNDisbanded by civil disorder: too few disbands were ordered.'
    )
    expect(items[1].textContent).toBe('GERMANY: D A BERUnit was disbanded.')
  })
})
