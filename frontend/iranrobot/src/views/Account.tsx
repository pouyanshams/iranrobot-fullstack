/**
 * Phase 6 -- Customer Dashboard MVP.
 *
 * Single-file dashboard implementation. Sub-sections are dispatched from
 * `route.param` (#/account, #/account/quotes, #/account/procurement, etc.).
 * Guests get the existing Phase 4 "sign-in prompt" placeholder that opens the
 * login modal. Logged-in users see the dashboard shell with a left sidebar +
 * a content panel.
 *
 * Security posture (mirrors Phase 5 + Phase 6 backend):
 *   - All data comes from `get_my_requests` / `get_my_request_detail` which
 *     enforce ownership server-side.
 *   - We never accept record ids that don't come from the backend's own list.
 *   - Internal notes / admin-only fields are not part of the backend
 *     projection, so the UI can't render them by accident.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ChevronLeft,
  ClipboardList,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Package,
  ShoppingBag,
  User as UserIcon,
} from 'lucide-react'
import { Section } from '../components/Section'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { Input, Select } from '../components/Input'
import { StatusBadge } from '../components/StatusBadge'
import { useAuth } from '../lib/useAuth'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'
import {
  type MyProcurementRequest,
  type MyQuoteRequest,
  type MyRequestsPayload,
  type MySupportTicket,
  type ProcurementRequestDetail,
  type QuoteRequestDetail,
  type RequestKind,
  type SupportTicketDetail,
  getMyRequests,
  getMyRequestDetail,
} from '../api/requests'
import { FrappeApiError } from '../lib/frappeApi'

type AccountSection = 'overview' | 'requests' | 'quotes' | 'procurement' | 'support' | 'profile'

const VALID_SECTIONS: AccountSection[] = ['overview', 'requests', 'quotes', 'procurement', 'support', 'profile']

function normalizeSection(param: string | undefined): AccountSection {
  if (!param) return 'overview'
  if ((VALID_SECTIONS as string[]).includes(param)) return param as AccountSection
  return 'overview'
}

// ---------------------------------------------------------------------------
// Root entry point -- guards guest + dispatches sub-section.
// ---------------------------------------------------------------------------

export function AccountView() {
  const { currentUser, isAuthenticated, isLoading: authLoading, openLogin, logout } = useAuth()
  const { go, route } = useApp()
  const { t } = useI18n()

  const section = normalizeSection(route.param)

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      openLogin()
    }
  }, [authLoading, isAuthenticated, openLogin])

  if (authLoading) {
    return (
      <Section spacing="md">
        <div className="mx-auto max-w-md rounded-2xl border border-line bg-white p-10 text-center shadow-soft">
          <div className="h-6 w-1/2 mx-auto rounded bg-soft animate-pulse" />
          <div className="mt-4 h-4 w-3/4 mx-auto rounded bg-soft animate-pulse" />
        </div>
      </Section>
    )
  }

  if (!isAuthenticated) {
    return (
      <Section spacing="md">
        <div className="mx-auto max-w-md rounded-2xl border border-line bg-white p-10 text-center shadow-soft">
          <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-brand-50 ring-1 ring-brand-100 text-brand-600">
            <UserIcon size={22} />
          </div>
          <h1 className="mt-4 text-xl font-bold text-fg">
            {t('برای مشاهده‌ی حساب وارد شوید', 'Sign in to view your account')}
          </h1>
          <p className="mt-3 text-sm text-muted leading-7">
            {t(
              'با ورود، می‌توانید درخواست‌های قبلی و اطلاعات حساب خود را ببینید.',
              'After signing in you can review past requests and your account details.',
            )}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              type="button"
              onClick={openLogin}
              className="h-11 px-6 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold transition-colors"
            >
              {t('ورود', 'Sign in')}
            </button>
            <button
              type="button"
              onClick={() => go('home')}
              className="h-11 px-6 rounded-lg border border-line bg-white text-fg text-sm font-semibold hover:bg-ink-50 transition-colors"
            >
              {t('بازگشت به خانه', 'Back to home')}
            </button>
          </div>
        </div>
      </Section>
    )
  }

  const user = currentUser!
  return (
    <AccountLayout section={section} onLogout={() => logout().catch(() => {})}>
      {section === 'overview' ? <OverviewView /> : null}
      {section === 'requests' ? <CombinedRequestsView /> : null}
      {section === 'quotes' ? <QuoteListView /> : null}
      {section === 'procurement' ? <ProcurementListView /> : null}
      {section === 'support' ? <SupportListView /> : null}
      {section === 'profile' ? <ProfileFormView user={user} /> : null}
    </AccountLayout>
  )
}

// ---------------------------------------------------------------------------
// Layout shell -- sidebar + content
// ---------------------------------------------------------------------------

interface SidebarItem {
  section: AccountSection
  Icon: typeof LayoutDashboard
  fa: string
  en: string
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  { section: 'overview', Icon: LayoutDashboard, fa: 'نمای کلی', en: 'Overview' },
  { section: 'requests', Icon: ClipboardList, fa: 'همه‌ی درخواست‌ها', en: 'All requests' },
  { section: 'quotes', Icon: ShoppingBag, fa: 'استعلام‌ها', en: 'Quote requests' },
  { section: 'procurement', Icon: Package, fa: 'درخواست تأمین', en: 'Procurement' },
  { section: 'support', Icon: LifeBuoy, fa: 'پشتیبانی', en: 'Support' },
  { section: 'profile', Icon: UserIcon, fa: 'پروفایل', en: 'Profile' },
]

function AccountLayout({
  section,
  onLogout,
  children,
}: {
  section: AccountSection
  onLogout: () => void
  children: React.ReactNode
}) {
  const { go } = useApp()
  const { t } = useI18n()
  const { currentUser } = useAuth()

  return (
    <Section spacing="md">
      <div className="grid lg:grid-cols-12 gap-6">
        <aside className="lg:col-span-3">
          <div className="bg-white border border-line rounded-3xl p-4 shadow-soft sticky top-24">
            <div className="px-2 py-3 flex items-center gap-3">
              <div className="grid size-10 place-items-center rounded-xl bg-brand-50 ring-1 ring-brand-100 text-brand-600">
                <UserIcon size={18} />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-faint">{t('حساب من', 'My account')}</div>
                <div className="text-sm font-bold text-fg truncate">
                  {currentUser?.customer_name || currentUser?.full_name || currentUser?.email}
                </div>
              </div>
            </div>
            <nav className="mt-2 grid gap-1">
              {SIDEBAR_ITEMS.map((it) => {
                const active = it.section === section
                return (
                  <button
                    key={it.section}
                    type="button"
                    onClick={() => go('account', it.section === 'overview' ? undefined : it.section)}
                    className={[
                      'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors',
                      active
                        ? 'bg-brand-50 text-brand-700 font-bold'
                        : 'text-fg hover:bg-ink-50',
                    ].join(' ')}
                  >
                    <it.Icon size={16} />
                    <span>{t(it.fa, it.en)}</span>
                  </button>
                )
              })}
            </nav>
            <div className="mt-3 pt-3 border-t border-line">
              <button
                type="button"
                onClick={onLogout}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-fg hover:bg-ink-50 transition-colors"
              >
                <LogOut size={16} />
                <span>{t('خروج از حساب', 'Sign out')}</span>
              </button>
            </div>
          </div>
        </aside>

        <div className="lg:col-span-9">{children}</div>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Hook -- shared list fetcher for /quotes /procurement /support /overview
// ---------------------------------------------------------------------------

interface RequestsState {
  data: MyRequestsPayload | null
  loading: boolean
  error: string | null
  reload: () => void
}

function useMyRequests(limit = 20): RequestsState {
  const [data, setData] = useState<MyRequestsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect -- standard "load on mount / refetch on key change" pattern
    setLoading(true)
    setError(null)
    getMyRequests(limit, controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) {
          setData(payload)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        const msg =
          err instanceof FrappeApiError && err.code
            ? err.message
            : (err as Error)?.message || 'Failed to load requests'
        setError(msg)
        setLoading(false)
      })
    return () => controller.abort()
  }, [limit, tick])

  const reload = useCallback(() => setTick((n) => n + 1), [])

  return { data, loading, error, reload }
}

// ---------------------------------------------------------------------------
// Shared chrome -- loading / empty / error states
// ---------------------------------------------------------------------------

function LoadingSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="grid gap-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl bg-white border border-line p-4 shadow-soft animate-pulse"
        >
          <div className="h-4 w-1/3 rounded bg-soft" />
          <div className="mt-3 h-3 w-2/3 rounded bg-soft" />
        </div>
      ))}
    </div>
  )
}

function EmptyState({
  title,
  body,
  ctaLabel,
  onCta,
}: {
  title: string
  body: string
  ctaLabel?: string
  onCta?: () => void
}) {
  return (
    <div className="rounded-3xl bg-white border border-dashed border-line p-10 text-center shadow-soft">
      <div className="mx-auto size-14 rounded-2xl bg-brand-50 ring-1 ring-brand-100 grid place-items-center text-brand-600">
        <ClipboardList size={24} />
      </div>
      <h3 className="mt-4 text-base font-bold text-fg">{title}</h3>
      <p className="mt-2 text-sm text-muted leading-7 max-w-md mx-auto">{body}</p>
      {ctaLabel && onCta ? (
        <div className="mt-5">
          <Button variant="outline" onClick={onCta}>
            {ctaLabel}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { t } = useI18n()
  return (
    <div className="rounded-3xl bg-brand-50 border border-brand-100 p-6 text-center">
      <h3 className="text-sm font-bold text-brand-700">
        {t('بارگذاری ناموفق بود', 'Loading failed')}
      </h3>
      <p className="mt-2 text-xs text-brand-700/80 leading-6">{message}</p>
      <div className="mt-4">
        <Button variant="outline" onClick={onRetry}>
          {t('تلاش مجدد', 'Try again')}
        </Button>
      </div>
    </div>
  )
}

function PageHeader({
  title,
  description,
  rightSlot,
}: {
  title: string
  description?: React.ReactNode
  rightSlot?: React.ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-3 mb-5">
      <div>
        <h2 className="text-xl sm:text-2xl font-extrabold text-fg">{title}</h2>
        {description ? (
          <p className="mt-1 text-sm text-muted leading-7">{description}</p>
        ) : null}
      </div>
      {rightSlot}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview view
// ---------------------------------------------------------------------------

function OverviewView() {
  const { t } = useI18n()
  const { go } = useApp()
  const { currentUser } = useAuth()
  const state = useMyRequests(10)

  const quoteCount = state.data?.quote_requests.length ?? 0
  const procCount = state.data?.procurement_requests.length ?? 0
  const supportCount = state.data?.support_tickets.length ?? 0

  const recent = useMemo(() => {
    if (!state.data) return []
    type RecentItem =
      | { kind: 'quote'; record: MyQuoteRequest }
      | { kind: 'procurement'; record: MyProcurementRequest }
      | { kind: 'support'; record: MySupportTicket }
    const all: RecentItem[] = [
      ...state.data.quote_requests.map((r) => ({ kind: 'quote' as const, record: r })),
      ...state.data.procurement_requests.map((r) => ({ kind: 'procurement' as const, record: r })),
      ...state.data.support_tickets.map((r) => ({ kind: 'support' as const, record: r })),
    ]
    all.sort((a, b) => (b.record.creation || '').localeCompare(a.record.creation || ''))
    return all.slice(0, 5)
  }, [state.data])

  return (
    <div className="grid gap-6">
      <PageHeader
        title={t(
          `${currentUser?.customer_name || currentUser?.first_name || ''} خوش آمدید`,
          `Welcome ${currentUser?.customer_name || currentUser?.first_name || ''}`,
        )}
        description={
          currentUser?.email ? (
            <>
              <span dir="ltr" className="font-mono text-tech-blue">{currentUser.email}</span>
              {' — '}
              {t(
                'مرور خلاصه‌ای از فعالیت حساب شما در ایران‌ربات.',
                'A quick overview of your IranRobot activity.',
              )}
            </>
          ) : (
            t(
              'مرور خلاصه‌ای از فعالیت حساب شما در ایران‌ربات.',
              'A quick overview of your IranRobot activity.',
            )
          )
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <CountCard
          icon={<ShoppingBag size={20} />}
          label={t('استعلام‌ها', 'Quote requests')}
          count={quoteCount}
          onClick={() => go('account', 'quotes')}
          loading={state.loading}
        />
        <CountCard
          icon={<Package size={20} />}
          label={t('درخواست تأمین', 'Procurement')}
          count={procCount}
          onClick={() => go('account', 'procurement')}
          loading={state.loading}
        />
        <CountCard
          icon={<LifeBuoy size={20} />}
          label={t('تیکت‌های پشتیبانی', 'Support tickets')}
          count={supportCount}
          onClick={() => go('account', 'support')}
          loading={state.loading}
        />
      </div>

      <div className="rounded-3xl border border-line bg-white shadow-soft overflow-hidden">
        <div className="px-5 py-4 border-b border-line flex items-center justify-between">
          <h3 className="text-base font-bold text-fg">{t('فعالیت اخیر', 'Recent activity')}</h3>
          <button
            type="button"
            onClick={() => go('account', 'requests')}
            className="text-xs font-semibold text-brand-700 hover:underline"
          >
            {t('مشاهده همه', 'View all')}
          </button>
        </div>
        <div className="p-4">
          {state.loading ? (
            <LoadingSkeleton rows={3} />
          ) : state.error ? (
            <ErrorState message={state.error} onRetry={state.reload} />
          ) : recent.length === 0 ? (
            <EmptyState
              title={t('هنوز فعالیتی ثبت نشده', 'No activity yet')}
              body={t(
                'پس از ثبت اولین درخواست استعلام، تأمین یا تیکت پشتیبانی، این بخش به‌روزرسانی می‌شود.',
                'This section updates after your first quote, procurement, or support submission.',
              )}
              ctaLabel={t('مشاهده فروشگاه', 'Browse robots')}
              onCta={() => go('catalog')}
            />
          ) : (
            <ul className="grid gap-2">
              {recent.map((it) => (
                <li
                  key={`${it.kind}:${it.record.name}`}
                  className="rounded-2xl bg-soft border border-line p-3 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] uppercase tracking-wide font-bold text-faint">
                        {it.kind === 'quote'
                          ? t('استعلام', 'Quote')
                          : it.kind === 'procurement'
                            ? t('تأمین', 'Procurement')
                            : t('پشتیبانی', 'Support')}
                      </span>
                      <span className="font-mono text-xs text-tech-blue">{it.record.name}</span>
                    </div>
                    <div className="text-sm text-fg truncate mt-0.5">
                      {it.kind === 'quote'
                        ? quotePreviewText(it.record, t)
                        : it.kind === 'procurement'
                          ? it.record.product_name || '—'
                          : it.record.subject || '—'}
                    </div>
                  </div>
                  <StatusBadge kind={it.kind} status={it.record.status} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

function CountCard({
  icon,
  label,
  count,
  onClick,
  loading,
}: {
  icon: React.ReactNode
  label: string
  count: number
  onClick: () => void
  loading: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="bg-white border border-line rounded-2xl p-5 shadow-soft hover:shadow-soft-lg hover:-translate-y-0.5 transition-all text-start"
    >
      <div className="flex items-center justify-between">
        <div className="size-10 rounded-xl bg-brand-50 ring-1 ring-brand-100 text-brand-600 grid place-items-center">
          {icon}
        </div>
        {loading ? (
          <span className="h-7 w-12 bg-soft rounded animate-pulse" />
        ) : (
          <span className="text-2xl font-extrabold text-fg num-fa">{count}</span>
        )}
      </div>
      <div className="mt-3 text-sm font-semibold text-fg">{label}</div>
    </button>
  )
}

function quotePreviewText(r: MyQuoteRequest, t: (fa: string, en: string) => string): string {
  if (!r.item_preview || r.item_preview.length === 0) {
    return t('بدون اقلام', 'No items')
  }
  const first = r.item_preview[0]!
  if ((r.item_count || 0) > 1) {
    return `${first} +${r.item_count - 1}`
  }
  return first
}

// ---------------------------------------------------------------------------
// Combined "All requests"
// ---------------------------------------------------------------------------

function CombinedRequestsView() {
  const { t } = useI18n()
  const state = useMyRequests(50)

  const all = useMemo(() => {
    if (!state.data) return []
    type RecentItem =
      | { kind: 'quote'; record: MyQuoteRequest }
      | { kind: 'procurement'; record: MyProcurementRequest }
      | { kind: 'support'; record: MySupportTicket }
    const merged: RecentItem[] = [
      ...state.data.quote_requests.map((r) => ({ kind: 'quote' as const, record: r })),
      ...state.data.procurement_requests.map((r) => ({ kind: 'procurement' as const, record: r })),
      ...state.data.support_tickets.map((r) => ({ kind: 'support' as const, record: r })),
    ]
    merged.sort((a, b) => (b.record.creation || '').localeCompare(a.record.creation || ''))
    return merged
  }, [state.data])

  const [openDetail, setOpenDetail] = useState<{ kind: RequestKind; name: string } | null>(null)

  return (
    <div className="grid gap-5">
      <PageHeader
        title={t('همه‌ی درخواست‌ها', 'All requests')}
        description={t(
          'استعلام‌ها، تأمین و تیکت‌های پشتیبانی شما در یک جا.',
          'All your quote, procurement, and support records in one place.',
        )}
      />
      {state.loading ? (
        <LoadingSkeleton />
      ) : state.error ? (
        <ErrorState message={state.error} onRetry={state.reload} />
      ) : all.length === 0 ? (
        <EmptyState
          title={t('هنوز درخواستی ثبت نکرده‌اید', "You haven't submitted any requests yet")}
          body={t(
            'پس از ثبت اولین درخواست، آن را اینجا پیگیری می‌کنید.',
            'After your first submission, you can track it here.',
          )}
        />
      ) : (
        <ul className="grid gap-2">
          {all.map((it) => (
            <li key={`${it.kind}:${it.record.name}`}>
              <RequestRow
                kind={it.kind}
                name={it.record.name}
                title={
                  it.kind === 'quote'
                    ? quotePreviewText(it.record, t)
                    : it.kind === 'procurement'
                      ? it.record.product_name || '—'
                      : it.record.subject || '—'
                }
                status={it.record.status}
                subtitle={`${
                  it.kind === 'quote' ? t('استعلام', 'Quote') : it.kind === 'procurement' ? t('تأمین', 'Procurement') : t('پشتیبانی', 'Support')
                } · ${formatDate(it.record.creation)}`}
                onOpen={() => setOpenDetail({ kind: it.kind, name: it.record.name })}
              />
            </li>
          ))}
        </ul>
      )}

      <RequestDetailDrawer open={openDetail} onClose={() => setOpenDetail(null)} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Quote / Procurement / Support list views
// ---------------------------------------------------------------------------

function QuoteListView() {
  const { t, usd } = useI18n()
  const { go } = useApp()
  const state = useMyRequests(50)
  const [openDetail, setOpenDetail] = useState<{ kind: RequestKind; name: string } | null>(null)
  const rows = state.data?.quote_requests ?? []

  return (
    <div className="grid gap-5">
      <PageHeader
        title={t('استعلام‌ها', 'Quote requests')}
        description={t(
          'لیست استعلام‌های ثبت‌شده توسط شما.',
          'Quote requests you have submitted.',
        )}
      />
      {state.loading ? (
        <LoadingSkeleton />
      ) : state.error ? (
        <ErrorState message={state.error} onRetry={state.reload} />
      ) : rows.length === 0 ? (
        <EmptyState
          title={t('هنوز استعلامی ثبت نکرده‌اید', 'No quote requests yet')}
          body={t(
            'با افزودن ربات‌ها به سبد و ثبت استعلام، می‌توانید اینجا پیگیری کنید.',
            'Add robots to your cart and submit a quote to start tracking here.',
          )}
          ctaLabel={t('مشاهده فروشگاه', 'Browse robots')}
          onCta={() => go('catalog')}
        />
      ) : (
        <ul className="grid gap-2">
          {rows.map((r) => (
            <li key={r.name}>
              <RequestRow
                kind="quote"
                name={r.name}
                title={quotePreviewText(r, t)}
                status={r.status}
                subtitle={
                  r.item_count > 0
                    ? `${r.item_count} ${t('قلم', 'items')} · ${formatDate(r.creation)}`
                    : formatDate(r.creation)
                }
                trailing={
                  r.total_estimate_usd && r.total_estimate_usd > 0 ? (
                    <div className="text-xs font-bold num-fa text-tech-blue">
                      {usd(r.total_estimate_usd)}
                    </div>
                  ) : null
                }
                onOpen={() => setOpenDetail({ kind: 'quote', name: r.name })}
              />
            </li>
          ))}
        </ul>
      )}
      <RequestDetailDrawer open={openDetail} onClose={() => setOpenDetail(null)} />
    </div>
  )
}

function ProcurementListView() {
  const { t, n, usd } = useI18n()
  const { go } = useApp()
  const state = useMyRequests(50)
  const [openDetail, setOpenDetail] = useState<{ kind: RequestKind; name: string } | null>(null)
  const rows = state.data?.procurement_requests ?? []

  return (
    <div className="grid gap-5">
      <PageHeader
        title={t('درخواست تأمین', 'Procurement requests')}
        description={t(
          'لیست درخواست‌های تأمین سفارشی شما.',
          'Custom sourcing requests you have submitted.',
        )}
      />
      {state.loading ? (
        <LoadingSkeleton />
      ) : state.error ? (
        <ErrorState message={state.error} onRetry={state.reload} />
      ) : rows.length === 0 ? (
        <EmptyState
          title={t('هنوز درخواست تأمینی ندارید', 'No procurement requests yet')}
          body={t(
            'اگر ربات خاصی در فروشگاه نیست، می‌توانید درخواست تأمین ثبت کنید.',
            "If a specific robot isn't in our shop, submit a sourcing request.",
          )}
          ctaLabel={t('ثبت درخواست تأمین', 'Request procurement')}
          onCta={() => go('procurement')}
        />
      ) : (
        <ul className="grid gap-2">
          {rows.map((r) => (
            <li key={r.name}>
              <RequestRow
                kind="procurement"
                name={r.name}
                title={r.product_name || '—'}
                status={r.status}
                subtitle={`${r.brand || ''}${r.brand && r.quantity ? ' · ' : ''}${r.quantity ? `${n(r.quantity)} ${t('عدد', 'units')}` : ''} · ${formatDate(r.creation)}`}
                trailing={
                  r.target_budget_usd && r.target_budget_usd > 0 ? (
                    <div className="text-xs font-bold num-fa text-tech-blue">{usd(r.target_budget_usd)}</div>
                  ) : null
                }
                onOpen={() => setOpenDetail({ kind: 'procurement', name: r.name })}
              />
            </li>
          ))}
        </ul>
      )}
      <RequestDetailDrawer open={openDetail} onClose={() => setOpenDetail(null)} />
    </div>
  )
}

function SupportListView() {
  const { t } = useI18n()
  const { go } = useApp()
  const state = useMyRequests(50)
  const [openDetail, setOpenDetail] = useState<{ kind: RequestKind; name: string } | null>(null)
  const rows = state.data?.support_tickets ?? []

  return (
    <div className="grid gap-5">
      <PageHeader
        title={t('تیکت‌های پشتیبانی', 'Support tickets')}
        description={t('لیست پیام‌های پشتیبانی شما.', 'Support messages you have sent.')}
      />
      {state.loading ? (
        <LoadingSkeleton />
      ) : state.error ? (
        <ErrorState message={state.error} onRetry={state.reload} />
      ) : rows.length === 0 ? (
        <EmptyState
          title={t('هنوز تیکتی ندارید', 'No support tickets yet')}
          body={t(
            'برای ارسال پرسش به تیم پشتیبانی، از فرم تماس استفاده کنید.',
            'Use the contact form to reach the support team.',
          )}
          ctaLabel={t('تماس با پشتیبانی', 'Contact support')}
          onCta={() => go('support')}
        />
      ) : (
        <ul className="grid gap-2">
          {rows.map((r) => (
            <li key={r.name}>
              <RequestRow
                kind="support"
                name={r.name}
                title={r.subject || '—'}
                status={r.status}
                subtitle={formatDate(r.creation)}
                onOpen={() => setOpenDetail({ kind: 'support', name: r.name })}
              />
            </li>
          ))}
        </ul>
      )}
      <RequestDetailDrawer open={openDetail} onClose={() => setOpenDetail(null)} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Row used by every list
// ---------------------------------------------------------------------------

function RequestRow({
  kind,
  name,
  title,
  subtitle,
  status,
  trailing,
  onOpen,
}: {
  kind: RequestKind
  name: string
  title: string
  subtitle: string
  status: string | null | undefined
  trailing?: React.ReactNode
  onOpen: () => void
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full text-start rounded-2xl bg-white border border-line p-4 shadow-soft hover:shadow-soft-lg hover:border-brand-100 transition-all"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-tech-blue">{name}</span>
          </div>
          <div className="mt-1 text-sm font-bold text-fg truncate">{title}</div>
          <div className="mt-1 text-xs text-faint">{subtitle}</div>
        </div>
        <div className="shrink-0 flex flex-col items-end gap-2">
          <StatusBadge kind={kind} status={status} />
          {trailing}
        </div>
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Detail drawer
// ---------------------------------------------------------------------------

interface DetailOpenRef {
  kind: RequestKind
  name: string
}

function RequestDetailDrawer({
  open,
  onClose,
}: {
  open: DetailOpenRef | null
  onClose: () => void
}) {
  const { t } = useI18n()
  const [detail, setDetail] = useState<
    | { kind: 'quote'; record: QuoteRequestDetail }
    | { kind: 'procurement'; record: ProcurementRequestDetail }
    | { kind: 'support'; record: SupportTicketDetail }
    | null
  >(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- canonical "clear on close" pattern
      setDetail(null)
      setError(null)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    setDetail(null)
    getMyRequestDetail(open.kind, open.name, controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return
        setDetail(res)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        const msg =
          err instanceof FrappeApiError
            ? err.code === 'NOT_FOUND'
              ? t('این رکورد یافت نشد.', 'This record was not found.')
              : err.message
            : (err as Error)?.message || 'Failed to load detail'
        setError(msg)
        setLoading(false)
      })
    return () => controller.abort()
  }, [open, t])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-ink-900/40 animate-fade-in"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="absolute top-0 end-0 h-full w-[min(560px,94vw)] bg-white border-s border-line shadow-soft-lg flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        <header className="px-5 py-4 border-b border-line flex items-center gap-3">
          <button
            type="button"
            onClick={onClose}
            className="size-9 grid place-items-center rounded-xl hover:bg-ink-50 text-fg transition-colors"
            aria-label={t('بستن', 'Close')}
          >
            <ChevronLeft size={18} />
          </button>
          <div className="min-w-0">
            <div className="text-xs text-faint">
              {open.kind === 'quote'
                ? t('استعلام', 'Quote request')
                : open.kind === 'procurement'
                  ? t('تأمین', 'Procurement request')
                  : t('پشتیبانی', 'Support ticket')}
            </div>
            <div className="font-mono text-sm text-fg">{open.name}</div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <LoadingSkeleton rows={4} />
          ) : error ? (
            <ErrorState message={error} onRetry={onClose} />
          ) : detail ? (
            detail.kind === 'quote' ? (
              <QuoteDetailBody record={detail.record} />
            ) : detail.kind === 'procurement' ? (
              <ProcurementDetailBody record={detail.record} />
            ) : (
              <SupportDetailBody record={detail.record} />
            )
          ) : null}
        </div>
      </aside>
    </div>
  )
}

function QuoteDetailBody({ record }: { record: QuoteRequestDetail }) {
  const { t, n, usd } = useI18n()
  return (
    <div className="grid gap-5">
      <div>
        <StatusBadge kind="quote" status={record.status} />
        <div className="mt-3 text-xs text-faint">
          {t('ثبت‌شده در', 'Submitted')}: <span className="text-fg">{formatDate(record.submitted_at || record.creation)}</span>
        </div>
        {record.total_estimate_usd && record.total_estimate_usd > 0 ? (
          <div className="mt-1 text-xs text-faint">
            {t('برآورد اولیه', 'Estimated total')}: <span className="text-tech-blue font-bold num-fa">{usd(record.total_estimate_usd)}</span>
          </div>
        ) : null}
      </div>

      {record.message ? (
        <Block label={t('پیام شما', 'Your message')}>
          <p className="text-sm text-fg leading-7 whitespace-pre-wrap">{record.message}</p>
        </Block>
      ) : null}

      <Block label={t('اقلام درخواست', 'Items')}>
        {(record.items || []).length === 0 ? (
          <p className="text-sm text-muted">{t('بدون اقلام', 'No items')}</p>
        ) : (
          <ul className="grid gap-2">
            {record.items.map((it) => (
              <li key={`${it.idx}:${it.robot_product}`} className="rounded-xl bg-soft border border-line p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-fg truncate">{it.product_name}</div>
                    <div className="mt-1 text-xs text-faint">
                      <span className="font-mono text-tech-blue">{it.robot_product}</span>
                      {' · '}
                      <Badge tone={it.mode === 'rent' ? 'rent' : it.mode === 'procure' ? 'tech' : 'brand'}>
                        {it.mode === 'rent' ? t('اجاره', 'Rent') : it.mode === 'procure' ? t('تأمین', 'Source') : t('خرید', 'Buy')}
                      </Badge>
                    </div>
                  </div>
                  <div className="text-end shrink-0">
                    <div className="text-xs text-faint">
                      {t('تعداد', 'Qty')}: <span className="font-bold text-fg num-fa">{n(it.quantity)}</span>
                    </div>
                    {it.mode === 'rent' && it.requested_days ? (
                      <div className="text-[11px] text-faint num-fa">{n(it.requested_days)} {t('روز', 'days')}</div>
                    ) : null}
                    {it.line_total_usd && it.line_total_usd > 0 ? (
                      <div className="text-xs font-bold num-fa text-tech-blue mt-1">{usd(it.line_total_usd)}</div>
                    ) : null}
                  </div>
                </div>
                {it.notes ? (
                  <p className="mt-2 text-xs text-muted leading-6 whitespace-pre-wrap">{it.notes}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Block>
    </div>
  )
}

function ProcurementDetailBody({ record }: { record: ProcurementRequestDetail }) {
  const { t, n, usd } = useI18n()
  return (
    <div className="grid gap-5">
      <div>
        <StatusBadge kind="procurement" status={record.status} />
        <div className="mt-3 text-xs text-faint">
          {t('ثبت‌شده در', 'Submitted')}: <span className="text-fg">{formatDate(record.submitted_at || record.creation)}</span>
        </div>
      </div>

      <Block label={t('محصول درخواستی', 'Requested item')}>
        <div className="text-sm font-bold text-fg">{record.product_name || '—'}</div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
          {record.brand ? <Field label={t('برند', 'Brand')} value={record.brand} /> : null}
          {record.quantity ? <Field label={t('تعداد', 'Quantity')} value={n(record.quantity)} /> : null}
          {record.origin_country ? <Field label={t('کشور مبدا', 'Origin')} value={record.origin_country} /> : null}
          {record.destination_city ? <Field label={t('شهر مقصد', 'Destination')} value={record.destination_city} /> : null}
          {record.target_budget_usd && record.target_budget_usd > 0 ? <Field label={t('بودجه', 'Budget')} value={usd(record.target_budget_usd)} /> : null}
          {record.timeline ? <Field label={t('زمان‌بندی', 'Timeline')} value={record.timeline} /> : null}
          {record.company ? <Field label={t('شرکت', 'Company')} value={record.company} /> : null}
        </dl>
      </Block>

      {record.message ? (
        <Block label={t('یادداشت‌ها', 'Notes')}>
          <p className="text-sm text-fg leading-7 whitespace-pre-wrap">{record.message}</p>
        </Block>
      ) : null}
    </div>
  )
}

function SupportDetailBody({ record }: { record: SupportTicketDetail }) {
  const { t } = useI18n()
  return (
    <div className="grid gap-5">
      <div>
        <StatusBadge kind="support" status={record.status} />
        <div className="mt-3 text-xs text-faint">
          {t('ثبت‌شده در', 'Created')}: <span className="text-fg">{formatDate(record.creation)}</span>
        </div>
      </div>
      <Block label={t('موضوع', 'Subject')}>
        <p className="text-sm font-bold text-fg">{record.subject || '—'}</p>
      </Block>
      {record.description ? (
        <Block label={t('پیام شما', 'Your message')}>
          <div
            className="text-sm text-fg leading-7 prose-sm max-w-none"
            // Backend escapes the user input before joining with <br>, so this
            // string is safe to render -- it only contains escaped text + <br>.
            dangerouslySetInnerHTML={{ __html: record.description }}
          />
        </Block>
      ) : null}
    </div>
  )
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="text-xs uppercase tracking-wide font-bold text-faint mb-2">{label}</div>
      <div className="rounded-2xl bg-white border border-line p-4">{children}</div>
    </section>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-soft border border-line px-3 py-2">
      <dt className="text-[11px] text-faint">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-fg">{value}</dd>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Profile form
// ---------------------------------------------------------------------------

function ProfileFormView({ user }: { user: NonNullable<ReturnType<typeof useAuth>['currentUser']> }) {
  const { t } = useI18n()
  const { updateProfile } = useAuth()
  const [firstName, setFirstName] = useState(user.first_name)
  const [lastName, setLastName] = useState(user.last_name)
  const [phone, setPhone] = useState(user.phone)
  const [lang, setLang] = useState<'fa' | 'en'>(user.preferred_language)
  const [marketing, setMarketing] = useState<boolean>(user.marketing_opt_in)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    setSaving(true)
    try {
      await updateProfile({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        preferred_language: lang,
        marketing_opt_in: marketing,
      })
      setSuccess(true)
    } catch (err) {
      const msg = err instanceof FrappeApiError ? err.message : (err as Error)?.message
      setError(msg || t('ذخیره ناموفق بود.', 'Could not save changes.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-5">
      <PageHeader
        title={t('پروفایل', 'Profile')}
        description={t(
          'اطلاعات پایه‌ی حساب خود را اینجا به‌روز کنید.',
          'Update your basic account details here.',
        )}
      />

      <form onSubmit={handleSave} className="bg-white border border-line rounded-3xl p-6 shadow-soft grid gap-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <Input label={t('نام', 'First name')} value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          <Input label={t('نام خانوادگی', 'Last name')} value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </div>
        <Input label={t('ایمیل', 'Email')} value={user.email} disabled dir="ltr" hint={t('برای تغییر ایمیل با پشتیبانی تماس بگیرید.', 'Email changes are handled by support.')} />
        <Input label={t('شماره تماس', 'Phone')} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0912 345 6789" dir="ltr" inputMode="tel" />
        <Select label={t('زبان ترجیحی', 'Preferred language')} value={lang} onChange={(e) => setLang((e.target.value as 'fa' | 'en') || 'fa')}>
          <option value="fa">فارسی</option>
          <option value="en">English</option>
        </Select>
        <label className="flex items-center gap-3 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={marketing}
            onChange={(e) => setMarketing(e.target.checked)}
          />
          <span className="text-fg">
            {t('دریافت ایمیل‌های اطلاع‌رسانی و محصولات جدید', 'Receive product news and announcements')}
          </span>
        </label>

        {error ? (
          <div className="rounded-lg bg-brand-50 border border-brand-100 text-brand-700 text-xs px-3 py-2 leading-6">
            {error}
          </div>
        ) : null}
        {success ? (
          <div className="rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-700 text-xs px-3 py-2 leading-6">
            {t('تغییرات ذخیره شد.', 'Changes saved.')}
          </div>
        ) : null}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving}>
            {saving ? t('در حال ذخیره...', 'Saving...') : t('ذخیره', 'Save')}
          </Button>
        </div>
      </form>

      <div className="rounded-2xl border border-dashed border-line bg-white p-5 text-center">
        <p className="text-xs text-muted leading-6">
          {t(
            'تغییر ایمیل، نقش‌ها، شناسه مشتری و سایر فیلدهای داخلی از این فرم در دسترس نیست.',
            'Email, roles, customer id and other internal fields are not editable from this form.',
          )}
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatDate(raw: string | null | undefined): string {
  if (!raw) return '—'
  // Backend timestamps look like "2026-06-03 12:56:24.673040". We render only
  // the date + HH:MM portion; the Phase 1 i18n date formatter expects a number
  // (epoch ms), so we use a simple slice here to avoid an extra dep.
  const trimmed = raw.split('.')[0]!
  return trimmed.replace('T', ' ').slice(0, 16)
}
