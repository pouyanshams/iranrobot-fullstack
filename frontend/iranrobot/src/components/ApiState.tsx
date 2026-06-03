/**
 * Tiny presentational helpers for the three API states (loading / error / empty).
 * Used by every page that consumes a `useApi(...)` result so the styling stays
 * consistent without redesigning anything.
 */

import { AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import { useI18n } from '../i18n'

export function ApiLoading({ rows = 6 }: { rows?: number }) {
  const { t } = useI18n()
  return (
    <div
      className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={t('در حال بارگذاری', 'Loading')}
    >
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="rounded-3xl border border-line bg-white p-5 shadow-soft"
        >
          <div className="aspect-[4/3] w-full animate-pulse rounded-2xl bg-soft" />
          <div className="mt-4 h-3 w-1/3 animate-pulse rounded bg-soft" />
          <div className="mt-2 h-5 w-2/3 animate-pulse rounded bg-soft" />
          <div className="mt-3 h-3 w-5/6 animate-pulse rounded bg-soft" />
          <div className="mt-5 flex gap-3">
            <div className="h-10 flex-1 animate-pulse rounded-lg bg-soft" />
            <div className="h-10 flex-1 animate-pulse rounded-lg bg-soft" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ApiError({
  error,
  onRetry,
}: {
  error: Error
  onRetry?: () => void
}) {
  const { t } = useI18n()
  return (
    <div className="mx-auto max-w-xl rounded-2xl border border-line bg-white p-10 text-center shadow-soft">
      <div className="mx-auto grid size-14 place-items-center rounded-full bg-amber-50 ring-1 ring-amber-100 text-amber-600">
        <AlertCircle size={24} />
      </div>
      <h3 className="mt-5 text-lg font-bold text-fg">
        {t('بارگذاری ناموفق بود', 'Could not load data')}
      </h3>
      <p className="mt-2 text-sm text-muted leading-7">
        {t(
          'ارتباط با سرور برقرار نشد. لطفاً اتصال خود را بررسی کنید و دوباره تلاش کنید.',
          'We could not reach the server. Check your connection and try again.',
        )}
      </p>
      <p className="mt-2 text-xs text-faint" dir="ltr">
        {error.message}
      </p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 inline-flex h-11 items-center gap-2 rounded-lg bg-brand-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
        >
          <RefreshCw size={16} />
          {t('تلاش دوباره', 'Try again')}
        </button>
      ) : null}
    </div>
  )
}

export function ApiEmpty({
  title,
  description,
}: {
  title?: string
  description?: string
}) {
  const { t } = useI18n()
  return (
    <div className="rounded-xl border border-dashed border-line bg-white p-10 text-center">
      <h3 className="text-lg font-semibold text-fg">
        {title ?? t('محصولی یافت نشد', 'No products found')}
      </h3>
      <p className="mt-2 text-sm text-muted">
        {description ??
          t(
            'هنوز محصولی به این دسته اضافه نشده است.',
            'No products have been added to this category yet.',
          )}
      </p>
    </div>
  )
}

export function ApiInlineLoading({ label }: { label?: string }) {
  const { t } = useI18n()
  return (
    <div
      className="inline-flex items-center gap-2 text-sm text-muted"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Loader2 size={16} className="animate-spin" />
      <span>{label ?? t('در حال بارگذاری…', 'Loading…')}</span>
    </div>
  )
}
