import type { ReactNode } from 'react'

type Tone =
  | 'brand'
  | 'tech'
  | 'neutral'
  | 'success'
  | 'warning'
  | 'glass'
  | 'rent'

const TONES: Record<Tone, string> = {
  brand: 'bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100',
  tech: 'bg-blue-soft text-tech-blue ring-1 ring-inset ring-blue-200',
  rent: 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-100',
  neutral: 'bg-ink-100 text-ink-700 ring-1 ring-inset ring-ink-200',
  success: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-100',
  warning: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-100',
  glass: 'bg-white/15 text-white ring-1 ring-inset ring-white/25 backdrop-blur',
}

export function Badge({
  tone = 'neutral',
  children,
  className = '',
  dot,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
  dot?: boolean
}) {
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full',
        TONES[tone],
        className,
      ].join(' ')}
    >
      {dot ? <span className="size-1.5 rounded-full bg-current animate-pulse-glow" /> : null}
      {children}
    </span>
  )
}
