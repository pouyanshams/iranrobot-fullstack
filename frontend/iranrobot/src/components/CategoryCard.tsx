import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import type { PlpCategory } from '../data/categories'
import { useI18n } from '../i18n'

interface CategoryCardProps {
  category: PlpCategory
  active: boolean
  count: number
  onClick: () => void
}

export function CategoryCard({ category, active, count, onClick }: CategoryCardProps) {
  const { t, n } = useI18n()
  const [imgFailed, setImgFailed] = useState(false)
  const label = t(category.label, category.labelEn)

  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileHover={{ y: -4 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 320, damping: 24 }}
      aria-pressed={active}
      aria-label={label}
      className={[
        'group relative flex flex-col items-center text-center rounded-3xl bg-white p-4 sm:p-5',
        'border transition-all duration-200',
        active
          ? 'border-brand-300 shadow-[0_16px_40px_-18px_rgba(127, 24, 16,0.45)] ring-2 ring-brand-200'
          : 'border-line shadow-soft hover:shadow-soft-lg hover:border-line-strong',
      ].join(' ')}
    >
      {/* active check */}
      {active ? (
        <span className="absolute top-2.5 end-2.5 z-10 grid place-items-center size-6 rounded-full bg-brand-600 text-white shadow">
          <Check size={14} />
        </span>
      ) : null}

      {/* square image */}
      <div className="relative w-full aspect-square rounded-2xl overflow-hidden bg-gradient-to-br from-ink-50 to-base-2">
        <div className="absolute inset-0 grid-faint opacity-40" />
        {!imgFailed ? (
          <img
            src={category.image}
            alt={label}
            loading="lazy"
            decoding="async"
            onError={() => setImgFailed(true)}
            className="absolute inset-0 size-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 grid place-items-center">
            <span className="text-4xl sm:text-5xl opacity-80 transition-transform duration-200 group-hover:scale-110">
              {category.icon}
            </span>
          </div>
        )}
        <div className="absolute inset-0 ring-1 ring-inset ring-black/5 rounded-2xl" />
      </div>

      <div className="mt-3 sm:mt-4">
        <div className={['font-bold text-sm sm:text-base leading-tight', active ? 'text-brand-700' : 'text-fg'].join(' ')}>
          {label}
        </div>
        <div className="mt-0.5 text-[11px] sm:text-xs text-faint num-fa">
          {n(count)} {t('محصول', count === 1 ? 'product' : 'products')}
        </div>
      </div>
    </motion.button>
  )
}
