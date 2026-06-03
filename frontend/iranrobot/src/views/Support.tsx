import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Phone, MessageCircle, Mail, Plus, Check } from 'lucide-react'
import { Section } from '../components/Section'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { Input, Textarea, Select } from '../components/Input'
import { useI18n } from '../i18n'
import { useAuth } from '../lib/useAuth'
import { submitSupportTicket } from '../api/requests'
import { FrappeApiError } from '../lib/frappeApi'

interface TicketForm {
  name: string
  email: string
  topic: string
  subject: string
  message: string
}

interface SubmittedTicket {
  ticket_id: string
  status: string
}

export function SupportView() {
  const { t, n } = useI18n()
  const { isAuthenticated, currentUser } = useAuth()
  const [openFaq, setOpenFaq] = useState<number | null>(0)
  const [form, setForm] = useState<TicketForm>({ name: '', email: '', topic: '', subject: '', message: '' })
  const [submitted, setSubmitted] = useState<SubmittedTicket | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const FAQ = [
    { q: t('آیا ایران‌ربات مارکت‌پلیس است؟', 'Is IranRobot a marketplace?'), a: t('خیر. ایران‌ربات یک شرکت فروش و تأمین مستقیم است. ربات‌ها از تولیدکنندگان رسمی تهیه و با گارانتی شرکتی ارائه می‌شوند.', 'No. IranRobot is a direct sales and sourcing company. Robots are obtained from official manufacturers and offered with corporate warranty.') },
    { q: t('قیمت‌ها دلاری هستند یا تومانی؟', 'Are prices in USD or Toman?'), a: t('قیمت‌های پایه به دلار آمریکا اعلام می‌شوند تا با نرخ روز قابل بررسی باشند. در کنار هر قیمت، تخمین تومانی به‌روز نیز نمایش داده می‌شود.', 'Base prices are quoted in USD so they track the daily rate. A live Toman estimate is shown beside every price.') },
    { q: t('گارانتی و خدمات پس از فروش چگونه است؟', 'How do warranty and after-sales work?'), a: t('تمامی ربات‌های فروشگاه با حداقل ۱۲ ماه گارانتی شرکتی، خدمات تعمیر و نگهداری و آموزش اپراتور ارائه می‌شوند.', 'All shop robots come with at least 12 months of corporate warranty, repair/maintenance and operator training.') },
    { q: t('تفاوت اجاره با خرید چیست؟', "What's the difference between rent and buy?"), a: t('اجاره برای پروژه‌های کوتاه و POC مناسب است. شامل پشتیبانی در محل، بیمه و امکان تمدید بدون هزینه‌ی سرمایه‌ای.', 'Rental suits short projects and POCs. It includes on-site support, insurance and extension, with no capital expense.') },
    { q: t('مدت تأمین سفارشی چقدر است؟', 'How long does custom sourcing take?'), a: t('بسته به برند و کشور مبدا بین ۳۰ تا ۹۰ روز کاری متغیر است. زمان دقیق در استعلام رسمی اعلام می‌شود.', 'Depending on brand and origin it ranges 30–90 business days. The exact time is stated in the official quote.') },
    { q: t('فاکتور رسمی برای سازمان‌ها صادر می‌شود؟', 'Do you issue official invoices for organizations?'), a: t('بله، فاکتور رسمی با شماره اقتصادی و قابلیت ارائه به سازمان مالیاتی برای کل خریدها و اجاره‌ها صادر می‌گردد.', 'Yes, official invoices with a tax ID are issued for all purchases and rentals.') },
  ]

  const CHANNELS = [
    { Icon: Phone, title: t('تماس مستقیم', 'Direct call'), line1: t('شنبه تا چهارشنبه ۹ تا ۱۸', 'Sat–Wed, 9 to 18'), line2: n('021 88 99 12 12'), cta: t('تماس بگیرید', 'Call now'), href: 'tel:+982188991212', tone: 'brand' as const },
    { Icon: MessageCircle, title: t('گفتگوی آنلاین', 'Live chat'), line1: t('پاسخ کارشناس در ۵ دقیقه', 'Expert reply in 5 min'), line2: t('هر روز هفته ۸ تا ۲۲', 'Every day, 8 to 22'), cta: t('شروع گفتگو', 'Start chat'), href: '#chat', tone: 'tech' as const },
    { Icon: Mail, title: t('پست الکترونیک', 'Email'), line1: t('برای استعلام رسمی', 'For formal inquiries'), line2: 'support@iranrobot.ir', cta: t('ارسال ایمیل', 'Send email'), href: 'mailto:support@iranrobot.ir', tone: 'brand' as const },
  ]

  async function send(e: React.FormEvent) {
    e.preventDefault()
    setSubmitError(null)

    const message = form.message.trim()
    if (!message) {
      setSubmitError(t('پیام الزامی است.', 'Message is required.'))
      return
    }

    if (!isAuthenticated) {
      if (!form.name.trim()) {
        setSubmitError(t('نام شما الزامی است.', 'Your name is required.'))
        return
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
        setSubmitError(t('ایمیل معتبر وارد کنید.', 'Enter a valid email.'))
        return
      }
    }

    setSubmitting(true)
    try {
      const res = await submitSupportTicket({
        name: isAuthenticated
          ? currentUser?.customer_name ?? currentUser?.full_name ?? ''
          : form.name.trim(),
        email: isAuthenticated ? currentUser?.email ?? '' : form.email.trim(),
        phone: isAuthenticated ? currentUser?.phone ?? '' : '',
        topic: form.topic,
        subject: form.subject.trim(),
        message,
        language: currentUser?.preferred_language ?? 'fa',
      })
      setSubmitted({ ticket_id: res.ticket_id, status: res.status })
      setForm({ name: '', email: '', topic: '', subject: '', message: '' })
    } catch (err) {
      const msg = err instanceof FrappeApiError
        ? frappeErrorMessage(err, t)
        : t('ارسال پیام با خطا مواجه شد. دوباره تلاش کنید.', 'Could not send the message. Try again.')
      setSubmitError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  function resetForm() {
    setSubmitted(null)
    setSubmitError(null)
  }

  return (
    <>
      <Section
        eyebrow={t('پشتیبانی', 'Support')}
        title={t('کمک می‌خواهید؟ ما اینجاییم', 'Need help? We are here')}
        description={t('تیم پشتیبانی فنی، فروش و تأمین ایران‌ربات همه روزه آماده پاسخگویی است.', "IranRobot's technical, sales and sourcing support teams are available every day.")}
      >
        <div className="grid sm:grid-cols-3 gap-4">
          {CHANNELS.map((c) => (
            <a key={c.title} href={c.href} className="bg-white border border-line rounded-3xl p-6 shadow-soft hover:shadow-soft-lg hover:-translate-y-1 transition-all group">
              <div className={['size-12 rounded-2xl grid place-items-center', c.tone === 'brand' ? 'bg-brand-50 text-brand-600 ring-1 ring-brand-100' : 'bg-blue-soft text-tech-blue ring-1 ring-blue-200'].join(' ')}>
                <c.Icon size={22} />
              </div>
              <div className="mt-4 font-bold text-fg">{c.title}</div>
              <div className="text-xs text-faint mt-1">{c.line1}</div>
              <div className="mt-1 text-sm font-semibold text-fg num-fa" dir="ltr">{c.line2}</div>
              <div className="mt-4 inline-flex items-center text-sm font-bold text-brand-600">{c.cta} ←</div>
            </a>
          ))}
        </div>
      </Section>

      <Section eyebrow={t('پرسش‌های متداول', 'FAQ')} title={t('پیش از تماس، شاید جواب اینجا باشد', 'Before reaching out, the answer may be here')}>
        <div className="grid lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7">
            <div className="bg-white border border-line rounded-3xl divide-y divide-line overflow-hidden shadow-soft">
              {FAQ.map((item, i) => {
                const open = openFaq === i
                return (
                  <div key={item.q}>
                    <button type="button" onClick={() => setOpenFaq(open ? null : i)} className="w-full text-start px-5 sm:px-6 py-5 flex items-center justify-between gap-3 hover:bg-ink-50 transition-colors" aria-expanded={open}>
                      <span className="font-semibold text-fg">{item.q}</span>
                      <motion.span animate={{ rotate: open ? 45 : 0 }} transition={{ duration: 0.2 }} className={['size-7 grid place-items-center rounded-full shrink-0', open ? 'bg-brand-50 text-brand-600' : 'bg-ink-100 text-muted'].join(' ')}>
                        <Plus size={16} />
                      </motion.span>
                    </button>
                    <AnimatePresence initial={false}>
                      {open ? (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden">
                          <p className="px-5 sm:px-6 pb-5 text-sm text-muted leading-8">{item.a}</p>
                        </motion.div>
                      ) : null}
                    </AnimatePresence>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="lg:col-span-5">
            {submitted ? (
              <div className="bg-white border border-line rounded-3xl p-6 shadow-soft text-center">
                <div className="mx-auto size-16 rounded-full bg-emerald-50 ring-1 ring-emerald-100 grid place-items-center text-emerald-600">
                  <Check size={28} />
                </div>
                <h3 className="mt-4 text-lg font-bold text-fg">
                  {t('پیام شما ثبت شد', 'Your message was received')}
                </h3>
                <p className="mt-2 text-sm text-muted leading-7">
                  {t('کد پیگیری', 'Tracking code')}{' '}
                  <span className="font-mono font-bold text-tech-blue">{submitted.ticket_id}</span>
                </p>
                <div className="mt-3 inline-flex items-center gap-2">
                  <Badge tone="warning">{submitted.status}</Badge>
                </div>
                <p className="mt-3 text-xs text-faint leading-6">
                  {t(
                    'در روزهای کاری حداکثر طی ۴ ساعت پاسخ می‌دهیم.',
                    'We reply within 4 business hours.',
                  )}
                </p>
                <div className="mt-5">
                  <Button variant="outline" fullWidth onClick={resetForm}>
                    {t('ارسال پیام جدید', 'Send another message')}
                  </Button>
                </div>
              </div>
            ) : (
              <form onSubmit={send} className="bg-white border border-line rounded-3xl p-6 shadow-soft grid gap-4">
                <div>
                  <Badge tone="brand" dot>{t('ارسال تیکت', 'Submit a ticket')}</Badge>
                  <h3 className="mt-3 text-lg font-bold text-fg">{t('پیام خود را ارسال کنید', 'Send us a message')}</h3>
                  <p className="text-xs text-faint mt-1 leading-6">{t('در روزهای کاری حداکثر طی ۴ ساعت پاسخ می‌دهیم.', 'We reply within 4 hours on business days.')}</p>
                </div>
                {isAuthenticated ? (
                  <div className="rounded-2xl bg-soft border border-line p-3 text-sm">
                    <div className="text-xs text-faint mb-1">{t('ارسال از حساب', 'Sending as')}</div>
                    <div className="font-bold text-fg">{currentUser?.customer_name || currentUser?.full_name}</div>
                    <div className="text-muted" dir="ltr">{currentUser?.email}</div>
                  </div>
                ) : (
                  <>
                    <Input label={t('نام شما', 'Your name')} placeholder={t('مثلاً: مریم رضایی', 'e.g. Maryam Rezaei')} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    <Input label={t('ایمیل تماس', 'Contact email')} type="email" dir="ltr" placeholder="you@company.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                  </>
                )}
                <Select label={t('موضوع', 'Topic')} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })}>
                  <option value="">{t('فروش', 'Sales')}</option>
                  <option value="procure">{t('تأمین', 'Sourcing')}</option>
                  <option value="rent">{t('اجاره', 'Rental')}</option>
                  <option value="tech">{t('پشتیبانی فنی', 'Technical support')}</option>
                  <option value="other">{t('سایر', 'Other')}</option>
                </Select>
                <Input label={t('عنوان (اختیاری)', 'Subject (optional)')} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
                <Textarea label={t('پیام', 'Message')} rows={4} placeholder={t('جزئیات درخواست خود را بنویسید...', 'Describe your request...')} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
                {submitError ? (
                  <div className="rounded-lg bg-brand-50 border border-brand-100 text-brand-700 text-xs px-3 py-2 leading-6">
                    {submitError}
                  </div>
                ) : null}
                <Button fullWidth size="lg" type="submit" disabled={submitting}>
                  {submitting ? t('در حال ارسال...', 'Submitting...') : t('ارسال تیکت', 'Send ticket')}
                </Button>
              </form>
            )}
          </div>
        </div>
      </Section>
    </>
  )
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
