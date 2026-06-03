/**
 * Generic data-fetching hook with loading / error / refetch state.
 *
 * Use:
 *   const { data, loading, error, refetch } = useApi(
 *     (signal) => fetchProducts({ category: 'humanoids' }, signal),
 *     [category],
 *   )
 *
 * Callers pass an inline async closure -- it's NOT used as a useEffect dep
 * (each render makes a new closure); instead we hold the latest closure in a
 * ref and re-run only when `deps` (or `refetch`) bumps.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

export interface UseApiResult<T> {
  data: T | null
  loading: boolean
  error: Error | null
  refetch: () => void
}

interface State<T> {
  data: T | null
  loading: boolean
  error: Error | null
}

export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<unknown>,
): UseApiResult<T> {
  const [state, setState] = useState<State<T>>({
    data: null,
    loading: true,
    error: null,
  })
  const [tick, setTick] = useState(0)

  // Keep the latest fetcher accessible to the effect without making it a dep.
  // Updating the ref in a layout effect avoids reads of stale closures during
  // the same commit and keeps "ref-during-render" lint rules satisfied.
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    const ctrl = new AbortController()
    let cancelled = false

    // Reset to "loading" at the start of each fetch cycle. The strict lint rule
    // would prefer derived state, but this hook is the canonical place where a
    // synchronous load transition is required as we kick off the async fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- standard async-fetch hook pattern; cancellation guards prevent cascades
    setState((prev) => (prev.loading && prev.error === null ? prev : { data: prev.data, loading: true, error: null }))

    fetcherRef.current(ctrl.signal)
      .then((value) => {
        if (cancelled) return
        setState({ data: value, loading: false, error: null })
      })
      .catch((e: unknown) => {
        if (cancelled) return
        if ((e as { name?: string })?.name === 'AbortError') return
        setState({
          data: null,
          loading: false,
          error: e instanceof Error ? e : new Error(String(e)),
        })
      })

    return () => {
      cancelled = true
      ctrl.abort()
    }
    // Re-run when the caller-declared `deps` change or refetch() bumps `tick`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const refetch = useCallback(() => setTick((t) => t + 1), [])

  return { data: state.data, loading: state.loading, error: state.error, refetch }
}
