import { useState } from 'react'
import { toast } from 'sonner'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { parseUtc } from '@/lib/messageMeta'

/** `pending_proposal` of `GET /games/{id}/deadline`: a majority vote to change the deadline. */
export type DeadlineProposal = {
  proposed_by: string
  /** Hours from the moment it passes; null proposes clearing the deadline. */
  value_hours: number | null
  yes_votes: string[]
  no_votes: string[]
  needed_for_majority: number
  vote_deadline?: string | null
}

const MAX_HOURS = 24 * 30

/** Hours as the bot reads them: more than 0 and at most 30 days, or null if it is not that. */
function parseHours(text: string): number | null {
  const n = Number(text.trim().replace(/h$/i, ''))
  return text.trim() !== '' && Number.isFinite(n) && n > 0 && n <= MAX_HOURS ? n : null
}

function localTime(iso: string): string {
  return parseUtc(iso).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })
}

/**
 * The deadline controls of the Telegram bot's `/deadline`, for a seated player of an active
 * game: set or clear this phase's deadline, a weekly schedule, and propose a change to a
 * majority vote (then vote, or withdraw your own). The API lets any player set a deadline
 * or schedule and only the power's own user propose/vote/withdraw, so one card serves every
 * seated player. `onChanged` re-reads the page's deadline state after each action.
 */
export function DeadlineCard({
  gameId,
  power,
  proposal,
  hasSchedule,
  onChanged,
}: {
  gameId: string
  power: string
  proposal: DeadlineProposal | null
  hasSchedule: boolean
  onChanged: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [setHours, setSetHours] = useState('')
  const [proposeHours, setProposeHours] = useState('')
  const [voteHours, setVoteHours] = useState('')
  const [days, setDays] = useState('')
  const [time, setTime] = useState('')
  const [zone, setZone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC')

  const post = async (path: string, body: unknown, ok: string): Promise<boolean> => {
    setBusy(true)
    try {
      await apiJson(`/games/${gameId}/${path}`, { method: 'POST', body: JSON.stringify(body) })
      toast.success(ok)
      onChanged()
      return true
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Request failed')
      return false
    } finally {
      setBusy(false)
    }
  }

  const setDeadline = async (hours: number | null) => {
    const ok = await post(
      'deadline',
      { deadline: hours === null ? null : new Date(Date.now() + hours * 3600_000).toISOString() },
      hours === null ? 'The deadline is removed.' : 'The deadline is set.'
    )
    if (ok) setSetHours('')
  }

  const propose = async (hours: number | null) => {
    const vote = voteHours.trim() === '' ? null : parseHours(voteHours)
    if (voteHours.trim() !== '' && vote === null) {
      toast.error('Vote hours must be more than 0 and at most 720 (30 days).')
      return
    }
    const ok = await post(
      'deadline/propose',
      { power, hours, vote_hours: vote },
      'Proposal sent: the other players can vote on it.'
    )
    if (ok) setProposeHours('')
  }

  const setSchedule = () => {
    if (days.trim() === '' || !/^\d{1,2}:\d{2}$/.test(time.trim())) {
      toast.error('Give the days (e.g. mon,wed,fri) and a time as HH:MM.')
      return
    }
    void post(
      'deadline/schedule',
      { schedule: `${days.trim()} ${time.trim()}`, timezone: zone.trim() || 'UTC' },
      'The weekly schedule is set.'
    )
  }

  const myVote = proposal
    ? proposal.yes_votes.includes(power)
      ? 'yes'
      : proposal.no_votes.includes(power)
        ? 'no'
        : null
    : null
  const mine = proposal?.proposed_by === power
  const row = 'flex flex-wrap items-center gap-2'

  return (
    <div className="space-y-3 border-t pt-3" data-testid="deadline-card">
      {proposal && (
        <div className="space-y-2 rounded-md border p-3" data-testid="deadline-proposal">
          <p className="text-sm font-medium">
            Deadline proposal from {proposal.proposed_by}:{' '}
            {proposal.value_hours === null ? 'clear the deadline' : `${proposal.value_hours}h from when it passes`}
          </p>
          <p className="text-sm">
            Yes {proposal.yes_votes.length}/{proposal.needed_for_majority} needed
            {proposal.yes_votes.length > 0 && ` (${proposal.yes_votes.join(', ')})`}
            {' · '}No {proposal.no_votes.length}
            {proposal.no_votes.length > 0 && ` (${proposal.no_votes.join(', ')})`}
          </p>
          {proposal.vote_deadline && (
            <p className="text-sm text-muted-foreground">Vote closes {localTime(proposal.vote_deadline)}.</p>
          )}
          {myVote && <p className="text-sm text-muted-foreground">You voted {myVote}.</p>}
          <div className={row}>
            <Button size="sm" disabled={busy} onClick={() => void post('deadline/vote', { power, vote: true }, 'Vote cast: yes.')}>
              Vote yes
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void post('deadline/vote', { power, vote: false }, 'Vote cast: no.')}
            >
              Vote no
            </Button>
            {mine && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => void post('deadline/withdraw', { power }, 'Proposal withdrawn.')}
              >
                Withdraw
              </Button>
            )}
          </div>
        </div>
      )}

      {/* DP4: the three controls and their help are the bulk of the turn status; they
          stay folded behind one line until a player wants to change the deadline. */}
      <details className="group" data-testid="deadline-controls">
        <summary className="cursor-pointer text-sm font-medium text-primary min-h-11 sm:min-h-0 flex items-center">
          Change the deadline or schedule
        </summary>
      <div className="mt-3 space-y-4">
      <div className="space-y-1">
        <p className="text-sm font-medium">Set this phase&apos;s deadline</p>
        <div className={row}>
          <Input
            className="h-9 w-24"
            aria-label="Deadline in hours"
            inputMode="decimal"
            placeholder="hours"
            value={setHours}
            onChange={(e) => setSetHours(e.target.value)}
          />
          <Button size="sm" disabled={busy || parseHours(setHours) === null} onClick={() => void setDeadline(parseHours(setHours))}>
            Set deadline
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => void setDeadline(null)}>
            Clear deadline
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Hours from now; the time shows in your local time. Everyone is told. To change it by majority vote instead,
          propose it below.
        </p>
      </div>

      {!proposal && (
        <div className="space-y-1">
          <p className="text-sm font-medium">Propose a deadline to a vote</p>
          <div className={row}>
            <Input
              className="h-9 w-24"
              aria-label="Proposed deadline in hours"
              inputMode="decimal"
              placeholder="hours"
              value={proposeHours}
              onChange={(e) => setProposeHours(e.target.value)}
            />
            <Input
              className="h-9 w-28"
              aria-label="Vote open for hours"
              inputMode="decimal"
              placeholder="vote hours"
              value={voteHours}
              onChange={(e) => setVoteHours(e.target.value)}
            />
            <Button size="sm" disabled={busy || parseHours(proposeHours) === null} onClick={() => void propose(parseHours(proposeHours))}>
              Propose
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void propose(null)}>
              Propose clearing
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Vote hours (optional) is how long the vote stays open. A majority of the active powers decides.
          </p>
        </div>
      )}

      <div className="space-y-1">
        <p className="text-sm font-medium">Weekly schedule</p>
        <div className={row}>
          <Input
            className="h-9 w-36"
            aria-label="Schedule days"
            placeholder="mon,wed,fri"
            value={days}
            onChange={(e) => setDays(e.target.value)}
          />
          <Input
            className="h-9 w-24"
            aria-label="Schedule time"
            placeholder="16:00"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
          <Input className="h-9 w-44" aria-label="Schedule timezone" value={zone} onChange={(e) => setZone(e.target.value)} />
          <Button size="sm" disabled={busy} onClick={setSchedule}>
            Set schedule
          </Button>
          {hasSchedule && (
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void post('deadline/schedule', { schedule: null }, 'The weekly schedule is removed.')}
            >
              Remove schedule
            </Button>
          )}
        </div>
      </div>
      </div>
      </details>
    </div>
  )
}
