import { useEffect, useState } from 'react'
import { apiJson } from '@/api/client'
import { type ProvinceNames } from '@/lib/provinceNames'
import { type OrderResultEntry, noResultsText } from '@/lib/resultText'
import { ResultList } from '@/components/OrderEntry'

/** One turn of `GET /games/{id}/resolutions`: `phase` is the code of the phase it resolved. */
type StoredResolution = { phase?: string; results: OrderResultEntry[] }

type Turn = { key: string; phase: string; resolution: StoredResolution }
/** One entry of the selector: a turn, or a movement turn and the retreat turn after it. */
export type TurnEntry = { key: string; label: string; turns: Turn[] }

const SEASONS: Record<string, string> = { S: 'Spring', F: 'Fall', W: 'Winter' }
const KINDS: Record<string, string> = { M: 'movement', R: 'retreat', A: 'adjustment' }

/** "F1902M" -> "Fall 1902 movement"; anything unrecognised is shown as it came. */
export function phaseLabel(code: string): string {
  const m = /^([SFW])(\d{4})([MRA])$/.exec(code)
  return m ? `${SEASONS[m[1]]} ${m[2]} ${KINDS[m[3]]}` : code
}

/** Newest-first turns grouped as the page shows them: a retreat turn joins the movement
 * turn of its season ("Fall 1901 movement and retreats"), just as "What happened last
 * turn" shows the two together after a retreat phase. */
export function groupTurns(turns: Turn[]): TurnEntry[] {
  const out: TurnEntry[] = []
  for (let i = 0; i < turns.length; i++) {
    const t = turns[i]
    const before = turns[i + 1]
    if (t.phase.endsWith('R') && before && before.phase === `${t.phase.slice(0, -1)}M`) {
      out.push({ key: before.key, label: `${phaseLabel(before.phase)} and retreats`, turns: [before, t] })
      i++
    } else {
      out.push({ key: t.key, label: phaseLabel(t.phase), turns: [t] })
    }
  }
  return out
}

/**
 * Earlier turns' orders and results, newest first, one season at a time behind a selector
 * (it must fit a phone). The newest entry is "What happened last turn", already on the
 * page (after a retreat phase, the movement turn and its retreats together), so only the
 * entries before it are offered, and the selector opens on the one just before (DP1).
 * Nothing renders without any. `phase` is the game's current phase: it changes when a
 * turn is processed, so refetch.
 */
export default function PreviousTurns({
  gameId,
  phase,
  myPower,
  provinceNames = {},
}: {
  gameId: string
  phase: string
  myPower: string | null
  provinceNames?: ProvinceNames
}) {
  const [entries, setEntries] = useState<TurnEntry[]>([])
  const [selected, setSelected] = useState<string>('')

  useEffect(() => {
    apiJson<{ resolutions?: Record<string, StoredResolution> }>(`/games/${gameId}/resolutions`)
      .then((body) => {
        const all = body.resolutions ?? {}
        const keys = Object.keys(all).sort((a, b) => Number(b) - Number(a))
        const grouped = groupTurns(
          keys.map((key) => ({ key, phase: all[key].phase ?? `Turn ${key}`, resolution: all[key] }))
        )
        setEntries(grouped.slice(1))
        setSelected('')
      })
      .catch(() => setEntries([]))
  }, [gameId, phase])

  if (entries.length === 0) return null
  const entry = entries.find((t) => t.key === selected) ?? entries[0]

  return (
    <section className="mb-6">
      <h2 className="text-lg font-medium mb-2">Previous turns</h2>
      <select
        aria-label="Previous turn"
        className="h-10 w-full rounded-md border bg-background px-2 py-1.5 text-sm mb-3"
        value={entry.key}
        onChange={(e) => setSelected(e.target.value)}
      >
        {entries.map((t) => (
          <option key={t.key} value={t.key}>
            {t.label}
          </option>
        ))}
      </select>
      {entry.turns.map((part) => (
        <TurnResults
          key={part.key}
          title={entry.turns.length > 1 ? (part.phase.endsWith('R') ? 'Retreats' : 'Movement') : null}
          results={part.resolution.results}
          myPower={myPower}
          provinceNames={provinceNames}
        />
      ))}
    </section>
  )
}

function TurnResults({
  title,
  results,
  myPower,
  provinceNames,
}: {
  title: string | null
  results: OrderResultEntry[]
  myPower: string | null
  provinceNames: ProvinceNames
}) {
  const mine = myPower ? results.filter((r) => r.power === myPower) : []
  const others = results.filter((r) => r.power !== myPower)
  // A retreat turn's own advice ("must retreat next phase") is stale by definition here.
  const listProps = { allResults: results, provinceNames, retreatPending: false }
  return (
    <div className="mb-3">
      {title && <h3 className="text-sm font-medium mb-1">{title}</h3>}
      {myPower ? (
        mine.length > 0 ? (
          <ResultList entries={mine} {...listProps} />
        ) : (
          <p className="text-sm text-muted-foreground mb-2">{noResultsText(myPower, results, title === 'Retreats')}</p>
        )
      ) : (
        <p className="text-sm text-muted-foreground mb-2">Join a power to see how its orders resolved.</p>
      )}
      {others.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
            Other powers&apos; results ({others.length})
          </summary>
          <div className="mt-2">
            <ResultList entries={others} showPower {...listProps} />
          </div>
        </details>
      )}
    </div>
  )
}
