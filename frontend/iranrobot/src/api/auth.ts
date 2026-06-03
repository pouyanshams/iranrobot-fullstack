/**
 * Phase 4 -- typed wrappers around the Frappe auth APIs.
 *
 * Endpoints:
 *   GET  iranrobot_backend.api.auth.whoami         allow_guest
 *   POST iranrobot_backend.api.auth.login          allow_guest
 *   POST iranrobot_backend.api.auth.logout         requires session
 *   POST iranrobot_backend.api.auth.update_profile requires session
 */

import type { ProfilePatch, SignupInput, WhoAmIPayload } from '../types'
import { frappeFetch, frappePost } from '../lib/frappeApi'

const BASE = 'iranrobot_backend.api.auth'

export async function fetchWhoami(signal?: AbortSignal): Promise<WhoAmIPayload> {
  return frappeFetch<WhoAmIPayload>(`${BASE}.whoami`, undefined, signal)
}

export async function login(
  email: string,
  password: string,
  signal?: AbortSignal,
): Promise<WhoAmIPayload> {
  return frappePost<WhoAmIPayload>(
    `${BASE}.login`,
    { usr: email, pwd: password },
    signal,
  )
}

export async function logout(signal?: AbortSignal): Promise<WhoAmIPayload> {
  return frappePost<WhoAmIPayload>(`${BASE}.logout`, undefined, signal)
}

export async function updateProfile(
  patch: ProfilePatch,
  signal?: AbortSignal,
): Promise<WhoAmIPayload> {
  // Coerce boolean to a string so the form-encoder doesn't drop it.
  const body: Record<string, string | number | boolean | undefined> = { ...patch }
  if (typeof patch.marketing_opt_in === 'boolean') {
    body.marketing_opt_in = patch.marketing_opt_in ? 'true' : 'false'
  }
  return frappePost<WhoAmIPayload>(`${BASE}.update_profile`, body, signal)
}

/**
 * Phase 4.5 -- signup result. Adds the `auto_login` flag the backend tacks on
 * top of the standard whoami payload so the SPA can distinguish a happy
 * "signed up + signed in" from "signed up but please log in manually".
 */
export type SignupResult = WhoAmIPayload & { auto_login: boolean; email?: string }

export async function signup(
  input: SignupInput,
  signal?: AbortSignal,
): Promise<SignupResult> {
  return frappePost<SignupResult>(
    `${BASE}.signup`,
    {
      email: input.email,
      password: input.password,
      confirm_password: input.confirm_password,
      first_name: input.first_name,
      last_name: input.last_name ?? '',
      phone: input.phone ?? '',
      preferred_language: input.preferred_language ?? '',
    },
    signal,
  )
}
