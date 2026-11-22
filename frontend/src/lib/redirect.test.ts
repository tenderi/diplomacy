import { describe, expect, it } from 'vitest'
import { safeNext } from './redirect'

describe('safeNext', () => {
  it('keeps a same-origin path with its query', () => {
    expect(safeNext('/games/1?tab=orders')).toBe('/games/1?tab=orders')
  })

  it.each([
    ['//evil.example/x'],
    ['https://evil.example'],
    ['/\\evil.example'],
    ['games/1'],
    ['/login'],
    ['/register'],
    [undefined],
    [42],
  ])('falls back to /games for %s', (v) => {
    expect(safeNext(v)).toBe('/games')
  })
})
