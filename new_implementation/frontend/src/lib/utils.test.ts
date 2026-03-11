import { describe, it, expect } from 'vitest'
import { cn } from './utils'

describe('cn', () => {
  it('merges single class', () => {
    expect(cn('foo')).toBe('foo')
  })

  it('merges multiple classes', () => {
    expect(cn('foo', 'bar')).toContain('foo')
    expect(cn('foo', 'bar')).toContain('bar')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', true && 'visible')).toContain('base')
    expect(cn('base', false && 'hidden', true && 'visible')).toContain('visible')
    expect(cn('base', false && 'hidden')).not.toContain('hidden')
  })

  it('tailwind-merge: later class overrides conflicting earlier', () => {
    const result = cn('p-4', 'p-2')
    expect(result).toContain('p-2')
    expect(result).not.toContain('p-4')
  })

  it('handles undefined and null', () => {
    expect(cn('foo', undefined, null)).toBe('foo')
  })
})
