/**
 * The order helper (#460): while a player gives orders, explain why an order is
 * impossible or what it depends on. The draft goes to
 * `POST /games/{id}/orders/{power}/notes`, which stores nothing and answers from the
 * board and the player's own orders only (never another power's pending orders).
 */
import { useEffect, useState } from 'react'
import { apiJson } from '@/api/client'

export type HelperNote = { kind: 'impossible' | 'warning'; code: string; text: string }
export type OrderNotesView = {
  orders: { order: string; ok: boolean; notes: HelperNote[] }[]
  notes: HelperNote[]
}

/** Every note of a notes response, each once, in order: per-order notes, then the set's. */
export function helperNotes(view: OrderNotesView | null): HelperNote[] {
  if (!view) return []
  const seen = new Set<string>()
  const out: HelperNote[] = []
  for (const n of [...view.orders.flatMap((o) => o.notes), ...view.notes]) {
    if (seen.has(n.text)) continue
    seen.add(n.text)
    out.push(n)
  }
  return out
}

function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1) + (/[.!?]$/.test(text) ? '' : '.')
}

/** Asks for notes on `orders` (debounced) and lists them; renders nothing without any. */
export function OrderNotes({
  gameId,
  power,
  orders,
  incomplete = [],
}: {
  gameId: string
  power: string
  orders: string[]
  /** Units (e.g. "A BUD") with an order type chosen but no target yet: the server only
   * sees the finished orders and would say they hold, so say they are incomplete (DW3). */
  incomplete?: string[]
}) {
  const [view, setView] = useState<OrderNotesView | null>(null)
  const key = orders.join('\n')
  useEffect(() => {
    if (!key) {
      setView(null)
      return
    }
    let cancelled = false
    const timer = setTimeout(() => {
      apiJson<OrderNotesView>(`/games/${gameId}/orders/${encodeURIComponent(power)}/notes`, {
        method: 'POST',
        body: JSON.stringify({ orders: key.split('\n') }),
      })
        .then((v) => {
          if (!cancelled) setView(v)
        })
        // The helper is advice: if it cannot be had, the form works as before.
        .catch(() => {
          if (!cancelled) setView(null)
        })
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [gameId, power, key])

  const notes = helperNotes(view).map((n) => {
    const unit = n.code === 'unordered' ? incomplete.find((u) => n.text === `${u} has no order, so it will hold`) : undefined
    return unit ? { ...n, text: `${unit} is incomplete: choose a target` } : n
  })
  // A half-filled row with no finished order sends no draft, so the server says nothing.
  for (const u of incomplete) {
    const text = `${u} is incomplete: choose a target`
    if (!notes.some((n) => n.text === text)) notes.push({ kind: 'warning', code: 'incomplete', text })
  }
  if (notes.length === 0) return null
  return (
    <div role="status" aria-live="polite" className="mt-3 max-w-xl rounded-lg border border-border p-3 text-sm">
      <p className="font-medium mb-1">Order helper</p>
      <ul className="space-y-1">
        {notes.map((n) => (
          <li key={n.text} className={n.kind === 'impossible' ? 'text-destructive' : 'text-muted-foreground'}>
            <span aria-hidden="true">{n.kind === 'impossible' ? '✕ ' : '⚠ '}</span>
            <span className="sr-only">{n.kind === 'impossible' ? 'Will not work: ' : 'Check: '}</span>
            {sentence(n.text)}
          </li>
        ))}
      </ul>
    </div>
  )
}
