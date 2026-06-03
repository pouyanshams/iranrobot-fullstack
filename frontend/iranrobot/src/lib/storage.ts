const PREFIX = 'iranrobot.v1.'

export function loadJSON<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(PREFIX + key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function saveJSON<T>(key: string, value: T): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value))
  } catch {
    /* quota exceeded — ignore */
  }
}

export function removeKey(key: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(PREFIX + key)
}

export function uid(prefix = ''): string {
  const r = Math.random().toString(36).slice(2, 8)
  const t = Date.now().toString(36)
  return prefix ? `${prefix}_${t}${r}` : `${t}${r}`
}
