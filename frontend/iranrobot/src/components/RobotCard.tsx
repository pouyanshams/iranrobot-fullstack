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
  variant?: 'grid' | 'featured'
}

export function RobotCard({ robot, variant = 'grid' }: RobotCardProps) {
  const { go, addToCart } = useApp()
  const { t, n, usd, tomanRange, lang } = useI18n()
  const category = CATEGORIES.find((c) => c.id === robot.category)
  const featured = variant === 'featured'

  const modeLabel = (m: string) =>
    m === 'rent' ? t('اجاره', 'Rent') : m === 'procure' ? t('تأمین', 'Source') : t('خرید', 'Buy')

  const specs = lang === 'en' ? robot.specsEn : robot.specs

  return (
    <motion.article
      layout
      whileHover={{ y: -6 }}
      transition={{ type: 'spring', stiffness: 320, damping: 26 }}
      className={[
        'group relative bg-white rounded-3xl overflow-hidden border border-line',
        'shadow-soft hover:shadow-soft-lg transition-shadow duration-300',
        // On desktop, the featured card spans 2 rows. Make it a flex-col so its
        // inner content can grow vertically and absorb the row-span height — no
        // empty space below the editorial section. Mobile is untouched.
        featured ? 'lg:col-span-2 lg:row-span-2 lg:flex lg:flex-col' : '',
      ].join(' ')}
    >
      <button
        type="button"
        onClick={() => go('robot', robot.slug)}
        className="block w-full text-start"
        aria-label={t(robot.name, robot.nameEn)}
      >
        <div className={['relative', featured ? 'aspect-[16/10] sm:aspect-[16/8]' : 'aspect-[4/3]'].join(' ')}>
          <RobotIllustration robot={robot} />
          <div className="absolute top-3 end-3 flex flex-wrap gap-2">
            {robot.inStock ? <Badge tone="success" dot>{t('موجود', 'In stock')}</Badge> : <Badge tone="warning">{t('پیش‌فروش', 'Pre-order')}</Badge>}
            {category ? <Badge tone="tech">{t(category.label, category.labelEn)}</Badge> : null}
          </div>
          <div className="absolute bottom-3 start-3 flex gap-1.5">
            {robot.modes.map((m) => (
              <Badge key={m} tone={m === 'rent' ? 'rent' : m === 'procure' ? 'tech' : 'brand'}>
                {modeLabel(m)}
              </Badge>
            ))}
          </div>
        </div>
      </button>

      <div
        className={[
          'p-5 sm:p-6',
          // Desktop only: grow vertically inside the featured flex-col article so
          // children below can use lg:flex-1 to absorb the row-span slack.
          featured ? 'sm:p-8 lg:flex lg:flex-1 lg:flex-col' : '',
        ].join(' ')}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs text-faint mb-1.5">
              <span>{robot.brand}</span>
              <span className="size-1 rounded-full bg-ink-300" />
              <span>{t(`ساخت ${robot.origin}`, `Made in ${robot.originEn}`)}</span>
            </div>
            <h3 className={['font-bold text-fg leading-tight', featured ? 'text-2xl sm:text-3xl' : 'text-lg'].join(' ')}>
              {t(robot.name, robot.nameEn)}
            </h3>
          </div>
          {typeof robot.rating === 'number' ? (
            <div className="flex items-center gap-1 text-xs font-semibold text-amber-600 bg-amber-50 ring-1 ring-amber-100 rounded-full px-2.5 py-1.5 shrink-0">
              <Star size={12} className="fill-amber-500 text-amber-500" />
              <span className="num-fa">{n(robot.rating.toFixed(1))}</span>
            </div>
          ) : null}
        </div>

        <p className={['text-sm text-muted mt-3 leading-7', featured ? 'sm:text-base' : 'line-clamp-2'].join(' ')}>
          {t(robot.tagline, robot.taglineEn)}
        </p>

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

        {/* ===== Footer: price stacked above the buttons row ===== */}
        <div className="mt-5 space-y-4">
          {/* Price block */}
          <div className="min-w-0">
            <div className="text-[11px] text-faint">{t('قیمت پایه', 'Base price')}</div>
            {typeof robot.priceUsd === 'number' ? (
              <>
                <div className="mt-1 text-xl font-extrabold leading-tight text-brand-600 num-fa">
                  {usd(robot.priceUsd)}
                </div>
                <div className="mt-0.5 text-[11px] text-faint">≈ {tomanRange(robot.priceUsd)}</div>
              </>
            ) : (
              <div className="mt-1 text-xl font-extrabold leading-tight text-brand-600">
                {t(robot.priceLabel ?? 'استعلام قیمت', robot.priceLabelEn ?? 'Request quote')}
              </div>
            )}
          </div>

          {/* Buttons row — equal-width grid so neither button can collide with the price */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => go('robot', robot.slug)}
              className="inline-flex h-11 items-center justify-center gap-1.5 rounded-lg border border-line bg-white px-4 text-sm font-semibold text-fg transition-colors hover:bg-ink-50"
            >
              {t('جزئیات', 'Details')}
              <ArrowLeft size={15} className="rtl:rotate-180" />
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
              className="inline-flex h-11 items-center justify-center gap-1.5 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
            >
              <Plus size={15} />
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
