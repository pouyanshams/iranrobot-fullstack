import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, ArrowRight, RotateCcw, Sparkles } from 'lucide-react'
import { Section } from '../components/Section'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import type { Robot, RobotCategory } from '../types'
import { RobotCard } from '../components/RobotCard'
import { ApiError, ApiInlineLoading } from '../components/ApiState'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import { useApi } from '../lib/useApi'
import { fetchProducts, mapApiCardToRobot } from '../api/catalog'

type Budget = 'lt5k' | '5k-20k' | '20k-50k' | 'gt50k' | 'flex'
type Mode = 'buy' | 'rent' | 'procure'
type Urgency = 'now' | 'month' | 'flex'

interface Answers {
  useCase: RobotCategory | null
  budget: Budget | null
  mode: Mode | null
  urgency: Urgency | null
}

interface Opt<T extends string> {
  id: T
  label: string
  sub: string
  icon?: string
}

function priceRange(b: Budget): [number, number] {
  switch (b) {
    case 'lt5k': return [0, 5000]
    case '5k-20k': return [5000, 20000]
    case '20k-50k': return [20000, 50000]
    case 'gt50k': return [50000, Number.POSITIVE_INFINITY]
    default: return [0, Number.POSITIVE_INFINITY]
  }
}

function scoreRobot(r: Robot, a: Answers): number {
  let score = 0
  if (a.useCase && r.category === a.useCase) score += 50
  if (a.mode && r.modes.includes(a.mode)) score += 25
  if (a.budget && typeof r.priceUsd === 'number') {
    const [lo, hi] = priceRange(a.budget)
    if (r.priceUsd >= lo && r.priceUsd <= hi) score += 20
    else if (a.budget === 'flex') score += 10
    else {
      const closeness = 1 - Math.min(1, Math.abs(r.priceUsd - (lo + hi) / 2) / Math.max(hi - lo, 1))
      score += 10 * closeness
    }
  } else if (a.budget === 'flex') {
    score += 10
  }
  if (a.urgency === 'now' && r.inStock) score += 15
  if (a.urgency === 'month' && r.leadTimeDays <= 35) score += 10
  if (a.urgency === 'flex') score += 5
  score += r.rating ?? 0
  return score
}

export function FinderView() {
  const { go } = useApp()
  const { t, n } = useI18n()
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Answers>({ useCase: null, budget: null, mode: null, urgency: null })

  // Fetch the full catalog once -- the scorer runs locally on the result.
  const products = useApi(
    (signal) => fetchProducts({ limit: 100, sort: 'display_order' }, signal),
    [],
  )
  const allRobots = useMemo<Robot[]>(
    () => (products.data?.products ?? []).map(mapApiCardToRobot),
    [products.data],
  )

  const USE_CASES: Opt<RobotCategory>[] = [
    { id: 'industrial', label: t('تولید صنعتی', 'Industrial production'), sub: t('مونتاژ، جوش، پیک‌اند‌پلیس', 'Assembly, welding, pick-and-place'), icon: '⚙️' },
    { id: 'service', label: t('خدمات و هتلداری', 'Service & hospitality'), sub: t('سرو غذا، تحویل، خوش‌آمدگویی', 'Serving, delivery, greeting'), icon: '🛎️' },
    { id: 'mobile', label: t('انبار و لجستیک', 'Warehouse & logistics'), sub: t('حمل پالت، بازرسی محیطی', 'Pallet transport, inspection'), icon: '🛻' },
    { id: 'humanoid', label: t('تحقیق و توسعه', 'Research & development'), sub: t('پلتفرم پژوهشی، AI، مدل کنترل', 'Research platform, AI, control'), icon: '🤖' },
    { id: 'educational', label: t('آموزش و دانش‌آموزی', 'Education & students'), sub: t('STEM، مدرسه، دانشگاه', 'STEM, schools, universities'), icon: '🎓' },
    { id: 'drone', label: t('نقشه‌برداری هوایی', 'Aerial surveying'), sub: t('فتوگرامتری، بازرسی پروژه', 'Photogrammetry, inspection'), icon: '🛸' },
  ]
  const BUDGETS: Opt<Budget>[] = [
    { id: 'lt5k', label: t('زیر $5K', 'Under $5K'), sub: t('پروژه‌های کوچک و آموزشی', 'Small & educational projects') },
    { id: '5k-20k', label: '$5K – $20K', sub: t('خدمات و کاربری متوسط', 'Service & mid-tier use') },
    { id: '20k-50k', label: '$20K – $50K', sub: t('صنعت و حمل و نقل', 'Industry & logistics') },
    { id: 'gt50k', label: t('بالای $50K', 'Above $50K'), sub: t('تخصصی، تحقیقاتی، سنگین', 'Specialized, research, heavy') },
    { id: 'flex', label: t('منعطف است', 'Flexible'), sub: t('بسته به ROI بررسی می‌کنیم', "We'll assess by ROI") },
  ]
  const MODES: Opt<Mode>[] = [
    { id: 'buy', label: t('خرید', 'Buy'), sub: t('دارایی، گارانتی بلندمدت', 'Asset, long-term warranty') },
    { id: 'rent', label: t('اجاره', 'Rent'), sub: t('پروژه‌ی کوتاه، POC', 'Short project, POC') },
    { id: 'procure', label: t('تأمین خارجی', 'Foreign sourcing'), sub: t('برند خاص، سفارش‌سازی', 'Specific brand, custom') },
  ]
  const URGENCY: Opt<Urgency>[] = [
    { id: 'now', label: t('فوری (≤ ۲ هفته)', 'Urgent (≤ 2 weeks)'), sub: t('فقط موجود در انبار', 'In-stock only') },
    { id: 'month', label: t('تا یک ماه', 'Within a month'), sub: t('پیش‌فروش و تحویل سریع', 'Pre-order & fast delivery') },
    { id: 'flex', label: t('منعطف', 'Flexible'), sub: t('فرصت بررسی همه‌ی گزینه‌ها', 'Time to review all options') },
  ]
  const STEPS = [t('کاربری', 'Use case'), t('بودجه', 'Budget'), t('نوع همکاری', 'Model'), t('فوریت', 'Urgency')]
  const TITLES = [
    t('ربات برای چه کاربری‌ست؟', 'What will the robot be used for?'),
    t('بودجه‌ی شما چقدر است؟', "What's your budget?"),
    t('مدل همکاری دلخواه؟', 'Preferred engagement model?'),
    t('چه زمانی به ربات نیاز دارید؟', 'When do you need the robot?'),
  ]

  const recommendations = useMemo(
    () =>
      [...allRobots]
        .map((r) => ({ r, s: scoreRobot(r, answers) }))
        .sort((a, b) => b.s - a.s)
        .slice(0, 3)
        .map((x) => x.r),
    [allRobots, answers],
  )

  const next = () => setStep((s) => s + 1)
  const restart = () => {
    setStep(0)
    setAnswers({ useCase: null, budget: null, mode: null, urgency: null })
  }

  const isResult = step >= STEPS.length

  return (
    <Section
      eyebrow={t('ربات‌یاب هوشمند', 'Smart Robot Finder')}
      title={t('چند پرسش ساده، یک پیشنهاد دقیق', 'A few simple questions, one precise recommendation')}
      description={t('پاسخ‌های شما را با موجودی فعلی و سابقه پروژه‌های مشابه تطبیق می‌دهیم.', 'We match your answers with current stock and similar past projects.')}
    >
      <div className="bg-white border border-line rounded-3xl overflow-hidden shadow-soft">
        {!isResult ? (
          <div className="p-6 sm:p-10">
            <div>
              <div className="flex items-center gap-3 text-sm font-semibold text-faint">
                <span className="text-brand-600 font-bold num-fa">{n(step + 1)}</span>
                <span>{t('از', 'of')}</span>
                <span className="num-fa">{n(STEPS.length)}</span>
                <span className="mx-2 h-1.5 w-32 sm:w-64 rounded-full bg-ink-200 overflow-hidden">
                  <motion.span className="block h-full rounded-full bg-gradient-to-r from-brand-500 to-tech-blue" initial={false} animate={{ width: `${((step + 1) / STEPS.length) * 100}%` }} transition={{ ease: [0.16, 1, 0.3, 1] }} />
                </span>
              </div>
              <h3 className="mt-3 text-2xl sm:text-3xl font-extrabold text-gradient">{TITLES[step]}</h3>
            </div>

            <AnimatePresence mode="wait">
              <motion.div key={step} initial={{ y: 16, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -16, opacity: 0 }} transition={{ duration: 0.25 }} className="mt-8">
                {step === 0 ? <ChoiceGrid options={USE_CASES} value={answers.useCase} onSelect={(v) => { setAnswers((a) => ({ ...a, useCase: v })); next() }} /> : null}
                {step === 1 ? <ChoiceGrid options={BUDGETS} value={answers.budget} onSelect={(v) => { setAnswers((a) => ({ ...a, budget: v })); next() }} /> : null}
                {step === 2 ? <ChoiceGrid options={MODES} value={answers.mode} onSelect={(v) => { setAnswers((a) => ({ ...a, mode: v })); next() }} /> : null}
                {step === 3 ? <ChoiceGrid options={URGENCY} value={answers.urgency} onSelect={(v) => { setAnswers((a) => ({ ...a, urgency: v })); next() }} /> : null}
              </motion.div>
            </AnimatePresence>

            <div className="mt-8 flex items-center justify-between">
              <Button variant="ghost" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))} leading={<ArrowRight size={16} />}>
                {t('بازگشت', 'Back')}
              </Button>
              <button type="button" onClick={restart} className="text-sm text-faint hover:text-brand-600 inline-flex items-center gap-1.5">
                <RotateCcw size={14} />
                {t('شروع دوباره', 'Start over')}
              </button>
            </div>
          </div>
        ) : (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="p-6 sm:p-10">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <Badge tone="tech" dot><Sparkles size={12} />{t('پیشنهاد ربات‌یاب', 'Finder recommendation')}</Badge>
                <h3 className="mt-3 text-2xl sm:text-3xl font-extrabold text-gradient">{t('بر اساس پاسخ‌های شما، این ۳ گزینه پیشنهاد ماست', 'Based on your answers, here are our top 3')}</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge tone="neutral">{USE_CASES.find((u) => u.id === answers.useCase)?.label ?? '—'}</Badge>
                  <Badge tone="neutral">{BUDGETS.find((b) => b.id === answers.budget)?.label ?? '—'}</Badge>
                  <Badge tone="neutral">{MODES.find((m) => m.id === answers.mode)?.label ?? '—'}</Badge>
                  <Badge tone="neutral">{URGENCY.find((u) => u.id === answers.urgency)?.label ?? '—'}</Badge>
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <Button variant="outline" onClick={restart}>{t('تنظیم دوباره', 'Adjust')}</Button>
                <Button onClick={() => go('catalog')}>{t('مشاهده فروشگاه کامل', 'View full shop')}</Button>
              </div>
            </div>

            <div className="mt-8">
              {products.loading ? (
                <ApiInlineLoading
                  label={t('در حال تحلیل کاتالوگ…', 'Analyzing the catalog…')}
                />
              ) : products.error ? (
                <ApiError error={products.error} onRetry={products.refetch} />
              ) : recommendations.length > 0 ? (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {recommendations.map((r) => (
                    <RobotCard key={r.id} robot={r} />
                  ))}
                </div>
              ) : null}
            </div>
          </motion.div>
        )}
      </div>
    </Section>
  )
}

function ChoiceGrid<T extends string>({
  options,
  value,
  onSelect,
}: {
  options: Opt<T>[]
  value: T | null
  onSelect: (v: T) => void
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {options.map((opt) => {
        const active = opt.id === value
        return (
          <motion.button
            key={opt.id}
            type="button"
            whileTap={{ scale: 0.98 }}
            whileHover={{ y: -3 }}
            onClick={() => onSelect(opt.id)}
            className={[
              'group text-start rounded-2xl p-5 border transition-all shadow-soft',
              active ? 'bg-brand-50 border-brand-200 shadow-[0_16px_40px_-20px_rgba(127, 24, 16,0.4)]' : 'bg-white border-line hover:border-tech-blue/40 hover:shadow-soft-lg',
            ].join(' ')}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                {opt.icon ? <div className="text-2xl mb-3">{opt.icon}</div> : null}
                <div className="font-bold text-fg">{opt.label}</div>
                <div className="text-xs text-muted mt-1 leading-6">{opt.sub}</div>
              </div>
              <div className={['size-6 rounded-full grid place-items-center transition-all shrink-0', active ? 'bg-brand-600 text-white' : 'bg-ink-100 text-ink-400 group-hover:bg-ink-200'].join(' ')}>
                <Check size={13} />
              </div>
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}
