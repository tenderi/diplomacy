/**
 * Province display names (G2): `BER` → `Berlin`, so a new player can read the
 * board without a lookup table.
 *
 * **Names are for display only. Codes are the wire format.** Order strings sent
 * back to the API must stay canonical, because the engine's grammar does not
 * accept full province names -- 26 of them are multi-word (`English Channel`,
 * `Gulf of Bothnia`) and the parser tokenizes on whitespace, so `A English
 * Channel - NTH` cannot work. G1 recorded that decision after finding the
 * Telegram bot's own help text had been teaching unparseable full-name orders
 * since before the engine rewrite. Nothing here rewrites an order; `glossOrder`
 * produces a *separate* readable line to show beside the real one.
 *
 * The table itself comes from `GET /maps/{map}/provinces`, whose source is
 * `maps/standard.map`'s `=` lines -- the same single source of truth as the
 * board topology. No name table is hardcoded in this client.
 */

/** code → full name, e.g. `{ BER: 'Berlin' }`. */
export type ProvinceNames = Record<string, string>

/** One province entry as returned by `GET /maps/{map}/provinces`. */
export interface ProvinceInfo {
  name: string
  type: string
  is_supply_center: boolean
  coasts: string[]
}

/** Reduce the endpoint payload to the code → name map the UI needs. */
export function provinceNamesFromResponse(body: {
  provinces?: Record<string, ProvinceInfo>
}): ProvinceNames {
  const out: ProvinceNames = {}
  for (const [code, info] of Object.entries(body.provinces ?? {})) {
    if (info?.name) out[code] = info.name
  }
  return out
}

/**
 * `"Berlin (BER)"` — the name *and* the code, deliberately.
 *
 * Showing only the name would leave a player unable to type an order, since
 * orders need the code; showing only the code is the problem G2 exists to fix.
 * Coasts are preserved and rendered against the base province:
 * `"STP/SC"` → `"St Petersburg (STP/SC)"`.
 *
 * Unknown codes pass through unchanged rather than rendering `undefined` — the
 * table is fetched asynchronously, so every caller renders at least once before
 * it arrives.
 */
export function provinceLabel(location: string, names: ProvinceNames): string {
  if (!location) return location
  const base = location.split('/')[0]
  const name = names[base]
  return name ? `${name} (${location})` : location
}

/** The bare full name, no code — for prose where the code would be noise. */
export function provinceName(location: string, names: ProvinceNames): string {
  if (!location) return location
  return names[location.split('/')[0]] ?? location
}

/** Province-code-shaped tokens: 3 letters, optionally `/XX` for a coast. */
const PROVINCE_TOKEN = /^[A-Z]{3}(\/[A-Z]{2})?$/

/**
 * A readable gloss of a canonical order string, for display *beside* it.
 *
 * `"A BER - KIE"` → `"Army Berlin → Kiel"`. Returns `null` when nothing could be
 * expanded (no known province in the string), so callers can skip rendering an
 * empty second line rather than showing a duplicate of the original.
 *
 * This never replaces the order string in the UI and is never sent anywhere.
 */
export function glossOrder(orderStr: string, names: ProvinceNames): string | null {
  if (!orderStr) return null
  let expanded = false
  const words = orderStr.split(' ').map((token) => {
    if (token === 'A') return 'Army'
    if (token === 'F') return 'Fleet'
    if (token === '-') return '→'
    if (token === 'H') return 'holds'
    if (token === 'S') return 'supports'
    if (token === 'C') return 'convoys'
    if (token === 'R') return 'retreats to'
    if (token === 'D') return 'disband'
    if (PROVINCE_TOKEN.test(token)) {
      const name = provinceName(token, names)
      if (name !== token) expanded = true
      return name
    }
    return token
  })
  return expanded ? words.join(' ') : null
}
