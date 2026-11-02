import { useEffect, useState } from 'react'
import { apiJson } from '@/api/client'
import { type ProvinceNames } from '@/lib/provinceNames'
import { type OrderResultEntry, noResultsText } from '@/lib/resultText'
import { ResultList } from '@/components/OrderEntry'

/** One turn of `GET /games/{id}/resolutions`: `phase` is the code of the phase it resolved. */
type StoredResolution = { phase?: string; results: OrderResultEntry[] }

const SEASONS: Record<string, string> = { S: 'Spring', F: 'Fall', W: 'Winter' }
const KINDS: Record<string, string> = { M: 'movement', R: 'retreat', A: 'adjustment' }

/** "F1902M" -> "Fall 1902 movement"; anything unrecognised is shown as it came. */
export function phaseLabel(code: string): string {
  const m = /^([SFW])(\d{4})([MRA])$/.exec(code)
  return m ? `${SEASONS[m[1]]} ${m[2]} ${KINDS[m[3]]}` : code
}

/**
 * Earlier turns' orders and results, newest first, one phase at a time behind a selector
 * (it must fit a phone). The newest stored turn is "What happened last turn", already
 * on the page, so only the ones before it are offered; nothing renders without any.
 * `phase` is the game's current phase: it changes when a turn is processed, so refetch.
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
  const [turns, setTurns] = useState<{ key: string; label: string; resolution: StoredResolution }[]>([])
  const [selected, setSelected] = useState<string>('')

  useEffect(() => {
    apiJson<{ resolutions?: Record<string, StoredResolution> }>(`/games/${gameId}/resolutions`)
      .then((body) => {
        const all = body.resolutions ?? {}
        const keys = Object.keys(all).sort((a, b) => Number(b) - Number(a))
        setTurns(
          keys.slice(1).map((key) => ({
            key,
            label: phaseLabel(all[key].phase ?? `Turn ${key}`),
            resolution: all[key],
          }))
        )
      })
      .catch(() => setTurns([]))
  }, [gameId, phase])

  if (turns.length === 0) return null
  const turn = turns.find((t) => t.key === selected) ?? turns[0]
  const results = turn.resolution.results
  const mine = myPower ? results.filter((r) => r.power === myPower) : []
  const others = results.filter((r) => r.power !== myPower)
  // A retreat turn's own advice ("must retreat next phase") is stale by definition here.
  const listProps = { allResults: results, provinceNames, retreatPending: false }

  return (
    <section className="mb-6">
      <h2 className="text-lg font-medium mb-2">Previous turns</h2>
      <select
        aria-label="Previous turn"
        className="w-full rounded-md border bg-background px-2 py-1.5 text-sm mb-3"
        value={turn.key}
        onChange={(e) => setSelected(e.target.value)}
      >
        {turns.map((t) => (
          <option key={t.key} value={t.key}>
            {t.label}
          </option>
        ))}
      </select>
      {myPower ? (
        mine.length > 0 ? (
          <ResultList entries={mine} {...listProps} />
        ) : (
          <p className="text-sm text-muted-foreground mb-2">{noResultsText(myPower, results)}</p>
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
    </section>
  )
}
