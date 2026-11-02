import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { formatDeadline } from './deadline'

// Helsinki is UTC+2/+3: a naive deadline read as local time comes out 2-3 h short. CI runs
// in UTC, where that mistake is invisible, so force a non-UTC zone for these tests.
declare const process: { env: Record<string, string | undefined> }
const savedTz = process.env.TZ
beforeAll(() => {
  process.env.TZ = 'Europe/Helsinki'
})
afterAll(() => {
  process.env.TZ = savedTz
})

describe('formatDeadline', () => {
  const now = Date.UTC(2026, 9, 27, 16, 0) // 16:00 UTC, 18:00 in Helsinki

  it('the test zone really is not UTC', () => {
    expect(new Date(now).getTimezoneOffset()).toBe(-120)
  })

  it('reads a naive deadline as UTC, not local time', () => {
    expect(formatDeadline('2026-10-27T18:30:00', now, 'UTC')).toBe('2h 30m left — Tue 18:30')
  })

  it('reads an aware UTC deadline', () => {
    expect(formatDeadline('2026-10-27T18:30:00+00:00', now, 'UTC')).toBe('2h 30m left — Tue 18:30')
    expect(formatDeadline('2026-10-28T18:30:00Z', now, 'UTC')).toBe('1d 2h 30m left — Wed 18:30')
  })

  it('says when there is none or it has passed', () => {
    expect(formatDeadline(null, now)).toBe('No deadline set for this phase.')
    expect(formatDeadline('not a date', now)).toBe('No deadline set for this phase.')
    expect(formatDeadline('2026-10-27T15:59:00+00:00', now)).toBe(
      'Deadline has passed — waiting for the turn to be processed.',
    )
  })

  it('shows the absolute deadline in the viewer zone (Helsinki here)', () => {
    expect(formatDeadline('2026-10-27T18:30:00+00:00', now)).toBe('2h 30m left — Tue 20:30')
    // 22:30 UTC on Tuesday is already Wednesday 00:30 in Helsinki.
    expect(formatDeadline('2026-10-27T22:30:00+00:00', now)).toBe('6h 30m left — Wed 00:30')
  })

  it('says "less than a minute" instead of 0m', () => {
    expect(formatDeadline('2026-10-27T16:00:20+00:00', now, 'UTC')).toBe(
      'less than a minute left — Tue 16:00',
    )
    expect(formatDeadline('2026-10-27T16:01:00+00:00', now, 'UTC')).toBe('1m left — Tue 16:01')
  })
})
