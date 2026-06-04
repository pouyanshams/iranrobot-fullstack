/**
 * Phase 7A.1 -- typed wrappers around the Frappe customer-address APIs.
 *
 * Endpoints:
 *   GET  iranrobot_backend.api.account.get_my_addresses    auth required
 *   POST iranrobot_backend.api.account.save_my_address     auth required
 *   POST iranrobot_backend.api.account.delete_my_address   auth required
 *
 * The backend strictly projects customer-safe fields and enforces ownership
 * via `frappe.session.user` -> Contact -> Customer (Phase 4 helper). The
 * frontend never sends a `customer` id.
 */

import { frappeFetch, frappePost } from '../lib/frappeApi'

const BASE = 'iranrobot_backend.api.account'

export type AddressType = 'Billing' | 'Shipping' | 'Office' | 'Personal' | 'Other'

export interface CustomerAddress {
  name: string
  address_title: string | null
  address_type: AddressType | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  country: string | null
  pincode: string | null
  phone: string | null
  email_id: string | null
  is_primary_address: 0 | 1 | null
  is_shipping_address: 0 | 1 | null
}

export interface AddressPayload {
  /** Omit on create; required on update. */
  name?: string
  address_title?: string
  address_type?: AddressType
  address_line1: string
  address_line2?: string
  city: string
  state?: string
  country: string
  pincode?: string
  phone?: string
  email_id?: string
  is_primary_address?: boolean
  is_shipping_address?: boolean
}

export async function fetchMyAddresses(
  signal?: AbortSignal,
): Promise<CustomerAddress[]> {
  const res = await frappeFetch<{ addresses: CustomerAddress[] }>(
    `${BASE}.get_my_addresses`,
    undefined,
    signal,
  )
  return res.addresses
}

export async function saveMyAddress(
  payload: AddressPayload,
  signal?: AbortSignal,
): Promise<CustomerAddress> {
  // Coerce booleans for the form-urlencoded body.
  const body: Record<string, string | number | boolean | undefined | null> = {
    name: payload.name,
    address_title: payload.address_title ?? '',
    address_type: payload.address_type ?? 'Billing',
    address_line1: payload.address_line1,
    address_line2: payload.address_line2 ?? '',
    city: payload.city,
    state: payload.state ?? '',
    country: payload.country,
    pincode: payload.pincode ?? '',
    phone: payload.phone ?? '',
    email_id: payload.email_id ?? '',
    is_primary_address: payload.is_primary_address ? 'true' : 'false',
    is_shipping_address: payload.is_shipping_address ? 'true' : 'false',
  }
  const res = await frappePost<{ address: CustomerAddress }>(
    `${BASE}.save_my_address`,
    body,
    signal,
  )
  return res.address
}

export async function deleteMyAddress(
  name: string,
  signal?: AbortSignal,
): Promise<{ deleted: string; soft?: boolean }> {
  return frappePost<{ deleted: string; soft?: boolean }>(
    `${BASE}.delete_my_address`,
    { name },
    signal,
  )
}
