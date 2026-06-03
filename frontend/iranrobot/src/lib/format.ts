import type { Lang } from '../types'
import { toFa } from './numerals'

/** Approximate USD → IRR Toman rate used only for indicative on-page ranges. */
export const USD_TO_TOMAN = 95_000

function dig(s: string, lang: Lang): string {
  return lang === 'fa' ? toFa(s) : s
}

/** Indicative ±6% band around the central toman estimate. */
export function tomanRange(priceUsd: number): { low: number; high: number; mid: number } {
  const mid = priceUsd * USD_TO_TOMAN
  return {
    mid,
    low: Math.round((mid * 0.94) / 100_000) * 100_000,
    high: Math.round((mid * 1.06) / 100_000) * 100_000,
  }
}

export function formatUsd(value: number, lang: Lang = 'fa'): string {
  const s = value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
  return dig(s, lang)
}

export function formatNumber(value: number, lang: Lang = 'fa'): string {
  return dig(value.toLocaleString('en-US'), lang)
}

export function formatToman(value: number, lang: Lang = 'fa'): string {
  const s = Math.round(value).toLocaleString('en-US')
  return lang === 'fa' ? `${toFa(s)} تومان` : `${s} Toman`
}

export function formatTomanRange(priceUsd: number, lang: Lang = 'fa'): string {
  const { low, high } = tomanRange(priceUsd)
  const l = low.toLocaleString('en-US')
  const h = high.toLocaleString('en-US')
  return lang === 'fa'
    ? `${toFa(l)} تا ${toFa(h)} تومان`
    : `${l} – ${h} Toman`
}

export function formatDate(ts: number, lang: Lang = 'fa'): string {
  try {
    return new Intl.DateTimeFormat(lang === 'fa' ? 'fa-IR' : 'en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    }).format(ts)
  } catch {
    return dig(new Date(ts).toLocaleDateString(), lang)
  }
}

export function formatDateTime(ts: number, lang: Lang = 'fa'): string {
  try {
    return new Intl.DateTimeFormat(lang === 'fa' ? 'fa-IR' : 'en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(ts)
  } catch {
    return dig(new Date(ts).toLocaleString(), lang)
  }
}
