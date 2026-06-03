/**
 * Phase 4 -- AuthProvider.
 *
 * Owns:
 *   - The boot-time `whoami` call that hydrates `currentUser`.
 *   - The CSRF token (kept both in React state and in the frappeApi module
 *     so non-React POST callers can read it without prop-drilling).
 *   - The `login` / `logout` / `refresh` / `updateProfile` mutations.
 *   - The "open login modal" UI signal so any component (e.g. Account view's
 *     guest fallback) can prompt the user without owning modal state.
 *
 * The `useAuth` hook and the bare AuthContext object live in
 * src/lib/useAuth.ts (keeps React Fast Refresh happy).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { CurrentUser, ProfilePatch, SignupInput, WhoAmIPayload } from '../types'
import {
  fetchWhoami,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
  updateProfile as apiUpdateProfile,
} from '../api/auth'
import { setCsrfToken } from '../lib/frappeApi'
import { AuthContext, type AuthContextValue, type SignupOutcome } from '../lib/useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [loginOpen, setLoginOpen] = useState(false)
  // We re-call whoami on demand. AbortController de-races overlapping requests.
  const inflightRef = useRef<AbortController | null>(null)

  const applyPayload = useCallback((payload: WhoAmIPayload) => {
    setCsrfToken(payload.csrf_token || null)
    setCurrentUser(payload.is_authenticated ? payload.user : null)
  }, [])

  const refresh = useCallback(async () => {
    inflightRef.current?.abort()
    const ctrl = new AbortController()
    inflightRef.current = ctrl
    setError(null)
    try {
      const payload = await fetchWhoami(ctrl.signal)
      applyPayload(payload)
    } catch (e: unknown) {
      if ((e as { name?: string })?.name === 'AbortError') return
      setError(e instanceof Error ? e : new Error(String(e)))
      // Treat unreachable / errored whoami as guest so the UI doesn't hang.
      setCurrentUser(null)
    }
  }, [applyPayload])

  // Boot: one whoami on mount. This is the canonical async-fetch pattern
  // (initial load => transition to loading => resolve to data); the strict
  // react-hooks/set-state-in-effect rule would prefer derived state but it
  // doesn't apply to mount-time data hydration.
  useEffect(() => {
    let cancelled = false
    const ctrl = new AbortController()
    inflightRef.current = ctrl
    // eslint-disable-next-line react-hooks/set-state-in-effect -- canonical boot-time hydration pattern
    setIsLoading(true)
    fetchWhoami(ctrl.signal)
      .then((payload) => {
        if (cancelled) return
        applyPayload(payload)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        if ((e as { name?: string })?.name === 'AbortError') return
        setError(e instanceof Error ? e : new Error(String(e)))
      })
      .finally(() => {
        if (cancelled) return
        setIsLoading(false)
      })
    return () => {
      cancelled = true
      ctrl.abort()
    }
  }, [applyPayload])

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null)
      try {
        const payload = await apiLogin(email, password)
        applyPayload(payload)
        setLoginOpen(false)
      } catch (e: unknown) {
        // Let the LoginModal display the error; re-throw so it knows it failed.
        setError(e instanceof Error ? e : new Error(String(e)))
        throw e
      }
    },
    [applyPayload],
  )

  const signup = useCallback(
    async (input: SignupInput): Promise<SignupOutcome> => {
      setError(null)
      const payload = await apiSignup(input)
      // payload is the whoami envelope + auto_login flag. If auto_login is
      // true and is_authenticated is true, we treat the response like a
      // login and close the modal. Otherwise we leave the modal open and let
      // the LoginModal nudge the user toward the Login tab.
      if (payload.auto_login && payload.is_authenticated) {
        applyPayload(payload)
        setLoginOpen(false)
        return { autoLoggedIn: true, email: input.email }
      }
      // Soft-failure path: account created but auto-login didn't take. The
      // backend sets a fresh csrf_token for the guest session; thread it.
      setCsrfToken(payload.csrf_token || null)
      return { autoLoggedIn: false, email: payload.email || input.email }
    },
    [applyPayload],
  )

  const logout = useCallback(async () => {
    setError(null)
    try {
      const payload = await apiLogout()
      applyPayload(payload)
    } catch (e: unknown) {
      setError(e instanceof Error ? e : new Error(String(e)))
      throw e
    }
  }, [applyPayload])

  const updateProfile = useCallback(
    async (patch: ProfilePatch) => {
      setError(null)
      try {
        const payload = await apiUpdateProfile(patch)
        applyPayload(payload)
      } catch (e: unknown) {
        setError(e instanceof Error ? e : new Error(String(e)))
        throw e
      }
    },
    [applyPayload],
  )

  const openLogin = useCallback(() => setLoginOpen(true), [])
  const closeLogin = useCallback(() => setLoginOpen(false), [])

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser,
      isAuthenticated: !!currentUser,
      isLoading,
      error,
      loginOpen,
      openLogin,
      closeLogin,
      login,
      signup,
      logout,
      refresh,
      updateProfile,
    }),
    [currentUser, isLoading, error, loginOpen, openLogin, closeLogin, login, signup, logout, refresh, updateProfile],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
