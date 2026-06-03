import { useMemo, useState } from 'react'
import { Check, ShoppingBag, Minus, Plus } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useAuth } from '../lib/useAuth'
import { useI18n } from '../i18n'
import { getRobotById } from '../data/robots'
import { Drawer } from './Drawer'
import { Button } from './Button'
import { Badge } from './Badge'
import { Input } from './Input'
import { RobotIllustration } from './RobotIllustration'
import { submitQuoteRequest } from '../api/requests'
import { FrappeApiError } from '../lib/frappeApi'

interface SubmittedQuote {
  request_id: string
  status: string
}

export function QuoteDrawer() {
  const {
    cart, cartOpen, setCartOpen, updateCartLine, removeCartLine, clearCart, go,
  } = useApp()
  const { currentUser, isAuthenticated } = useAuth()
  const { t, n, usd, tomanRange } = useI18n()

  const [submitted, setSubmitted] = useState<SubmittedQuote | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Guest contact form (only used when !isAuthenticated)
  const [guestName, setGuestName] = useState('')
  const [guestEmail, setGuestEmail] = useState('')
  const [guestPhone, setGuestPhone] = useState('')
  const [guestMessage, setGuestMessage] = useState('')

  const modeLabel = (m: string) =>
    m === 'rent' ? t('اجاره', 'Rent') : m === 'procure' ? t('تأمین', 'Source') : t('خرید', 'Buy')

  const lines = useMemo(
    () =>
      cart
        .map((l) => {
          const robot = getRobotById(l.robotId)
          if (!robot) return null
          const unit =
            l.mode === 'rent'
              ? (robot.rentPerDayUsd ?? 0) * (l.days ?? 1)
              : (robot.priceUsd ?? 0)
          return { line: l, robot, unit, subtotal: unit * l.qty }
        })
        .filter((v): v is NonNullable<typeof v> => v !== null),
    [cart],
  )

  const totalUsd = lines.reduce((s, l) => s + l.subtotal, 0)
  const isEmpty = lines.length === 0

  function resetSubmit() {
    setSubmitted(null)
    setSubmitError(null)
    setGuestName('')
    setGuestEmail('')
    setGuestPhone('')
    setGuestMessage('')
  }

  async function submitQuote() {
    if (isEmpty || submitting) return
    setSubmitError(null)

    if (!isAuthenticated) {
      // Quick client-side guard so we don't bounce the server on obvious misses.
      if (!guestName.trim()) {
        setSubmitError(t('نام شما الزامی است.', 'Your name is required.'))
        return
      }
      if (!guestEmail.trim() && !guestPhone.trim()) {
        setSubmitError(t('ایمیل یا شماره تماس را وارد کنید.', 'Provide an email or phone number.'))
        return
      }
    }

    setSubmitting(true)
    try {
      const payload = await submitQuoteRequest({
        items: lines.map(({ line }) => ({
          robot_product: line.robotId,
          quantity: line.qty,
          mode: line.mode,
          requested_days: line.mode === 'rent' ? (line.days ?? 1) : undefined,
          notes: line.notes ?? '',
        })),
        customer_name: isAuthenticated
          ? currentUser?.customer_name ?? currentUser?.full_name ?? ''
          : guestName.trim(),
        email: isAuthenticated ? currentUser?.email ?? '' : guestEmail.trim(),
        phone: isAuthenticated ? currentUser?.phone ?? '' : guestPhone.trim(),
        message: isAuthenticated ? '' : guestMessage.trim(),
        language: currentUser?.preferred_language ?? 'fa',
      })
      setSubmitted({ request_id: payload.request_id, status: payload.status })
      clearCart()
    } catch (e) {
      const msg = e instanceof FrappeApiError
        ? frappeErrorMessage(e, t)
        : t('ارسال درخواست با خطا مواجه شد. دوباره تلاش کنید.', 'Could not submit the request. Try again.')
      setSubmitError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Drawer
      open={cartOpen}
      onClose={() => setCartOpen(false)}
      title={t('سبد و درخواست استعلام', 'Cart & quote request')}
      side="left"
      width="w-[min(460px,94vw)]"
      footer={
        submitted ? (
          <Button fullWidth onClick={() => { resetSubmit(); setCartOpen(false) }}>
            {t('متوجه شدم', 'Got it')}
          </Button>
        ) : isEmpty ? (
          <Button fullWidth onClick={() => { setCartOpen(false); go('catalog') }}>
            {t('مشاهده فروشگاه', 'View shop')}
          </Button>
        ) : (
          <div className="grid gap-3">
            {totalUsd > 0 ? (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted">{t('تخمین مجموع', 'Estimated total')}</span>
                <span className="text-lg font-extrabold text-brand-600 num-fa">{usd(totalUsd)}</span>
              </div>
            ) : (
              <div className="text-xs text-muted leading-5">
                {t(
                  'قیمت نهایی پس از بررسی توسط کارشناس فروش اعلام می‌شود.',
                  'Final pricing is sent by our sales team after review.',
                )}
              </div>
            )}
            {totalUsd > 0 ? (
              <div className="text-xs text-faint">≈ {tomanRange(totalUsd)}</div>
            ) : null}
            {submitError ? (
              <div className="rounded-lg bg-brand-50 border border-brand-100 text-brand-700 text-xs px-3 py-2 leading-6">
                {submitError}
              </div>
            ) : null}
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" onClick={clearCart} disabled={submitting}>
                {t('خالی کردن', 'Clear')}
              </Button>
              <Button onClick={submitQuote} disabled={submitting}>
                {submitting
                  ? t('در حال ارسال...', 'Submitting...')
                  : t('ثبت درخواست استعلام', 'Submit quote request')}
              </Button>
            </div>
            <div className="text-[11px] text-center text-faint leading-5">
              {isAuthenticated
                ? t('این درخواست به حساب شما متصل می‌شود.', 'This request will be linked to your account.')
                : t('برای پیگیری بهتر، می‌توانید وارد حساب خود شوید.', 'You can sign in for easier tracking.')}
            </div>
          </div>
        )
      }
    >
      {submitted ? (
        <SubmitSuccess id={submitted.request_id} status={submitted.status} />
      ) : isEmpty ? (
        <EmptyState />
      ) : (
        <div className="p-4 grid gap-3">
          <ul className="grid gap-3">
            {lines.map(({ line, robot, subtotal }) => (
              <li key={line.id} className="rounded-3xl bg-soft border border-line p-3">
                <div className="flex gap-3">
                  <div className="size-20 rounded-2xl overflow-hidden border border-line shrink-0">
                    <RobotIllustration robot={robot} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-bold text-fg truncate">{t(robot.name, robot.nameEn)}</h4>
                      <button type="button" onClick={() => removeCartLine(line.id)} className="text-xs text-faint hover:text-brand-600 shrink-0">
                        {t('حذف', 'Remove')}
                      </button>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-xs">
                      <Badge tone={line.mode === 'rent' ? 'rent' : 'brand'}>{modeLabel(line.mode)}</Badge>
                      {line.mode === 'rent' ? <span className="text-faint num-fa">{n(line.days ?? 1)} {t('روز', 'days')}</span> : null}
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <Stepper value={line.qty} onChange={(v) => updateCartLine(line.id, { qty: v })} n={n} />
                      {subtotal > 0 ? (
                        <div className="text-sm font-bold num-fa text-fg">{usd(subtotal)}</div>
                      ) : (
                        <div className="text-xs text-muted">{t('استعلام', 'Quote')}</div>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {!isAuthenticated ? (
            <div className="mt-2 rounded-2xl border border-dashed border-line bg-white p-4 grid gap-3">
              <div className="text-sm font-semibold text-fg">
                {t('اطلاعات تماس برای پیگیری', 'Contact details for follow-up')}
              </div>
              <Input
                label={t('نام', 'Name')}
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
              />
              <Input
                label={t('ایمیل', 'Email')}
                type="email"
                dir="ltr"
                value={guestEmail}
                onChange={(e) => setGuestEmail(e.target.value)}
              />
              <Input
                label={t('شماره تماس', 'Phone')}
                inputMode="tel"
                dir="ltr"
                value={guestPhone}
                onChange={(e) => setGuestPhone(e.target.value)}
              />
              <Input
                label={t('یادداشت (اختیاری)', 'Notes (optional)')}
                value={guestMessage}
                onChange={(e) => setGuestMessage(e.target.value)}
              />
            </div>
          ) : null}
        </div>
      )}
    </Drawer>
  )
}

function SubmitSuccess({ id, status }: { id: string; status: string }) {
  const { t } = useI18n()
  return (
    <div className="p-6 text-center">
      <div className="mx-auto size-20 rounded-full bg-emerald-50 ring-1 ring-emerald-100 grid place-items-center text-emerald-600">
        <Check size={36} />
      </div>
      <h3 className="mt-5 text-xl font-bold text-fg">
        {t('درخواست استعلام شما ثبت شد', 'Your quote request was submitted')}
      </h3>
      <p className="mt-2 text-sm text-muted leading-7">
        {t('کد پیگیری', 'Tracking code')}{' '}
        <span className="font-mono font-bold text-tech-blue">{id}</span>
      </p>
      <div className="mt-4 inline-flex items-center gap-2">
        <Badge tone="warning">{status || t('در صف بررسی', 'In review queue')}</Badge>
      </div>
      <p className="mt-4 text-xs text-faint leading-6">
        {t(
          'کارشناس فروش طی ۲۴ ساعت کاری تماس می‌گیرد.',
          'A sales rep will reach out within 24 business hours.',
        )}
      </p>
    </div>
  )
}

function Stepper({ value, onChange, n }: { value: number; onChange: (n: number) => void; n: (v: number | string) => string }) {
  return (
    <div className="inline-flex items-center bg-white border border-line rounded-lg">
      <button type="button" onClick={() => onChange(Math.max(1, value - 1))} className="size-8 grid place-items-center text-faint hover:text-brand-600" aria-label="−">
        <Minus size={14} />
      </button>
      <span className="w-7 text-center text-sm font-semibold num-fa text-fg">{n(value)}</span>
      <button type="button" onClick={() => onChange(value + 1)} className="size-8 grid place-items-center text-faint hover:text-tech-blue" aria-label="+">
        <Plus size={14} />
      </button>
    </div>
  )
}

function EmptyState() {
  const { t } = useI18n()
  return (
    <div className="p-10 text-center">
      <div className="mx-auto size-24 rounded-full bg-brand-50 ring-1 ring-brand-100 grid place-items-center text-brand-600">
        <ShoppingBag size={40} />
      </div>
      <h3 className="mt-5 text-base font-bold text-fg">{t('سبد خالی است', 'Your cart is empty')}</h3>
      <p className="mt-2 text-sm text-muted leading-7">{t('برای شروع، یکی از ربات‌های فروشگاه را اضافه کنید یا با ابزار ربات‌یاب بهترین گزینه را پیدا کنید.', 'Add a robot from the shop to start, or use the Robot Finder to discover the best option.')}</p>
    </div>
  )
}

function frappeErrorMessage(e: FrappeApiError, t: (fa: string, en: string) => string): string {
  switch (e.code) {
    case 'EMPTY_CART':
      return t('سبد خالی است.', 'Your cart is empty.')
    case 'INVALID_PRODUCT':
      return t('یکی از محصولات سبد قابل پردازش نیست.', 'One of the cart items is not available.')
    case 'VALIDATION_ERROR':
      return e.message || t('داده‌های واردشده معتبر نیست.', 'Submitted data is invalid.')
    case 'AUTH_REQUIRED':
      return t('برای ادامه وارد حساب شوید.', 'Sign in to continue.')
    case 'NETWORK_ERROR':
      return t('اتصال به سرور برقرار نشد.', 'Could not reach the server.')
    default:
      return e.message || t('خطای ناشناخته.', 'Unknown error.')
  }
}
