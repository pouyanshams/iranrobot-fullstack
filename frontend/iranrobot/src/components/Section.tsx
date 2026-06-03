import type { ReactNode } from 'react'
import { motion } from 'framer-motion'

export function Section({
  eyebrow,
  title,
  description,
  action,
  children,
  className = '',
  spacing = 'lg',
  align = 'start',
}: {
  eyebrow?: ReactNode
  title?: ReactNode
  description?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  spacing?: 'md' | 'lg'
  align?: 'start' | 'center'
}) {
  const centered = align === 'center'
  return (
    <section
      className={[
        'max-w-7xl mx-auto px-4 sm:px-6',
        spacing === 'lg' ? 'py-16 sm:py-24' : 'py-12 sm:py-16',
        className,
      ].join(' ')}
    >
      {title || description || eyebrow ? (
        <header
          className={[
            'mb-10 sm:mb-14 gap-4',
            centered
              ? 'flex flex-col items-center text-center'
              : 'flex flex-col sm:flex-row sm:items-end sm:justify-between',
          ].join(' ')}
        >
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className={centered ? 'max-w-2xl' : 'max-w-2xl'}
          >
            {eyebrow ? (
              <div className="inline-flex items-center gap-2 text-xs font-bold tracking-[0.18em] uppercase mb-4 text-brand-600">
                <span className="h-px w-6 bg-gradient-to-r from-transparent to-brand-500" />
                {eyebrow}
              </div>
            ) : null}
            {title ? (
              <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-gradient">
                {title}
              </h2>
            ) : null}
            {description ? (
              <p className="mt-4 text-[15px] sm:text-base text-muted leading-8">
                {description}
              </p>
            ) : null}
          </motion.div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  )
}
