import { useState } from 'react'
import { ChevronLeft, Minus, Plus, Star } from 'lucide-react'
import { Section } from '../components/Section'
import { RobotCard } from '../components/RobotCard'
import { RobotIllustration } from '../components/RobotIllustration'
import { ApiError, ApiLoading } from '../components/ApiState'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import { useApi } from '../lib/useApi'
import { CATEGORIES } from '../data/robots'
import {
  categoryToPlpSlug,
  fetchProductDetail,
  mapApiCardToRobot,
  mapApiDetailToRobot,
} from '../api/catalog'
import { FrappeApiError } from '../lib/frappeApi'

export function RobotDetailView({ slug }: { slug: string }) {
  const { go, addToCart } = useApp()
  const { t, n, usd, tomanRange, lang } = useI18n()

  const { data, loading, error, refetch } = useApi(
    (signal) => fetchProductDetail(slug, signal),
    [slug],
  )

  // Reset gallery + qty whenever the slug param changes (state-from-prop pattern).
  const [trackedSlug, setTrackedSlug] = useState(slug)
  const [thumbIndex, setThumbIndex] = useState(0)
  const [qty, setQty] = useState(1)
  if (slug !== trackedSlug) {
    setTrackedSlug(slug)
    setThumbIndex(0)
    setQty(1)
  }

  if (loading) {
    return (
      <Section spacing="md">
        <ApiLoading rows={2} />
      </Section>
    )
  }

  if (error) {
    // The Frappe NOT_FOUND error becomes a friendly "product not found" panel;
    // everything else falls through to the generic ApiError.
    const isNotFound =
      error instanceof FrappeApiError && error.code === 'NOT_FOUND'
    if (isNotFound) {
      return (
        <Section spacing="md">
          <div className="mx-auto max-w-xl bg-white border border-line rounded-2xl p-10 text-center shadow-soft">
            <div className="mx-auto size-16 rounded-full bg-brand-50 ring-1 ring-brand-100 grid place-items-center text-brand-600 text-2xl font-bold">!</div>
            <h2 className="mt-5 text-xl font-bold text-fg">{t('ربات پیدا نشد', 'Product not found')}</h2>
            <p className="mt-2 text-sm text-muted leading-7">
              {t(
                'متأسفانه ربات درخواستی پیدا نشد یا از فهرست خارج شده است.',
                'Sorry, the requested product was not found or is no longer listed.',
              )}
            </p>
            <button
              type="button"
              onClick={() => go('catalog')}
              className="mt-6 inline-flex h-11 items-center justify-center rounded-lg bg-brand-600 px-6 text-sm font-semibold text-white hover:bg-brand-700 transition-colors"
            >
              {t('بازگشت به فروشگاه', 'Back to shop')}
            </button>
          </div>
        </Section>
      )
    }
    return (
      <Section spacing="md">
        <ApiError error={error} onRetry={refetch} />
      </Section>
    )
  }

  if (!data) return null

  const robot = mapApiDetailToRobot(data)
  const related = data.related_products.map(mapApiCardToRobot)

  const category = CATEGORIES.find((c) => c.id === robot.category)
  const specs = lang === 'en' ? robot.specsEn : robot.specs

  // No real gallery UI yet -- the API can return multiple non-hero images, but
  // the page currently shows just the hero. When per-image thumbs land, drive
  // them from robot.gallery (already populated by mapApiDetailToRobot).
  const galleryCount = 1
  const safeIndex = Math.min(thumbIndex, galleryCount - 1)

  const rating = robot.rating
  const stars = [0, 1, 2, 3, 4].map((i) =>
    typeof rating === 'number' ? i < Math.round(rating) : false,
  )
  const cartMode = robot.modes.includes('buy') ? 'buy' : robot.modes[0] ?? 'procure'
  const buyDisabled = !robot.modes.includes('buy')

  const categoryNavSlug = categoryToPlpSlug(robot.category)

  return (
    <Section spacing="md">
      {/* Breadcrumb */}
      <nav className="mb-6 flex items-center gap-2 text-sm text-faint">
        <button type="button" onClick={() => go('catalog')} className="hover:text-brand-700 transition-colors">
          {t('فروشگاه', 'Shop')}
        </button>
        <ChevronLeft size={14} className="rtl:rotate-180" />
        {category ? (
          <>
            <button
              type="button"
              onClick={() => go('catalog', categoryNavSlug ?? undefined)}
              className="hover:text-brand-700 transition-colors"
            >
              {t(category.label, category.labelEn)}
            </button>
            <ChevronLeft size={14} className="rtl:rotate-180" />
          </>
        ) : null}
        <span className="text-fg font-semibold truncate">{t(robot.name, robot.nameEn)}</span>
      </nav>

      {/* Main two-column layout */}
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-2 lg:gap-12">
        {/* ===== Left: gallery ===== */}
        <div className="lg:sticky lg:top-28 lg:self-start">
          <div className="rounded-xl border border-line bg-white p-4 sm:p-6">
            <div className="mx-auto flex aspect-square w-full max-w-[620px] items-center justify-center">
              {robot.image ? (
                <img
                  src={robot.image}
                  alt={t(robot.name, robot.nameEn)}
                  className="max-h-full max-w-full object-contain"
                />
              ) : (
                <RobotIllustration robot={robot} />
              )}
            </div>
          </div>

          {galleryCount > 1 ? (
            <div className="mt-5 flex gap-3 sm:gap-4">
              {Array.from({ length: galleryCount }).map((_, i) => {
                const active = i === safeIndex
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setThumbIndex(i)}
                    aria-label={t(`نمای ${i + 1}`, `View ${i + 1}`)}
                    className={[
                      'flex h-20 w-20 items-center justify-center rounded-lg border bg-white p-2 transition-colors sm:h-24 sm:w-24',
                      active ? 'border-brand-600' : 'border-line hover:border-brand-600/40',
                    ].join(' ')}
                  >
                    {robot.image ? (
                      <img
                        src={robot.image}
                        alt={t(robot.name, robot.nameEn)}
                        className="max-h-full max-w-full object-contain"
                      />
                    ) : (
                      <div className="h-full w-full overflow-hidden rounded-md">
                        <RobotIllustration robot={robot} />
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>

        {/* ===== Right: product info ===== */}
        <div>
          {/* Brand line */}
          <div className="text-sm text-faint">
            {robot.brand} · {t(`ساخت ${robot.origin}`, `Made in ${robot.originEn}`)}
          </div>

          {/* Title */}
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-fg lg:text-4xl leading-tight">
            {t(robot.name, robot.nameEn)}
          </h1>

          {/* Rating row */}
          <div className="mt-3 flex items-center gap-2">
            <div className="flex items-center gap-0.5">
              {stars.map((filled, i) => (
                <Star
                  key={i}
                  size={16}
                  className={filled ? 'fill-amber-400 text-amber-400' : 'fill-ink-100 text-ink-200'}
                />
              ))}
            </div>
            {typeof rating === 'number' ? (
              <>
                <span className="text-sm font-semibold num-fa text-fg">{n(rating.toFixed(1))}</span>
                <span className="text-xs text-faint">/ {n(5)}</span>
              </>
            ) : (
              <span className="text-xs text-faint">{t('بدون نظر', 'No reviews yet')}</span>
            )}
          </div>

          {/* Description */}
          <p className="mt-5 text-[15px] leading-8 text-muted">
            {t(robot.description, robot.descriptionEn)}
          </p>

          {/* Stock */}
          <div className="mt-5">
            {robot.inStock ? (
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700">
                <span className="size-2 rounded-full bg-emerald-500" />
                {t('موجود در انبار', 'In stock')}
              </span>
            ) : (
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-amber-700">
                <span className="size-2 rounded-full bg-amber-500" />
                {t('در صورت درخواست تأمین می‌شود', 'Available on request')}
              </span>
            )}
          </div>

          {/* Specs table */}
          {specs.length > 0 ? (
            <dl className="mt-6 divide-y divide-line border-y border-line">
              {specs.map((s) => (
                <div key={s.label} className="grid grid-cols-2 gap-4 py-3 text-sm">
                  <dt className="font-bold uppercase tracking-wide text-ink-700">{s.label}</dt>
                  <dd className="text-fg num-fa">{s.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}

          {/* Price */}
          <div className="mt-7">
            <div className="text-xs text-faint">{t('قیمت پایه', 'Base price')}</div>
            {typeof robot.priceUsd === 'number' ? (
              <>
                <div className="mt-1 text-3xl font-extrabold num-fa text-brand-600">
                  {usd(robot.priceUsd)}
                </div>
                <div className="mt-1 text-xs text-faint">≈ {tomanRange(robot.priceUsd)}</div>
              </>
            ) : (
              <div className="mt-1 text-3xl font-extrabold text-brand-600">
                {t(robot.priceLabel ?? 'استعلام قیمت', robot.priceLabelEn ?? 'Request quote')}
              </div>
            )}
          </div>

          {/* Quantity + Add To Cart row */}
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-stretch">
            <QtyStepper value={qty} onChange={setQty} n={n} t={t} />
            <button
              type="button"
              onClick={() => addToCart({ robotId: robot.id, mode: cartMode, qty })}
              disabled={buyDisabled && cartMode === 'procure'}
              className={[
                'inline-flex h-12 flex-1 items-center justify-center rounded-lg px-6 text-sm font-semibold transition-colors',
                buyDisabled
                  ? 'bg-ink-200 text-ink-500 cursor-not-allowed'
                  : 'bg-brand-600 text-white hover:bg-brand-700',
              ].join(' ')}
            >
              {buyDisabled
                ? t('فقط با استعلام قیمت', 'Quote only')
                : t('افزودن به سبد خرید', 'Add To Cart')}
            </button>
          </div>

          {/* Add To Quote — full width */}
          <button
            type="button"
            onClick={() => addToCart({ robotId: robot.id, mode: 'procure', qty })}
            className="mt-3 inline-flex h-12 w-full items-center justify-center rounded-lg border border-brand-600 bg-white px-6 text-sm font-semibold text-brand-600 transition-colors hover:bg-brand-50"
          >
            {t('افزودن به پیش‌فاکتور', 'Add To Quote')}
          </button>
        </div>
      </div>

      {/* ===== Related products (from API) ===== */}
      {related.length > 0 ? (
        <div className="mt-16 lg:mt-20">
          <div className="mb-6 flex items-end justify-between gap-4">
            <h2 className="text-2xl font-extrabold text-fg sm:text-3xl">
              {t('محصولات مرتبط', 'Related products')}
            </h2>
            <button
              type="button"
              onClick={() => go('catalog')}
              className="hidden text-sm font-semibold text-brand-600 hover:text-brand-700 sm:inline-flex"
            >
              {t('مشاهده همه', 'View all')}
            </button>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {related.map((r) => (
              <RobotCard key={r.id} robot={r} />
            ))}
          </div>
        </div>
      ) : null}
    </Section>
  )
}

function QtyStepper({
  value,
  onChange,
  n,
  t,
}: {
  value: number
  onChange: (v: number) => void
  n: (v: number | string) => string
  t: (fa: string, en: string) => string
}) {
  return (
    <div className="inline-flex h-12 items-stretch overflow-hidden rounded-lg border border-line bg-white">
      <button
        type="button"
        onClick={() => onChange(Math.max(1, value - 1))}
        className="grid w-12 place-items-center text-ink-700 hover:bg-ink-50 disabled:opacity-40"
        aria-label={t('کاهش', 'Decrease')}
        disabled={value <= 1}
      >
        <Minus size={16} />
      </button>
      <div className="grid min-w-[3rem] place-items-center px-3 text-base font-bold num-fa text-fg">
        {n(value)}
      </div>
      <button
        type="button"
        onClick={() => onChange(value + 1)}
        className="grid w-12 place-items-center text-ink-700 hover:bg-ink-50"
        aria-label={t('افزایش', 'Increase')}
      >
        <Plus size={16} />
      </button>
    </div>
  )
}
