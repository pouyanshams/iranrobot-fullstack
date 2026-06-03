import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { Modal } from './Modal'
import { Button } from './Button'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'

export function OnboardingModal() {
  const { onboardingOpen, dismissOnboarding, go } = useApp()
  const { t } = useI18n()
  const STEPS = [
    { title: t('به ایران‌ربات خوش آمدید', 'Welcome to IranRobot'), body: t('پلتفرم تخصصی فروش، تأمین و اجاره ربات. مستقیم از تولیدکننده، بدون واسطه‌ی مارکت‌پلیس.', 'A specialized platform to sell, source and rent robots — direct from the manufacturer, no marketplace middlemen.'), art: <StepArt0 /> },
    { title: t('سه مسیر برای هر نیاز', 'Three paths for every need'), body: t('خرید مستقیم از فروشگاه، تأمین سفارشی برندهای خاص از خارج، یا اجاره روزانه برای پروژه‌های کوتاه.', 'Buy directly from the shop, source specific foreign brands, or rent daily for short projects.'), art: <StepArt1 /> },
    { title: t('ربات‌یاب هوشمند', 'Smart Robot Finder'), body: t('با چند سؤال ساده، بهترین ربات متناسب با کاربری شما را پیشنهاد می‌دهیم.', 'A few simple questions and we recommend the best robot for your use case.'), art: <StepArt2 /> },
  ]
  const [step, setStep] = useState(0)

  function close() {
    dismissOnboarding()
    setStep(0)
  }
  function next() {
    if (step >= STEPS.length - 1) {
      close()
      return
    }
    setStep((s) => s + 1)
  }

  const current = STEPS[step]!

  return (
    <Modal open={onboardingOpen} onClose={close} size="md">
      <div className="relative">
        <div
          className="relative aspect-[16/9] grid place-items-center overflow-hidden border-b border-line"
          style={{ background: 'radial-gradient(120% 95% at 50% 10%, #ffffff 0%, #eef2f7 75%, #e2e8f0 100%)' }}
        >
          <div className="absolute inset-0 grid-faint opacity-40" />
          <div aria-hidden className="absolute -top-16 right-10 size-56 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(127, 24, 16,0.12), transparent 65%)' }} />
          <div aria-hidden className="absolute -bottom-16 left-10 size-56 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(56,189,248,0.16), transparent 65%)' }} />
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ y: 12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -12, opacity: 0 }} transition={{ duration: 0.25 }} className="relative">
              {current.art}
            </motion.div>
          </AnimatePresence>
          <button type="button" onClick={close} aria-label="بستن" className="absolute top-3 left-3 size-9 rounded-full bg-white/80 hover:bg-white border border-line text-fg grid place-items-center backdrop-blur">
            <X size={16} />
          </button>
        </div>

        <div className="p-7 sm:p-8 text-center">
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ y: 8, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -8, opacity: 0 }} transition={{ duration: 0.2 }}>
              <h2 className="text-2xl font-extrabold text-fg">{current.title}</h2>
              <p className="mt-3 text-[15px] text-muted leading-8 max-w-md mx-auto">{current.body}</p>
            </motion.div>
          </AnimatePresence>

          <div className="mt-6 flex items-center justify-center gap-1.5">
            {STEPS.map((_, i) => (
              <span key={i} className={['h-1.5 rounded-full transition-all', i === step ? 'w-8 bg-brand-600' : 'w-2.5 bg-ink-200'].join(' ')} />
            ))}
          </div>

          <div className="mt-7 grid grid-cols-2 gap-3 sm:max-w-sm sm:mx-auto">
            <Button variant="outline" onClick={close}>{t('رد شدن', 'Skip')}</Button>
            <Button onClick={next}>{step >= STEPS.length - 1 ? t('شروع', 'Start') : t('بعدی', 'Next')}</Button>
          </div>

          {step === STEPS.length - 1 ? (
            <button type="button" onClick={() => { close(); go('finder') }} className="mt-3 text-sm text-tech-blue font-semibold hover:underline">
              {t('همین حالا با ربات‌یاب شروع کنم →', 'Start with the Robot Finder now →')}
            </button>
          ) : null}
        </div>
      </div>
    </Modal>
  )
}

const STROKE = '#334155'
const FILL = '#ffffff'
const PANEL = '#f1f5f9'

function StepArt0() {
  return (
    <svg width="220" height="160" viewBox="0 0 220 160" fill="none">
      <rect x="40" y="30" width="140" height="100" rx="20" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="70" y="15" width="80" height="20" rx="6" fill={PANEL} stroke="#38bdf8" strokeWidth="2.5" />
      <circle cx="90" cy="75" r="10" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="130" cy="75" r="10" fill={PANEL} stroke={STROKE} strokeWidth="2.2" />
      <circle cx="90" cy="75" r="3" fill="#38bdf8" />
      <circle cx="130" cy="75" r="3" fill="#38bdf8" />
      <rect x="95" y="100" width="30" height="8" rx="4" fill="#7f1810" opacity="0.8" />
    </svg>
  )
}

function StepArt1() {
  return (
    <svg width="260" height="160" viewBox="0 0 260 160" fill="none">
      <rect x="10" y="50" width="70" height="80" rx="14" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <rect x="95" y="40" width="70" height="90" rx="14" fill={FILL} stroke="#7f1810" strokeWidth="2.5" />
      <rect x="180" y="50" width="70" height="80" rx="14" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <text x="45" y="100" textAnchor="middle" fontSize="22" fontWeight="700" fill="#2563eb">$</text>
      <text x="130" y="100" textAnchor="middle" fontSize="22" fontWeight="700" fill="#7f1810">⚙</text>
      <text x="215" y="100" textAnchor="middle" fontSize="22" fontWeight="700" fill="#2563eb">⏱</text>
    </svg>
  )
}

function StepArt2() {
  return (
    <svg width="240" height="160" viewBox="0 0 240 160" fill="none">
      <circle cx="120" cy="80" r="55" fill={FILL} stroke={STROKE} strokeWidth="2.2" />
      <path d="M155 115 L185 145" stroke={STROKE} strokeWidth="6" strokeLinecap="round" />
      <circle cx="120" cy="80" r="32" fill="#7f1810" />
      <path d="M108 80 l8 8 l16 -16" stroke="#fff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
