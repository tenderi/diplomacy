/** Where to go after login: the page a logged-out visitor was sent away from (DW1). Only a
 * same-origin relative path is honoured (one leading `/`, not `//host` or `/\host`), so a
 * crafted link cannot turn the login page into an open redirect. */
export function safeNext(from: unknown, fallback = '/games'): string {
  if (typeof from !== 'string') return fallback
  if (!from.startsWith('/') || from.startsWith('//') || from.includes('\\')) return fallback
  if (from === '/login' || from === '/register') return fallback
  return from
}
