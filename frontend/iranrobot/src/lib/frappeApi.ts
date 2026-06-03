/**
 * Base HTTP client for Frappe's `/api/method/` endpoints.
 *
 * Frappe wraps every whitelisted method's return value in `{"message": <value>}`.
 * Our Phase 2 backend additionally wraps payloads in `{ ok, data, error }`.
 * `frappeFetch`/`frappePost` unwrap both layers and throw on either an HTTP
 * error or an `ok: false` payload, so callers receive plain data on success
 * and an Error on failure.
 *
 * Phase 4 auth additions:
 *   - `credentials: 'include'` so the browser sends/keeps the Frappe `sid`
 *     session cookie across page loads.
 *   - `frappePost(method, body)` companion that form-encodes the body and
 *     attaches the CSRF token (set by `setCsrfToken` from AuthContext).
 *
 * Base URL:
 *   - Reads `VITE_FRAPPE_BASE_URL` if set (production / cross-origin setups).
 *   - Otherwise uses `''` (relative) — Vite's dev proxy forwards `/api/*` to
 *     the Frappe dev server. See vite.config.ts.
 */

const ENV_BASE = (import.meta.env.VITE_FRAPPE_BASE_URL as string | undefined) ?? ''
const BASE_URL = ENV_BASE.replace(/\/$/, '')

export interface FrappeOk<T> {
  ok: true
  data: T
  message?: string
}

export interface FrappeErr {
  ok: false
  error: { code: string; message: string }
}

export type FrappeEnvelope<T> = FrappeOk<T> | FrappeErr

export class FrappeApiError extends Error {
  code: string
  status?: number
  constructor(message: string, code: string, status?: number) {
    super(message)
    this.name = 'FrappeApiError'
    this.code = code
    this.status = status
  }
}

// --- CSRF token store (set by AuthContext, read by frappePost) -----------

let _csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  _csrfToken = token || null
}

export function getCsrfToken(): string | null {
  return _csrfToken
}

// --- Shared envelope handling --------------------------------------------

async function _parseEnvelope<T>(resp: Response): Promise<T> {
  let body: unknown
  try {
    body = await resp.json()
  } catch {
    throw new FrappeApiError(
      `Server returned non-JSON response (HTTP ${resp.status}).`,
      'BAD_RESPONSE',
      resp.status,
    )
  }

  if (!resp.ok) {
    // Frappe sometimes returns 417 / 500 with `_error_message` for built-in
    // errors; surface that when present.
    const msg =
      (isObj(body) && typeof body._error_message === 'string' && body._error_message) ||
      `HTTP ${resp.status}`
    throw new FrappeApiError(String(msg), 'HTTP_ERROR', resp.status)
  }

  // Unwrap Frappe's outer { message: ... } envelope.
  const inner = isObj(body) && 'message' in body ? (body as { message: unknown }).message : body

  if (!isObj(inner) || typeof (inner as { ok?: unknown }).ok !== 'boolean') {
    throw new FrappeApiError(
      'Response did not match expected { ok, data } envelope.',
      'BAD_ENVELOPE',
    )
  }

  const env = inner as unknown as FrappeEnvelope<T>
  if (!env.ok) {
    throw new FrappeApiError(env.error.message || 'Server error', env.error.code)
  }
  return env.data
}

// --- GET -----------------------------------------------------------------

/**
 * Call a Frappe whitelisted method (GET).
 *
 * @param method dotted path, e.g. "iranrobot_backend.api.catalog.get_products"
 * @param params query parameters (undefined values are dropped)
 * @param signal optional AbortSignal for cancellation
 */
export async function frappeFetch<T>(
  method: string,
  params?: Record<string, string | number | boolean | undefined | null>,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(`${BASE_URL}/api/method/${method}`, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue
      url.searchParams.set(k, String(v))
    }
  }

  let resp: Response
  try {
    resp = await fetch(url.toString(), {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
      signal,
    })
  } catch (e) {
    if ((e as { name?: string })?.name === 'AbortError') throw e
    throw new FrappeApiError(
      'Network error: could not reach the Frappe server.',
      'NETWORK_ERROR',
    )
  }

  return _parseEnvelope<T>(resp)
}

// --- POST ----------------------------------------------------------------

/**
 * Call a Frappe whitelisted method (POST). Used by the Phase 4 auth APIs and
 * future write endpoints. The body is form-urlencoded (Frappe's preferred
 * format for `/api/method/`), and the CSRF token (set via `setCsrfToken`) is
 * attached as `X-Frappe-CSRF-Token`.
 */
export async function frappePost<T>(
  method: string,
  body?: Record<string, string | number | boolean | undefined | null>,
  signal?: AbortSignal,
): Promise<T> {
  const params = new URLSearchParams()
  if (body) {
    for (const [k, v] of Object.entries(body)) {
      if (v === undefined || v === null) continue
      params.set(k, String(v))
    }
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/x-www-form-urlencoded',
  }
  if (_csrfToken) headers['X-Frappe-CSRF-Token'] = _csrfToken

  let resp: Response
  try {
    resp = await fetch(`${BASE_URL}/api/method/${method}`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: params.toString(),
      signal,
    })
  } catch (e) {
    if ((e as { name?: string })?.name === 'AbortError') throw e
    throw new FrappeApiError(
      'Network error: could not reach the Frappe server.',
      'NETWORK_ERROR',
    )
  }

  return _parseEnvelope<T>(resp)
}

function isObj(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null
}
