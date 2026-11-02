import { parseUtc } from '@/lib/messageMeta'

/** Render a submission/order deadline as a short relative countdown. The API sends aware UTC;
 * a naive string is UTC too (`parseUtc`), never the viewer's local time. */
export function formatDeadline(iso: string | null, now: number, timeZone?: string): string {
  if (!iso) return 'No deadline set for this phase.'
  const target = parseUtc(iso).getTime()
  if (Number.isNaN(target)) return 'No deadline set for this phase.'
  const ms = target - now
  if (ms <= 0) return 'Deadline has passed — waiting for the turn to be processed.'
  const at = localDeadline(target, timeZone)
  if (ms < 60000) return `less than a minute left — ${at}`
  const totalMinutes = Math.round(ms / 60000)
  const days = Math.floor(totalMinutes / 1440)
  const hours = Math.floor((totalMinutes % 1440) / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (days > 0 || hours > 0) parts.push(`${hours}h`)
  parts.push(`${minutes}m`)
  return `${parts.join(' ')} left — ${at}`
}

/** "Mon 16:00": the deadline's weekday and clock in the viewer's zone (or `timeZone`). */
function localDeadline(target: number, timeZone?: string): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone,
  }).formatToParts(new Date(target))
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? ''
  return `${get('weekday')} ${get('hour')}:${get('minute')}`
}
