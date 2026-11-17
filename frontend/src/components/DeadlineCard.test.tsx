import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { toast } from 'sonner'
import { DeadlineCard, type DeadlineProposal } from './DeadlineCard'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

function respond(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response)
}

const PROPOSAL: DeadlineProposal = {
  proposed_by: 'FRANCE',
  value_hours: 24,
  yes_votes: ['FRANCE'],
  no_votes: ['ITALY'],
  needed_for_majority: 4,
  vote_deadline: null,
}

function setup(over: Partial<{ proposal: DeadlineProposal | null; hasSchedule: boolean; power: string }> = {}, res = () => respond({ status: 'ok' })) {
  const fetchMock = vi.fn(res)
  vi.stubGlobal('fetch', fetchMock)
  const onChanged = vi.fn()
  render(
    <DeadlineCard gameId="7" power={over.power ?? 'ENGLAND'} proposal={over.proposal ?? null} hasSchedule={over.hasSchedule ?? false} onChanged={onChanged} />
  )
  const last = () => {
    const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as unknown as [string, RequestInit]
    return { url, init, body: JSON.parse(String(init.body)) }
  }
  return { fetchMock, onChanged, last }
}

describe('DeadlineCard', () => {
  it('sets the deadline as a UTC instant N hours from now and refreshes the page', async () => {
    const { last, onChanged } = setup()
    const before = Date.now()
    fireEvent.change(screen.getByLabelText('Deadline in hours'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Set deadline' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
    const { url, body } = last()
    expect(url).toMatch(/\/games\/7\/deadline$/)
    const sent = Date.parse(body.deadline)
    expect(body.deadline).toMatch(/Z$/)
    expect(sent).toBeGreaterThanOrEqual(before + 2 * 3600_000)
    expect(sent).toBeLessThanOrEqual(Date.now() + 2 * 3600_000)
    expect(toast.success).toHaveBeenCalledWith('The deadline is set.')
  })

  it('keeps Set deadline disabled until the hours are valid', () => {
    setup()
    const button = screen.getByRole('button', { name: 'Set deadline' })
    expect(button).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Deadline in hours'), { target: { value: '721' } })
    expect(button).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Deadline in hours'), { target: { value: '12h' } })
    expect(button).toBeEnabled()
  })

  it('clears the deadline with a null', async () => {
    const { last, onChanged } = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Clear deadline' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(last().body).toEqual({ deadline: null })
  })

  it('shows the server message when a request is refused, and does not refresh', async () => {
    const { onChanged } = setup({}, () => respond({ detail: 'That deadline has already passed.' }, 422))
    fireEvent.click(screen.getByRole('button', { name: 'Clear deadline' }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('That deadline has already passed.'))
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('proposes a deadline with the optional vote length, or proposes clearing it', async () => {
    const { last, onChanged } = setup()
    fireEvent.change(screen.getByLabelText('Proposed deadline in hours'), { target: { value: '48' } })
    fireEvent.change(screen.getByLabelText('Vote open for hours'), { target: { value: '6' } })
    fireEvent.click(screen.getByRole('button', { name: 'Propose' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
    expect(last().url).toMatch(/\/games\/7\/deadline\/propose$/)
    expect(last().body).toEqual({ power: 'ENGLAND', hours: 48, vote_hours: 6 })
    fireEvent.click(screen.getByRole('button', { name: 'Propose clearing' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(2))
    expect(last().body).toEqual({ power: 'ENGLAND', hours: null, vote_hours: 6 })
  })

  it('refuses bad vote hours without sending', () => {
    const { fetchMock } = setup()
    fireEvent.change(screen.getByLabelText('Vote open for hours'), { target: { value: 'abc' } })
    fireEvent.click(screen.getByRole('button', { name: 'Propose clearing' }))
    expect(toast.error).toHaveBeenCalledWith('Vote hours must be more than 0 and at most 720 (30 days).')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows a pending proposal with its tally and votes yes and no for the viewer power', async () => {
    const { last, onChanged } = setup({ proposal: PROPOSAL })
    const box = screen.getByTestId('deadline-proposal')
    expect(box).toHaveTextContent('Deadline proposal from FRANCE: 24h from when it passes')
    expect(box).toHaveTextContent('Yes 1/4 needed (FRANCE)')
    expect(box).toHaveTextContent('No 1 (ITALY)')
    expect(screen.queryByRole('button', { name: 'Propose' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Vote yes' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
    expect(last().url).toMatch(/\/games\/7\/deadline\/vote$/)
    expect(last().body).toEqual({ power: 'ENGLAND', vote: true })
    fireEvent.click(screen.getByRole('button', { name: 'Vote no' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(2))
    expect(last().body).toEqual({ power: 'ENGLAND', vote: false })
  })

  it('offers Withdraw only to the proposer, and shows their own vote', async () => {
    cleanup()
    const { last, onChanged } = setup({ proposal: PROPOSAL, power: 'FRANCE' })
    expect(screen.getByText('You voted yes.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Withdraw' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(last().url).toMatch(/\/games\/7\/deadline\/withdraw$/)
    expect(last().body).toEqual({ power: 'FRANCE' })
  })

  it('does not offer Withdraw to another player, and a clearing proposal reads as such', () => {
    setup({ proposal: { ...PROPOSAL, value_hours: null } })
    expect(screen.queryByRole('button', { name: 'Withdraw' })).toBeNull()
    expect(screen.getByTestId('deadline-proposal')).toHaveTextContent('clear the deadline')
  })

  it('sets and removes the weekly schedule', async () => {
    const { last, onChanged } = setup({ hasSchedule: true })
    fireEvent.change(screen.getByLabelText('Schedule days'), { target: { value: 'mon,wed' } })
    fireEvent.change(screen.getByLabelText('Schedule time'), { target: { value: '16:00' } })
    fireEvent.change(screen.getByLabelText('Schedule timezone'), { target: { value: 'Europe/Helsinki' } })
    fireEvent.click(screen.getByRole('button', { name: 'Set schedule' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
    expect(last().url).toMatch(/\/games\/7\/deadline\/schedule$/)
    expect(last().body).toEqual({ schedule: 'mon,wed 16:00', timezone: 'Europe/Helsinki' })
    fireEvent.click(screen.getByRole('button', { name: 'Remove schedule' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(2))
    expect(last().body).toEqual({ schedule: null })
  })

  it('hides Remove schedule when there is none and rejects a malformed time', () => {
    const { fetchMock } = setup()
    expect(screen.queryByRole('button', { name: 'Remove schedule' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Set schedule' }))
    expect(toast.error).toHaveBeenCalledWith('Give the days (e.g. mon,wed,fri) and a time as HH:MM.')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('DeadlineCard folding (DP4)', () => {
  it('keeps the three controls behind a closed summary and a pending proposal outside it', () => {
    setup({ proposal: PROPOSAL })
    const folded = screen.getByTestId('deadline-controls') as HTMLDetailsElement
    expect(folded.tagName).toBe('DETAILS')
    expect(folded.open).toBe(false)
    expect(folded.querySelector('summary')!.textContent).toContain('Change the deadline or schedule')
    expect(folded.contains(screen.getByLabelText('Deadline in hours'))).toBe(true)
    expect(folded.contains(screen.getByLabelText('Schedule days'))).toBe(true)
    expect(folded.contains(screen.getByRole('button', { name: 'Vote yes' }))).toBe(false)
  })
})
