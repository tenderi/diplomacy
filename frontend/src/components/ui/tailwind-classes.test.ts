// @vitest-environment node
import postcss from 'postcss'
import tailwindcss from 'tailwindcss'
import { beforeAll, describe, expect, it } from 'vitest'
// @ts-expect-error the config is plain JavaScript
import config from '../../../tailwind.config.js'

// The shadcn components were generated for Tailwind v4; the project builds with
// v3, which silently drops any class it cannot generate (no ring, no destructive
// colour, no focus style). Run Tailwind on the ui sources and require a rule for
// every variant/opacity/arbitrary class they use.
const raw = import.meta.glob<string>(['./*.tsx', '!./sonner.tsx', '!./*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
})
const sources = Object.values(raw)

const esc = (c: string): string => c.replace(/[^a-zA-Z0-9_-]/g, (ch) => `\\${ch}`)

function utilityTokens(): string[] {
  const out = new Set<string>()
  for (const src of sources) {
    for (const m of src.matchAll(/"([^"\n]*)"/g)) {
      for (const t of m[1].split(/\s+/)) {
        if (/^(group|peer)\//.test(t) || t.startsWith('@')) continue
        if (/[:/[(]/.test(t)) out.add(t)
      }
    }
  }
  return [...out]
}

let css = ''
beforeAll(async () => {
  const result = await postcss([
    tailwindcss({ ...config, content: sources.map((r) => ({ raw: r, extension: 'tsx' })) }),
  ]).process('@tailwind utilities;', { from: undefined })
  // Unminified output spells a comma `\2c ` and quotes attribute values.
  css = result.css.replace(/\\2c /g, '\\,').replace(/="true"\]/g, '=true]')
})

describe('shadcn ui classes under Tailwind v3', () => {
  it('generates a rule for every variant, opacity and arbitrary class', () => {
    const missing = utilityTokens().filter((t) => !css.includes(`.${esc(t)}`))
    expect(missing).toEqual([])
  })

  it('draws a visible focus ring on inputs and buttons', () => {
    expect(css).toContain(`${esc('focus-visible:ring-ring/50')}:focus-visible`)
    expect(css).toContain(`${esc('focus-visible:ring-[3px]')}:focus-visible`)
    expect(css).toContain('color-mix(in oklch, var(--ring) 50%, transparent)')
  })

  it('colours the destructive and invalid states', () => {
    expect(css).toContain('color-mix(in oklch, var(--destructive) 10%, transparent)')
    expect(css).toContain(`${esc('aria-[invalid=true]:border-destructive')}[aria-invalid=true]`)
  })
})
