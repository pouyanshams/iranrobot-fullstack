/**
 * Phase 8C -- Real wallet view backed by `iranrobot_backend.api.wallet`.
 *
 * Two render modes:
 *   - standalone (default, `#/wallet`): wraps the body in <Section>. For
 *     authenticated users an effect redirects to `#/account/wallet` so the
 *     dashboard navigation stays consistent. Guests see a login-required panel.
 *   - embedded (`<WalletView embedded />` from Account.tsx): renders without
 *     the outer <Section>/title so it can live inside AccountLayout.
 *
 * Source of truth is the backend. No localStorage reads or writes.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Wallet as WalletIcon,
  Plus,
  ArrowDownCircle,
  ArrowUpCircle,
  Loader2,
  Copy,
  X,
} from 'lucide-react'

import { Section } from '../components/Section'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { NumberInput } from '../components/Input'
import { StatusBadge } from '../components/StatusBadge'
import { useApp } from '../context/AppContext'
import { useAuth } from '../lib/useAuth'
import { useI18n } from '../i18n'
import { FrappeApiError } from '../lib/frappeApi'
import {
  cancelTopUpRequest,
  createTopUpRequest,
  type TopUpInstructions,
  type TopUpMethod,
  type WalletTopUpRequest,
  type WalletTransaction,
} from '../api/wallet'
import {
  useMyTopUpRequests,
  useWalletSummary,
  useWalletTransactions,
} from '../lib/useWallet'

interface WalletViewProps {
  embedded?: boolean
}

const PRESET_AMOUNTS = [100, 250, 500, 1000]

export function WalletView({ embedded = false }: WalletViewProps) {
  const { go } = useApp()
  const { isAuthenticated, isLoading: authLoading, openLogin } = useAuth()
  const { t } = useI18n()

  // Standalone `#/wallet` for authenticated users redirects into the
  // dashboard so the sidebar/header stays consistent.
  useEffect(() => {
    if (embedded) return
    if (authLoading) return
    if (isAuthenticated) {
      go('account', 'wallet')
    }
  }, [embedded, authLoading, isAuthenticated, go])

  if (!embedded && (authLoading || !isAuthenticated)) {
    return (
      <Section
        eyebrow={t('کیف پول', 'Wallet')}
        title={t('کیف پول دلاری شما', 'Your USD wallet')}
      >
        {authLoading ? (
          <div className="flex items-center gap-3 text-muted">
            <Loader2 size={18} className="animate-spin" />
            <span>{t('در حال بررسی وضعیت ورود…', 'Checking your sign-in…')}</span>
          </div>
        ) : (
          <GuestPanel onLogin={openLogin} t={t} />
        )}
      </Section>
    )
  }

  return embedded ? (
    <WalletBody />
  ) : (
    <Section
      eyebrow={t('کیف پول', 'Wallet')}
      title={t('کیف پول دلاری شما', 'Your USD wallet')}
      description={t(
        'موجودی و تاریخچه از سرور می‌آید. درخواست‌های افزایش موجودی پس از تأیید پشتیبانی، به موجودی افزوده می‌شوند.',
        'Balance and history come from the server. Top-up requests credit your balance once staff approves them.',
      )}
    >
      <WalletBody />
    </Section>
  )
}

// ---------- Guest panel ----------------------------------------------------

function GuestPanel({
  onLogin,
  t,
}: {
  onLogin: () => void
  t: (fa: string, en: string) => string
}) {
  return (
    <div className="max-w-2xl rounded-2xl bg-white border border-line p-6 sm:p-8">
      <div className="flex items-center gap-3 mb-3">
        <WalletIcon size={20} className="text-brand-600" />
        <h3 className="text-xl font-bold">
          {t('برای استفاده از کیف پول وارد شوید', 'Log in to use your wallet')}
        </h3>
      </div>
      <p className="text-muted leading-7 mb-5">
        {t(
          'برای ساخت درخواست افزایش موجودی، دیدن موجودی و تاریخچه‌ی تراکنش‌ها ابتدا وارد حساب مشتری خود شوید.',
          'Log in to your customer account to view your balance, transaction history, and create top-up requests.',
        )}
      </p>
      <Button onClick={onLogin}>{t('ورود', 'Log in')}</Button>
    </div>
  )
}

// ---------- Main body -----------------------------------------------------

function WalletBody() {
  const { t, n, usd, dateTime } = useI18n()
  const { isAuthenticated } = useAuth()
  const summary = useWalletSummary(isAuthenticated)
  const transactions = useWalletTransactions(isAuthenticated)
  const requests = useMyTopUpRequests(isAuthenticated)

  const reloadAll = useCallback(() => {
    summary.reload()
    transactions.reload()
    requests.reload()
  }, [summary, transactions, requests])

  const wallet = summary.data?.wallet ?? null
  const canTopUp = !!summary.data?.can_top_up
  const canSpend = !!summary.data?.can_spend
  const pendingTopUps = summary.data?.pending_top_ups ?? []
  const balance = wallet?.balance_usd ?? 0
  const available = wallet?.available_balance_usd ?? balance

  return (
    <div className="grid gap-6">
      <BalanceCard
        loading={summary.loading}
        error={summary.error}
        currency={wallet?.currency ?? 'USD'}
        status={wallet?.status}
        balance={balance}
        available={available}
        canTopUp={canTopUp}
        canSpend={canSpend}
        lastTxAt={wallet?.last_transaction_at}
        t={t}
        usd={usd}
        dateTime={dateTime}
        onReload={reloadAll}
      />

      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7">
          <TopUpForm canTopUp={canTopUp} onCreated={reloadAll} />
        </div>
        <div className="lg:col-span-5">
          <PendingList
            data={pendingTopUps}
            loading={summary.loading}
            onCancelled={reloadAll}
          />
        </div>
      </div>

      <TransactionsCard
        data={transactions.data}
        loading={transactions.loading}
        error={transactions.error}
        t={t}
        n={n}
        usd={usd}
        dateTime={dateTime}
      />
    </div>
  )
}

// ---------- Balance card --------------------------------------------------

function BalanceCard({
  loading,
  error,
  currency,
  status,
  balance,
  available,
  canTopUp,
  canSpend,
  lastTxAt,
  t,
  usd,
  dateTime,
  onReload,
}: {
  loading: boolean
  error: string | null
  currency: string
  status: string | undefined
  balance: number
  available: number
  canTopUp: boolean
  canSpend: boolean
  lastTxAt: string | null | undefined
  t: (fa: string, en: string) => string
  usd: (n: number) => string
  dateTime: (ts: number) => string
  onReload: () => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-3xl bg-gradient-to-tr from-brand-600 to-brand-500 p-6 sm:p-8 text-white shadow-[0_20px_60px_-20px_rgba(127,24,16,0.4)]"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-white/80 text-sm font-medium">
            <WalletIcon size={16} />
            <span>{t('موجودی کیف پول', 'Wallet balance')}</span>
            <span className="text-white/60">·</span>
            <span className="font-bold">{currency}</span>
            {status ? (
              <Badge tone="brand">
                {t(
                  status === 'Active' ? 'فعال' : status === 'Frozen' ? 'مسدود' : 'بسته شد',
                  status,
                )}
              </Badge>
            ) : null}
          </div>
          {error ? (
            <div className="mt-3 text-sm">
              <span className="font-bold">{t('خطا: ', 'Error: ')}</span>
              <span>{error}</span>
              <button
                onClick={onReload}
                className="ms-3 underline underline-offset-4 text-white/90 hover:text-white"
              >
                {t('تلاش مجدد', 'Retry')}
              </button>
            </div>
          ) : (
            <>
              <div
                className="mt-3 text-5xl font-extrabold num-fa text-white"
                data-testid="wallet-balance"
              >
                {loading ? '—' : usd(balance)}
              </div>
              {available !== balance ? (
                <div className="mt-1 text-sm text-white/80">
                  {t('قابل استفاده: ', 'Available: ')}
                  <span className="num-fa">{usd(available)}</span>
                </div>
              ) : null}
            </>
          )}
        </div>
        <div className="text-end">
          <div className="flex flex-col items-end gap-1 text-xs text-white/80">
            <span>
              {canTopUp ? (
                <span className="text-emerald-200">✓ {t('افزایش موجودی فعال', 'Top-up enabled')}</span>
              ) : (
                <span className="text-white/60">
                  {t('افزایش موجودی غیرفعال', 'Top-up disabled')}
                </span>
              )}
            </span>
            <span
              title={t(
                'پرداخت با کیف پول در فاز ۸D اضافه می‌شود.',
                'Pay with Wallet ships in Phase 8D.',
              )}
            >
              {canSpend ? (
                <span className="text-emerald-200">
                  ✓ {t('پرداخت با کیف پول فعال', 'Spend enabled')}
                </span>
              ) : (
                <span className="text-white/60">
                  {t('پرداخت با کیف پول (به زودی)', 'Spend (coming soon)')}
                </span>
              )}
            </span>
          </div>
        </div>
      </div>
      {lastTxAt ? (
        <div className="mt-6 text-xs text-white/70">
          {t('آخرین تراکنش: ', 'Last transaction: ')}
          <span>{dateTime(new Date(lastTxAt).getTime())}</span>
        </div>
      ) : null}
    </motion.div>
  )
}

// ---------- Top-up form ---------------------------------------------------

function TopUpForm({
  canTopUp,
  onCreated,
}: {
  canTopUp: boolean
  onCreated: () => void
}) {
  const { t, usd } = useI18n()
  const [amount, setAmount] = useState<number | null>(250)
  const [method, setMethod] = useState<TopUpMethod>('Bank Transfer')
  const [note, setNote] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastInstructions, setLastInstructions] = useState<TopUpInstructions | null>(null)
  const [lastRequestId, setLastRequestId] = useState<string | null>(null)

  const handleSubmit = useCallback(async () => {
    setError(null)
    if (!amount || amount <= 0) {
      setError(t('مبلغ نامعتبر است.', 'Invalid amount.'))
      return
    }
    setSubmitting(true)
    try {
      const res = await createTopUpRequest(amount, method, note.trim() || undefined)
      setLastInstructions(res.instructions)
      setLastRequestId(res.request_id)
      setAmount(null)
      setNote('')
      onCreated()
    } catch (err) {
      if (err instanceof FrappeApiError) {
        if (err.code === 'TOO_MANY_PENDING') {
          setError(
            t(
              'سقف درخواست‌های در انتظار پر است. ابتدا یکی را لغو کنید یا منتظر تأیید بمانید.',
              err.message,
            ),
          )
        } else {
          setError(err.message)
        }
      } else {
        setError((err as Error).message || t('خطایی رخ داد.', 'Something went wrong.'))
      }
    } finally {
      setSubmitting(false)
    }
  }, [amount, method, note, onCreated, t])

  return (
    <div className="rounded-2xl bg-white border border-line p-5 sm:p-6">
      <div className="flex items-center gap-2 mb-4">
        <Plus size={18} className="text-brand-600" />
        <h3 className="text-base sm:text-lg font-bold">{t('افزایش موجودی', 'Top up')}</h3>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        {PRESET_AMOUNTS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setAmount(p)}
            disabled={submitting || !canTopUp}
            className={[
              'h-10 rounded-lg border text-sm font-semibold transition-colors',
              amount === p
                ? 'border-brand-500 bg-brand-50 text-brand-700'
                : 'border-line bg-white hover:bg-ink-50',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            ].join(' ')}
          >
            <span className="num-fa">{usd(p)}</span>
          </button>
        ))}
      </div>

      <label className="block text-sm font-semibold mb-1 text-fg">
        {t('مبلغ (دلار)', 'Amount (USD)')}
      </label>
      <NumberInput
        value={amount ?? null}
        onValueChange={(v) => setAmount(v)}
        min={1}
        placeholder={t('مثلاً ۲۵۰', 'e.g. 250')}
        disabled={submitting || !canTopUp}
      />

      <fieldset className="mt-4" disabled={submitting || !canTopUp}>
        <legend className="text-sm font-semibold mb-1 text-fg">
          {t('روش پرداخت', 'Payment method')}
        </legend>
        <div className="flex flex-col sm:flex-row gap-2">
          {(['Bank Transfer', 'Cash Deposit'] as TopUpMethod[]).map((m) => (
            <label
              key={m}
              className={[
                'flex-1 inline-flex items-center gap-2 h-11 px-3 rounded-lg border cursor-pointer text-sm font-medium',
                method === m
                  ? 'border-brand-500 bg-brand-50 text-brand-700'
                  : 'border-line hover:bg-ink-50',
              ].join(' ')}
            >
              <input
                type="radio"
                className="accent-brand-600"
                checked={method === m}
                onChange={() => setMethod(m)}
                name="topup-method"
              />
              <span>
                {m === 'Bank Transfer'
                  ? t('انتقال بانکی', 'Bank Transfer')
                  : t('واریز نقدی', 'Cash Deposit')}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="block text-sm font-semibold mt-4 mb-1 text-fg">
        {t('یادداشت (اختیاری)', 'Note (optional)')}
      </label>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        disabled={submitting || !canTopUp}
        rows={2}
        maxLength={1000}
        placeholder={t('شماره فیش، نام بانک، …', 'Receipt number, bank name, …')}
        className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:border-brand-500 disabled:opacity-50"
      />

      {error ? (
        <div className="mt-3 text-sm text-red-600 font-medium">{error}</div>
      ) : null}

      <div className="mt-4 flex justify-end">
        <Button
          onClick={handleSubmit}
          disabled={submitting || !canTopUp || !amount || amount <= 0}
          data-testid="wallet-topup-submit"
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
          {submitting
            ? t('در حال ارسال…', 'Submitting…')
            : t('ارسال درخواست افزایش موجودی', 'Submit top-up request')}
        </Button>
      </div>

      {lastInstructions && lastRequestId ? (
        <InstructionsBanner
          requestId={lastRequestId}
          instructions={lastInstructions}
          t={t}
        />
      ) : null}
    </div>
  )
}

function InstructionsBanner({
  requestId,
  instructions,
  t,
}: {
  requestId: string
  instructions: TopUpInstructions
  t: (fa: string, en: string) => string
}) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(instructions.iban)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard not available; ignore */
    }
  }, [instructions.iban])

  return (
    <div
      className="mt-5 rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900"
      data-testid="wallet-topup-instructions"
    >
      <div className="font-bold mb-2">
        {t('درخواست شما ثبت شد:', 'Your request was submitted:')}{' '}
        <span className="font-mono">{requestId}</span>
      </div>
      <ul className="space-y-1">
        <li>
          <span className="font-semibold">{t('ذی‌نفع: ', 'Beneficiary: ')}</span>
          {instructions.beneficiary}
        </li>
        <li>
          <span className="font-semibold">{t('بانک: ', 'Bank: ')}</span>
          {instructions.bank_name}
        </li>
        <li className="flex items-center flex-wrap gap-2">
          <span className="font-semibold">{t('شبا: ', 'IBAN: ')}</span>
          <span className="font-mono break-all">{instructions.iban}</span>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 text-xs underline underline-offset-4"
          >
            <Copy size={12} /> {copied ? t('کپی شد', 'Copied') : t('کپی', 'Copy')}
          </button>
        </li>
        <li>
          <span className="font-semibold">
            {t('کد پیگیری برای واریز: ', 'Reference for transfer: ')}
          </span>
          <span className="font-mono">{instructions.reference}</span>
        </li>
      </ul>
      <p className="mt-3 text-xs">
        {t(
          'لطفاً کد پیگیری بالا را در توضیحات واریز ذکر کنید تا پشتیبانی بتواند درخواست شما را شناسایی کند.',
          'Please mention the reference above in your bank transfer note so staff can match the payment to your request.',
        )}
      </p>
    </div>
  )
}

// ---------- Pending list --------------------------------------------------

function PendingList({
  data,
  loading,
  onCancelled,
}: {
  data: WalletTopUpRequest[]
  loading: boolean
  onCancelled: () => void
}) {
  const { t, usd, dateTime } = useI18n()
  return (
    <div className="rounded-2xl bg-white border border-line p-5 sm:p-6 h-full">
      <h3 className="text-base sm:text-lg font-bold mb-3">
        {t('در انتظار تأیید', 'Pending review')}
      </h3>
      {loading ? (
        <div className="text-muted text-sm flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" />
          {t('در حال بارگذاری…', 'Loading…')}
        </div>
      ) : data.length === 0 ? (
        <div className="text-muted text-sm" data-testid="wallet-pending-empty">
          {t(
            'در حال حاضر درخواستی در انتظار تأیید نیست.',
            'No pending top-up requests right now.',
          )}
        </div>
      ) : (
        <ul className="space-y-3" data-testid="wallet-pending-list">
          {data.map((req) => (
            <PendingRow
              key={req.name}
              req={req}
              onCancelled={onCancelled}
              t={t}
              usd={usd}
              dateTime={dateTime}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function PendingRow({
  req,
  onCancelled,
  t,
  usd,
  dateTime,
}: {
  req: WalletTopUpRequest
  onCancelled: () => void
  t: (fa: string, en: string) => string
  usd: (n: number) => string
  dateTime: (ts: number) => string
}) {
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const onCancel = useCallback(async () => {
    if (cancelling) return
    const confirmed = window.confirm(
      t('این درخواست افزایش موجودی لغو شود؟', 'Cancel this top-up request?'),
    )
    if (!confirmed) return
    setCancelling(true)
    setError(null)
    try {
      await cancelTopUpRequest(req.name)
      onCancelled()
    } catch (err) {
      if (err instanceof FrappeApiError) setError(err.message)
      else setError((err as Error).message || t('خطایی رخ داد.', 'Something went wrong.'))
      setCancelling(false)
    }
  }, [cancelling, onCancelled, req.name, t])

  return (
    <li
      className="rounded-xl border border-line p-3"
      data-testid="wallet-pending-row"
      data-request-id={req.name}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <StatusBadge kind="wallet" status={req.status} />
            <span className="text-xs text-muted font-mono">{req.name}</span>
          </div>
          <div className="mt-1.5 text-lg font-extrabold num-fa">{usd(req.amount_usd)}</div>
          <div className="mt-1 text-xs text-muted">
            <span>
              {req.method === 'Bank Transfer'
                ? t('انتقال بانکی', 'Bank Transfer')
                : t('واریز نقدی', 'Cash Deposit')}
            </span>
            <span className="mx-1.5">·</span>
            <span>{dateTime(new Date(req.submitted_at).getTime())}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onCancel}
          disabled={cancelling}
          className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
          data-testid="wallet-pending-cancel"
        >
          {cancelling ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}
          {cancelling ? t('در حال لغو…', 'Cancelling…') : t('لغو', 'Cancel')}
        </button>
      </div>
      {error ? <div className="mt-2 text-xs text-red-600">{error}</div> : null}
    </li>
  )
}

// ---------- Transactions card ---------------------------------------------

function TransactionsCard({
  data,
  loading,
  error,
  t,
  n,
  usd,
  dateTime,
}: {
  data: WalletTransaction[] | null
  loading: boolean
  error: string | null
  t: (fa: string, en: string) => string
  n: (v: number | string) => string
  usd: (n: number) => string
  dateTime: (ts: number) => string
}) {
  const items = useMemo(() => data ?? [], [data])
  return (
    <div className="rounded-2xl bg-white border border-line p-5 sm:p-6">
      <h3 className="text-base sm:text-lg font-bold mb-3">
        {t('تاریخچه تراکنش‌ها', 'Transaction history')}
      </h3>
      {loading ? (
        <div className="text-muted text-sm flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" />
          {t('در حال بارگذاری…', 'Loading…')}
        </div>
      ) : error ? (
        <div className="text-sm text-red-600">{error}</div>
      ) : items.length === 0 ? (
        <div className="text-muted text-sm" data-testid="wallet-tx-empty">
          {t('هنوز تراکنشی ثبت نشده است.', 'No transactions yet.')}
        </div>
      ) : (
        <ul className="space-y-3" data-testid="wallet-tx-list">
          {items.map((tx) => (
            <TxRow key={tx.name} tx={tx} t={t} n={n} usd={usd} dateTime={dateTime} />
          ))}
        </ul>
      )}
    </div>
  )
}

function TxRow({
  tx,
  t,
  usd,
  dateTime,
}: {
  tx: WalletTransaction
  t: (fa: string, en: string) => string
  n: (v: number | string) => string
  usd: (n: number) => string
  dateTime: (ts: number) => string
}) {
  const isCredit = tx.direction === 'Credit'
  const amount = isCredit ? tx.credit_amount_usd : tx.debit_amount_usd
  return (
    <li className="flex items-center justify-between gap-3 rounded-xl border border-line p-3">
      <div className="flex items-center gap-3">
        <div
          className={[
            'h-9 w-9 rounded-full flex items-center justify-center',
            isCredit ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700',
          ].join(' ')}
        >
          {isCredit ? <ArrowDownCircle size={18} /> : <ArrowUpCircle size={18} />}
        </div>
        <div>
          <div className="text-sm font-bold">{labelForType(tx.transaction_type, t)}</div>
          <div className="text-xs text-muted">
            <span>{dateTime(new Date(tx.posted_at).getTime())}</span>
            {tx.linked_top_up_request ? (
              <>
                <span className="mx-1.5">·</span>
                <span className="font-mono">{tx.linked_top_up_request}</span>
              </>
            ) : null}
            {tx.linked_sales_invoice ? (
              <>
                <span className="mx-1.5">·</span>
                <span className="font-mono">{tx.linked_sales_invoice}</span>
              </>
            ) : null}
          </div>
        </div>
      </div>
      <div
        className={[
          'text-base font-extrabold num-fa',
          isCredit ? 'text-emerald-700' : 'text-red-700',
        ].join(' ')}
      >
        {isCredit ? '+' : '-'}
        {usd(amount)}
      </div>
    </li>
  )
}

function labelForType(
  type: WalletTransaction['transaction_type'],
  t: (fa: string, en: string) => string,
): string {
  switch (type) {
    case 'Top Up':
      return t('افزایش موجودی', 'Top Up')
    case 'Spend':
      return t('پرداخت', 'Spend')
    case 'Refund':
      return t('بازگشت وجه', 'Refund')
    case 'Adjustment-Credit':
      return t('تنظیم (افزایش)', 'Adjustment (Credit)')
    case 'Adjustment-Debit':
      return t('تنظیم (کاهش)', 'Adjustment (Debit)')
    default:
      return type
  }
}
