import { useState } from 'react'
import { ArrowUpRight } from 'lucide-react'
import type { CarouselCategory } from '../data/categoryCarousel'
import { useI18n } from '../i18n'

interface CategoryBentoCardProps {
  category: CarouselCategory
  /** Column-span + height utilities controlling this tile in the bento grid. */
  className?: string
  /** Larger title for the hero / featured tile (e.g. Humanoids). */
  featured?: boolean
  onClick?: () => void
}

/**
 * Flat mosaic tile — no rounded corners, no border, no shadow.
 * Tiles sit edge-to-edge; dividers come from the grid wrapper's gap colour.
 */
export function CategoryBentoCard({
  category,
  className = '',
  featured = false,
  onClick,
}: CategoryBentoCardProps) {
  const { t } = useI18n()
  const [imgFailed, setImgFailed] = useState(false)
  const title = t(category.titleFa, category.title)
  const hasImage = !!category.image && !imgFailed

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={title}
      className={[
        'group relative overflow-hidden bg-slate-900 text-start',
        className,
      ].join(' ')}
    >
      {/* Image — full tile cover, subtle zoom on hover */}
      {hasImage ? (
        <img
          src={category.image}
          alt={title}
          loading="lazy"
          decoding="async"
          onError={() => setImgFailed(true)}
          className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
      ) : (
        <div
          aria-hidden
          className="absolute inset-0"
          style={{ background: 'linear-gradient(155deg, #11192a 0%, #0a1120 55%, #050811 100%)' }}
        />
      )}

      {/* Dark gradient overlay so titles stay readable */}
      <div
        aria-hidden
        className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent"
      />

      {/* Title + arrow row */}
      <div className="absolute bottom-5 inset-x-5 z-10 flex items-end justify-between gap-3">
        <h3
          className={[
            'font-extrabold text-white leading-tight',
            featured ? 'text-2xl sm:text-3xl lg:text-4xl' : 'text-xl lg:text-2xl',
          ].join(' ')}
        >
          {title}
        </h3>
        <span
          aria-hidden
          className="flex h-10 w-10 items-center justify-center border border-white/40 bg-black/30 text-white backdrop-blur-sm"
        >
          <ArrowUpRight size={18} className="rtl:-scale-x-100" />
        </span>
      </div>
    </button>
  )
}
