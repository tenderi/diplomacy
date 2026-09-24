import { vi } from 'vitest'

export function createMockFetch() {
  return vi.fn()
}

export function mockFetchJsonResponse(data: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response)
}

export function mockFetchTextResponse(text: string, ok = false, status = 400) {
  return Promise.resolve({
    ok,
    status,
    text: () => Promise.resolve(text),
    json: () => Promise.reject(new Error('Not JSON')),
  } as Response)
}

export function stubGlobalFetch(mockFn: ReturnType<typeof createMockFetch>) {
  vi.stubGlobal('fetch', mockFn)
}
