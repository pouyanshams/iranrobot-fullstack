import { useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import type { CarouselCategory } from '../data/categoryCarousel'
import { categories } from '../data/categoryCarousel'
import { useI18n } from '../i18n'
import { CategoryBentoCard } from './CategoryBentoCard'

interface BentoTile {
  id: string
  className: string
  featured?: boolean
}

/**
 * Top-level mosaic — editorial magazine spacing.
 *  • mobile  (grid-cols-1)
 *  • tablet  (md:grid-cols-2)
 *  • desktop (lg:grid-cols-12) — 3 rows: 3/6/3 · 6/6 · 3/3/3/3
 */
const LAYOUT: BentoTile[] = [
  { id: 'solutions',    className: 'lg:col-span-3 h-[240px] lg:h-[270px]' },
  { id: 'humanoids',    className: 'lg:col-span-6 h-[260px] lg:h-[270px]', featured: true },
  { id: 'quadrupeds',   className: 'lg:col-span-3 h-[240px] lg:h-[270px]' },
  { id: 'amrs',         className: 'lg:col-span-6 h-[240px] lg:h-[270px]' },
  { id: 'cobots',       className: 'lg:col-span-6 h-[240px] lg:h-[270px]' },
  { id: 'drones',       className: 'lg:col-span-3 h-[210px] lg:h-[230px]' },
  { id: 'ugvs',         className: 'lg:col-span-3 h-[210px] lg:h-[230px]' },
  { id: 'accessories',  className: 'lg:col-span-3 h-[210px] lg:h-[230px]' },
  { id: 'new-arrivals', className: 'lg:col-span-3 h-[210px] lg:h-[230px]' },
]

/** Subcategory drill-down — uniform 4×N grid in the same mosaic style. */
const SUBVIEW_CLASS = 'lg:col-span-3 h-[210px] lg:h-[230px]'

export function CategoryBentoSection() {
  const { t } = useI18n()
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null)

  const selected = activeCategoryId ? categories.find((c) => c.id === activeCategoryId) : null
  const isSubview = !!(selected?.subcategories && selected.subcategories.length > 0)
  const byId = new Map(categories.map((c) => [c.id, c]))

  function handleClick(category: CarouselCategory) {
    if (category.subcategories && category.subcategories.length > 0) {
      setActiveCategoryId(category.id)
      return
    }
    // Other categories: keep existing (no-op) behaviour for now
  }

  function goBack() {
    setActiveCategoryId(null)
  }

  return (
    <section className="py-14">
      {/* Heading stays aligned with the site container */}
      <div className="mx-auto max-w-7xl px-6 lg:px-8 mb-6 sm:mb-8">
        {isSubview ? (
          <>
            <button
              type="button"
              onClick={goBack}
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-700 hover:text-brand-700 mb-3 transition-colors"
            >
              <ArrowLeft size={16} className="rtl:-scale-x-100" />
              {t('بازگشت به دسته‌بندی‌ها', 'Back to categories')}
            </button>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-fg leading-tight">
              {t(`مرور ${selected!.titleFa}`, `Browse ${selected!.title}`)}
            </h2>
          </>
        ) : (
          <>
            <div className="inline-flex items-center gap-2 text-xs font-bold tracking-[0.18em] uppercase mb-2 text-brand-600">
              <span className="h-px w-6 bg-gradient-to-r from-transparent to-brand-500" />
              {t('دسته‌بندی', 'Categories')}
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-fg leading-tight">
              {t('در دسته‌بندی دلخواه جستجو کنید', 'Browse by category')}
            </h2>
          </>
        )}
      </div>

      {/* Mosaic grid — full viewport width, edge to edge */}
      <div className="grid w-full grid-cols-1 gap-[3px] bg-slate-200 md:grid-cols-2 lg:grid-cols-12">
        {isSubview
          ? selected!.subcategories!.map((sub) => (
              <CategoryBentoCard
                key={sub.id}
                category={sub}
                className={SUBVIEW_CLASS}
                onClick={() => handleClick(sub)}
              />
            ))
          : LAYOUT.map((tile) => {
              const category = byId.get(tile.id)
              if (!category) return null
              return (
                <CategoryBentoCard
                  key={tile.id}
                  category={category}
                  className={tile.className}
                  featured={tile.featured}
                  onClick={() => handleClick(category)}
                />
              )
            })}
      </div>
    </section>
  )
}
