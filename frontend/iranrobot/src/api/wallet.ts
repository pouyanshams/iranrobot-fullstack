/**
 * Phase 8C -- Frontend client for the wallet APIs.
 *
 * Mirrors src/api/invoices.ts / src/api/orders.ts. The shapes here track the
 * customer-safe projections in iranrobot_backend.api.wallet (Phase 8A + 8B).
 *
 * Source of truth is the backend: balance, transactions, and top-up requests
 * are never read from localStorage. Optimistic local writes are avoided --
 * the UI calls reload helpers after every successful create/cancel.
 */

import { frappeFetch, frappePost } from '../lib/frappeApi'

const BASE = 'iranrobot_backend.api.wallet'

// ---------- Types -----------------------------------------------------------

export interface WalletAccount {
  name: string
  customer: string
  currency: 'USD'
  status: 'Active' | 'Frozen' | 'Closed'
  balance_usd: number
  available_balance_usd: number
  last_transaction_at: string | null
}

export type TopUpStatus = 'Pending' | 'Approved' | 'Rejected' | 'Cancelled'
export type TopUpMethod = 'Bank Transfer' | 'Cash Deposit'

export interface WalletTopUpRequest {
  name: string
  status: TopUpStatus
  amount_usd: number
  currency: 'USD'
  method: TopUpMethod
  submitted_at: string
  approved_at: string | null
  rejected_at: string | null
  cancelled_at: string | null
  customer_note: string | null
  bank_reference: string | null
  rejection_reason: string | null
  linked_transaction: string | null
}

export interface WalletSummary {
  wallet: WalletAccount | null
  pending_top_ups: WalletTopUpRequest[]
  can_top_up: boolean
  can_spend: boolean
}

export type WalletTransactionType =
  | 'Top Up'
  | 'Spend'
  | 'Refund'
  | 'Adjustment-Credit'
  | 'Adjustment-Debit'

export interface WalletTransaction {
  name: string
  transaction_type: WalletTransactionType
  direction: 'Credit' | 'Debit'
  currency: 'USD'
  credit_amount_usd: number
  debit_amount_usd: number
  balance_after_usd: number
  posted_at: string
  linked_top_up_request: string | null
  linked_sales_invoice: string | null
  linked_quote_request: string | null
  notes: string | null
}

export interface TopUpInstructions {
  beneficiary: string
  bank_name: string
  iban: string
  currency: 'USD'
  reference: string
}

export interface CreateTopUpResult {
  request_id: string
  status: 'Pending'
  amount_usd: number
  currency: 'USD'
  submitted_at: string
  instructions: TopUpInstructions
}

export interface CancelTopUpResult {
  request_id: string
  status: 'Cancelled'
  cancelled_at: string
  cancelled_by: string
}

// ---------- Reads -----------------------------------------------------------

export async function fetchWalletSummary(signal?: AbortSignal): Promise<WalletSummary> {
  return frappeFetch<WalletSummary>(`${BASE}.get_wallet_summary`, undefined, signal)
}

export async function fetchWalletTransactions(
  limit = 20,
  offset = 0,
  signal?: AbortSignal,
): Promise<{ transactions: WalletTransaction[]; total_count: number }> {
  return frappeFetch<{ transactions: WalletTransaction[]; total_count: number }>(
    `${BASE}.get_wallet_transactions`,
    { limit, offset },
    signal,
  )
}

export async function fetchMyTopUpRequests(
  limit = 20,
  offset = 0,
  status?: TopUpStatus,
  signal?: AbortSignal,
): Promise<{ top_up_requests: WalletTopUpRequest[]; total_count: number }> {
  return frappeFetch<{ top_up_requests: WalletTopUpRequest[]; total_count: number }>(
    `${BASE}.get_my_top_up_requests`,
    { limit, offset, status },
    signal,
  )
}

// ---------- Writes ----------------------------------------------------------

export async function createTopUpRequest(
  amount_usd: number,
  method: TopUpMethod,
  customer_note?: string,
): Promise<CreateTopUpResult> {
  return frappePost<CreateTopUpResult>(`${BASE}.create_top_up_request`, {
    amount_usd,
    method,
    customer_note: customer_note ?? '',
  })
}

export async function cancelTopUpRequest(name: string): Promise<CancelTopUpResult> {
  return frappePost<CancelTopUpResult>(`${BASE}.cancel_top_up_request`, { name })
}
