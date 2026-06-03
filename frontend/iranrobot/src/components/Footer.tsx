import { MapPin, Phone, Mail, ShieldCheck, Truck } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import type { RouteName } from '../types'

const LINKS: { titleFa: string; titleEn: string; items: { fa: string; en: string; to: RouteName }[] }[] = [
  {
    titleFa: 'محصولات',
    titleEn: 'Products',
    items: [
      { fa: 'فروشگاه ربات', en: 'Shop', to: 'catalog' },
      { fa: 'تأمین سفارشی', en: 'Procurement', to: 'procurement' },
      { fa: 'اجاره ربات', en: 'Rent', to: 'rent' },
      { fa: 'ربات‌یاب', en: 'Robot Finder', to: 'finder' },
    ],
  },
  {
    titleFa: 'حساب',
    titleEn: 'Account',
    items: [
      { fa: 'کیف پول', en: 'Wallet', to: 'wallet' },
      { fa: 'پشتیبانی', en: 'Support', to: 'support' },
    ],
  },
]

export function Footer() {
  const { go } = useApp()
  const { t, n } = useI18n()
  return (
    <footer className="relative mt-24 bg-darksec text-white">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-500/60 to-transparent" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
        <div className="grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <div className="flex items-center gap-2.5">
              <span className="size-10 grid place-items-center rounded-2xl bg-brand-600 text-white text-sm font-extrabold">
                IR
              </span>
              <span className="text-lg font-extrabold tracking-tight text-white">
                {t('ایران‌', 'Iran')}<span className="text-brand-400">{t('ربات', 'Robot')}</span>
              </span>
            </div>
            <p className="mt-4 text-sm text-ink-300 leading-8 max-w-md">
              {t(
                'پلتفرم فروش مستقیم، تأمین و اجاره ربات‌های هوشمند صنعتی، خدماتی، پژوهشی و پهپاد. بدون واسطه، با گارانتی شرکتی و پشتیبانی فنی فارسی در سراسر ایران.',
                'A direct sales, procurement and rental platform for industrial, service, research robots and drones. No middlemen — corporate warranty and Persian technical support across Iran.',
              )}
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <span className="inline-flex h-9 items-center gap-2 px-3 rounded-full bg-white/8 ring-1 ring-white/12 text-xs font-semibold text-ink-200">
                <ShieldCheck size={14} className="text-emerald-400" />
                {t('نماد اعتماد الکترونیکی', 'Verified eTrust')}
              </span>
              <span className="inline-flex h-9 items-center gap-2 px-3 rounded-full bg-white/8 ring-1 ring-white/12 text-xs font-semibold text-ink-200">
                <Truck size={14} className="text-tech-cyan" />
                {t('ارسال و نصب امن', 'Safe delivery & install')}
              </span>
            </div>
          </div>

          {LINKS.map((col) => (
            <div key={col.titleEn} className="lg:col-span-2">
              <h4 className="text-sm font-bold text-white mb-4">{t(col.titleFa, col.titleEn)}</h4>
              <ul className="space-y-3">
                {col.items.map((item) => (
                  <li key={item.en}>
                    <button
                      type="button"
                      onClick={() => go(item.to)}
                      className="text-sm text-ink-300 hover:text-brand-400 transition-colors"
                    >
                      {t(item.fa, item.en)}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          <div className="lg:col-span-3">
            <h4 className="text-sm font-bold text-white mb-4">{t('تماس با ما', 'Contact us')}</h4>
            <ul className="space-y-3 text-sm text-ink-300">
              <li className="flex items-start gap-2">
                <MapPin size={16} className="mt-0.5 text-ink-400 shrink-0" />
                {t('تهران، خیابان مطهری، پلاک ۱۲۰', 'No. 120, Motahari St, Tehran')}
              </li>
              <li className="flex items-center gap-2" dir="ltr">
                <Phone size={16} className="text-ink-400 shrink-0" />
                <span className="num-fa">{n('+98 21 88 99 12 12')}</span>
              </li>
              <li className="flex items-center gap-2" dir="ltr">
                <Mail size={16} className="text-ink-400 shrink-0" />
                support@iranrobot.ir
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-white/10 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <span className="text-xs text-ink-400">
            {t('© ۱۴۰۵ ایران‌ربات. تمامی حقوق محفوظ است.', '© 2026 IranRobot. All rights reserved.')}
          </span>
          <span className="text-xs text-ink-400">{t('طراحی و توسعه در تهران', 'Designed & built in Tehran')}</span>
        </div>
      </div>
    </footer>
  )
}
