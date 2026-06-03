import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { ShieldCheck, MapPin, RefreshCw } from 'lucide-react'
import { Section } from '../components/Section'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { NumberInput, Select } from '../components/Input'
import { ApiError, ApiInlineLoading } from '../components/ApiState'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import { RobotIllustration } from '../components/RobotIllustration'
import { useApi } from '../lib/useApi'
import { fetchProducts, mapApiCardToRobot } from '../api/catalog'

export function RentView() {
  const { addToCart } = useApp()
  const { t, n, usd, tomanRange } = useI18n()

  // Fetch the catalog (filtered server-side to mode_rent=1 -> rentables only).
  const products = useApi(
    (signal) =>
      fetchProducts(
        { limit: 100, sort: 'display_order', is_featured: undefined, search: undefined },
        signal,
      ),
    [],
  )
  const rentable = useMemo(
    () =>
      (products.data?.products ?? [])
        .map(mapApiCardToRobot)
        .filter((r) => r.modes.includes('rent') && r.rentPerDayUsd),
    [products.data],
  )

  const [selectedId, setSelectedId] = useState<string>('')
  const [days, setDays] = useState<number | null>(7)
  const [qty, setQty] = useState<number | null>(1)
  const [withOperator, setWithOperator] = useState(false)

  // Default-select the first rentable robot once data arrives (without useEffect).
  const effectiveSelectedId =
    selectedId || (rentable[0]?.id ?? '')
  const selected = useMemo(
    () => rentable.find((r) => r.id === effectiveSelectedId),
    [effectiveSelectedId, rentable],
  )

  const safeDays = Math.max(1, days ?? 1)
  const safeQty = Math.max(1, qty ?? 1)
  const baseDaily = selected?.rentPerDayUsd ?? 0
  const operatorRate = 80
  const dailyTotal = baseDaily + (withOperator ? operatorRate : 0)
  const subTotal = dailyTotal * safeDays * safeQty
  const discountRatio = safeDays >= 30 ? 0.15 : safeDays >= 14 ? 0.08 : safeDays >= 7 ? 0.04 : 0
  const discount = Math.round(subTotal * discountRatio)
  const total = subTotal - discount

  return (
    <Section
      eyebrow={t('اجاره روزانه', 'Daily rental')}
      title={t('ماشین‌حساب اجاره ربات', 'Robot rental calculator')}
      description={t(
        'مدل دلخواه را انتخاب کنید، تعداد روز را وارد کنید، در لحظه قیمت دلاری و تخمین تومانی را ببینید.',
        'Pick a model, enter the number of days, and see the USD price and Toman estimate instantly.',
      )}
    >
      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 bg-white border border-line rounded-3xl p-6 sm:p-8 shadow-soft">
          {products.loading ? (
            <ApiInlineLoading
              label={t('در حال بارگذاری مدل‌های قابل اجاره…', 'Loading rentable models…')}
            />
          ) : products.error ? (
            <ApiError error={products.error} onRetry={products.refetch} />
          ) : rentable.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-line bg-white p-6 text-center text-sm text-muted">
              {t(
                'هنوز هیچ مدلی برای اجاره ثبت نشده است.',
                'No rentable models are listed yet.',
              )}
            </div>
          ) : (
            <Select
              label={t('انتخاب ربات', 'Select a robot')}
              value={effectiveSelectedId}
              onChange={(e) => setSelectedId(e.target.value)}
            >
              {rentable.map((r) => (
                <option key={r.id} value={r.id}>
                  {t(r.name, r.nameEn)} — {usd(r.rentPerDayUsd ?? 0)}/{t('روز', 'day')}
                </option>
              ))}
            </Select>
          )}

          {selected ? (
            <div className="mt-5 rounded-3xl bg-soft border border-line p-4 flex gap-4 items-center">
              <div className="size-24 rounded-2xl overflow-hidden border border-line shrink-0">
                <RobotIllustration robot={selected} />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-faint">{selected.brand}</div>
                <div className="font-bold text-fg truncate">{t(selected.name, selected.nameEn)}</div>
                <div className="text-xs text-muted mt-1 leading-6 line-clamp-2">{t(selected.tagline, selected.taglineEn)}</div>
              </div>
            </div>
          ) : null}

          <div className="grid sm:grid-cols-2 gap-4 mt-6">
            <NumberInput label={t('مدت اجاره (روز)', 'Rental duration (days)')} value={days} onValueChange={setDays} min={1} max={365} hint={t('اعداد فارسی هم پذیرفته می‌شوند', 'Persian digits are also accepted')} />
            <NumberInput label={t('تعداد دستگاه', 'Number of units')} value={qty} onValueChange={setQty} min={1} max={50} />
          </div>

          <label className="mt-5 flex items-start gap-3 bg-soft border border-line rounded-2xl p-4 cursor-pointer hover:border-line-strong transition-colors">
            <input type="checkbox" checked={withOperator} onChange={(e) => setWithOperator(e.target.checked)} className="mt-1 size-4 accent-brand-600" />
            <div className="flex-1">
              <div className="text-sm font-bold text-fg">{t('اپراتور و راه‌اندازی در محل', 'On-site operator & setup')}</div>
              <div className="text-xs text-muted mt-0.5">
                {t('کارشناس فنی برای راه‌اندازی روزانه — افزوده‌ی', 'A technician for daily setup — adds')}{' '}
                <span className="num-fa font-semibold text-tech-blue">{usd(operatorRate)}</span> {t('در روز', 'per day')}
              </div>
            </div>
          </label>

          <div className="mt-7 flex flex-wrap gap-2">
            {[3, 7, 14, 30, 90].map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setDays(v)}
                className={[
                  'h-9 px-4 rounded-lg text-sm font-semibold transition-colors num-fa border',
                  safeDays === v ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-ink-700 border-line hover:bg-ink-50',
                ].join(' ')}
              >
                {n(v)} {t('روز', 'days')}
              </button>
            ))}
          </div>
        </div>

        <aside className="lg:col-span-5">
          <motion.div layout className="relative surface-navy rounded-3xl p-6 sm:p-8 sticky top-24 overflow-hidden shadow-soft-lg">
            <div aria-hidden className="pointer-events-none absolute -top-24 -start-20 size-64 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(127, 24, 16,0.28), transparent 65%)' }} />
            <Badge tone="glass" dot>{t('برآورد اجاره', 'Rental estimate')}</Badge>
            <div className="relative mt-3">
              <div className="text-ink-400 text-xs">{t('نرخ روزانه', 'Daily rate')}</div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-extrabold num-fa text-white">{usd(dailyTotal)}</span>
                <span className="text-sm text-ink-400">/ {t('روز', 'day')}</span>
              </div>
            </div>

            <div className="relative mt-6 grid grid-cols-2 gap-3">
              <Stat label={t('مدت', 'Duration')} value={`${n(safeDays)} ${t('روز', 'days')}`} />
              <Stat label={t('تعداد', 'Units')} value={`${n(safeQty)} ${t('دستگاه', 'units')}`} />
              <Stat label={t('جمع کل', 'Subtotal')} value={usd(subTotal)} />
              <Stat label={t('تخفیف', 'Discount')} value={discount > 0 ? `−${usd(discount)}` : '—'} />
            </div>

            <div className="relative mt-6 pt-6 border-t border-white/10">
              <div className="text-ink-400 text-xs">{t('قابل پرداخت', 'Total payable')}</div>
              <div className="flex items-baseline justify-between">
                <span className="text-4xl font-extrabold num-fa text-white">{usd(total)}</span>
                {discountRatio > 0 ? <Badge tone="success">{n(Math.round(discountRatio * 100))}{t('٪ تخفیف', '% off')}</Badge> : null}
              </div>
              <div className="text-xs text-ink-400 mt-2">≈ {tomanRange(total)}</div>
            </div>

            <div className="relative mt-6">
              <Button
                fullWidth
                size="lg"
                onClick={() => {
                  if (!selected) return
                  addToCart({ robotId: selected.id, mode: 'rent', qty: safeQty, days: safeDays })
                }}
              >
                {t('افزودن به سبد اجاره', 'Add to rental cart')}
              </Button>
            </div>
          </motion.div>
        </aside>
      </div>

      <div className="mt-12 grid sm:grid-cols-3 gap-4">
        {[
          { t: t('پشتیبانی در محل', 'On-site support'), d: t('تیم فنی در طول دوره اجاره در دسترس است.', 'A technical team is available throughout the rental.'), Icon: MapPin },
          { t: t('بیمه دستگاه', 'Equipment insurance'), d: t('بیمه‌ی آسیب فیزیکی و خرابی فنی شامل اجاره است.', 'Physical damage and technical failure insurance is included.'), Icon: ShieldCheck },
          { t: t('تمدید آسان', 'Easy extension'), d: t('تمدید روزانه با همان نرخ تخفیف‌خورده.', 'Extend daily at the same discounted rate.'), Icon: RefreshCw },
        ].map((f) => (
          <div key={f.t} className="bg-white border border-line rounded-3xl p-6 shadow-soft">
            <div className="size-10 rounded-2xl bg-blue-soft ring-1 ring-blue-200 grid place-items-center text-tech-blue">
              <f.Icon size={18} />
            </div>
            <div className="mt-3 text-sm font-bold text-fg">{f.t}</div>
            <div className="text-xs text-muted mt-1 leading-6">{f.d}</div>
          </div>
        ))}
      </div>
    </Section>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white/8 border border-white/10 p-3">
      <div className="text-[11px] text-ink-400">{label}</div>
      <div className="text-sm font-bold num-fa mt-0.5 text-white">{value}</div>
    </div>
  )
}
