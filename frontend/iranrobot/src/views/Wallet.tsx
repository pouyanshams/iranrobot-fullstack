import { useState } from 'react'
import { motion } from 'framer-motion'
import { Wallet as WalletIcon, CreditCard, Plus, Minus } from 'lucide-react'
import { Section } from '../components/Section'
import { Button } from '../components/Button'
import { Badge } from '../components/Badge'
import { NumberInput } from '../components/Input'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'

const PRESETS = [100, 250, 500, 1000, 2500]

export function WalletView() {
  const { walletBalanceUsd, walletTxs, topupWallet } = useApp()
  const { t, n, usd, tomanRange, dateTime } = useI18n()
  const [amount, setAmount] = useState<number | null>(500)

  function txLabel(label: string) {
    if (label === 'افزایش موجودی کیف پول') return t(label, 'Wallet top-up')
    if (label === 'پرداخت سبد سفارش') return t(label, 'Order payment')
    return label
  }

  return (
    <Section
      eyebrow={t('کیف پول', 'Wallet')}
      title={t('موجودی و تراکنش‌های ایران‌ربات', 'Your IranRobot balance & transactions')}
      description={t(
        'کیف پول دلاری شما برای پرداخت‌های فروشگاه، اجاره و سفارش‌های تأمین. موجودی روی این مرورگر ذخیره می‌شود.',
        'Your USD wallet for shop, rental and sourcing payments. The balance is stored in this browser.',
      )}
    >
      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="relative overflow-hidden rounded-3xl p-8 surface-navy shadow-soft-lg">
            <div aria-hidden className="pointer-events-none absolute -top-24 -start-24 size-72 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(127, 24, 16,0.3), transparent 65%)' }} />
            <div aria-hidden className="pointer-events-none absolute -bottom-24 -end-10 size-72 rounded-full blur-3xl" style={{ background: 'radial-gradient(circle, rgba(56,189,248,0.24), transparent 65%)' }} />
            <div className="relative flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-widest text-ink-400">{t('موجودی کیف پول', 'Wallet balance')}</div>
                <div className="mt-3 text-5xl font-extrabold num-fa text-white">{usd(walletBalanceUsd)}</div>
                <div className="mt-2 text-sm text-ink-300">≈ {tomanRange(walletBalanceUsd)}</div>
              </div>
              <div className="size-16 rounded-2xl glass-dark grid place-items-center text-tech-cyan">
                <WalletIcon size={28} />
              </div>
            </div>
            <div className="relative mt-7 flex flex-wrap gap-2">
              <Badge tone="glass">{t('ذخیره‌سازی محلی', 'Stored locally')}</Badge>
              <Badge tone="glass">{t('بدون کارمزد داخلی', 'No internal fees')}</Badge>
            </div>
          </motion.div>

          <div className="mt-6 bg-white border border-line rounded-3xl p-6 sm:p-8 shadow-soft">
            <h3 className="text-lg font-bold text-fg">{t('افزایش موجودی', 'Top up balance')}</h3>
            <p className="text-sm text-muted mt-1">{t('مبلغ مدنظر را به دلار وارد کنید — معادل تومانی به‌صورت تخمینی نمایش داده می‌شود.', 'Enter an amount in USD — the Toman equivalent is shown as an estimate.')}</p>

            <div className="mt-5 flex flex-wrap gap-2">
              {PRESETS.map((v) => (
                <button
                  type="button"
                  key={v}
                  onClick={() => setAmount(v)}
                  className={['h-10 px-4 rounded-lg text-sm font-semibold transition-colors num-fa border', amount === v ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-ink-700 border-line hover:bg-ink-50'].join(' ')}
                >
                  {usd(v)}
                </button>
              ))}
            </div>

            <div className="mt-5 grid sm:grid-cols-[1fr_auto] gap-3 items-end">
              <NumberInput
                label={t('مبلغ افزایش (دلار)', 'Top-up amount (USD)')}
                value={amount}
                onValueChange={setAmount}
                min={1}
                leading={<span className="text-sm font-bold">$</span>}
                hint={amount ? `≈ ${tomanRange(amount)}` : t('با اعداد فارسی هم می‌توانید وارد کنید', 'Persian digits accepted too')}
              />
              <Button
                size="lg"
                leading={<Plus size={18} />}
                onClick={() => {
                  if (amount && amount > 0) {
                    topupWallet(amount)
                    setAmount(0)
                  }
                }}
                disabled={!amount || amount <= 0}
              >
                {t('افزودن به موجودی', 'Add to balance')}
              </Button>
            </div>
          </div>
        </div>

        <aside className="lg:col-span-5">
          <div className="bg-white border border-line rounded-3xl p-6 shadow-soft">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-fg">{t('تاریخچه تراکنش', 'Transaction history')}</h3>
              <Badge tone="neutral">{n(walletTxs.length)}</Badge>
            </div>

            {walletTxs.length === 0 ? (
              <div className="mt-6 text-center py-8">
                <div className="mx-auto size-14 rounded-2xl bg-soft border border-line grid place-items-center text-faint">
                  <CreditCard size={24} />
                </div>
                <p className="mt-3 text-sm text-muted leading-7">{t('هنوز تراکنشی نداشته‌اید. با افزایش موجودی، اولین آیتم اینجا ظاهر می‌شود.', 'No transactions yet. Top up and your first item will appear here.')}</p>
              </div>
            ) : (
              <ul className="mt-4 divide-y divide-line">
                {walletTxs.map((tx) => {
                  const positive = tx.type !== 'spend'
                  return (
                    <li key={tx.id} className="py-3 flex items-center gap-3">
                      <span className={['size-10 rounded-2xl grid place-items-center shrink-0', positive ? 'bg-emerald-50 text-emerald-600 ring-1 ring-emerald-100' : 'bg-brand-50 text-brand-600 ring-1 ring-brand-100'].join(' ')}>
                        {positive ? <Plus size={16} /> : <Minus size={16} />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold text-fg truncate">{txLabel(tx.label)}</div>
                        <div className="text-xs text-faint truncate">{dateTime(tx.at)}</div>
                      </div>
                      <div className={['text-sm font-bold num-fa shrink-0', positive ? 'text-emerald-600' : 'text-brand-600'].join(' ')}>
                        {positive ? '+' : '−'}
                        {usd(tx.amountUsd)}
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </Section>
  )
}
