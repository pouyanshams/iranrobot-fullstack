import { motion } from 'framer-motion'
import { ArrowLeft, MessageSquare } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'

export function Hero() {
  const { go } = useApp()
  const { t, lang } = useI18n()

  return (
    <section
      className="relative w-full overflow-hidden bg-white"
      style={{ background: 'linear-gradient(180deg, #ffffff 0%, #ffffff 70%, var(--color-base) 100%)' }}
    >
      {/* ===== Background layers (HTML/CSS only) ===== */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 right-[8%] size-[40rem] rounded-full blur-3xl animate-pulse-glow"
        style={{ background: 'radial-gradient(circle, rgba(127, 24, 16,0.10), transparent 62%)' }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute top-10 left-[4%] size-[34rem] rounded-full blur-3xl animate-pulse-glow"
        style={{ background: 'radial-gradient(circle, rgba(37,99,235,0.09), transparent 62%)' }}
      />

      {/* Light perspective grid floor behind the robots */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[44%]"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(15,23,42,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(15,23,42,0.06) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          transform: 'perspective(640px) rotateX(64deg)',
          transformOrigin: 'center bottom',
          maskImage: 'linear-gradient(to top, #000 5%, transparent 78%)',
          WebkitMaskImage: 'linear-gradient(to top, #000 5%, transparent 78%)',
        }}
      />

      {/* Soft stage glow under the robots */}
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-[8%] left-1/2 -translate-x-1/2 w-[70%] h-48 rounded-full blur-3xl"
        style={{ background: 'radial-gradient(ellipse, rgba(56,189,248,0.16), transparent 70%)' }}
      />

      {/* ===== Content (top) ===== */}
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8 pt-16 sm:pt-20 text-center">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col items-center"
        >
          <h1 className="mx-auto max-w-5xl text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.05]">
            {lang === 'fa' ? (
              <>
                <span className="text-gradient">آینده رباتیک</span>{' '}
                <span className="text-gradient-brand">همین‌جاست</span>
              </>
            ) : (
              <>
                <span className="text-gradient">The future of robotics</span>{' '}
                <span className="text-gradient-brand">is here</span>
              </>
            )}
          </h1>

          <p className="mx-auto mt-6 max-w-3xl text-base sm:text-lg text-muted leading-8">
            {t(
              'خرید، اجاره و تأمین ربات‌های هوشمند برای صنعت، پژوهش و کسب‌وکار — مستقیم از تولیدکننده، با گارانتی و پشتیبانی فنی فارسی.',
              'Buy, rent and source intelligent robots for industry, research and business — direct from the manufacturer, with warranty and local technical support.',
            )}
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => go('catalog')}
              className="group h-12 sm:h-14 px-6 sm:px-8 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-bold inline-flex items-center gap-2.5 shadow-[0_14px_40px_-12px_rgba(127,24,16,0.5)] transition-all hover:-translate-y-0.5"
            >
              {t('مشاهده ربات‌ها', 'Browse robots')}
              <ArrowLeft size={18} className="transition-transform group-hover:-translate-x-1 rtl:rotate-0 ltr:rotate-180" />
            </button>
            <button
              type="button"
              onClick={() => go('support')}
              className="h-12 sm:h-14 px-6 sm:px-8 rounded-lg bg-white border border-line hover:bg-ink-50 text-fg font-bold inline-flex items-center gap-2.5 transition-all hover:-translate-y-0.5 shadow-soft"
            >
              <MessageSquare size={18} className="text-tech-blue" />
              {t('درخواست مشاوره', 'Request a consultation')}
            </button>
          </div>
        </motion.div>
      </div>

      {/* ===== Robot lineup (sibling, naturally sized — visually dominant) ===== */}
      <div className="relative mx-auto mt-8 sm:mt-12 flex max-w-7xl justify-center px-6 lg:px-8">
        <img
          src="/assets/hero-robots-lineup.webp"
          alt="مجموعه ربات‌های هوشمند ایران‌ربات"
          className="pointer-events-none select-none w-full max-w-[1200px] object-contain"
          loading="eager"
          fetchPriority="high"
          draggable={false}
        />
      </div>
    </section>
  )
}
