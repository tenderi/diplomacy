import { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { type OrderResultEntry } from '@/lib/resultText'
import { groupLegalOrdersByType, parseLegalOrder } from '@/lib/orderParsing'
import { ResultList, UnitOrdersSection, describeTarget } from './OrderEntry'

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

const GROUPED_ORDERS = [
  'F EDI H',
  'F EDI - CLY',
  'F EDI - NTH',
  'F EDI S F LON - NTH',
  'F EDI S A LVP H',
]

function Harness({ names = {}, phaseCode }: { names?: Record<string, string>; phaseCode?: string }) {
  const [orders, setOrders] = useState<Record<string, string>>({})
  return (
    <UnitOrdersSection
      phase="Movement"
      myUnits={[{ unit_type: 'F', province: 'EDI' }]}
      orderByUnit={orders}
      setOrderByUnit={setOrders}
      legalOrdersByUnit={{
        'F EDI': { orders: GROUPED_ORDERS, grouped: groupLegalOrdersByType(GROUPED_ORDERS) },
      }}
      loading={false}
      onSubmit={() => {}}
      provinceNames={names}
      phaseCode={phaseCode}
    />
  )
}

afterEach(cleanup)

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.setPointerCapture ??= () => {}
  Element.prototype.releasePointerCapture ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

function open(name: string) {
  fireEvent.keyDown(screen.getByRole('combobox', { name }), { key: 'Enter' })
}

function submitDisabled(): boolean {
  return (screen.getByRole('button', { name: 'Submit orders' }) as HTMLButtonElement).disabled
}

describe('UnitOrdersSection', () => {
  it('shows an unordered unit as holding', () => {
    render(<Harness />)
    expect(screen.getByRole('combobox', { name: 'Order type for F EDI' }).textContent).toBe(
      'No order (holds)'
    )
  })

  it('leaves the target empty after choosing Move and blocks Submit with a reason', async () => {
    render(<Harness />)
    open('Order type for F EDI')
    fireEvent.click(await screen.findByRole('option', { name: 'Move' }))
    expect(screen.getByRole('combobox', { name: 'Target for F EDI order' }).textContent).toBe(
      'Choose target'
    )
    expect(submitDisabled()).toBe(true)
    expect(screen.getByText('Choose a target for F EDI before submitting.')).toBeTruthy()
  })

  it('enables Submit once a target is chosen, and names the province', async () => {
    render(<Harness names={{ NTH: 'North Sea', CLY: 'Clyde' }} />)
    open('Order type for F EDI')
    fireEvent.click(await screen.findByRole('option', { name: 'Move' }))
    open('Target for F EDI order')
    const options = (await screen.findAllByRole('option')).map((o) => o.textContent)
    expect(options).toEqual(['CLY – Clyde', 'NTH – North Sea'])
    fireEvent.click(screen.getByRole('option', { name: 'NTH – North Sea' }))
    expect(submitDisabled()).toBe(false)
  })

  it('forgets a half-made choice when the phase changes', async () => {
    const { rerender } = render(<Harness phaseCode="S1901M" />)
    open('Order type for F EDI')
    fireEvent.click(await screen.findByRole('option', { name: 'Move' }))
    expect(submitDisabled()).toBe(true)
    rerender(<Harness phaseCode="F1901M" />)
    expect(screen.getByRole('combobox', { name: 'Order type for F EDI' }).textContent).toBe(
      'No order (holds)'
    )
    expect(submitDisabled()).toBe(false)
  })

  it('does not require a target for Hold', async () => {
    render(<Harness />)
    open('Order type for F EDI')
    fireEvent.click(await screen.findByRole('option', { name: 'Hold' }))
    expect(submitDisabled()).toBe(false)
  })
})

describe('describeTarget', () => {
  const names = { NTH: 'North Sea', LON: 'London', LVP: 'Liverpool' }
  const owners = { LON: 'ENGLAND', LVP: 'ENGLAND' }
  it('names the supported unit owner and destination', () => {
    const opt = parseLegalOrder('F EDI S F LON - NTH')!
    expect(describeTarget(opt, names, owners)).toBe('F LON (ENGLAND) → NTH – North Sea')
    const hold = parseLegalOrder('F EDI S A LVP H')!
    expect(describeTarget(hold, names, owners)).toBe('A LVP (ENGLAND) (hold)')
  })
  it('keeps a bare code when the name is unknown', () => {
    expect(describeTarget(parseLegalOrder('F EDI - CLY')!, {})).toBe('CLY')
  })
})
