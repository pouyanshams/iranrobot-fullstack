import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'
import {
  Wallet as WalletIcon,
  ShoppingBag,
  Menu,
  X,
  Languages,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import { UserMenu } from './UserMenu'
import type { RouteName } from '../types'

const NAV: { id: RouteName; fa: string; en: string }[] = [
  { id: 'home', fa: 'خانه', en: 'Home' },
  { id: 'catalog', fa: 'فروشگاه ربات', en: 'Shop' },
  { id: 'procurement', fa: 'تأمین سفارشی', en: 'Procurement' },
  { id: 'rent', fa: 'اجاره', en: 'Rent' },
  { id: 'finder', fa: 'ربات‌یاب', en: 'Robot Finder' },
  { id: 'support', fa: 'پشتیبانی', en: 'Support' },
]

interface ShopSub { id: string; fa: string; en: string }
interface ShopCategory { id: string; fa: string; en: string; subs?: ShopSub[] }

/** Shop dropdown — ids match PLP_CATEGORIES so they preselect on the catalog. */
const SHOP_CATEGORIES: ShopCategory[] = [
  {
    id: 'solutions',
    fa: 'راهکارها',
    en: 'Solutions',
    subs: [
      { id: 'education',  fa: 'آموزش و پژوهش',     en: 'Education & Research' },
      { id: 'warehouse',  fa: 'انبارداری و لجستیک', en: 'Warehouse & Logistics' },
      { id: 'inspection', fa: 'بازرسی و پایش',     en: 'Inspection & Monitoring' },
      { id: 'security',   fa: 'امنیت و گشت‌زنی',    en: 'Security & Patrol' },
      { id: 'healthcare', fa: 'سلامت و خدمات',     en: 'Healthcare & Services' },
      { id: 'custom',     fa: 'راهکار سفارشی',     en: 'Custom Solution' },
    ],
  },
  {
    id: 'humanoids',
    fa: 'انسان‌نماها',
    en: 'Humanoids',
    subs: [
      { id: 'bipedal-humanoids',    fa: 'انسان‌نمای دو پا',     en: 'Bipedal Humanoids' },
      { id: 'wheeled-humanoids',    fa: 'انسان‌نمای چرخ‌دار',    en: 'Wheeled Humanoids' },
      { id: 'upper-body-humanoids', fa: 'انسان‌نمای بالاتنه',   en: 'Upper Body Humanoids' },
    ],
  },
  {
    id: 'quadrupeds',
    fa: 'چهارپاها',
    en: 'Quadrupeds',
    subs: [
      { id: 'standard-quadrupeds', fa: 'چهارپای استاندارد', en: 'Standard Quadrupeds' },
      { id: 'wheeled-quadrupeds',  fa: 'چهارپای چرخ‌دار',    en: 'Wheeled Quadrupeds' },
    ],
  },
  { id: 'amrs',   fa: 'ربات‌های متحرک خودران', en: 'AMRs' },
  { id: 'cobots', fa: 'بازوهای همکار',          en: 'Cobots' },
  { id: 'drones', fa: 'پهپادها',                en: 'Drones' },
  { id: 'ugvs',   fa: 'خودروهای زمینی',         en: 'UGVs' },
  {
    id: 'accessories',
    fa: 'لوازم جانبی',
    en: 'Accessories',
    subs: [
      { id: 'robot-arms',      fa: 'بازوهای ربات',  en: 'Robot Arms' },
      { id: 'robot-batteries', fa: 'باتری ربات',     en: 'Robot Batteries' },
      { id: 'robot-chargers',  fa: 'شارژر ربات',     en: 'Robot Chargers' },
      { id: 'robot-hands',     fa: 'دست‌های ربات',  en: 'Robot Hands' },
      { id: 'sensors',         fa: 'سنسورها',        en: 'Sensors' },
    ],
  },
  { id: 'new', fa: 'تازه‌واردها', en: 'New Arrivals' },
]

export function Header() {
  const { route, go, cart, setCartOpen } = useApp()
  const { t, n, toggle, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  // Click-to-navigate on the desktop Shop button has to fight the hover
  // dropdown -- the cursor is still on the trigger after the click, so
  // `group-hover` keeps the dropdown visible. We suppress the dropdown
  // classes for as long as the cursor stays on the Shop wrapper; the
  // `onMouseLeave` handler clears the flag so the next hover opens cleanly.
  const [shopDropdownSuppressed, setShopDropdownSuppressed] = useState(false)
  /** Which Shop category's subs are shown in the right panel of the mega-menu. */
  const [activeCategoryId, setActiveCategoryId] = useState<string>('solutions')

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const cartCount = cart.reduce((sum, l) => sum + l.qty, 0)

  return (
    <header
      className={[
        'sticky top-0 z-30 bg-white text-fg border-b transition-shadow duration-300',
        scrolled ? 'shadow-[0_8px_24px_-16px_rgba(15,23,42,0.18)] border-line' : 'border-line/60',
      ].join(' ')}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-16 sm:h-20 flex items-center gap-6">
          <button
            type="button"
            onClick={() => go('home')}
            className="flex items-center gap-2.5 group shrink-0"
            aria-label="ایران‌ربات — خانه"
          >
            <span className="relative grid place-items-center size-10 rounded-xl bg-brand-600 text-white shadow-[0_8px_24px_-10px_rgba(127,24,16,0.55)]">
              <LogoMark />
              <span className="absolute inset-0 rounded-xl ring-1 ring-white/15" />
            </span>
            <span className="text-lg font-extrabold tracking-tight text-fg">
              {t('ایران‌', 'Iran')}<span className="text-brand-600">{t('ربات', 'Robot')}</span>
            </span>
          </button>

          <nav className="hidden lg:flex items-center gap-1 mx-2">
            {NAV.map((item) => {
              const active = route.name === item.id

              // ===== Shop item: pure-CSS hover/focus dropdown =====
              if (item.id === 'catalog') {
                return (
                  <div
                    key={item.id}
                    className="relative group"
                    onMouseLeave={() => setShopDropdownSuppressed(false)}
                  >
                    <button
                      type="button"
                      aria-haspopup="menu"
                      onClick={(e) => {
                        // Drop focus + suppress the hover/focus dropdown
                        // before navigating so it doesn't linger on the
                        // catalog page while the cursor is still on Shop.
                        ;(e.currentTarget as HTMLButtonElement).blur()
                        setShopDropdownSuppressed(true)
                        go('catalog')
                      }}
                      className={[
                        'relative inline-flex items-center gap-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                        active ? 'text-brand-700' : 'text-ink-700 hover:text-brand-700 group-hover:text-brand-700 group-focus-within:text-brand-700',
                      ].join(' ')}
                    >
                      {t(item.fa, item.en)}
                      <ChevronDown
                        size={14}
                        className="transition-transform duration-200 group-hover:rotate-180 group-focus-within:rotate-180"
                      />
                      {active ? (
                        <motion.span
                          layoutId="nav-pill"
                          className="absolute inset-0 -z-10 bg-brand-50 ring-1 ring-brand-100 rounded-lg"
                          transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                        />
                      ) : null}
                    </button>

                    {/*
                      Absolute, hidden by default. `pt-3` on the outer wrapper is the
                      hover bridge so moving the cursor from button to card doesn't
                      drop the :hover state. Visibility controlled by CSS only.
                    */}
                    <div
                      className={[
                        'absolute top-full start-0 pt-3 z-40',
                        'opacity-0 pointer-events-none transition-opacity duration-200',
                        // When the click handler has just navigated, keep the
                        // dropdown hidden even though the cursor is still on
                        // the trigger; the wrapper's `onMouseLeave` clears
                        // the flag so a fresh hover opens it again.
                        shopDropdownSuppressed
                          ? ''
                          : 'group-hover:opacity-100 group-hover:pointer-events-auto group-focus-within:opacity-100 group-focus-within:pointer-events-auto',
                      ].join(' ')}
                    >
                      {(() => {
                        const activeData =
                          SHOP_CATEGORIES.find((c) => c.id === activeCategoryId) ??
                          SHOP_CATEGORIES[0]!
                        const activeSubs = activeData.subs ?? []

                        return (
                          <div
                            role="menu"
                            aria-label={t('فروشگاه ربات', 'Shop')}
                            className="w-[860px] overflow-hidden rounded-xl border border-line bg-white shadow-[0_18px_50px_-20px_rgba(15,23,42,0.25)]"
                          >
                            <div className="grid grid-cols-[280px_1fr]">
                              {/* ===== Left: main categories ===== */}
                              <div className="border-e border-line p-3">
                                <div className="grid gap-0.5">
                                  {SHOP_CATEGORIES.map((c) => {
                                    const isActive = c.id === activeCategoryId
                                    const hasSubs = !!(c.subs && c.subs.length > 0)
                                    // Only categories WITH subs update the right panel.
                                    // Hovering AMRs / Cobots / Drones / UGVs / New Arrivals
                                    // must NOT replace the currently displayed subs.
                                    const updateActive = () => {
                                      if (hasSubs) setActiveCategoryId(c.id)
                                    }
                                    return (
                                      <button
                                        key={c.id}
                                        type="button"
                                        role="menuitem"
                                        onMouseEnter={updateActive}
                                        onFocus={updateActive}
                                        onClick={() => go('catalog', c.id)}
                                        className={[
                                          'flex items-center justify-between rounded-lg px-4 py-3 text-sm font-medium transition-colors',
                                          isActive
                                            ? 'bg-brand-50 text-brand-700'
                                            : 'text-ink-700 hover:bg-brand-50 hover:text-brand-700',
                                        ].join(' ')}
                                      >
                                        <span>{t(c.fa, c.en)}</span>
                                        <ChevronRight
                                          size={14}
                                          className={[
                                            'rtl:-scale-x-100',
                                            isActive ? 'text-brand-600' : hasSubs ? 'text-ink-400' : 'text-ink-300',
                                          ].join(' ')}
                                        />
                                      </button>
                                    )
                                  })}
                                </div>

                                <div className="mt-3 border-t border-line pt-3">
                                  <button
                                    type="button"
                                    role="menuitem"
                                    onClick={() => go('catalog')}
                                    className="flex items-center justify-between w-full rounded-lg px-4 py-3 text-sm font-semibold text-brand-700 hover:bg-brand-50 transition-colors"
                                  >
                                    <span>{t('مشاهده کل فروشگاه', 'View all categories')}</span>
                                    <ChevronRight size={14} className="rtl:-scale-x-100" />
                                  </button>
                                </div>
                              </div>

                              {/*
                                ===== Right: subs of the active category =====
                                activeCategoryId only ever lands on a category
                                with subs (hover/focus is gated above), so we
                                always render the subcategory grid here.
                                Hovering AMRs/Cobots/Drones/UGVs/New Arrivals
                                in the left column leaves this panel unchanged.
                              */}
                              <div className="p-4">
                                <div className="mb-3 px-1 text-[11px] font-bold uppercase tracking-[0.18em] text-ink-400">
                                  {t(activeData.fa, activeData.en)}
                                </div>
                                <div
                                  className="gap-2"
                                  style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                                    gap: '8px',
                                  }}
                                >
                                  {activeSubs.map((sub) => (
                                    <button
                                      key={sub.id}
                                      type="button"
                                      role="menuitem"
                                      onClick={() => go('catalog', sub.id)}
                                      className="min-w-0 rounded-lg border border-ink-100 bg-white px-4 py-3 text-sm font-medium text-ink-700 transition-colors hover:border-brand-600/30 hover:bg-brand-50 hover:text-brand-700 focus-visible:border-brand-600/30 focus-visible:bg-brand-50 focus-visible:text-brand-700"
                                    >
                                      <div className="flex min-w-0 items-center justify-between gap-3">
                                        <span className="min-w-0 leading-snug text-start">{t(sub.fa, sub.en)}</span>
                                        <ChevronRight size={14} className="shrink-0 text-ink-300 rtl:-scale-x-100" />
                                      </div>
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                )
              }

              // ===== All other nav items =====
              return (
                <button
                  type="button"
                  key={item.id}
                  onClick={() => go(item.id)}
                  className={[
                    'relative px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    active ? 'text-brand-700' : 'text-ink-700 hover:text-brand-700',
                  ].join(' ')}
                >
                  {t(item.fa, item.en)}
                  {active ? (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 -z-10 bg-brand-50 ring-1 ring-brand-100 rounded-lg"
                      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                    />
                  ) : null}
                </button>
              )
            })}
          </nav>

          <div className="flex-1" />

          <button
            type="button"
            onClick={toggle}
            className="h-10 px-3 rounded-lg bg-white border border-line hover:bg-ink-50 text-fg inline-flex items-center gap-1.5 transition-colors"
            aria-label={t('تغییر زبان به انگلیسی', 'Switch language to Persian')}
          >
            <Languages size={16} className="text-brand-600" />
            <span className="text-sm font-bold">{lang === 'fa' ? 'EN' : 'فا'}</span>
          </button>

          {/* Phase 8C: balance display removed. The header link only opens
              the wallet; the real balance lives on the wallet page itself,
              fetched from the backend. */}
          <button
            type="button"
            onClick={() => go('wallet')}
            className="hidden md:inline-flex h-10 px-3 rounded-lg bg-white border border-line hover:bg-ink-50 text-fg items-center gap-2 transition-colors"
            aria-label={t('کیف پول', 'Wallet')}
          >
            <WalletIcon size={17} className="text-brand-600" />
            <span className="text-sm font-semibold">{t('کیف پول', 'Wallet')}</span>
          </button>

          {/* Phase 4 -- login button when guest, user menu when authenticated */}
          <UserMenu />

          <button
            type="button"
            onClick={() => setCartOpen(true)}
            className="relative h-10 sm:h-11 px-4 sm:px-5 rounded-lg bg-brand-600 hover:bg-brand-700 text-white inline-flex items-center gap-2 transition-all hover:-translate-y-0.5 shadow-[0_10px_24px_-12px_rgba(127,24,16,0.55)]"
            aria-label={t('سبد سفارش', 'Order cart')}
          >
            <ShoppingBag size={17} />
            <span className="hidden sm:inline text-sm font-semibold">{t('سبد سفارش', 'Cart')}</span>
            {cartCount > 0 ? (
              <span className="grid place-items-center min-w-5 h-5 rounded-full bg-white text-brand-700 text-[11px] font-bold px-1.5 num-fa">
                {n(cartCount)}
              </span>
            ) : null}
          </button>

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={t('منو', 'Menu')}
            aria-expanded={open}
            className="lg:hidden size-10 grid place-items-center rounded-lg bg-white border border-line text-fg"
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        <AnimatePresence>
          {open ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="lg:hidden overflow-hidden"
            >
              <div className="pb-4 grid gap-1">
                {NAV.map((item) => {
                  const active = route.name === item.id

                  // On mobile there is no hover, so tapping Shop navigates
                  // directly to the catalog page (same target as desktop's
                  // "View all categories"). The previous tap-to-expand
                  // subcategory dropdown is intentionally removed -- users
                  // browse categories on the catalog page itself.
                  if (item.id === 'catalog') {
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          go('catalog')
                          setOpen(false)
                        }}
                        className={[
                          'w-full h-11 px-4 rounded-lg text-sm font-semibold text-start transition-colors flex items-center justify-between',
                          active ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-100' : 'text-ink-700 hover:text-brand-700 hover:bg-ink-50',
                        ].join(' ')}
                      >
                        <span>{t(item.fa, item.en)}</span>
                      </button>
                    )
                  }

                  return (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => {
                        go(item.id)
                        setOpen(false)
                      }}
                      className={[
                        'h-11 px-4 rounded-lg text-sm font-semibold text-start transition-colors',
                        active ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-100' : 'text-ink-700 hover:text-brand-700 hover:bg-ink-50',
                      ].join(' ')}
                    >
                      {t(item.fa, item.en)}
                    </button>
                  )
                })}
                <button
                  type="button"
                  onClick={() => {
                    go('wallet')
                    setOpen(false)
                  }}
                  className="h-11 px-4 rounded-lg text-sm font-semibold text-start text-ink-700 hover:text-brand-700 hover:bg-ink-50 flex items-center"
                >
                  <span>{t('کیف پول', 'Wallet')}</span>
                </button>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </header>
  )
}

function LogoMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <rect x="4" y="8" width="16" height="12" rx="3" fill="white" />
      <rect x="9" y="3" width="6" height="5" rx="1.5" fill="white" />
      <circle cx="9" cy="14" r="1.6" fill="#7f1810" />
      <circle cx="15" cy="14" r="1.6" fill="#7f1810" />
      <rect x="2" y="11" width="2" height="6" rx="1" fill="white" />
      <rect x="20" y="11" width="2" height="6" rx="1" fill="white" />
    </svg>
  )
}
