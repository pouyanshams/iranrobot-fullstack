import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import type { Lang } from './types'
import { loadJSON, saveJSON } from './lib/storage'
import { localizeDigits } from './lib/numerals'
import {
  formatDate,
  formatDateTime,
  formatToman,
  formatTomanRange,
  formatUsd,
} from './lib/format'

interface I18nValue {
  lang: Lang
  dir: 'rtl' | 'ltr'
  setLang: (l: Lang) => void
  toggle: () => void
  /** Pick the string for the active language. */
  t: (fa: string, en: string) => string
  /** Localize digits (Persian vs western). */
  n: (v: number | string) => string
  usd: (v: number) => string
  toman: (v: number) => string
  tomanRange: (usdValue: number) => string
  date: (ts: number) => string
  dateTime: (ts: number) => string
}

const I18nContext = createContext<I18nValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => loadJSON<Lang>('lang', 'fa'))
  const dir: 'rtl' | 'ltr' = lang === 'fa' ? 'rtl' : 'ltr'

  useEffect(() => {
    saveJSON('lang', lang)
    const el = document.documentElement
    el.lang = lang
    el.dir = dir
  }, [lang, dir])

  const setLang = useCallback((l: Lang) => setLangState(l), [])
  const toggle = useCallback(() => setLangState((l) => (l === 'fa' ? 'en' : 'fa')), [])

  const value = useMemo<I18nValue>(
    () => ({
      lang,
      dir,
      setLang,
      toggle,
      t: (fa, en) => (lang === 'fa' ? fa : en),
      n: (v) => localizeDigits(v, lang),
      usd: (v) => formatUsd(v, lang),
      toman: (v) => formatToman(v, lang),
      tomanRange: (v) => formatTomanRange(v, lang),
      date: (ts) => formatDate(ts, lang),
      dateTime: (ts) => formatDateTime(ts, lang),
    }),
    [lang, dir, setLang, toggle],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components -- provider + hook colocated by design
export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within LanguageProvider')
  return ctx
}
