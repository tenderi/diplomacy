import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  setTokens,
  clearTokens,
  getAccessToken,
  apiFetch,
  apiJson,
  errorDetailToMessage,
} from './client'

describe('errorDetailToMessage', () => {
  it('extracts first validation error msg from 422 array detail', () => {
    const body = JSON.stringify({ detail: [{ msg: 'Invalid email' }, { msg: 'Other' }] })
    expect(errorDetailToMessage(body, 422)).toBe('Invalid email')
  })

  it('falls back to string of first element when detail array has no msg', () => {
    const body = JSON.stringify({ detail: ['Invalid input'] })
    expect(errorDetailToMessage(body, 422)).toBe('Invalid input')
  })

  it('returns string detail as-is', () => {
    const body = JSON.stringify({ detail: 'Unauthorized' })
    expect(errorDetailToMessage(body, 401)).toBe('Unauthorized')
  })

  it('converts non-string detail to string', () => {
    const body = JSON.stringify({ detail: 123 })
    expect(errorDetailToMessage(body, 400)).toBe('123')
  })

  it('returns server unavailable for status >= 500', () => {
    expect(errorDetailToMessage('', 500)).toBe('Server unavailable. Is the API running?')
    expect(errorDetailToMessage('', 502)).toBe('Server unavailable. Is the API running?')
  })

  it('returns server unavailable for status 0', () => {
    expect(errorDetailToMessage('', 0)).toBe('Server unavailable. Is the API running?')
  })

  it('returns Request failed for empty text and non-5xx', () => {
    expect(errorDetailToMessage('', 400)).toBe('Request failed')
  })

  it('returns raw text when JSON parse fails and status is 4xx', () => {
    expect(errorDetailToMessage('not json', 400)).toBe('not json')
  })
})

describe('setTokens, clearTokens, getAccessToken', () => {
  beforeEach(() => {
    clearTokens()
  })

  it('getAccessToken returns null when no token set', () => {
    expect(getAccessToken()).toBeNull()
  })

  it('setTokens stores and getAccessToken returns access token', () => {
    setTokens('access-123', 'refresh-456')
    expect(getAccessToken()).toBe('access-123')
  })

  it('clearTokens clears stored tokens', () => {
    setTokens('a', 'r')
    clearTokens()
    expect(getAccessToken()).toBeNull()
  })
})

describe('apiFetch', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    clearTokens()
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('attaches Authorization header when access token is set', async () => {
    setTokens('my-token', 'refresh')
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({}),
    })
    await apiFetch('/test')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer my-token' }),
      })
    )
  })

  it('does not attach Authorization when no token', async () => {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({}),
    })
    await apiFetch('/test')
    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1]
    expect(call?.headers && (call.headers as Record<string, string>).Authorization).toBeUndefined()
  })
})

describe('apiJson', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    clearTokens()
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('returns parsed JSON on ok response', async () => {
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ id: 1 }),
      text: () => Promise.resolve('{"id":1}'),
    })
    const data = await apiJson<{ id: number }>('/test')
    expect(data).toEqual({ id: 1 })
  })

  it('throws with message from error body (422 detail array)', async () => {
    const body = JSON.stringify({ detail: [{ msg: 'Email taken' }] })
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 422,
      text: () => Promise.resolve(body),
    })
    await expect(apiJson('/test')).rejects.toThrow('Email taken')
  })

  it('throws with message from error body (string detail)', async () => {
    const body = JSON.stringify({ detail: 'Forbidden' })
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 403,
      text: () => Promise.resolve(body),
    })
    await expect(apiJson('/test')).rejects.toThrow('Forbidden')
  })
})

describe('apiFetch 401 refresh flow', () => {
  const originalFetch = globalThis.fetch
  const originalLocalStorage = globalThis.localStorage

  beforeEach(() => {
    clearTokens()
    setTokens('expired', 'refresh-token')
    globalThis.fetch = vi.fn()
    const store: Record<string, string> = {}
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (k: string) => store[k] ?? null,
        setItem: (k: string, v: string) => { store[k] = v },
        removeItem: (k: string) => { delete store[k] },
        length: 0,
        key: () => null,
        clear: () => {},
      },
      configurable: true,
    })
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    Object.defineProperty(globalThis, 'localStorage', { value: originalLocalStorage, configurable: true })
  })

  it('retries request with new token after successful refresh', async () => {
    const fetchMock = globalThis.fetch as ReturnType<typeof vi.fn>
    fetchMock
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'new-access', refresh_token: 'refresh-token' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'ok' }),
        text: () => Promise.resolve('{"data":"ok"}'),
      })
    const res = await apiFetch('/users/me')
    expect(res.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})
