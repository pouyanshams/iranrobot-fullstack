/**
 * Phase 8C wallet hooks. Mirror the `useMyInvoices` pattern from Account.tsx
 * (Phase 7D): AbortController cleanup on unmount, manual reload via tick bump,
 * loud `FrappeApiError` surfacing.
 *
 * No localStorage. No polling. Manual reloads after create/cancel are wired
 * by the caller -- in Phase 8C that's WalletView.
 *
 * When `enabled === false` the effect simply does not fetch, leaving the
 * internal state at its initial values. We avoid the
 * `react-hooks/set-state-in-effect` lint rule by NOT calling setState inside
 * the effect's disabled branch -- the disabled state is returned directly.
 */

import { useCallback, useEffect, useState } from 'react'

import {
  fetchMyTopUpRequests,
  fetchWalletSummary,
  fetchWalletTransactions,
  type WalletSummary,
  type WalletTopUpRequest,
  type WalletTransaction,
} from '../api/wallet'
import { FrappeApiError } from './frappeApi'

function errorMessage(err: unknown): string {
  if (err instanceof FrappeApiError) return err.message || err.code
  if (err instanceof Error) return err.message
  return 'Unknown error'
}

// ---------- summary --------------------------------------------------------

export interface WalletSummaryState {
  data: WalletSummary | null
  loading: boolean
  error: string | null
  reload: () => void
}

const DISABLED_SUMMARY: WalletSummaryState = {
  data: null,
  loading: false,
  error: null,
  reload: () => {},
}

export function useWalletSummary(enabled: boolean = true): WalletSummaryState {
  const [data, setData] = useState<WalletSummary | null>(null)
  const [loading, setLoading] = useState<boolean>(enabled)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect -- standard "load on mount / refetch on key change" pattern
    setLoading(true)
    setError(null)
    fetchWalletSummary(controller.signal)
      .then((s) => {
        if (!controller.signal.aborted) {
          setData(s)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        if ((err as { name?: string })?.name === 'AbortError') return
        setError(errorMessage(err))
        setLoading(false)
      })
    return () => controller.abort()
  }, [enabled, tick])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  if (!enabled) return DISABLED_SUMMARY
  return { data, loading, error, reload }
}

// ---------- transactions ---------------------------------------------------

export interface WalletTransactionsState {
  data: WalletTransaction[] | null
  totalCount: number
  loading: boolean
  error: string | null
  reload: () => void
}

const DISABLED_TX: WalletTransactionsState = {
  data: null,
  totalCount: 0,
  loading: false,
  error: null,
  reload: () => {},
}

export function useWalletTransactions(
  enabled: boolean = true,
  limit: number = 20,
): WalletTransactionsState {
  const [data, setData] = useState<WalletTransaction[] | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState<boolean>(enabled)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect -- standard "load on mount / refetch on key change" pattern
    setLoading(true)
    setError(null)
    fetchWalletTransactions(limit, 0, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) {
          setData(res.transactions)
          setTotalCount(res.total_count)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        if ((err as { name?: string })?.name === 'AbortError') return
        setError(errorMessage(err))
        setLoading(false)
      })
    return () => controller.abort()
  }, [enabled, limit, tick])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  if (!enabled) return DISABLED_TX
  return { data, totalCount, loading, error, reload }
}

// ---------- top-up requests -------------------------------------------------

export interface WalletTopUpRequestsState {
  data: WalletTopUpRequest[] | null
  totalCount: number
  loading: boolean
  error: string | null
  reload: () => void
}

const DISABLED_TOPUPS: WalletTopUpRequestsState = {
  data: null,
  totalCount: 0,
  loading: false,
  error: null,
  reload: () => {},
}

export function useMyTopUpRequests(
  enabled: boolean = true,
  limit: number = 20,
): WalletTopUpRequestsState {
  const [data, setData] = useState<WalletTopUpRequest[] | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState<boolean>(enabled)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect -- standard "load on mount / refetch on key change" pattern
    setLoading(true)
    setError(null)
    fetchMyTopUpRequests(limit, 0, undefined, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) {
          setData(res.top_up_requests)
          setTotalCount(res.total_count)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        if ((err as { name?: string })?.name === 'AbortError') return
        setError(errorMessage(err))
        setLoading(false)
      })
    return () => controller.abort()
  }, [enabled, limit, tick])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  if (!enabled) return DISABLED_TOPUPS
  return { data, totalCount, loading, error, reload }
}
