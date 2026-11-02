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

  it('tells a viewer without a power to join one', async () => {
    stub({ resolutions })
    const { container } = render(<PreviousTurns gameId="7" phase="S1903M" myPower={null} />)
    expect(await within(container).findByText('Join a power to see how its orders resolved.')).toBeInTheDocument()
  })
})
