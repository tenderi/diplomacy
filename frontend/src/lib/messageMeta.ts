/**
 * Helpers for the game page's message log (BR5): a short local time, and which
 * messages are new since the viewer last saw the log.
 */

/** The API sends naive UTC (`2026-10-24T09:05:00`); read it as UTC, not local time. */
export function parseUtc(iso: string): Date {
  return new Date(/([zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`)
}

/** "24 Oct, 11:05" in the viewer's zone, or '' when the time is missing or unreadable. */
export function formatMessageTime(
  iso: string | undefined | null,
  locale?: string,
  timeZone?: string
): string {
  if (!iso) return ''
  const d = parseUtc(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(locale ?? 'en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone,
  })
}

const seenKey = (gameId: string | undefined) => `diplomacy:messages-seen:${gameId}`

/** The newest message id the viewer has seen in this game (0 when never, or no storage). */
export function readSeenMessageId(gameId: string | undefined): number {
  try {
    const n = Number(window.localStorage.getItem(seenKey(gameId)))
    return Number.isFinite(n) && n > 0 ? n : 0
  } catch {
    return 0
  }
}

export function writeSeenMessageId(gameId: string | undefined, id: number): void {
  try {
    if (id > readSeenMessageId(gameId)) window.localStorage.setItem(seenKey(gameId), String(id))
  } catch {
    // storage unavailable (private mode): the log just marks everything new next visit
  }
}

/** Ids of messages newer than `seen` that the viewer did not write themselves. */
export function unreadMessageIds(
  messages: { id?: number; sender_power?: string | null }[],
  seen: number,
  myPower: string | null
): Set<number> {
  const out = new Set<number>()
  for (const m of messages) {
    if (m.id === undefined || m.id <= seen) continue
    if (myPower && m.sender_power === myPower) continue
    out.add(m.id)
  }
  return out
}
