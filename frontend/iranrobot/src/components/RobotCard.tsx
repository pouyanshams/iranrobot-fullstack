import { motion } from 'framer-motion'
import { Star, ArrowLeft, Plus } from 'lucide-react'
import type { Robot } from '../types'
import { CATEGORIES } from '../data/robots'
import { Badge } from './Badge'
import { RobotIllustration } from './RobotIllustration'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'

interface RobotCardProps {
  robot: Robot
  /**
   * `grid` (default) is the compact catalog card. `featured` is the legacy
   * home-rail premium card with the gradient stage and editorial section.
   * `home` reuses the clean grid styling (no badges, flat white stage) but
   * opens up the description to ~5 lines so the larger home-rail card doesn't
   * leave empty space below the tagline.
   */
  variant?: 'grid' | 'featured' | 'home'
}

export function RobotCard({ robot, variant = 'grid' }: RobotCardProps) {
  const { go, addToCart } = useApp()
  const { t, n, usd, tomanRange, lang } = useI18n()
  const category = CATEGORIES.find((c) => c.id === robot.category)
  const featured = variant === 'featured'
  const home = variant === 'home'

  const modeLabel = (m: string) =>
    m === 'rent' ? t('اجاره', 'Rent') : m === 'procure' ? t('تأمین', 'Source') : t('خرید', 'Buy')

  const specs = lang === 'en' ? robot.specsEn : robot.specs

  // The featured-card editorial extras (Why it's popular / Best for / Key specs)
  // are optional and only ship for hand-curated products in the bundled data
  // file -- the Phase 2 catalog API does not surface these fields. We compute
  // this flag here and use it to drive layout decisions that depend on whether
  // the card will actually render editorial content (row-span, footer push,
  // specs-grid fallback) so empty featured cards no longer leave dead space.
  const editorialBullets = lang === 'en' ? robot.editorialBulletsEn : robot.editorialBullets
  const editorialBestFor = lang === 'en' ? robot.bestForEn : robot.bestFor
  const hasEditorial = featured && ((editorialBullets?.length || 0) > 0 || (editorialBestFor?.length || 0) > 0)

  const hasRating = typeof robot.rating === 'number' && robot.rating > 0

  return (
    <motion.article
      layout
      whileHover={{ y: featured ? -6 : -3 }}
      transition={{ type: 'spring', stiffness: 320, damping: 26 }}
      className={[
        'group relative bg-white overflow-hidden border border-line',
        'shadow-soft hover:shadow-soft-lg transition-shadow duration-300',
        featured ? 'rounded-3xl' : 'rounded-2xl',
        'flex flex-col',
        featured ? 'lg:col-span-2' : '',
        hasEditorial ? 'lg:row-span-2' : '',
      ].join(' ')}
    >
      <button
        type="button"
        onClick={() => go('robot', robot.slug)}
        className="block w-full text-start"
        aria-label={t(robot.name, robot.nameEn)}
      >
        {/*
          Grid variant: no overlay chrome -- the image surface inherits the
          card's white background and RobotIllustration runs in `flat` mode so
          there is no nested gradient stage. Stock / category / sourcing data is
          still on the Robot object for filtering + accessibility (the card
          aria-label is the product name); we just don't render pill badges on
          the artwork. Featured keeps the editorial overlay chrome.
        */}
        <div
          className={[
            'relative',
            featured ? 'aspect-[16/10] sm:aspect-[16/8]' : 'aspect-[5/4]',
          ].join(' ')}
        >
          <RobotIllustration robot={robot} flat={!featured} />
          {featured ? (
            <>
              <div className="absolute top-3 end-3 flex flex-wrap gap-2">
                {robot.inStock ? (
                  <Badge tone="success" dot>{t('موجود', 'In stock')}</Badge>
                ) : (
                  <Badge tone="warning">{t('پیش‌فروش', 'Pre-order')}</Badge>
                )}
                {category ? (
                  <Badge tone="tech">{t(category.label, category.labelEn)}</Badge>
                ) : null}
              </div>
              <div className="absolute bottom-3 start-3 flex gap-1.5">
                {robot.modes.map((m) => (
                  <Badge
                    key={m}
                    tone={m === 'rent' ? 'rent' : m === 'procure' ? 'tech' : 'brand'}
                  >
                    {modeLabel(m)}
                  </Badge>
                ))}
              </div>
            </>
          ) : null}
        </div>
      </button>

      <div
        className={[
          'flex flex-col flex-1',
          featured ? 'p-5 sm:p-6 sm:p-8' : 'p-4 sm:p-5',
        ].join(' ')}
      >
        <div className={['flex items-start justify-between', featured ? 'gap-3' : 'gap-2'].join(' ')}>
          <div className="min-w-0 flex-1">
            {featured ? (
              <div className="flex items-center gap-2 text-xs text-faint mb-1.5">
                <span>{robot.brand}</span>
                <span className="size-1 rounded-full bg-ink-300" />
                <span>{t(`ساخت ${robot.origin}`, `Made in ${robot.originEn}`)}</span>
              </div>
            ) : (
              <div className="text-[11px] text-faint mb-0.5 truncate">{robot.brand}</div>
            )}
            <h3
              className={[
                'leading-tight tracking-tight',
                featured
                  ? 'font-bold text-fg text-2xl sm:text-3xl'
                  : 'font-bold text-ink-900 text-base sm:text-[17px] line-clamp-2',
              ].join(' ')}
            >
              {t(robot.name, robot.nameEn)}
            </h3>
          </div>
          {hasRating ? (
            <div
              className={[
                'flex items-center font-semibold text-amber-600 bg-amber-50 ring-1 ring-amber-100 rounded-full shrink-0',
                featured ? 'gap-1 text-xs px-2.5 py-1.5' : 'gap-0.5 text-[11px] px-1.5 py-0.5',
              ].join(' ')}
            >
              <Star size={featured ? 12 : 11} className="fill-amber-500 text-amber-500" />
              <span className="num-fa">{n(robot.rating!.toFixed(1))}</span>
            </div>
          ) : null}
        </div>

        {/*
          Tagline behaviour:
          - featured: roomy editorial paragraph, unclamped
          - home: 5-line clamp + slightly bigger size so the larger home-rail
            card fills the available vertical space (no big empty gap between
            tagline and footer)
          - grid (catalog): tight 2-line clamp for marketplace browsing density
        */}
        {featured ? (
          <p className="text-sm text-muted mt-3 leading-7 sm:text-base">
            {t(robot.tagline, robot.taglineEn)}
          </p>
        ) : robot.tagline || robot.taglineEn ? (
          <p
            className={[
              'text-muted',
              home
                ? 'text-sm mt-2 leading-6 line-clamp-5'
                : 'text-xs mt-1.5 leading-5 line-clamp-2',
            ].join(' ')}
          >
            {t(robot.tagline, robot.taglineEn)}
          </p>
        ) : null}

        {/* Featured-only specs grid — shown only when editorial content is NOT provided,
            to avoid duplicating the Key Specs block in the editorial section below. */}
        {featured && !(lang === 'en' ? robot.editorialBulletsEn : robot.editorialBullets) ? (
          <div className="mt-5 grid grid-cols-2 gap-3">
            {specs.slice(0, 4).map((s) => (
              <div key={s.label} className="rounded-2xl bg-soft border border-line px-4 py-3">
                <div className="text-[11px] text-faint">{s.label}</div>
                <div className="text-sm font-semibold text-fg mt-0.5 num-fa">{s.value}</div>
              </div>
            ))}
          </div>
        ) : null}

        {/*
          Footer (price + actions). Pinned to the bottom via `mt-auto` whenever
          no editorial section follows; featured-with-editorial leaves the
          footer at natural flow position so EditorialSection can absorb the
          row-span slack via its own lg:flex-1 chain.
        */}
        <div
          className={[
            featured ? 'space-y-4' : 'space-y-3',
            hasEditorial ? 'mt-4' : featured ? 'mt-auto pt-5' : 'mt-auto pt-4',
          ].join(' ')}
        >
          <div className="min-w-0">
            {featured ? <div className="text-[11px] text-faint">{t('قیمت پایه', 'Base price')}</div> : null}
            {typeof robot.priceUsd === 'number' ? (
              <>
                <div
                  className={[
                    'font-extrabold leading-tight text-brand-600 num-fa',
                    featured ? 'mt-1 text-xl' : 'text-base',
                  ].join(' ')}
                >
                  {usd(robot.priceUsd)}
                </div>
                <div className={featured ? 'mt-0.5 text-[11px] text-faint' : 'mt-0.5 text-[10px] text-faint num-fa'}>
                  ≈ {tomanRange(robot.priceUsd)}
                </div>
              </>
            ) : (
              <div
                className={[
                  'font-extrabold leading-tight text-brand-600',
                  featured ? 'mt-1 text-xl' : 'text-sm',
                ].join(' ')}
              >
                {t(robot.priceLabel ?? 'استعلام قیمت', robot.priceLabelEn ?? 'Request quote')}
              </div>
            )}
          </div>

          <div className={featured ? 'grid grid-cols-2 gap-3' : 'grid grid-cols-2 gap-2.5'}>
            <button
              type="button"
              onClick={() => go('robot', robot.slug)}
              className={[
                'inline-flex items-center justify-center rounded-lg border border-line bg-white font-semibold text-fg transition-colors hover:bg-ink-50',
                featured ? 'h-11 px-4 text-sm gap-1.5' : 'h-10 px-3 text-sm gap-1.5',
              ].join(' ')}
            >
              {t('جزئیات', 'Details')}
              <ArrowLeft size={featured ? 15 : 14} className="rtl:rotate-180" />
            </button>
            <button
              type="button"
              onClick={() =>
                addToCart({
                  robotId: robot.id,
                  mode: robot.modes.includes('buy') ? 'buy' : robot.modes[0] ?? 'procure',
                  qty: 1,
                })
              }
              className={[
                'inline-flex items-center justify-center rounded-lg bg-brand-600 font-semibold text-white transition-colors hover:bg-brand-700',
                featured ? 'h-11 px-4 text-sm gap-1.5' : 'h-10 px-3 text-sm gap-1.5',
              ].join(' ')}
            >
              <Plus size={featured ? 15 : 14} />
              {t('افزودن', 'Add')}
            </button>
          </div>
        </div>

        {/* ===== Editorial section — featured-card-only, fills the lower whitespace ===== */}
        {featured ? <EditorialSection robot={robot} /> : null}
      </div>
    </motion.article>
  )
}

function EditorialSection({ robot }: { robot: Robot }) {
  const { t, lang } = useI18n()
  const bullets = lang === 'en' ? robot.editorialBulletsEn : robot.editorialBullets
  const bestFor = lang === 'en' ? robot.bestForEn : robot.bestFor
  const specs = lang === 'en' ? robot.specsEn : robot.specs

  // Render nothing if no editorial data is curated for this product.
  if (!bullets?.length && !bestFor?.length) return null

  // Key specs = first 4 non-SKU rows.
  const keySpecs = specs.filter((s) => !/^sku$|^کد محصول$/i.test(s.label.trim())).slice(0, 4)

  return (
    // Mobile/tablet: vertical grid stack (unchanged).
    // Desktop: switch to flex-col + flex-1 so this section grows to fill the
    // featured card's row-span allotment. The Best for + Key specs panels absorb
    // the slack on desktop so the card never has empty space below the editorial.
    <div className="mt-5 grid gap-4 lg:flex lg:flex-1 lg:flex-col lg:gap-4">
      {bullets?.length ? (
        <div className="rounded-2xl bg-brand-50/40 p-4">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-brand-600">
            {t('چرا محبوب است', 'Why it’s popular')}
          </p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-ink-700">
            {bullets.map((b) => (
              <li key={b} className="flex items-start gap-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-600" />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* On desktop this row becomes a flex-row that stretches vertically (lg:flex-1)
          so its two panels also stretch — backgrounds extend, no empty card space. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:flex lg:flex-1 lg:flex-row lg:items-stretch lg:gap-4">
        {bestFor?.length ? (
          <div className="rounded-2xl border border-line bg-white p-4 lg:flex-1">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-ink-400">
              {t('مناسب برای', 'Best for')}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {bestFor.map((item) => (
                <span
                  key={item}
                  className="rounded-lg bg-soft px-3 py-1.5 text-xs font-semibold text-ink-700"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {keySpecs.length ? (
          <div className="rounded-2xl border border-line bg-white p-4 lg:flex-1">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-ink-400">
              {t('مشخصات کلیدی', 'Key specs')}
            </p>
            <dl className="mt-3 space-y-2 text-sm">
              {keySpecs.map((s) => (
                <div key={s.label} className="flex justify-between gap-3">
                  <dt className="text-ink-500">{s.label}</dt>
                  <dd className="font-semibold text-fg num-fa text-end">{s.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
      </div>
    </div>
  )
}
