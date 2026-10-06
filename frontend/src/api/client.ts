// In dev, use /api so Vite proxies API only; SPA routes (/games/123) stay local and refresh works
export const API_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '/api' : '')

/** localStorage key for refresh token (shared with AuthContext). */
export const REFRESH_STORAGE_KEY = 'diplomacy_refresh'

let accessToken: string | null = null
let refreshToken: string | null = null

/**
 * The refresh token is the session: it is kept in localStorage so a reload stays
 * signed in. Every token the API issues replaces it there -- the API's refresh
 * tokens slide (7 days from each refresh), and keeping only the one from login
 * logged an everyday player out a week after they signed in.
 */
function persistRefreshToken(token: string | null) {
  try {
    if (typeof localStorage === 'undefined') return
    if (token) localStorage.setItem(REFRESH_STORAGE_KEY, JSON.stringify({ refresh_token: token }))
    else localStorage.removeItem(REFRESH_STORAGE_KEY)
  } catch {
    // storage unavailable (private mode): the session just won't survive a reload
  }
}

export function setTokens(access: string, refresh: string) {
  accessToken = access
  refreshToken = refresh
  persistRefreshToken(refresh)
}

export function clearTokens() {
  accessToken = null
  refreshToken = null
  persistRefreshToken(null)
}

export function getAccessToken() {
  return accessToken
}

async function doRefresh(): Promise<boolean> {
  if (!refreshToken) return false
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (res.status === 401) {
      clearTokens()
      return false
    }
    if (!res.ok) return false
    const data = await res.json()
    setTokens(data.access_token, data.refresh_token || refreshToken)
    return true
  } catch {
    return false
  }
}

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers: HeadersInit = {
    ...(options.headers as Record<string, string>),
  }
  if (accessToken) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`
  }
  let res = await fetch(url, { ...options, headers })
  if (res.status === 401 && refreshToken) {
    const ok = await doRefresh()
    if (ok && accessToken) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`
      res = await fetch(url, { ...options, headers })
    }
  }
  return res
}

/**
 * Error thrown by `apiJson` on a non-ok response. Carries the HTTP status so
 * callers can branch on specific codes (e.g. 409 `StaleGameError`) without
 * parsing the message string -- the message itself may be a raw backend
 * string not meant for display (see `errorDetailToMessage`).
 *
 * `code` is the response's `X-Error-Code` header, when the server sent one: a
 * stable name for a refusal (e.g. `seats_unfilled`) to switch on, where the
 * message is prose that may change.
 */
export class ApiError extends Error {
  status: number
  code: string | null
  constructor(message: string, status: number, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/** Turn API error body into a single readable message (handles 422 validation and plain detail). */
export function errorDetailToMessage(text: string, status: number): string {
  try {
    const j = JSON.parse(text)
    const detail = j.detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      return typeof first === 'object' && first?.msg != null ? first.msg : String(detail[0])
    }
    if (typeof detail === 'string') return detail
    if (detail != null) return String(detail)
  } catch {
    // ignore
  }
  if (status === 0 || status >= 500) return 'Server unavailable. Is the API running?'
  return text || 'Request failed'
}

export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers as object) },
  })
  if (!res.ok) {
    const text = await res.text()
    const message = errorDetailToMessage(text, res.status)
    // Test doubles of `Response` often carry no headers at all.
    throw new ApiError(message, res.status, res.headers?.get('X-Error-Code') ?? null)
  }
  return res.json()
}
