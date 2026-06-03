import { AnimatePresence, motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { useEffect } from 'react'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  side?: 'left' | 'right'
  children: ReactNode
  footer?: ReactNode
  width?: string
}

export function Drawer({
  open,
  onClose,
  title,
  side = 'left',
  children,
  footer,
  width = 'w-[min(420px,92vw)]',
}: DrawerProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  const x = side === 'left' ? '-100%' : '100%'

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-ink-900/50 backdrop-blur-sm"
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            initial={{ x }}
            animate={{ x: 0 }}
            exit={{ x }}
            transition={{ type: 'spring', stiffness: 320, damping: 36 }}
            className={[
              'fixed top-0 bottom-0 z-50 bg-white shadow-soft-lg flex flex-col',
              side === 'left' ? 'left-0' : 'right-0',
              width,
            ].join(' ')}
          >
            <span
              className="pointer-events-none absolute inset-y-0 w-px"
              style={{
                [side === 'left' ? 'right' : 'left']: 0,
                background:
                  'linear-gradient(to bottom, transparent, rgba(127, 24, 16,0.4), transparent)',
              } as React.CSSProperties}
            />
            <header className="flex items-center justify-between px-6 h-16 border-b border-line shrink-0">
              <h2 className="text-lg font-bold text-fg">{title}</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="بستن"
                className="size-9 rounded-full hover:bg-ink-100 text-faint hover:text-fg grid place-items-center transition-colors"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </header>
            <div className="flex-1 overflow-y-auto">{children}</div>
            {footer ? (
              <div className="border-t border-line px-6 py-4 bg-soft shrink-0">{footer}</div>
            ) : null}
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  )
}
