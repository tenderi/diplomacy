// In dev, use /api so Vite proxies API only; SPA routes (/games/123) stay local and refresh works
export const API_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '/api' : '')

let accessToken: string | null = null
let refreshToken: string | null = null

export function setTokens(access: string, refresh: string) {
  accessToken = access
  refreshToken = refresh
}

export function clearTokens() {
  accessToken = null
  refreshToken = null
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
    if (!res.ok) return false
    const data = await res.json()
    accessToken = data.access_token
    if (data.refresh_token) refreshToken = data.refresh_token
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

/** Turn API error body into a single readable message (handles 422 validation and plain detail). */
function errorDetailToMessage(text: string, status: number): string {
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
    throw new Error(message)
  }
  return res.json()
}
