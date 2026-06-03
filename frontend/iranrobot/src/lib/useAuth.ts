/**
 * Phase 4 -- Standalone useAuth hook + AuthContext object.
 *
 * Split out of AuthContext.tsx so that React Fast Refresh stays happy: the
 * `react-refresh/only-export-components` lint rule wants component files to
 * export only components. AuthContext.tsx keeps the <AuthProvider>; this file
 * keeps the createContext call and the useAuth() hook so any module can
 * consume the auth state without depending on the component module.
 */

import { createContext, useContext } from 'react'
import type { CurrentUser, ProfilePatch, SignupInput } from '../types'

/** Phase 4.5 -- result of a signup call. Distinguishes auto-login success
 * from "account created, please log in manually" so the LoginModal can pick
 * the right next state. */
export interface SignupOutcome {
  autoLoggedIn: boolean
  email: string
}

export interface AuthContextValue {
  currentUser: CurrentUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: Error | null
  loginOpen: boolean
  openLogin: () => void
  closeLogin: () => void
  login: (email: string, password: string) => Promise<void>
  signup: (input: SignupInput) => Promise<SignupOutcome>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  updateProfile: (patch: ProfilePatch) => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
