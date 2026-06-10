import { motion } from 'framer-motion'
import {
  ShoppingCart,
  Globe2,
  Timer,
  Wrench,
  ArrowLeft,
  Sparkles,
  Cpu,
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import { Section } from '../components/Section'
import { Badge } from '../components/Badge'
import { RobotCard } from '../components/RobotCard'
import { Hero } from '../components/Hero'
import { CategoryBentoSection } from '../components/CategoryBentoSection'
import { ApiError, ApiLoading } from '../components/ApiState'
import { useApi } from '../lib/useApi'
import {
  fetchHomepageCatalog,
  mapApiCardToRobot,
  mapApiDetailToRobot,
} from '../api/catalog'

export function HomeView() {
  const { go } = useApp()
  const { t } = useI18n()

  const { data, loading, error, refetch } = useApi(
    (signal) => fetchHomepageCatalog(signal),
    [],
  )

  const featured = data?.featured ? mapApiDetailToRobot(data.featured) : null
  // Editor's Pick row: featured product up front + supporting cards drawn from
  // `new_arrivals` (excluding the featured product itself). All entries render
  // in the same consistent home-rail card variant, so we flatten into one list
  // and target two balanced rows of 3 on desktop (6 total).
  const rest = (data?.new_arrivals ?? [])
    .filter((p) => !featured || p.product_id !== featured.id)
    .slice(0, 5)
    .map(mapApiCardToRobot)
  const editorsPick = featured ? [featured, ...rest] : rest

  const VALUE_PILLARS = [
    { title: t('فروش مستقیم', 'Direct sales'), text: t('بدون واسطه‌ی مارکت‌پلیس، با گارانتی شرکت و فاکتور رسمی.', 'No marketplace middlemen — corporate warranty and official invoicing.'), Icon: ShoppingCart, tone: 'brand' as const },
    { title: t('تأمین برندهای خاص', 'Sourcing special brands'), text: t('سفارش از تولیدکنندگان آلمانی، ژاپنی، کره‌ای و چینی.', 'Order from German, Japanese, Korean and Chinese manufacturers.'), Icon: Globe2, tone: 'tech' as const },
    { title: t('اجاره روزانه', 'Daily rental'), text: t('برای پروژه‌های کوتاه و نمایشگاهی، بدون هزینه‌ی سرمایه‌ای.', 'For short projects and expos, with no capital expense.'), Icon: Timer, tone: 'brand' as const },
    { title: t('پشتیبانی فنی', 'Technical support'), text: t('تیم نصب، نگهداری و آموزش به زبان فارسی در سراسر کشور.', 'Installation, maintenance and training teams nationwide.'), Icon: Wrench, tone: 'tech' as const },
  ]

  const STATS = [
    { value: t('۱۲۰+', '120+'), label: t('مدل ربات فعال', 'active robot models') },
    { value: t('۳۲', '32'), label: t('برند بین‌المللی', 'international brands') },
    { value: t('۹۸٪', '98%'), label: t('رضایت مشتری سازمانی', 'enterprise satisfaction') },
    { value: t('۴۸ ساعت', '48h'), label: t('پاسخ به استعلام', 'quote turnaround') },
  ]

  return (
    <>
      <Hero />

      {/* Category carousel — placed directly below the hero */}
      <CategoryBentoSection />

      {/* Trust strip */}
      <div className="bg-base-2 border-b border-line">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-9 grid grid-cols-2 sm:grid-cols-4 gap-6">
          {STATS.map((s) => (
            <div key={s.label}>
              <div className="text-2xl sm:text-3xl font-extrabold text-brand-600 num-fa">{s.value}</div>
              <div className="text-xs sm:text-sm text-muted mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      <Section
        eyebrow={t('چرا ایران‌ربات', 'Why IranRobot')}
        title={t('یک پلتفرم برای کل چرخه‌ی تهیه‌ی ربات', 'One platform for the entire robot procurement cycle')}
        description={t(
          'ایران‌ربات یک مارکت‌پلیس نیست — مستقیم می‌فروشیم، تأمین می‌کنیم و اجاره می‌دهیم تا نگران واسطه، گارانتی و خدمات پس از فروش نباشید.',
          'IranRobot is not a marketplace — we sell, source and rent directly, so you never worry about middlemen, warranty or after-sales service.',
        )}
      >
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {VALUE_PILLARS.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ y: 16, opacity: 0 }}
              whileInView={{ y: 0, opacity: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
              className="bg-white border border-line rounded-3xl p-6 shadow-soft hover:shadow-soft-lg transition-shadow"
            >
              <div
                className={[
                  'size-12 rounded-2xl grid place-items-center',
                  p.tone === 'brand' ? 'bg-brand-50 text-brand-600 ring-1 ring-brand-100' : 'bg-blue-soft text-tech-blue ring-1 ring-blue-200',
                ].join(' ')}
              >
                <p.Icon size={22} />
              </div>
              <h3 className="mt-4 text-base font-bold text-fg">{p.title}</h3>
              <p className="mt-2 text-sm text-muted leading-7">{p.text}</p>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Featured catalog */}
      <Section
        eyebrow={t('پیشنهاد سردبیر', "Editor's pick")}
        title={t('ربات‌های پرتقاضای این فصل', 'The most-requested robots this season')}
        description={t('مدل‌هایی که بیشترین استعلام را در سه ماه گذشته داشته‌اند.', 'Models with the most inquiries over the past three months.')}
        action={
          <button
            type="button"
            onClick={() => go('catalog')}
            className="h-11 px-5 rounded-lg bg-white border border-line hover:bg-ink-50 text-fg font-semibold inline-flex items-center gap-2 transition-colors shadow-soft"
          >
            {t('مشاهده فروشگاه', 'View shop')}
            <ArrowLeft size={17} />
          </button>
        }
      >
        {loading ? (
          <ApiLoading rows={4} />
        ) : error ? (
          <ApiError error={error} onRetry={refetch} />
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 lg:auto-rows-fr">
            {editorsPick.map((r) => (
              <RobotCard key={r.id} robot={r} variant="home" />
            ))}
          </div>
        )}
      </Section>

      {/* Three modes */}
      <Section eyebrow={t('مدل‌های همکاری', 'Engagement models')} title={t('بسته به اولویت پروژه، یکی را انتخاب کنید', 'Pick one based on your project priority')}>
        <div className="grid md:grid-cols-3 gap-5">
          <ModeCard
            title={t('خرید مستقیم', 'Direct purchase')}
            tone="brand"
            cta={t('ورود به فروشگاه', 'Enter shop')}
            onClick={() => go('catalog')}
            bullets={[t('تحویل از انبار تهران', 'Delivery from Tehran warehouse'), t('گارانتی ۱۲ تا ۲۴ ماه', '12–24 month warranty'), t('فاکتور رسمی برای سازمان‌ها', 'Official invoicing for organizations')]}
          />
          <ModeCard
            title={t('تأمین سفارشی', 'Custom sourcing')}
            tone="dark"
            cta={t('ثبت درخواست تأمین', 'Submit a request')}
            onClick={() => go('procurement')}
            bullets={[t('برندهای خارج از کاتالوگ', 'Brands beyond the catalog'), t('مدیریت گمرک و حمل', 'Customs & shipping handled'), t('استعلام در ۴۸ ساعت', 'Quote within 48 hours')]}
          />
          <ModeCard
            title={t('اجاره‌ی روزانه', 'Daily rental')}
            tone="plain"
            cta={t('محاسبه‌ی اجاره', 'Calculate rental')}
            onClick={() => go('rent')}
            bullets={[t('مناسب نمایشگاه و POC', 'Great for expos & POCs'), t('بدون هزینه‌ی سرمایه‌ای', 'No capital expense'), t('پشتیبانی در محل', 'On-site support')]}
          />
        </div>
      </Section>

      {/* Finder CTA — dark navy accent band */}
      <Section spacing="md">
        <div className="relative overflow-hidden rounded-[2rem] surface-navy p-8 sm:p-14">
          <div aria-hidden className="pointer-events-none absolute -top-28 -left-24 size-96 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(127, 24, 16,0.28), transparent 65%)' }} />
          <div aria-hidden className="pointer-events-none absolute -bottom-28 -right-24 size-96 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(56,189,248,0.24), transparent 65%)' }} />
          <div className="relative grid lg:grid-cols-12 gap-8 items-center">
            <div className="lg:col-span-8">
              <Badge tone="glass" dot>{t('ربات‌یاب هوشمند', 'Smart Robot Finder')}</Badge>
              <h2 className="mt-4 text-2xl sm:text-4xl font-extrabold leading-tight text-white">
                {t('نمی‌دانید برای نیازتان چه رباتی مناسب است؟', 'Not sure which robot fits your needs?')}
              </h2>
              <p className="mt-3 text-ink-300 leading-8 max-w-xl">
                {t(
                  'با سه پرسش ساده، بهترین مدل را پیشنهاد می‌دهیم — از بازوی همکار برای خط مونتاژ تا ربات سرو برای رستوران.',
                  'In a few simple questions we recommend the best model — from a cobot for the assembly line to a serving robot for restaurants.',
                )}
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => go('finder')}
                  className="h-12 px-6 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-bold inline-flex items-center gap-2 shadow-[0_12px_36px_-12px_rgba(127, 24, 16,0.6)] hover:-translate-y-0.5 transition-all"
                >
                  <Sparkles size={18} />
                  {t('شروع ربات‌یاب', 'Start the finder')}
                </button>
                <button
                  type="button"
                  onClick={() => go('support')}
                  className="h-12 px-6 rounded-lg glass-dark hover:bg-white/15 text-white font-bold transition-colors"
                >
                  {t('مشاوره با کارشناس', 'Talk to an expert')}
                </button>
              </div>
            </div>
            <div className="lg:col-span-4 grid place-items-center">
              <div className="relative size-44 rounded-full grid place-items-center glass-dark animate-float-slow">
                <div className="absolute inset-0 rounded-full blur-xl" style={{ background: 'radial-gradient(circle, rgba(56,189,248,0.28), transparent 70%)' }} />
                <Cpu size={64} className="relative text-tech-cyan" />
              </div>
            </div>
          </div>
        </div>
      </Section>
    </>
  )
}

function ModeCard({
  title,
  bullets,
  cta,
  onClick,
  tone,
}: {
  title: string
  bullets: string[]
  cta: string
  onClick: () => void
  tone: 'brand' | 'dark' | 'plain'
}) {
  const wrap =
    tone === 'brand'
      ? 'bg-gradient-to-br from-brand-50 to-brand-50 border-brand-100'
      : tone === 'dark'
        ? 'surface-navy border-transparent'
        : 'bg-white border-line'
  const isDark = tone === 'dark'
  const titleCls = isDark ? 'text-white' : 'text-fg'
  const subCls = isDark ? 'text-ink-300' : 'text-muted'
  const dot = tone === 'brand' ? 'bg-brand-500' : tone === 'dark' ? 'bg-tech-cyan' : 'bg-tech-blue'
  const btn =
    tone === 'brand'
      ? 'bg-brand-600 text-white hover:bg-brand-700'
      : tone === 'dark'
        ? 'bg-white text-ink-900 hover:bg-ink-100'
        : 'bg-ink-900 text-white hover:bg-ink-800'

  return (
    <div className={['rounded-3xl p-7 border shadow-soft flex flex-col h-full', wrap].join(' ')}>
      <h3 className={['text-xl font-extrabold', titleCls].join(' ')}>{title}</h3>
      <ul className={['mt-5 space-y-3 text-sm leading-7', subCls].join(' ')}>
        {bullets.map((b) => (
          <li key={b} className="flex items-start gap-2.5">
            <span className={['mt-2 size-1.5 rounded-full shrink-0', dot].join(' ')} />
            <span>{b}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onClick}
        className={['mt-6 h-11 px-5 rounded-lg text-sm font-bold transition-all hover:-translate-y-0.5 inline-flex items-center justify-center gap-2', btn].join(' ')}
      >
        {cta}
        <ArrowLeft size={16} />
      </button>
    </div>
  )
}
