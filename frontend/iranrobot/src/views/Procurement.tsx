import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Check } from 'lucide-react'
import { Section } from '../components/Section'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { Input, Textarea, Select, NumberInput } from '../components/Input'
import { useI18n } from '../i18n'
import { useAuth } from '../lib/useAuth'
import { submitProcurementRequest } from '../api/requests'
import { FrappeApiError } from '../lib/frappeApi'

const COUNTRIES: { fa: string; en: string }[] = [
  { fa: 'آلمان', en: 'Germany' },
  { fa: 'ژاپن', en: 'Japan' },
  { fa: 'کره جنوبی', en: 'South Korea' },
  { fa: 'چین', en: 'China' },
  { fa: 'ایتالیا', en: 'Italy' },
  { fa: 'سوئیس', en: 'Switzerland' },
  { fa: 'فرانسه', en: 'France' },
  { fa: 'آمریکا', en: 'USA' },
  { fa: 'انگلستان', en: 'UK' },
  { fa: 'سایر', en: 'Other' },
]

interface FormState {
  productName: string
  brand: string
  qty: number | null
  country: string
  budget: number | null
  notes: string
  name: string
  phone: string
  email: string
}

interface SubmittedReceipt {
  request_id: string
  status: string
  productName: string
  brand: string
  at: number
}

export function ProcurementView() {
  const { t, n, usd, tomanRange, dateTime } = useI18n()
  const { isAuthenticated, currentUser } = useAuth()
  const STEPS = [t('اطلاعات محصول', 'Product details'), t('مشخصات تجاری', 'Commercial details'), t('اطلاعات تماس', 'Contact details')]
  const [step, setStep] = useState(0)
  const [submitted, setSubmitted] = useState<SubmittedReceipt | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>({
    productName: '', brand: '', qty: 1, country: COUNTRIES[0]!.fa, budget: null, notes: '', name: '', phone: '', email: '',
  })
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})

  function set<K extends keyof FormState>(key: K, v: FormState[K]) {
    setForm((f) => ({ ...f, [key]: v }))
    setErrors((e) => ({ ...e, [key]: undefined }))
  }

  function validateStep(s: number) {
    const next: typeof errors = {}
    if (s === 0) {
      if (!form.productName.trim()) next.productName = t('نام محصول الزامی است', 'Product name is required')
      if (!form.brand.trim()) next.brand = t('برند یا تولیدکننده را وارد کنید', 'Enter a brand or manufacturer')
    }
    if (s === 1) {
      if (!form.qty || form.qty < 1) next.qty = t('تعداد حداقل ۱ باشد', 'Quantity must be at least 1')
    }
    if (s === 2 && !isAuthenticated) {
      if (!form.name.trim()) next.name = t('نام شما الزامی است', 'Your name is required')
      if (!/^[0-9۰-۹+\-\s]{7,}$/.test(form.phone.trim())) next.phone = t('شماره تماس معتبر وارد کنید', 'Enter a valid phone number')
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function next() {
    if (!validateStep(step)) return
    if (step < STEPS.length - 1) {
      setStep(step + 1)
      return
    }
    setSubmitError(null)
    setSubmitting(true)
    try {
      const result = await submitProcurementRequest({
        product_name: form.productName.trim(),
        brand: form.brand.trim(),
        quantity: form.qty ?? 1,
        origin_country: form.country,
        target_budget_usd: form.budget ?? undefined,
        timeline: '',
        message: form.notes.trim(),
        contact_name: isAuthenticated
          ? currentUser?.customer_name ?? currentUser?.full_name ?? ''
          : form.name.trim(),
        email: isAuthenticated ? currentUser?.email ?? '' : form.email.trim(),
        phone: isAuthenticated ? currentUser?.phone ?? '' : form.phone.trim(),
        language: currentUser?.preferred_language ?? 'fa',
      })
      setSubmitted({
        request_id: result.request_id,
        status: result.status,
        productName: form.productName.trim(),
        brand: form.brand.trim(),
        at: Date.now(),
      })
    } catch (e) {
      const msg = e instanceof FrappeApiError
        ? frappeErrorMessage(e, t)
        : t('ارسال درخواست با خطا مواجه شد. دوباره تلاش کنید.', 'Could not submit the request. Try again.')
      setSubmitError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  function reset() {
    setSubmitted(null)
    setStep(0)
    setSubmitError(null)
    setForm({ productName: '', brand: '', qty: 1, country: COUNTRIES[0]!.fa, budget: null, notes: '', name: '', phone: '', email: '' })
  }

  return (
    <Section
      eyebrow={t('تأمین سفارشی', 'Custom sourcing')}
      title={t('ربات مورد نظرتان را برای شما تأمین می‌کنیم', 'We source the robot you need')}
      description={t(
        'اگر ربات خاصی در فروشگاه ما نیست، فرم زیر را پر کنید. تیم تأمین ایران‌ربات طی ۴۸ ساعت استعلام قیمت و زمان تحویل را ارسال می‌کند.',
        "If a specific robot isn't in our shop, fill out the form below. Our sourcing team sends a price and lead-time quote within 48 hours.",
      )}
    >
      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 bg-white border border-line rounded-3xl overflow-hidden shadow-soft">
          <AnimatePresence mode="wait">
            {submitted ? (
              <SubmitSuccess key="ok" receipt={submitted} onReset={reset} />
            ) : (
              <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="p-6 sm:p-8">
                <Stepper step={step} steps={STEPS} />
                <AnimatePresence mode="wait">
                  <motion.div key={step} initial={{ x: 16, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -16, opacity: 0 }} transition={{ duration: 0.25 }} className="mt-6 grid gap-4">
                    {step === 0 ? (
                      <>
                        <Input label={t('نام محصول', 'Product name')} placeholder={t('مثلاً: بازوی همکار شش‌محوره ۶ کیلوگرم', 'e.g. 6 kg six-axis collaborative arm')} value={form.productName} onChange={(e) => set('productName', e.target.value)} error={errors.productName} />
                        <Input label={t('برند یا تولیدکننده', 'Brand or manufacturer')} placeholder="Universal Robots, FANUC" value={form.brand} onChange={(e) => set('brand', e.target.value)} error={errors.brand} />
                        <Textarea label={t('یادداشت / مشخصات فنی', 'Notes / technical specs')} placeholder={t('مدل دقیق، نسخه، آپشن‌های موردنیاز...', 'Exact model, version, required options...')} rows={4} value={form.notes} onChange={(e) => set('notes', e.target.value)} />
                      </>
                    ) : null}
                    {step === 1 ? (
                      <>
                        <div className="grid sm:grid-cols-2 gap-4">
                          <NumberInput label={t('تعداد', 'Quantity')} value={form.qty} onValueChange={(v) => set('qty', v)} min={1} error={errors.qty} />
                          <Select label={t('کشور مبدا', 'Origin country')} value={form.country} onChange={(e) => set('country', e.target.value)}>
                            {COUNTRIES.map((c) => (
                              <option key={c.en} value={c.fa}>{t(c.fa, c.en)}</option>
                            ))}
                          </Select>
                        </div>
                        <NumberInput label={t('بودجه تقریبی (دلار)', 'Approx. budget (USD)')} value={form.budget} onValueChange={(v) => set('budget', v)} hint={t('اختیاری — کمک می‌کند گزینه‌های مناسب‌تری پیشنهاد دهیم', 'Optional — helps us suggest better options')} min={0} leading={<span className="text-sm font-bold">$</span>} />
                      </>
                    ) : null}
                    {step === 2 ? (
                      <>
                        {isAuthenticated ? (
                          <div className="rounded-2xl bg-soft border border-line p-4 text-sm">
                            <div className="text-xs text-faint mb-2">{t('اطلاعات حساب شما', 'Your account details')}</div>
                            <div className="font-bold text-fg">{currentUser?.customer_name || currentUser?.full_name}</div>
                            <div className="text-muted mt-1" dir="ltr">{currentUser?.email}</div>
                            {currentUser?.phone ? (
                              <div className="text-muted num-fa" dir="ltr">{currentUser.phone}</div>
                            ) : null}
                          </div>
                        ) : (
                          <>
                            <Input label={t('نام و نام خانوادگی', 'Full name')} placeholder={t('مثلاً: علی محمدی', 'e.g. Ali Mohammadi')} value={form.name} onChange={(e) => set('name', e.target.value)} error={errors.name} />
                            <Input label={t('ایمیل', 'Email')} type="email" dir="ltr" placeholder="you@company.com" value={form.email} onChange={(e) => set('email', e.target.value)} />
                            <Input label={t('شماره تماس', 'Phone number')} placeholder={t('۰۹۱۲ ۳۴۵ ۶۷۸۹', '0912 345 6789')} dir="ltr" inputMode="tel" value={form.phone} onChange={(e) => set('phone', e.target.value)} error={errors.phone} />
                          </>
                        )}
                        <div className="rounded-2xl bg-soft border border-line p-4">
                          <div className="text-sm font-bold text-fg mb-2">{t('خلاصه درخواست', 'Request summary')}</div>
                          <ul className="text-sm text-muted space-y-1">
                            <li>{t('محصول', 'Product')}: <span className="text-fg">{form.productName || '—'}</span></li>
                            <li>{t('برند', 'Brand')}: <span className="text-fg">{form.brand || '—'}</span></li>
                            <li>{t('تعداد', 'Quantity')}: <span className="num-fa text-fg">{n(form.qty ?? 0)}</span></li>
                            <li>{t('کشور مبدا', 'Origin')}: <span className="text-fg">{t(form.country, COUNTRIES.find((c) => c.fa === form.country)?.en ?? form.country)}</span></li>
                            {form.budget ? (
                              <li>{t('بودجه', 'Budget')}: <span className="num-fa text-fg">{usd(form.budget)}</span> ({tomanRange(form.budget)})</li>
                            ) : null}
                          </ul>
                        </div>
                      </>
                    ) : null}
                  </motion.div>
                </AnimatePresence>

                {submitError ? (
                  <div className="mt-4 rounded-lg bg-brand-50 border border-brand-100 text-brand-700 text-sm px-4 py-3 leading-6">
                    {submitError}
                  </div>
                ) : null}

                <div className="mt-7 flex items-center justify-between gap-3">
                  <Button variant="outline" disabled={step === 0 || submitting} onClick={() => setStep((s) => Math.max(0, s - 1))}>{t('قبلی', 'Back')}</Button>
                  <Button onClick={next} disabled={submitting}>
                    {submitting
                      ? t('در حال ارسال...', 'Submitting...')
                      : step < STEPS.length - 1
                        ? t('مرحله بعد', 'Next step')
                        : t('ثبت درخواست', 'Submit request')}
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <aside className="lg:col-span-5 grid gap-4 content-start">
          <InfoCard
            title={t('چرا تأمین از طریق ایران‌ربات؟', 'Why source through IranRobot?')}
            items={[
              t('دسترسی به بیش از ۳۰ تولیدکننده مستقیم', 'Access to 30+ direct manufacturers'),
              t('مدیریت گمرک، حمل و بیمه', 'Customs, shipping and insurance handled'),
              t('گارانتی و خدمات پس از فروش داخلی', 'Local warranty and after-sales service'),
              t('پرداخت ریالی، فاکتور رسمی', 'Rial payment, official invoice'),
            ]}
          />
          <SessionPanel receipt={submitted} />
        </aside>
      </div>
    </Section>
  )

  function Stepper({ step, steps }: { step: number; steps: string[] }) {
    return (
      <div className="flex items-center gap-2">
        {steps.map((label, i) => {
          const active = i === step
          const done = i < step
          return (
            <div key={label} className="flex items-center gap-2 flex-1">
              <div className={['size-8 rounded-full grid place-items-center text-sm font-bold transition-all shrink-0', done ? 'bg-emerald-500 text-white' : active ? 'bg-brand-600 text-white' : 'bg-ink-100 text-faint'].join(' ')}>
                {done ? <Check size={15} /> : n(i + 1)}
              </div>
              <span className={['text-sm font-semibold whitespace-nowrap', active ? 'text-fg' : 'text-faint'].join(' ')}>{label}</span>
              {i < steps.length - 1 ? <span className="hidden sm:block flex-1 h-px bg-line" /> : null}
            </div>
          )
        })}
      </div>
    )
  }

  function SubmitSuccess({ receipt, onReset }: { receipt: SubmittedReceipt; onReset: () => void }) {
    return (
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="p-10 text-center">
        <div className="mx-auto size-20 rounded-full bg-emerald-50 ring-1 ring-emerald-100 grid place-items-center text-emerald-600">
          <Check size={36} />
        </div>
        <h3 className="mt-5 text-xl font-extrabold text-fg">{t('درخواست تأمین شما ثبت شد', 'Your sourcing request was submitted')}</h3>
        <p className="mt-3 text-sm text-muted leading-7 max-w-md mx-auto">
          {t('کد پیگیری', 'Tracking code')} <span className="font-mono font-bold text-tech-blue">{receipt.request_id}</span> —{' '}
          {t('کارشناس ما طی ۴۸ ساعت کاری تماس می‌گیرد و استعلام قیمت را ارسال می‌کند.', 'Our specialist will contact you within 48 business hours with a quote.')}
        </p>
        <div className="mt-6 inline-flex items-center gap-2">
          <Badge tone="warning">{receipt.status || t('در صف بررسی', 'In review queue')}</Badge>
          <span className="text-xs text-faint">{dateTime(receipt.at)}</span>
        </div>
        <div className="mt-7">
          <Button variant="outline" onClick={onReset}>{t('ثبت درخواست دیگر', 'Submit another request')}</Button>
        </div>
      </motion.div>
    )
  }

  function InfoCard({ title, items }: { title: string; items: string[] }) {
    return (
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-600 to-brand-700 text-white p-6 shadow-[0_18px_44px_-18px_rgba(127, 24, 16,0.5)]">
        <div aria-hidden className="pointer-events-none absolute -top-20 -end-16 size-56 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(255,255,255,0.25), transparent 65%)' }} />
        <h3 className="relative text-lg font-extrabold">{title}</h3>
        <ul className="relative mt-4 space-y-2.5 text-sm leading-7 text-white/90">
          {items.map((i) => (
            <li key={i} className="flex items-start gap-2.5">
              <span className="mt-2 size-1.5 rounded-full bg-white/80 shrink-0" />
              <span>{i}</span>
            </li>
          ))}
        </ul>
      </div>
    )
  }

  function SessionPanel({ receipt }: { receipt: SubmittedReceipt | null }) {
    return (
      <div className="bg-white border border-line rounded-3xl p-6 shadow-soft">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-fg">{t('این جلسه', 'This session')}</h3>
          <Badge tone="neutral">{n(receipt ? 1 : 0)}</Badge>
        </div>
        {receipt ? (
          <div className="mt-3 rounded-2xl bg-soft border border-line p-3">
            <div className="text-sm font-bold text-fg truncate">{receipt.productName}</div>
            <div className="text-xs text-faint truncate">{receipt.brand} • {dateTime(receipt.at)}</div>
            <div className="mt-2 flex items-center gap-2">
              <Badge tone="warning">{receipt.status}</Badge>
              <span className="font-mono text-xs text-tech-blue">{receipt.request_id}</span>
            </div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted leading-7">
            {t(
              'هنوز درخواستی ثبت نکرده‌اید. تاریخچه‌ی کامل در داشبورد فاز ۶ نمایش داده می‌شود.',
              "You haven't submitted any requests yet. Full history will appear in the Phase 6 dashboard.",
            )}
          </p>
        )}
      </div>
    )
  }
}

function frappeErrorMessage(e: FrappeApiError, t: (fa: string, en: string) => string): string {
  switch (e.code) {
    case 'VALIDATION_ERROR':
      return e.message || t('داده‌های واردشده معتبر نیست.', 'Submitted data is invalid.')
    case 'NETWORK_ERROR':
      return t('اتصال به سرور برقرار نشد.', 'Could not reach the server.')
    default:
      return e.message || t('خطای ناشناخته.', 'Unknown error.')
  }
}
