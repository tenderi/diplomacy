import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, within, waitFor, fireEvent, cleanup } from '@testing-library/react'
import PreviousTurns, { phaseLabel } from './PreviousTurns'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const entry = (
  power: string,
  type: string,
  order: Record<string, unknown>,
  order_str: string,
  result: string,
  dislodged = false
) => ({ order: { type, power, ...order }, result, dislodged, retreat_options: [], power, order_str })

const resolutions = {
  // The newest turn is already shown as "What happened last turn": it must not be offered here.
  '2': { phase: 'F1902M', results: [entry('FRANCE', 'HOLD', { unit: 'PAR' }, 'A PAR H', 'OK')] },
  '1': {
    phase: 'S1902M',
    results: [
      entry('FRANCE', 'MOVE', { unit: 'BRE', dest: 'ENG' }, 'F BRE - ENG', 'BOUNCE'),
      entry('ENGLAND', 'HOLD', { unit: 'LON' }, 'A LON H', 'OK'),
    ],
  },
  '0': {
    phase: 'F1901M',
    results: [
      entry('FRANCE', 'HOLD', { unit: 'MAR' }, 'A MAR H', 'DISLODGED', true),
      entry('ITALY', 'MOVE', { unit: 'PIE', dest: 'MAR' }, 'A PIE - MAR', 'OK'),
    ],
  },
}

function stub(body: unknown, ok = true) {
  const fetchMock = vi.fn(() =>
    Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body), text: () => Promise.resolve('') } as Response)
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('phaseLabel', () => {
  it('spells out a phase code', () => {
    expect(phaseLabel('F1902M')).toBe('Fall 1902 movement')
    expect(phaseLabel('S1903R')).toBe('Spring 1903 retreat')
    expect(phaseLabel('W1901A')).toBe('Winter 1901 adjustment')
    expect(phaseLabel('Turn 3')).toBe('Turn 3')
  })
})

describe('PreviousTurns', () => {
  it('makes the turn select at least 40px tall (DW5)', async () => {
    stub({ resolutions })
    const { container } = render(<PreviousTurns gameId="7" phase="S1903M" myPower="FRANCE" />)
    const select = await within(container).findByLabelText('Previous turn')
    expect(select.classList.contains('h-10')).toBe(true)
  })

  it('lists the turns before the newest, newest first, and shows the selected one', async () => {
    stub({ resolutions })
    const { container } = render(<PreviousTurns gameId="7" phase="S1903M" myPower="FRANCE" />)
    const select = (await within(container).findByLabelText('Previous turn')) as HTMLSelectElement
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual([
      'Spring 1902 movement',
      'Fall 1901 movement',
    ])
    expect(within(container).getByText('F BRE - ENG')).toBeInTheDocument()
    expect(
      within(container).getByText('Move was blocked (bounced) — the unit stayed in place.')
    ).toBeInTheDocument()

    fireEvent.change(select, { target: { value: '0' } })
    expect(within(container).getByText('A MAR H')).toBeInTheDocument()
    expect(within(container).getByText('Unit was dislodged by A PIE (ITALY).')).toBeInTheDocument()
    expect(within(container).queryByText('F BRE - ENG')).toBeNull()
  })

  it('shows nothing when there is no earlier turn, or the request fails', async () => {
    const fetchMock = stub({ resolutions: { '0': resolutions['0'] } })
    const { container } = render(<PreviousTurns gameId="7" phase="F1901M" myPower="FRANCE" />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(container.textContent).toBe('')
    cleanup()
    stub({}, false)
    const second = render(<PreviousTurns gameId="7" phase="F1901M" myPower="FRANCE" />)
    await waitFor(() => expect(second.container.textContent).toBe(''))
  })

  // DP1: F1901M, then its retreat phase, then the Winter builds.
  const withRetreat = {
    '3': { phase: 'W1901A', results: [entry('RUSSIA', 'BUILD', { location: 'MOS' }, 'BUILD A MOS', 'BUILD')] },
    '2': {
      phase: 'F1901R',
      results: [{ ...entry('GERMANY', 'DISBAND', { unit: 'BUR' }, 'D A BUR', 'DISBAND'), civil_disorder: true }],
    },
    '1': {
      phase: 'F1901M',
      results: [
        entry('RUSSIA', 'MOVE', { unit: 'UKR', dest: 'RUM' }, 'A UKR - RUM', 'OK'),
        entry('GERMANY', 'HOLD', { unit: 'BUR' }, 'A BUR H', 'DISLODGED', true),
      ],
    },
    '0': { phase: 'S1901M', results: [entry('RUSSIA', 'MOVE', { unit: 'MOS', dest: 'UKR' }, 'A MOS - UKR', 'OK')] },
  }

  it('opens on the season before last turn, its movement and retreats together (DP1)', async () => {
    stub({ resolutions: withRetreat })
    const { container } = render(<PreviousTurns gameId="7" phase="S1902M" myPower="RUSSIA" />)
    const select = (await within(container).findByLabelText('Previous turn')) as HTMLSelectElement
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual([
      'Fall 1901 movement and retreats',
      'Spring 1901 movement',
    ])
    expect(within(container).getByText('A UKR - RUM')).toBeInTheDocument()
    expect(within(container).getByRole('heading', { name: 'Retreats' })).toBeInTheDocument()
    expect(within(container).getByText('RUSSIA had no units to retreat.')).toBeInTheDocument()
  })

  it('does not repeat a movement turn that last turn already shows with its retreats (DP1)', async () => {
    const { '3': _winter, ...upToRetreat } = withRetreat
    void _winter
    stub({ resolutions: upToRetreat })
    const { container } = render(<PreviousTurns gameId="7" phase="W1901A" myPower="RUSSIA" />)
    const select = (await within(container).findByLabelText('Previous turn')) as HTMLSelectElement
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual(['Spring 1901 movement'])
    expect(within(container).queryByText('A UKR - RUM')).toBeNull()
  })

  it('tells a viewer without a power to join one', async () => {
    stub({ resolutions })
    const { container } = render(<PreviousTurns gameId="7" phase="S1903M" myPower={null} />)
    expect(await within(container).findByText('Join a power to see how its orders resolved.')).toBeInTheDocument()
  })
})
