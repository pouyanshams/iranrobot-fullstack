const FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
const EN_DIGIT_MAP: Record<string, string> = {
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
}

export function toFa(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)] ?? d)
}

/** Localize digits for the active language (fa → Persian, en → western). */
export function localizeDigits(value: string | number, lang: 'fa' | 'en'): string {
  return lang === 'fa' ? toFa(String(value)) : toEn(String(value))
}

export function toEn(value: string): string {
  return value.replace(/[۰-۹٠-٩]/g, (d) => EN_DIGIT_MAP[d] ?? d)
}

export function parseLocalizedNumber(value: string): number | null {
  const cleaned = toEn(value).replace(/[,\s٬]/g, '').trim()
  if (cleaned === '' || cleaned === '-') return null
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

export function formatFaNumber(value: number, fractionDigits = 0): string {
  return toFa(
    value.toLocaleString('en-US', {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }),
  )
}
