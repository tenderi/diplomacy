import { describe, it, expect, beforeEach } from 'vitest'
import {
  formatMessageTime,
  readSeenMessageId,
  unreadMessageIds,
  writeSeenMessageId,
} from './messageMeta'

describe('formatMessageTime', () => {
  it('reads the naive API time as UTC and shows it in the given zone', () => {
    expect(formatMessageTime('2026-10-24T09:05:00', 'en-GB', 'UTC')).toBe('24 Oct, 09:05')
    expect(formatMessageTime('2026-10-24T09:05:00', 'en-GB', 'Europe/Helsinki')).toBe('24 Oct, 12:05')
  })
  it('returns nothing for a missing or unreadable time', () => {
    expect(formatMessageTime(undefined)).toBe('')
    expect(formatMessageTime('not a date')).toBe('')
  })
})

describe('unreadMessageIds', () => {
  const msgs = [
    { id: 1, sender_power: 'GERMANY' },
    { id: 2, sender_power: 'FRANCE' },
    { id: 3, sender_power: 'GERMANY' },
    { id: 4, sender_power: null },
  ]
  it("marks messages newer than the last seen, except the viewer's own", () => {
    expect([...unreadMessageIds(msgs, 1, 'FRANCE')]).toEqual([3, 4])
  })
  it('marks everything when nothing was seen', () => {
    expect([...unreadMessageIds(msgs, 0, null)]).toEqual([1, 2, 3, 4])
  })
})

describe('seen message id', () => {
  beforeEach(() => window.localStorage.clear())
  it('is stored per game and only moves forward', () => {
    expect(readSeenMessageId('7')).toBe(0)
    writeSeenMessageId('7', 5)
    writeSeenMessageId('7', 3)
    expect(readSeenMessageId('7')).toBe(5)
    expect(readSeenMessageId('8')).toBe(0)
  })
})
