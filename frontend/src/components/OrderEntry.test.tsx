import { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { type OrderResultEntry } from '@/lib/resultText'
import { groupLegalOrdersByType, parseLegalOrder } from '@/lib/orderParsing'
import { BuildOrdersSection, ResultList, UnitOrdersSection, describeTarget } from './OrderEntry'

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


const RETREAT_ORDERS = ['A MUN R BOH', 'A MUN R TYR', 'D A MUN']

function RetreatHarness({ orders = RETREAT_ORDERS }: { orders?: string[] }) {
  const [sel, setSel] = useState<Record<string, string>>({})
  return (
    <>
      <UnitOrdersSection
        phase="Retreat"
        myUnits={[{ unit_type: 'A', province: 'MUN', is_dislodged: true }]}
        orderByUnit={sel}
        setOrderByUnit={setSel}
        legalOrdersByUnit={{ 'A MUN': { orders, grouped: groupLegalOrdersByType(orders) } }}
        loading={false}
        onSubmit={() => {}}
      />
      <output data-testid="sel">{JSON.stringify(sel)}</output>
    </>
  )
}

describe('retreat phase', () => {
  it('says an unordered dislodged unit is disbanded', () => {
    render(<RetreatHarness />)
    expect(screen.getByRole('combobox', { name: 'Order type for A MUN' }).textContent).toBe(
      'No order (disbands)'
    )
    expect(screen.getByText(/One row per unit/).textContent).toBe(
      'One row per unit. Choose order type, then target. A dislodged unit with no order is disbanded.'
    )
  })

  it.each([[RETREAT_ORDERS], [['D A MUN']]])('offers Disband and submits the legal string', async (orders) => {
    render(<RetreatHarness orders={orders} />)
    open('Order type for A MUN')
    const names = (await screen.findAllByRole('option')).map((o) => o.textContent)
    expect(names).toEqual(orders.length > 1 ? ['Retreat', 'Disband'] : ['Disband'])
    fireEvent.click(screen.getByRole('option', { name: 'Disband' }))
    expect(screen.getByTestId('sel').textContent).toBe('{"A MUN":"D A MUN"}')
    expect(submitDisabled()).toBe(false)
  })
})

describe('BuildOrdersSection', () => {
  it('does not offer a province already chosen in another slot, on any coast', async () => {
    const orders = ['BUILD F STP/SC', 'BUILD F STP/NC', 'BUILD A MOS']
    render(
      <BuildOrdersSection
        adjustment={{ action: 'build', slots: 2 } as never}
        orders={orders}
        buildOrderSlots={['BUILD F STP/SC', '']}
        setBuildOrderSlots={() => {}}
        loading={false}
      />
    )
    open('Build or destroy order for slot 2')
    const names = (await screen.findAllByRole('option')).map((o) => o.textContent)
    expect(names).toEqual(['Build army – MOS'])
  })

  it('says how many builds and why, and labels options with verb, name and coast', async () => {
    const names = { STP: 'St Petersburg', MOS: 'Moscow' }
    render(
      <BuildOrdersSection
        adjustment={{ action: 'build', delta: 2, slots: 2, centers: 6, units: 4 }}
        orders={['BUILD F STP/SC', 'BUILD A MOS', 'WAIVE']}
        provinceNames={names}
        buildOrderSlots={['', '']}
        setBuildOrderSlots={() => {}}
        loading={false}
      />
    )
    expect(screen.getByText(/^2 builds: 6 centres, 4 units/).textContent).toBe(
      '2 builds: 6 centres, 4 units. Select one order per slot, or waive.'
    )
    open('Build or destroy order for slot 1')
    const labels = (await screen.findAllByRole('option')).map((o) => o.textContent)
    expect(labels).toEqual([
      'Build fleet – St Petersburg (south coast)',
      'Build army – Moscow',
      'Waive (build nothing)',
    ])
  })

  it('uses the singular for one centre or one unit', () => {
    render(
      <BuildOrdersSection
        adjustment={{ action: 'disband', delta: -1, slots: 1, centers: 1, units: 2 }}
        orders={['D A MUN']}
        provinceNames={{ MUN: 'Munich' }}
        buildOrderSlots={['']}
        setBuildOrderSlots={() => {}}
        loading={false}
      />
    )
    expect(screen.getByText(/^1 disband:/).textContent).toBe(
      '1 disband: 1 centre, 2 units. Select a unit to remove per slot.'
    )
  })

  it('names a disband count and labels disbands', async () => {
    render(
      <BuildOrdersSection
        adjustment={{ action: 'disband', delta: -1, slots: 1, centers: 3, units: 4 }}
        orders={['D A MUN']}
        provinceNames={{ MUN: 'Munich' }}
        buildOrderSlots={['']}
        setBuildOrderSlots={() => {}}
        loading={false}
      />
    )
    expect(screen.getByText(/^1 disband:/).textContent).toBe(
      '1 disband: 3 centres, 4 units. Select a unit to remove per slot.'
    )
    open('Build or destroy order for slot 1')
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual([
      'Disband A MUN – Munich',
    ])
  })
})
